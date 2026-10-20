# Tests de los endpoints de logística: se recorre el circuito completo por HTTP
# (pedido, orden, remito, despacho, recepción y verificación) y se comprueba que
# los errores del negocio salgan como códigos HTTP claros. Usa una base temporal.
import pytest
from fastapi.testclient import TestClient

from backend.api import rutas_logistica
from backend.main import app
from backend.persistencia.conexion import crear_tablas, get_conexion
from backend.persistencia.dao_logistica import DaoLogistica
from backend.servicios.recepcion_service import RecepcionService
from backend.servicios.reposicion_service import ReposicionService
from backend.servicios.stock_service import StockService

CD, LOCAL_1, LOCAL_2 = 1, 2, 3
PRECINTO = "PRE-001"


@pytest.fixture
def api(tmp_path, monkeypatch):
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
        cx.executemany(
            "INSERT INTO ubicaciones (tipo, nombre, direccion) VALUES (?, ?, ?)",
            [("CD", "CD Central", "Calle 1"), ("SUCURSAL", "Local 1", "Calle 2"), ("SUCURSAL", "Local 2", "Calle 3")],
        )
        cx.commit()
    finally:
        cx.close()
    # Los servicios de stock abren la base real por su cuenta: se los redirige a la temporal
    monkeypatch.setattr("backend.persistencia.dao_stock.get_conexion", lambda: get_conexion(ruta))
    dao = DaoLogistica(ruta)
    monkeypatch.setattr(rutas_logistica, "reposicion", ReposicionService(dao, StockService()))
    monkeypatch.setattr(rutas_logistica, "recepcion", RecepcionService(dao, StockService()))
    cliente = TestClient(app)
    # Stock inicial del CD, cargado por la API como se haría desde /docs
    for producto, cantidad in ((1, 100), (2, 50)):
        r = cliente.post(
            "/stock/ingresar",
            json={"ubicacion_id": CD, "producto_id": producto, "cantidad": cantidad, "referencia": "compra inicial"},
        )
        assert r.status_code == 201
    return cliente


# ---------- helpers ----------

def stock(api, ubicacion, producto):
    return api.get(f"/stock/{ubicacion}/{producto}").json()["cantidad"]


def crear_pedido(api, local=LOCAL_1, items=((1, 10),)):
    r = api.post(
        "/logistica/pedidos",
        json={"local_id": local, "items": [{"producto_id": p, "cantidad": c} for p, c in items]},
    )
    return r.json()["id"]


def pedido_consolidado(api, local=LOCAL_1, items=((1, 10),)):
    pedido_id = crear_pedido(api, local, items)
    api.post(f"/logistica/pedidos/{pedido_id}/consolidar")
    return pedido_id


def armar_remito(api, items=((1, 10),), precinto=PRECINTO, destino=LOCAL_1):
    return api.post(
        "/logistica/remitos",
        json={
            "origen_id": CD,
            "destino_id": destino,
            "bultos": [{"precinto": precinto, "items": [{"producto_id": p, "cantidad": c} for p, c in items]}],
        },
    )


def despachar(api, items=((1, 10),)):
    """Arma un remito con un bulto, lo despacha y devuelve (id del remito, id del bulto)."""
    remito_id = armar_remito(api, items).json()["id"]
    assert api.post(f"/logistica/remitos/{remito_id}/despachar").status_code == 200
    bulto_id = api.get(f"/logistica/remitos/{remito_id}").json()["bultos"][0]["id"]
    return remito_id, bulto_id


# ---------- pedidos ----------

def test_crear_un_pedido_devuelve_201_y_se_puede_leer(api):
    r = api.post("/logistica/pedidos", json={"local_id": LOCAL_1, "items": [{"producto_id": 1, "cantidad": 10}]})
    assert r.status_code == 201
    pedido_id = r.json()["id"]
    leido = api.get(f"/logistica/pedidos/{pedido_id}")
    assert leido.status_code == 200
    assert leido.json() == {
        "id": pedido_id, "local_id": LOCAL_1, "estado": "PENDIENTE",
        "items": [{"producto_id": 1, "cantidad": 10}],
    }


