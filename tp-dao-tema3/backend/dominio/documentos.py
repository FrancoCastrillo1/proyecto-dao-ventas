# Documentos comerciales: el comprobante de una venta y la nota de crédito de
# una devolución (para el cliente), y el remito que viaja con los bultos.
#
# Patrón Template Method: DocumentoComercial.armar() fija CÓMO se arma
# cualquier documento (encabezado del comercio y del local, renglones, totales
# y notas, siempre en ese orden) y cada hija redefine solo lo que cambia: el
# título, el número, los renglones, los totales y las notas.
#
# Acá NO va el dibujo del PDF (eso es servicios/documentos_pdf.py, que dibuja
# cualquier documento sin saber cuál es) ni nada de base de datos: lo que no
# está en la venta (nombres del local y de los productos, quién atendió, datos
# del comercio) se lo pasa el service en un ContextoDocumento.
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from backend.dominio.dinero import CERO
from backend.dominio.excepciones import DatoInvalido

# Cómo se escribe cada medio de pago en un documento (en la base va el código)
NOMBRES_MEDIO = {"EFECTIVO": "Efectivo", "DEBITO": "Débito", "CREDITO": "Crédito", "TRANSFERENCIA": "Transferencia"}


def nombre_del_medio(codigo):
    return NOMBRES_MEDIO.get(codigo, codigo)


@dataclass(frozen=True)
class DatosComercio:
    razon_social: str
    cuit: str
    direccion: str


@dataclass(frozen=True)
class ContextoDocumento:
    """Lo que el documento necesita y no está en la venta: lo arma el service."""
    comercio: DatosComercio
    local: str
    direccion_local: str
    atendio: str | None                          # quién hizo la operación (None si no se sabe)
    nombres_productos: dict = field(default_factory=dict)  # producto_id → nombre


@dataclass(frozen=True)
class Renglon:
    descripcion: str
    cantidad: int
    precio_unitario: object | None   # Decimal, o un texto (ej: el bulto del remito); None si no va
    importe: object                  # Decimal, o un texto (ej: el precinto); None si no va


@dataclass(frozen=True)
class Total:
    etiqueta: str
    importe: object                  # Decimal si es plata; un entero si es una cuenta (ej: bultos)
    destacado: bool = False


@dataclass(frozen=True)
class ContenidoDocumento:
    """El documento ya armado: qué dice, no cómo se ve. Cualquier documento
    comercial termina en esta misma forma, por eso el PDF lo dibuja uno solo."""
    titulo: str
    codigo: str
    fecha: datetime
    encabezado: tuple        # renglones de texto del comercio y del local
    renglones: tuple
    totales: tuple
    notas: tuple
    nombre_archivo: str
    columnas: tuple = ("Producto", "Cant.", "Precio", "Importe")


class DocumentoComercial(ABC):

    def __init__(self, contexto):
        self.contexto = contexto

    # ------------------------------------------------- El método plantilla
    def armar(self):
        """Arma cualquier documento siempre en el mismo orden. Las hijas no
        redefinen este método: completan los pasos que se llaman desde acá."""
        return ContenidoDocumento(
            titulo=self.titulo(),
            codigo=self.codigo(),
            fecha=self.fecha(),
            encabezado=tuple(self.encabezado()),
            renglones=tuple(self.renglones()),
            totales=tuple(self.totales()),
            notas=tuple(self.notas() + self.notas_comunes()),
            nombre_archivo=f"{self.prefijo_archivo()}-{self.codigo()}.pdf",
            columnas=tuple(self.columnas()),
        )

    # ------------------------------------------ Pasos comunes a todos
    def encabezado(self):
        comercio = self.contexto.comercio
        return [
            comercio.razon_social,
            f"CUIT {comercio.cuit} · {comercio.direccion}",
            f"{self.contexto.local} · {self.contexto.direccion_local}",
        ]

    def notas_comunes(self):
        if not self.contexto.atendio:
            return []
        return [f"{self.etiqueta_responsable()}: {self.contexto.atendio}"]

    def nombre_producto(self, producto_id):
        return self.contexto.nombres_productos.get(producto_id, f"Producto {producto_id}")

    # --------------------------------- Pasos que redefine cada documento
    @abstractmethod
    def titulo(self):
        pass

    @abstractmethod
    def codigo(self):
        pass

    @abstractmethod
    def fecha(self):
        pass

    @abstractmethod
    def renglones(self):
        pass

    @abstractmethod
    def totales(self):
        pass

    @abstractmethod
    def prefijo_archivo(self):
        pass

    # Ganchos (hooks): tienen un valor por defecto; quien quiera, los redefine
    def notas(self):
        return []

    def columnas(self):
        return ("Producto", "Cant.", "Precio", "Importe")

    def etiqueta_responsable(self):
        return "Atendió"


