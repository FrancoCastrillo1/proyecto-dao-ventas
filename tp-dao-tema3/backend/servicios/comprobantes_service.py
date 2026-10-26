# Casos de uso de los documentos que se descargan: el comprobante de una venta,
# la nota de crédito de una devolución y el remito de un envío. Busca la
# operación, arma el contexto que el documento necesita (local, productos,
# quién la hizo, datos del comercio), le pide al dominio el contenido
# (Template Method) y lo dibuja en PDF.
# Acá NO va SQL (usa los DAO), ni qué dice cada documento (dominio/documentos.py),
# ni quién puede descargarlo (eso lo controla la api).
from backend.config import COMERCIO
from backend.dominio.documentos import ComprobanteVenta, ContextoDocumento, DatosComercio, NotaCredito, RemitoDocumento
from backend.dominio.excepciones import NoEncontrado
from backend.persistencia.dao_logistica import RemitoDAO
from backend.persistencia.dao_maestros import ProductoDAO, UbicacionDAO
from backend.persistencia.dao_ventas import VentaDAO
from backend.servicios.documentos_pdf import dibujar


class ComprobantesService:
    def __init__(self, venta_dao=None, ubicacion_dao=None, producto_dao=None, remito_dao=None):
        self.venta_dao = venta_dao or VentaDAO()
        self.ubicacion_dao = ubicacion_dao or UbicacionDAO(self.venta_dao.db_path)
        self.producto_dao = producto_dao or ProductoDAO(self.venta_dao.db_path)
        self.remito_dao = remito_dao or RemitoDAO(self.venta_dao.db_path)

    def obtener_remito(self, remito_id):
        remito = self.remito_dao.obtener(remito_id)
        if remito is None:
            raise NoEncontrado(f"El remito {remito_id} no existe")
        return remito

    def remito(self, remito):
        """Devuelve (nombre del archivo, bytes del PDF) del remito. Lo emite el
        CD (encabezado con el origen) y va al local destino."""
        origen = self.ubicacion_dao.obtener_por_id(remito.origen)
        destino = self.ubicacion_dao.obtener_por_id(remito.destino)
        ids = {d.producto for bulto in remito.bultos for d in bulto.items}
        productos = {pid: self.producto_dao.obtener_por_id(pid) for pid in ids}
        contexto = ContextoDocumento(
            comercio=DatosComercio(**COMERCIO), local=origen.nombre, direccion_local=origen.direccion,
            atendio=self.remito_dao.quien_lo_armo(remito.id_remito),
            nombres_productos={pid: p.nombre for pid, p in productos.items() if p},
        )
        contenido = RemitoDocumento(remito, contexto, destino.nombre, destino.direccion).armar()
        return contenido.nombre_archivo, dibujar(contenido)

    def obtener_venta(self, venta_id):
        venta = self.venta_dao.obtener(venta_id)
        if venta is None:
            raise NoEncontrado(f"La venta {venta_id} no existe")
        return venta

    def contexto(self, venta, tabla, id):
        local = self.ubicacion_dao.obtener_por_id(venta.sucursal_id)
        productos = {d.producto_id: self.producto_dao.obtener_por_id(d.producto_id) for d in venta.detalles}
        return ContextoDocumento(
            comercio=DatosComercio(**COMERCIO),
            local=local.nombre,
            direccion_local=local.direccion,
            atendio=self.venta_dao.quien_hizo(tabla, id),
            nombres_productos={pid: p.nombre for pid, p in productos.items() if p},
        )

    def comprobante_de_venta(self, venta):
        """Devuelve (nombre del archivo, bytes del PDF)."""
        contenido = ComprobanteVenta(venta, self.contexto(venta, "ventas", venta.id)).armar()
        return contenido.nombre_archivo, dibujar(contenido)

    def nota_de_credito(self, venta, devolucion_id):
        devolucion = next((d for d in venta.devoluciones if d.id == devolucion_id), None)
        if devolucion is None:
            raise NoEncontrado(f"La devolución {devolucion_id} no es de la venta {venta.id}")
        contenido = NotaCredito(devolucion, venta, self.contexto(venta, "devoluciones", devolucion.id)).armar()
        return contenido.nombre_archivo, dibujar(contenido)