@pytest.mark.parametrize("cantidad", [0, -3])
def test_un_pedido_con_cantidad_invalida_es_400(api, cantidad):
    r = api.post("/logistica/pedidos", json={"local_id": LOCAL_1, "items": [{"producto_id": 1, "cantidad": cantidad}]})
    assert r.status_code == 400


def test_consolidar_un_pedido_devuelve_el_pedido_consolidado(api):
    pedido_id = crear_pedido(api)
    r = api.post(f"/logistica/pedidos/{pedido_id}/consolidar")
    assert r.status_code == 200
    assert r.json()["estado"] == "CONSOLIDADO"


def test_un_pedido_inexistente_es_404(api):
    assert api.get("/logistica/pedidos/999").status_code == 404
    assert api.post("/logistica/pedidos/999/consolidar").status_code == 404


# ---------- órdenes ----------

def test_crear_una_orden_junta_pedidos_de_varios_locales(api):
    p1 = pedido_consolidado(api, LOCAL_1, ((1, 10),))
    p2 = pedido_consolidado(api, LOCAL_2, ((1, 5), (2, 4)))
    r = api.post("/logistica/ordenes", json={"origen_id": CD, "pedido_ids": [p1, p2]})
    assert r.status_code == 201
    orden = api.get(f"/logistica/ordenes/{r.json()['id']}").json()
    assert orden["estado"] == "CERRADA"
    assert orden["pedido_ids"] == [p1, p2]
    assert orden["total_por_producto"] == {"1": 15, "2": 4}


def test_una_orden_con_un_pedido_sin_consolidar_es_400(api):
    pedido_id = crear_pedido(api)
    r = api.post("/logistica/ordenes", json={"origen_id": CD, "pedido_ids": [pedido_id]})
    assert r.status_code == 400


def test_un_pedido_no_puede_ir_en_dos_ordenes(api):
    cuerpo = {"origen_id": CD, "pedido_ids": [pedido_consolidado(api)]}
    assert api.post("/logistica/ordenes", json=cuerpo).status_code == 201
    assert api.post("/logistica/ordenes", json=cuerpo).status_code == 400


# ---------- remitos ----------

def test_armar_un_remito_precinta_los_bultos_y_lo_cierra(api):
    r = armar_remito(api, items=((1, 10), (2, 4)))
    assert r.status_code == 201
    remito = api.get(f"/logistica/remitos/{r.json()['id']}").json()
    assert (remito["origen_id"], remito["destino_id"], remito["estado"]) == (CD, LOCAL_1, "CERRADO")
    assert [b["estado"] for b in remito["bultos"]] == ["PRECINTADO"]
    assert remito["bultos"][0]["nro_precinto"] == PRECINTO
    assert remito["total_por_producto"] == {"1": 10, "2": 4}


@pytest.mark.parametrize("bultos", [
    [],
    [{"precinto": PRECINTO, "items": []}],
    [{"precinto": "", "items": [{"producto_id": 1, "cantidad": 10}]}],
])
def test_armar_un_remito_invalido_es_400(api, bultos):
    r = api.post("/logistica/remitos", json={"origen_id": CD, "destino_id": LOCAL_1, "bultos": bultos})
    assert r.status_code == 400


# ---------- despacho ----------

def test_despachar_pasa_el_bulto_a_en_transito_y_descuenta_el_stock_del_cd(api):
    _, bulto_id = despachar(api, items=((1, 10), (2, 4)))
    assert api.get(f"/logistica/bultos/{bulto_id}").json()["estado"] == "EN_TRANSITO"
    assert (stock(api, CD, 1), stock(api, CD, 2)) == (90, 46)
    assert stock(api, LOCAL_1, 1) == 0


def test_despachar_con_stock_insuficiente_es_409_y_no_cambia_nada(api):
    remito_id = armar_remito(api, items=((1, 101),)).json()["id"]
    assert api.post(f"/logistica/remitos/{remito_id}/despachar").status_code == 409
    assert stock(api, CD, 1) == 100
    assert api.get(f"/logistica/remitos/{remito_id}").json()["bultos"][0]["estado"] == "PRECINTADO"