class ComprobanteVenta(DocumentoComercial):
    """El ticket de una venta cobrada: productos, precio de lista, descuento
    o recargo del medio de pago (Strategy) y total."""

    def __init__(self, venta, contexto):
        if venta.comprobante is None:
            raise DatoInvalido("La venta no tiene comprobante emitido")
        super().__init__(contexto)
        self.venta = venta

    def titulo(self):
        return "Comprobante de venta"

    def codigo(self):
        return self.venta.comprobante.codigo

    def fecha(self):
        return self.venta.fecha

    def prefijo_archivo(self):
        return "comprobante"

    def renglones(self):
        return [Renglon(self.nombre_producto(d.producto_id), d.cantidad, d.precio_unitario, d.subtotal)
                for d in self.venta.detalles]

    def totales(self):
        pago = self.venta.pago
        totales = [Total("Subtotal", self.venta.subtotal)]
        ajuste = self.venta.total - self.venta.subtotal
        if ajuste != CERO:
            tipo = "Descuento" if ajuste < 0 else "Recargo"
            totales.append(Total(f"{tipo} {abs(pago.porcentaje_ajuste)}% ({nombre_del_medio(pago.medio.nombre)})", ajuste))
        # El vuelto no va: es un dato del momento del cobro, no del comprobante
        totales.append(Total("Total", self.venta.total, destacado=True))
        return totales

    def notas(self):
        return [f"Pagado con {nombre_del_medio(self.venta.pago.medio.nombre)}"]


class NotaCredito(DocumentoComercial):
    """Lo que se le reintegra al cliente por una devolución: qué devolvió, por
    qué y cuánto, con referencia a la venta original."""

    def __init__(self, devolucion, venta, contexto):
        if devolucion.nota_credito is None:
            raise DatoInvalido("La devolución no tiene nota de crédito emitida")
        super().__init__(contexto)
        self.devolucion = devolucion
        self.venta = venta

    def titulo(self):
        return "Nota de crédito"

    def codigo(self):
        return self.devolucion.nota_credito.codigo

    def fecha(self):
        return self.devolucion.fecha

    def prefijo_archivo(self):
        return "nota-credito"

    # Sin precio unitario: lo que se reintegra ya tiene aplicado el ajuste del
    # medio de pago de la venta (ver Venta.devolver)
    def renglones(self):
        return [Renglon(self.nombre_producto(d.producto_id), d.cantidad, None, d.importe)
                for d in self.devolucion.detalles]

    def totales(self):
        return [Total("Total reintegrado", self.devolucion.importe, destacado=True)]

    def notas(self):
        return [
            f"Por la devolución de la venta {self.venta.comprobante.codigo}",
            f"Motivo: {self.devolucion.motivo}",
            f"Se reintegra en {nombre_del_medio(self.devolucion.medio_pago)}",
        ]


class RemitoDocumento(DocumentoComercial):
    """El remito que viaja con los bultos del CD al local: qué lleva cada bulto
    y con qué precinto, para que el local lo controle al recibir. No tiene
    precios. Se descarga una vez despachado (antes todavía puede cambiar).
    Es una hija más de la plantilla: usa los ganchos columnas() y
    etiqueta_responsable() sin tocar armar()."""

    def __init__(self, remito, contexto, destino, direccion_destino):
        if remito.estado == remito.ABIERTO:
            raise DatoInvalido("El remito se puede descargar una vez despachado")
        super().__init__(contexto)
        self.remito = remito
        self.destino = destino
        self.direccion_destino = direccion_destino

    def titulo(self):
        return "Remito"

    def codigo(self):
        return f"{self.remito.origen:04d}-{self.remito.id_remito:08d}"

    def fecha(self):
        return self.remito.fecha

    def prefijo_archivo(self):
        return "remito"

    def columnas(self):
        return ("Producto", "Cant.", "Bulto", "Precinto")

    def etiqueta_responsable(self):
        return "Preparó"

    def renglones(self):
        return [Renglon(self.nombre_producto(d.producto), d.cantidad, f"#{bulto.id_bulto}", bulto.nro_precinto or "-")
                for bulto in self.remito.bultos for d in bulto.items]

    def totales(self):
        unidades = sum(d.cantidad for bulto in self.remito.bultos for d in bulto.items)
        return [Total("Bultos", len(self.remito.bultos)), Total("Unidades", unidades, destacado=True)]

    def notas(self):
        notas = [f"Destino: {self.destino} · {self.direccion_destino}"]
        if self.remito.llegada_estimada:
            notas.append(f"Llegada estimada: {self.remito.llegada_estimada:%d/%m/%Y %H:%M}")
        notas.append("Al recibir, el local controla el precinto de cada bulto: si no coincide o llegó roto, "
                     "el bulto se rechaza y su mercadería no entra al stock.")
        return notas

