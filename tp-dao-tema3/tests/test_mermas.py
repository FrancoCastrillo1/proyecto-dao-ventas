# Tests de los bultos en merma: un bulto con el precinto roto se rechaza,
# vuelve directo al CD y ahí el CD revisa la mercadería y decide, por el bulto
# entero, si vuelve a su stock (REINTEGRO) o se tira. Se prueba el State
# (Rechazado → Reintegrado o Descartado), el service contra un SQLite temporal,
# la migración de bases viejas, la bandeja del CD y los permisos de la api.
import sqlite3
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.config import ESQUEMA_PATH
from backend.dominio.estados_bulto import Rechazado, Verificado
from backend.dominio.excepciones import DatoInvalido, TransicionDeEstadoInvalida
from backend.dominio.logistica import Bulto, Remito
from backend.dominio.stock import TipoMovimiento
from backend.dominio.usuarios import UsuarioCD
from backend.main import app
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import BultoDAO, PedidoDAO, RemitoDAO
from backend.persistencia.dao_maestros import UbicacionDAO
from backend.persistencia.dao_stock import StockDAO
from backend.servicios.maestros_service import CategoriaService, ProductoService, UbicacionService
from backend.servicios.merma_service import MermaService
from backend.servicios.stock_service import StockService
from backend.servicios.tareas_service import TareasService
from backend.servicios.usuarios_service import UsuarioService
from tests.test_logistica_service import MANANA, armar_remito, cantidad, e  # noqa: F401 (e es un fixture)


def bulto_en_merma():
    bulto = Bulto(1)
    bulto.estado_actual = Rechazado()
    return bulto


@pytest.fixture
def m(e):
    """El escenario de logística con un bulto de 10 cocas ya rechazado en el Centro."""
    remito_id, (bulto_id,) = armar_remito(e, [(e.coca.id, 10)], [[(e.coca.id, 10)]])
    e.repo.despachar(remito_id, MANANA)
    e.rec.recibir(bulto_id)
    e.rec.verificar(bulto_id, f"P-{remito_id}-1", False)   # el precinto llegó roto
    e.mermas = MermaService(BultoDAO(e.db), RemitoDAO(e.db), e.stock)
    e.remito_id, e.bulto_id = remito_id, bulto_id
    return e


# ================================================================== Dominio

def test_un_bulto_en_merma_se_reintegra_y_deja_lo_que_vio_el_cd():
    bulto = bulto_en_merma()
    bulto.reintegrar("  Cajas sanas, solo el precinto cortado ")
    assert bulto.estado == "REINTEGRADO"
    assert bulto.historial[-1].observacion == "Revisado en el CD: Cajas sanas, solo el precinto cortado"


def test_un_bulto_en_merma_se_descarta():
    bulto = bulto_en_merma()
    bulto.descartar("Botellas rotas")
    assert (bulto.estado, bulto.historial[-1].estado_anterior) == ("DESCARTADO", "RECHAZADO")


@pytest.mark.parametrize("observacion", ["", "   ", None])
def test_sin_decir_en_que_estado_llego_no_se_decide(observacion):
    bulto = bulto_en_merma()
    with pytest.raises(DatoInvalido, match="en qué estado llegó"):
        bulto.reintegrar(observacion)
    assert bulto.estado == "RECHAZADO" and bulto.historial == ()


def test_solo_un_bulto_en_merma_se_revisa_y_una_sola_vez():
    with pytest.raises(TransicionDeEstadoInvalida):
        Bulto(1).reintegrar("ok")            # recién armado: Preparado
    bulto = bulto_en_merma()
    bulto.descartar("Rotas")
    with pytest.raises(TransicionDeEstadoInvalida):
        bulto.reintegrar("Me arrepentí")      # ya se decidió
    assert not bulto.habilita_venta()


def test_el_remito_se_cierra_aunque_el_cd_ya_haya_revisado_la_merma():
    remito = Remito(1, "CD", "Centro")
    bueno, revisado = Bulto(1), bulto_en_merma()
    remito.bultos = [bueno, revisado]
    remito.estado = Remito.EN_TRANSITO
    revisado.reintegrar("Estaba bien")
    bueno.estado_actual = Verificado()
    assert remito.registrar_verificacion() is True
    assert remito.estado == Remito.VERIFICADO_CON_RECHAZOS


