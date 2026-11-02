# Test del seed: corre el script real (como lo correría alguien del grupo)
# contra una base temporal y verifica que el escenario quede cargado y
# coherente. Se corre en otro proceso porque la ruta de la base se fija al
# importar los módulos (variable de entorno TP_DAO_DB).
#
# El seed tarda (carga 90 días de operación de prueba): se corre UNA vez por
# módulo (fixture "sembrada") y solo el test de --reiniciar lo vuelve a correr.
import os
import re
import subprocess
import sys
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

import pytest

from backend.persistencia.dao_logistica import RemitoDAO
from backend.persistencia.dao_maestros import ProductoDAO
from backend.persistencia.dao_reportes import ReporteDAO
from backend.persistencia.conexion import get_conexion
from backend.persistencia.dao_usuarios import UsuarioDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.reportes_service import ReportesService
from backend.servicios.usuarios_service import AuthService

RAIZ = Path(__file__).resolve().parent.parent


def correr_seed(db, *argumentos):
    resultado = subprocess.run(
        [sys.executable, "-m", "backend.datos.seed", *argumentos],
        cwd=RAIZ, env={**os.environ, "TP_DAO_DB": str(db)},
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


@pytest.fixture(scope="module")
def sembrada(tmp_path_factory):
    """(base, lo que imprimió el seed, cuántas ventas de prueba cargó)."""
    db = tmp_path_factory.mktemp("seed") / "seed.db"
    salida = correr_seed(db)
    historial = int(re.search(r"(\d+) ventas DE PRUEBA", salida).group(1))
    return db, salida, historial


def test_el_seed_carga_el_escenario_completo(sembrada):
    db, _, historial = sembrada
    assert len(ProductoDAO(db).listar()) == 10
    estados = [r.estado for r in RemitoDAO(db).listar()]
    # los envíos de todo el historial, el de Norte con un bulto roto, el de Sur
    # en camino y el que el CD está armando para Norte (los de hoy)
    assert estados.count("VERIFICADO") > 30
    assert {"ABIERTO", "EN_TRANSITO", "VERIFICADO_CON_RECHAZOS"} <= set(estados)
    ventas = VentaDAO(db).listar()
    assert len(ventas) == 8 + historial
    assert sum(1 for v in ventas if v.fecha.date() == date.today()) >= 8     # el historial llega hasta hoy
    reportes = ReportesService(ReporteDAO(db))
    margenes = {f["codigo"]: f["margen"] for f in reportes.productos_mas_vendidos(limite=20)["filas"]}
    assert margenes["LAC-002"] < 0                                      # el producto en promo pierde plata


def test_el_historial_alcanza_para_los_tableros(sembrada):
    db, _, historial = sembrada
    assert historial > 600
    ventas = VentaDAO(db).listar()
    assert len({v.fecha.hour for v in ventas}) >= 10                   # a distintas horas: hay mapa de calor
    assert len({v.fecha.date() for v in ventas}) > 80                  # casi todos los días de los 90


def test_nada_queda_con_fecha_futura(sembrada):
    db, _, _ = sembrada
    ahora = datetime.now().isoformat(sep=" ")
    with closing(get_conexion(db)) as cx:
        for tabla, columna in (("ventas", "fecha"), ("devoluciones", "fecha"), ("pedidos_reposicion", "fecha"),
                               ("remitos", "fecha"), ("historial_bultos", "fecha_hora"),
                               ("movimientos_stock", "fecha"), ("movimientos_caja", "fecha")):
            assert cx.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {columna} > ?", (ahora,)).fetchone()[0] == 0, tabla


def test_hay_devoluciones_y_pedidos_a_lo_largo_del_historial(sembrada):
    db, _, _ = sembrada
    with closing(get_conexion(db)) as cx:
        devoluciones = cx.execute("SELECT COUNT(*), COUNT(DISTINCT motivo) FROM devoluciones").fetchone()
        assert devoluciones[0] > 20 and devoluciones[1] >= 3              # varias, por distintos motivos
        dias_con_pedidos = cx.execute("SELECT COUNT(DISTINCT substr(fecha, 1, 10)) FROM pedidos_reposicion").fetchone()[0]
        assert dias_con_pedidos > 20                                    # cada local pide cada pocos días
        # Del despacho a la recepción pasan horas (no se recibe en el acto)
        horas = cx.execute(
            "SELECT AVG((julianday(llega.fecha_hora) - julianday(sale.fecha_hora)) * 24) FROM historial_bultos sale "
            "JOIN historial_bultos llega ON llega.bulto_id = sale.bulto_id AND llega.estado_nuevo = 'RECIBIDO' "
            "WHERE sale.estado_nuevo = 'EN_TRANSITO'").fetchone()[0]
        assert horas > 6


def test_correr_el_seed_dos_veces_no_duplica(sembrada):
    db, _, historial = sembrada
    salida = correr_seed(db)
    assert "ya tiene datos" in salida
    assert len(VentaDAO(db).listar()) == 8 + historial


def test_reiniciar_borra_y_vuelve_a_cargar(tmp_path):
    db = tmp_path / "seed.db"
    correr_seed(db)
    # Una marca para saber si la base se borró (el with de sqlite confirma pero
    # no cierra: en Windows un archivo abierto no se puede borrar)
    with closing(get_conexion(db)) as cx, cx:
        cx.execute("INSERT INTO categorias (nombre, nombre_normalizado) VALUES ('Sobra', 'sobra')")
    correr_seed(db, "--reiniciar")
    with closing(get_conexion(db)) as cx:
        assert cx.execute("SELECT COUNT(*) FROM categorias WHERE nombre = 'Sobra'").fetchone()[0] == 0


def test_el_seed_trae_un_usuario_de_cada_perfil_que_puede_entrar(sembrada):
    db, salida, _ = sembrada
    assert "tpdao2026" in salida                      # el seed muestra con qué entrar
    usuarios = {u.nombre_usuario: u for u in UsuarioDAO(db).listar()}
    assert {n: u.perfil for n, u in usuarios.items()} == {
        "admin": "ADMIN", "cd.central": "CD", "centro": "SUCURSAL", "norte": "SUCURSAL", "sur": "SUCURSAL",
    }
    for nombre in usuarios:
        AuthService(UsuarioDAO(db)).login(nombre, "tpdao2026")


def test_en_el_seed_cada_operacion_la_hizo_quien_corresponde(sembrada):
    db, _, _ = sembrada
    with get_conexion(db) as cx:
        def perfiles(tabla):
            return {f[0] for f in cx.execute(
                f"SELECT DISTINCT u.perfil FROM {tabla} t LEFT JOIN usuarios u ON u.id = t.usuario_id")}
        assert perfiles("pedidos_reposicion") == {"SUCURSAL"}
        assert perfiles("ordenes_reposicion") == {"CD"}
        assert perfiles("remitos") == {"CD"}
        assert perfiles("ventas") == {"SUCURSAL"}
        assert perfiles("devoluciones") == {"SUCURSAL"}
        assert perfiles("historial_bultos") == {"CD", "SUCURSAL"}   # el CD precinta y despacha; el local recibe
        assert perfiles("movimientos_stock") == {"CD", "SUCURSAL"}


def test_crear_el_primer_administrador(tmp_path):
    db = tmp_path / "vacia.db"
    resultado = subprocess.run(
        [sys.executable, "-c",
         "from backend.datos.crear_admin import crear_admin; print(crear_admin('jefa', 'La Jefa', 'clave-larga-1').perfil)"],
        cwd=RAIZ, env={**os.environ, "TP_DAO_DB": str(db)}, capture_output=True, text=True,
    )
    assert resultado.stdout.strip() == "ADMIN", resultado.stderr
    AuthService(UsuarioDAO(db)).login("jefa", "clave-larga-1")
