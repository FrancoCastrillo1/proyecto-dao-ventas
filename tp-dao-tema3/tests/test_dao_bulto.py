# Tests del DAO de logística para el bulto: que un bulto guardado vuelva igual
# al leerlo, que el estado se guarde como texto y que el historial solo se
# inserte. Usa una base temporal en un archivo, no la base real.
import pytest

from backend.dominio.excepciones import NoEncontrado
from backend.dominio.logistica import Bulto
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import DaoLogistica

PRECINTO = "PRE-001"
ESTADOS = ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO", "RECHAZADO"]


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "test.db"
    crear_tablas(ruta)
    cx = get_conexion(ruta)
    try:
        cx.execute("INSERT INTO categorias (nombre) VALUES ('Almacen')")
        cx.executemany(
            "INSERT INTO productos (codigo, nombre, categoria_id, precio_venta, costo) "
            "VALUES (?, ?, 1, 100, 60)",
            [("P1", "Yerba"), ("P2", "Azucar")],
        )
        cx.commit()
    finally:
        cx.close()
    return ruta


def consultar(db, sql, parametros=()):
    cx = get_conexion(db)
    try:
        return [tuple(fila) for fila in cx.execute(sql, parametros).fetchall()]
    finally:
        cx.close()


def filas_historial(db, bulto_id):
    return consultar(
        db,
        "SELECT estado_anterior, estado_nuevo, observacion FROM historial_bulto "
        "WHERE bulto_id = ? ORDER BY id",
        (bulto_id,),
    )


def armar(estado):
    """Lleva un bulto nuevo (con los productos 1 y 2) hasta el estado pedido."""
    bulto = Bulto(None)
    bulto.agregar_item(1, 5)
    bulto.agregar_item(2, 3)
    if estado == "PREPARADO":
        return bulto
    bulto.precintar(PRECINTO)
    if estado == "PRECINTADO":
        return bulto
    bulto.despachar()
    if estado == "EN_TRANSITO":
        return bulto
    bulto.recibir()
    if estado == "RECIBIDO":
        return bulto
    bulto.verificar(PRECINTO if estado == "VERIFICADO" else "OTRO-PRECINTO", intacto=True)
    return bulto


# ---------- ida y vuelta ----------

@pytest.mark.parametrize("estado", ESTADOS)
def test_un_bulto_guardado_vuelve_igual_al_leerlo(db, estado):
    dao = DaoLogistica(db)
    original = armar(estado)
    bulto_id = dao.guardar_bulto(original)
    leido = dao.obtener_bulto(bulto_id)
    assert leido.id_bulto == bulto_id
    assert leido.estado == estado
    assert leido.nro_precinto == original.nro_precinto
    assert leido.items == original.items
    assert leido.historial == original.historial
    assert leido.habilita_venta() is original.habilita_venta()


def test_guardar_un_bulto_nuevo_le_asigna_el_id_de_la_base(db):
    dao = DaoLogistica(db)
    bulto = armar("PREPARADO")
    bulto_id = dao.guardar_bulto(bulto)
    assert bulto_id > 0
    assert bulto.id_bulto == bulto_id


def test_el_estado_se_guarda_como_texto(db):
    bulto_id = DaoLogistica(db).guardar_bulto(armar("PRECINTADO"))
    filas = consultar(db, "SELECT estado, nro_precinto FROM bultos WHERE id = ?", (bulto_id,))
    assert filas == [("PRECINTADO", PRECINTO)]


def test_obtener_un_bulto_inexistente_es_no_encontrado(db):
    with pytest.raises(NoEncontrado):
        DaoLogistica(db).obtener_bulto(999)


# ---------- guardar de nuevo ----------

def test_guardar_dos_veces_el_mismo_bulto_no_crea_otro_ni_duplica_el_historial(db):
    dao = DaoLogistica(db)
    bulto = armar("EN_TRANSITO")
    bulto_id = dao.guardar_bulto(bulto)
    dao.guardar_bulto(bulto)
    assert consultar(db, "SELECT COUNT(*) FROM bultos") == [(1,)]
    assert len(filas_historial(db, bulto_id)) == 2


def test_al_guardar_de_nuevo_solo_se_agregan_los_cambios_nuevos(db):
    dao = DaoLogistica(db)
    bulto = armar("PRECINTADO")
    bulto_id = dao.guardar_bulto(bulto)
    primero = filas_historial(db, bulto_id)
    bulto.despachar()
    bulto.recibir()
    dao.guardar_bulto(bulto)
    filas = filas_historial(db, bulto_id)
    assert filas[:1] == primero  # el registro anterior no se tocó
    assert [fila[1] for fila in filas] == ["PRECINTADO", "EN_TRANSITO", "RECIBIDO"]


def test_las_lineas_se_actualizan_al_quitar_un_item(db):
    dao = DaoLogistica(db)
    bulto = armar("PREPARADO")
    bulto_id = dao.guardar_bulto(bulto)
    bulto.quitar_item(1)
    dao.guardar_bulto(bulto)
    leido = dao.obtener_bulto(bulto_id)
    assert [d.producto for d in leido.items] == [2]


def test_el_rechazo_conserva_la_observacion(db):
    dao = DaoLogistica(db)
    bulto_id = dao.guardar_bulto(armar("RECHAZADO"))
    assert "Precinto" in dao.obtener_bulto(bulto_id).historial[-1].observacion


# ---------- un bulto leído sigue su ciclo de vida ----------

def test_un_bulto_leido_puede_seguir_su_ciclo_de_vida(db):
    dao = DaoLogistica(db)
    bulto_id = dao.guardar_bulto(armar("EN_TRANSITO"))
    leido = dao.obtener_bulto(bulto_id)
    leido.recibir()
    leido.verificar(PRECINTO, intacto=True)
    dao.guardar_bulto(leido)
    final = dao.obtener_bulto(bulto_id)
    assert final.estado == "VERIFICADO"
    assert final.habilita_venta() is True
    assert len(final.historial) == 4