# ================================================================== Service

def test_el_bulto_rechazado_queda_en_merma_en_el_cd(m):
    [(bulto, remito)] = m.mermas.listar()
    assert (bulto.id_bulto, bulto.estado, remito.destino) == (m.bulto_id, "RECHAZADO", m.centro.id)
    assert cantidad(m, m.centro, m.coca) == 0     # no entró al local
    assert cantidad(m, m.cd, m.coca) == 90        # y salió del CD al despachar


def test_reintegrar_devuelve_todo_al_stock_del_cd(m):
    bulto = m.mermas.reintegrar(m.bulto_id, "Cajas sanas")
    assert bulto.estado == "REINTEGRADO"
    assert cantidad(m, m.cd, m.coca) == 100
    assert cantidad(m, m.centro, m.coca) == 0
    ultimo = m.stock.listar_movimientos(m.cd.id, m.coca.id)[-1]
    assert (ultimo.tipo, ultimo.cantidad) == (TipoMovimiento.REINTEGRO, 10)
    assert f"Bulto {m.bulto_id}" in ultimo.referencia
    assert m.mermas.listar() == []


def test_descartar_no_mueve_stock_y_queda_en_el_historial(m):
    m.mermas.descartar(m.bulto_id, "Botellas pinchadas")
    leido = m.repo.obtener_bulto(m.bulto_id)      # vuelve a leerse de la base
    assert leido.estado == "DESCARTADO"
    assert leido.historial[-1].observacion == "Revisado en el CD: Botellas pinchadas"
    assert cantidad(m, m.cd, m.coca) == 90
    assert m.mermas.listar() == []


def test_no_se_revisa_dos_veces_ni_un_bulto_que_no_esta_en_merma(m):
    m.mermas.descartar(m.bulto_id, "Rotas")
    with pytest.raises(TransicionDeEstadoInvalida):
        m.mermas.reintegrar(m.bulto_id, "Ahora sí")
    assert cantidad(m, m.cd, m.coca) == 90        # no se sumó nada

    otro, (bueno,) = armar_remito(m, [(m.agua.id, 2)], [[(m.agua.id, 2)]])
    with pytest.raises(TransicionDeEstadoInvalida):
        m.mermas.descartar(bueno, "No corresponde")


def test_el_reintegro_solo_vale_en_el_cd(m):
    with pytest.raises(DatoInvalido, match="Centro de Distribución"):
        m.stock.ingresar(m.centro.id, m.coca.id, 1, TipoMovimiento.REINTEGRO, "trampa")


def test_el_cd_ve_la_merma_en_su_bandeja(m):
    tareas = TareasService(PedidoDAO(m.db), RemitoDAO(m.db), StockDAO(m.db), UbicacionDAO(m.db))
    cd = UsuarioCD("ana", "Ana", m.cd.id)
    [tarea] = [t for t in tareas.para(cd) if t.tipo == "merma"]
    assert (tarea.titulo, tarea.pantalla) == ("Revisar 1 bulto en merma", "mermas")   # su propia pantalla
    m.mermas.reintegrar(m.bulto_id, "Sano")
    assert all(t.tipo != "merma" for t in tareas.para(cd))


# ================================================================ Migración