def test_despachar_dos_veces_es_409_y_no_descuenta_dos_veces(api):
    remito_id, _ = despachar(api)
    assert api.post(f"/logistica/remitos/{remito_id}/despachar").status_code == 409
    assert stock(api, CD, 1) == 90


def test_despachar_un_remito_inexistente_es_404(api):
    assert api.post("/logistica/remitos/999/despachar").status_code == 404


# ---------- recepción ----------

def test_recibir_pasa_a_recibido_y_todavia_no_suma_stock(api):
    _, bulto_id = despachar(api)
    r = api.post(f"/logistica/bultos/{bulto_id}/recibir")
    assert r.status_code == 200
    assert r.json()["estado"] == "RECIBIDO"
    assert stock(api, LOCAL_1, 1) == 0


def test_recibir_un_bulto_inexistente_es_404(api):
    assert api.post("/logistica/bultos/999/recibir").status_code == 404


def test_verificar_con_precinto_intacto_habilita_la_venta_y_suma_el_stock(api):
    _, bulto_id = despachar(api)
    api.post(f"/logistica/bultos/{bulto_id}/recibir")
    r = api.post(f"/logistica/bultos/{bulto_id}/verificar", json={"nro_leido": PRECINTO, "intacto": True})
    assert r.status_code == 200
    assert (r.json()["estado"], r.json()["habilita_venta"]) == ("VERIFICADO", True)
    assert stock(api, LOCAL_1, 1) == 10


def test_verificar_con_precinto_roto_rechaza_el_bulto_y_no_suma_stock(api):
    _, bulto_id = despachar(api)
    api.post(f"/logistica/bultos/{bulto_id}/recibir")
    r = api.post(f"/logistica/bultos/{bulto_id}/verificar", json={"nro_leido": PRECINTO, "intacto": False})
    assert r.status_code == 200
    assert (r.json()["estado"], r.json()["habilita_venta"]) == ("RECHAZADO", False)
    assert stock(api, LOCAL_1, 1) == 0
    assert stock(api, CD, 1) == 90  # merma: no vuelve al CD (decisión provisoria)


def test_verificar_un_bulto_que_no_fue_recibido_es_409(api):
    _, bulto_id = despachar(api)
    r = api.post(f"/logistica/bultos/{bulto_id}/verificar", json={"nro_leido": PRECINTO, "intacto": True})
    assert r.status_code == 409
    assert stock(api, LOCAL_1, 1) == 0


def test_verificar_sin_indicar_si_el_precinto_esta_intacto_es_422(api):
    _, bulto_id = despachar(api)
    api.post(f"/logistica/bultos/{bulto_id}/recibir")
    assert api.post(f"/logistica/bultos/{bulto_id}/verificar", json={"nro_leido": PRECINTO}).status_code == 422


# ---------- el circuito completo ----------

def test_se_recorre_un_bulto_completo_desde_el_pedido_hasta_la_verificacion(api):
    pedido_id = pedido_consolidado(api)
    assert api.post("/logistica/ordenes", json={"origen_id": CD, "pedido_ids": [pedido_id]}).status_code == 201
    _, bulto_id = despachar(api)
    assert api.post(f"/logistica/bultos/{bulto_id}/recibir").status_code == 200
    r = api.post(f"/logistica/bultos/{bulto_id}/verificar", json={"nro_leido": PRECINTO, "intacto": True})
    assert r.status_code == 200
    bulto = r.json()
    assert bulto["estado"] == "VERIFICADO"
    assert [(c["estado_anterior"], c["estado_nuevo"]) for c in bulto["historial"]] == [
        ("PREPARADO", "PRECINTADO"),
        ("PRECINTADO", "EN_TRANSITO"),
        ("EN_TRANSITO", "RECIBIDO"),
        ("RECIBIDO", "VERIFICADO"),
    ]
    assert (stock(api, CD, 1), stock(api, LOCAL_1, 1)) == (90, 10)
    