def test_migra_una_base_que_no_conocia_los_estados_de_merma(tmp_path):
    ruta = tmp_path / "vieja.db"
    viejo = (ESQUEMA_PATH.read_text(encoding="utf-8")
             .replace(", 'REINTEGRO'", "")
             .replace(",\n                                 'REINTEGRADO', 'DESCARTADO'", ""))
    assert "REINTEGRO" not in viejo
    with sqlite3.connect(ruta) as cx:
        cx.executescript(viejo)
        cx.execute("INSERT INTO bultos (id, remito_id, nro_precinto, estado) VALUES (7, 1, 'P-7', 'RECHAZADO')")
        cx.execute("INSERT INTO movimientos_stock (id, stock_id, fecha, cantidad, tipo) VALUES (3, 1, '2026-01-01', 5, 'COMPRA')")
        with pytest.raises(sqlite3.IntegrityError):
            cx.execute("UPDATE bultos SET estado = 'REINTEGRADO' WHERE id = 7")

    crear_tablas(ruta)

    with get_conexion(ruta) as cx:
        cx.execute("PRAGMA foreign_keys = OFF")
        cx.execute("UPDATE bultos SET estado = 'REINTEGRADO' WHERE id = 7")     # ahora la base lo acepta
        cx.execute("INSERT INTO movimientos_stock (stock_id, fecha, cantidad, tipo) VALUES (1, '2026-01-02', 5, 'REINTEGRO')")
        assert cx.execute("SELECT nro_precinto FROM bultos WHERE id = 7").fetchone()[0] == "P-7"
        assert cx.execute("SELECT COUNT(*) FROM movimientos_stock").fetchone()[0] == 2
        tablas = {f[0] for f in cx.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert not {"bultos_anterior", "movimientos_stock_anterior"} & tablas
        with pytest.raises(sqlite3.IntegrityError, match="inmutables"):        # los triggers siguen
            cx.execute("DELETE FROM movimientos_stock WHERE id = 3")
    crear_tablas(ruta)   # correrla otra vez no rompe nada


# ====================================================================== Api

def test_solo_el_cd_revisa_la_merma_desde_la_api():
    # La base de la api es una sola para todos los tests: si otro ya creó el CD, se usa ese
    ubicaciones = UbicacionService()
    cd = UbicacionDAO().obtener_cd_activo() or ubicaciones.crear("CD", "CD Mermas", "Ruta 2")
    local = ubicaciones.crear("SUCURSAL", "Local Mermas", "Calle M")
    categoria = CategoriaService().crear("Categoría Mermas")
    producto = ProductoService().crear("MER-001", "Producto Mermas", categoria.id, 100, 60, 0)
    StockService().ingresar(cd.id, producto.id, 20, TipoMovimiento.COMPRA, "stock inicial")
    UsuarioService().crear("CD", "mer.cd", "Del CD", cd.id, "secreta123")
    UsuarioService().crear("SUCURSAL", "mer.local", "Del local", local.id, "secreta123")

    cliente = TestClient(app)

    def token(nombre):
        r = cliente.post("/auth/login", json={"nombre_usuario": nombre, "contrasena": "secreta123"})
        return {"Authorization": f"Bearer {r.json()['token']}"}

    del_cd, del_local = token("mer.cd"), token("mer.local")
    pedido = cliente.post("/pedidos", json={"items": [{"producto_id": producto.id, "cantidad": 4}]}, headers=del_local).json()
    orden = cliente.post("/ordenes", json={"pedido_ids": [pedido["id"]]}, headers=del_cd).json()
    remito = cliente.post("/remitos", json={"orden_id": orden["id"], "destino_id": local.id}, headers=del_cd).json()
    bulto = cliente.post(f"/remitos/{remito['id']}/bultos", json={"items": [{"producto_id": producto.id, "cantidad": 4}]},
                         headers=del_cd).json()
    cliente.post(f"/bultos/{bulto['id']}/precintar", json={"nro_precinto": "MER-P1"}, headers=del_cd)
    llegada = (datetime.now() + timedelta(days=1)).isoformat()
    cliente.post(f"/remitos/{remito['id']}/despachar", json={"llegada_estimada": llegada}, headers=del_cd)
    cliente.post(f"/bultos/{bulto['id']}/recibir", headers=del_local)
    r = cliente.post(f"/bultos/{bulto['id']}/verificar", json={"nro_leido": "MER-P1", "intacto": False}, headers=del_local)
    assert r.json()["bulto"]["estado"] == "RECHAZADO"

    assert cliente.get("/mermas", headers=del_local).status_code == 403
    assert cliente.post(f"/mermas/{bulto['id']}/reintegrar", json={"observacion": "x"}, headers=del_local).status_code == 403

    mermas = cliente.get("/mermas", headers=del_cd).json()
    assert [(x["bulto"]["id"], x["local_id"]) for x in mermas if x["bulto"]["id"] == bulto["id"]] == [(bulto["id"], local.id)]
    r = cliente.post(f"/mermas/{bulto['id']}/reintegrar", json={"observacion": "Estaba sano"}, headers=del_cd)
    assert r.status_code == 200 and r.json()["estado"] == "REINTEGRADO"
    assert StockService().obtener(cd.id, producto.id).cantidad == 20   # volvieron las 4 que salieron
