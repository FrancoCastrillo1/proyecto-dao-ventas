# Diagramas del TP

Están en **Mermaid**: GitHub los dibuja solos al abrir este archivo, y se
corrigen editando el texto. Para la presentación hay una imagen PNG de cada uno
en [`docs/img/`](img/) (se regeneran con `docs/img/generar.mjs`).

1. [Estados del bulto (patrón State)](#1-estados-del-bulto-patrón-state)
2. [Estados del remito](#2-estados-del-remito)
3. [Clases: logística y patrón State](#3-clases-logística-y-patrón-state)
4. [Clases: ventas, Strategy y Template Method](#4-clases-ventas-strategy-y-template-method)
5. [Clases: maestros, stock y usuarios](#5-clases-maestros-stock-y-usuarios)
6. [Capas](#6-capas)

---

## 1. Estados del bulto (patrón State)

Cada estado es una clase (`backend/dominio/estados_bulto.py`) que permite solo
sus transiciones; cualquier otra acción lanza `TransicionDeEstadoInvalida`.
Cada cambio queda en el historial (inmutable: triggers en la base) con quién lo
hizo. Solo **Verificado** habilita la venta (`habilita_venta()`).

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Preparado : el CD arma el bulto
    Preparado --> Preparado : agregar / quitar productos
    Preparado --> Precintado : precintar(nro) [CD]
    Precintado --> EnTransito : despachar el remito [CD]
    EnTransito --> Recibido : recibir [local]
    Recibido --> Verificado : verificar · precinto igual y sano [local]
    Recibido --> Rechazado : verificar · precinto distinto o roto [local]
    Verificado --> [*] : su mercadería entra al stock del local
    Rechazado --> [*] : merma, no entra al stock
    EnTransito : En tránsito
    note right of Verificado
        habilita_venta() = True
        (en todos los demás, False)
    end note
```

## 2. Estados del remito

El remito no usa State: su ciclo es lineal y no cambia de comportamiento según
el estado (son constantes en `Remito`). Pasa a su estado final cuando se
verifica el **último** bulto; recién ahí entra el stock al local.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> ABIERTO : un remito por local de la orden
    ABIERTO --> ABIERTO : agregar bultos
    ABIERTO --> CERRADO : cerrar · todos precintados
    ABIERTO --> EN_TRANSITO : despachar(llegada estimada)
    CERRADO --> EN_TRANSITO : despachar(llegada estimada)
    EN_TRANSITO --> VERIFICADO : último bulto verificado y ninguno rechazado
    EN_TRANSITO --> VERIFICADO_CON_RECHAZOS : último bulto verificado y alguno rechazado
    VERIFICADO --> [*]
    VERIFICADO_CON_RECHAZOS --> [*]
    note right of EN_TRANSITO
        Al despachar sale el stock del CD.
        Si pasa la llegada estimada: esta_demorado()
    end note
```

## 3. Clases: logística y patrón State

```mermaid
classDiagram
    direction LR
    class PedidoReposicion {
        +local
        +estado: PENDIENTE | CONSOLIDADO
        +items: DetallePedido[]
        +agregar_item(producto, cantidad)
        +consolidar()
    }
    class OrdenReposicion {
        +origen: el CD activo
        +pedidos: PedidoReposicion[]
        +agregar_pedido(pedido)
        +cerrar()
        +total_por_producto()
    }
    class Remito {
        +origen
        +destino
        +estado
        +llegada_estimada
        +agregar_bulto(bulto)
        +despachar(llegada_estimada)
        +registrar_verificacion() bool
        +bultos_verificados()
        +esta_demorado() bool
    }
    class Bulto {
        +nro_precinto
        +items: DetalleBulto[]
        +historial: CambioEstadoBulto[]
        +estado_actual: EstadoBulto
        +agregar_item(producto, cantidad)
        +precintar(nro)
        +despachar()
        +recibir()
        +verificar(nro_leido, intacto)
        +habilita_venta() bool
        +cambiar_estado(nuevo, observacion)
    }
    class EstadoBulto {
        <<abstract>>
        +nombre*
        +agregar_item() error por defecto
        +precintar() error por defecto
        +despachar() error por defecto
        +recibir() error por defecto
        +verificar() error por defecto
        +habilita_venta() False
    }
    class Preparado
    class Precintado
    class EnTransito
    class Recibido
    class Verificado {
        +habilita_venta() True
    }
    class Rechazado
    class CambioEstadoBulto {
        +fecha_hora
        +estado_anterior
        +estado_nuevo
        +observacion
    }
    class DetalleBulto {
        +producto
        +cantidad
    }

    OrdenReposicion "1" o-- "1..*" PedidoReposicion : consolida
    OrdenReposicion "1" -- "1..*" Remito : un remito por local
    Remito "1" *-- "1..*" Bulto
    Bulto "1" *-- "1..*" DetalleBulto
    Bulto "1" *-- "*" CambioEstadoBulto : historial inmutable
    Bulto --> EstadoBulto : delega en estado_actual
    EstadoBulto <|-- Preparado
    EstadoBulto <|-- Precintado
    EstadoBulto <|-- EnTransito
    EstadoBulto <|-- Recibido
    EstadoBulto <|-- Verificado
    EstadoBulto <|-- Rechazado
```

`crear_estado(nombre)` (fábrica simple con el diccionario `ESTADOS_BULTO`)
vuelve a armar el objeto estado a partir del texto que se guarda en la base.

## 4. Clases: ventas, Strategy y Template Method

```mermaid
classDiagram
    direction LR
    class Venta {
        +sucursal_id
        +detalles: DetalleVenta[]
        +pago: Pago
        +comprobante: Comprobante
        +devoluciones: Devolucion[]
        +agregar_item(producto, cantidad)
        +cobrar(medio, monto_entregado)
        +emitir_comprobante(numero)
        +devolver(items, motivo) Devolucion
    }
    class MedioPago {
        <<abstract>>
        +nombre*
        +porcentaje_ajuste*
        +calcular_total(subtotal)
        +calcular_vuelto(total, entregado)
    }
    class Efectivo {
        -15%
        +calcular_vuelto() valida y da vuelto
    }
    class Debito
    class Transferencia
    class Credito {
        +10%
    }
    class Devolucion {
        +motivo
        +detalles
        +nota_credito: Comprobante
        +importe
        +emitir_nota_credito(numero)
    }
    class Comprobante {
        +punto_venta
        +numero
        +codigo 0002-00000015
    }
    class DocumentoComercial {
        <<abstract>>
        +armar() ContenidoDocumento
        +encabezado() común
        +notas() gancho
        +columnas() gancho
        +etiqueta_responsable() gancho
        +titulo()*
        +codigo()*
        +renglones()*
        +totales()*
    }
    class ComprobanteVenta
    class NotaCredito
    class RemitoDocumento {
        +columnas() bulto y precinto
        +etiqueta_responsable() Preparó
    }
    class ContenidoDocumento {
        +titulo
        +codigo
        +columnas
        +renglones
        +totales
        +notas
    }

    Venta --> MedioPago : Strategy, delega el cálculo
    MedioPago <|-- Efectivo
    MedioPago <|-- Debito
    MedioPago <|-- Transferencia
    MedioPago <|-- Credito
    Venta "1" *-- "*" Devolucion
    Venta --> Comprobante
    Devolucion --> Comprobante : nota de crédito
    DocumentoComercial <|-- ComprobanteVenta
    DocumentoComercial <|-- NotaCredito
    DocumentoComercial <|-- RemitoDocumento
    ComprobanteVenta --> Venta
    NotaCredito --> Devolucion
    DocumentoComercial ..> ContenidoDocumento : armar() devuelve
```

`armar()` es el **método plantilla**: fija el orden (encabezado, renglones,
totales, notas) y cada documento completa solo los pasos marcados con `*`; los
ganchos tienen un valor por defecto. `RemitoDocumento` (el remito del envío)
redefine dos ganchos y no toca `armar()`.
El PDF lo dibuja `servicios/documentos_pdf.py` a partir del `ContenidoDocumento`,
sin saber qué documento es.

## 5. Clases: maestros, stock y usuarios

```mermaid
classDiagram
    direction LR
    class Ubicacion {
        <<abstract>>
        +nombre
        +direccion
        +tipo*
        +puede_vender() bool
        +puede_despachar() bool
        +puede_recibir() bool
    }
    class Sucursal {
        +puede_vender() True
        +puede_recibir() True
    }
    class CentroDistribucion {
        +puede_despachar() True
    }
    class Usuario {
        <<abstract>>
        +nombre_usuario
        +perfil*
        +trabaja_en_una_ubicacion() bool
        +puede_gestionar_maestros() bool
        +puede_preparar_envios() bool
        +puede_vender() bool
        +ve_toda_la_red() bool
        +validar_ubicacion(ubicacion)
    }
    class UsuarioAdministrador {
        sin ubicación
        maestros y usuarios
    }
    class UsuarioCD {
        compra y despacha
    }
    class UsuarioSucursal {
        pide, recibe y vende
    }
    class Producto {
        +codigo SKU
        +nombre
        +precio_venta
        +costo
        +stock_minimo
        +margen_unitario()
        +dar_de_baja(unidades_en_stock)
    }
    class Categoria
    class Proveedor {
        +cuit validado
        +razon_social
    }
    class Stock {
        +cantidad
        +stock_minimo
        +ingresar(cantidad, tipo)
        +egresar(cantidad, tipo)
        +esta_bajo_minimo() bool
        +faltante_para_el_minimo()
    }
    class MovimientoStock {
        +tipo: COMPRA | DESPACHO | RECEPCION | VENTA | DEVOLUCION | AJUSTE
        +cantidad con signo
    }
    class FiltroProductos {
        +texto
        +categoria_id
        +proveedor_id
        +precio_desde
        +precio_hasta
    }

    Ubicacion <|-- Sucursal
    Ubicacion <|-- CentroDistribucion
    Usuario <|-- UsuarioAdministrador
    Usuario <|-- UsuarioCD
    Usuario <|-- UsuarioSucursal
    Usuario --> Ubicacion : trabaja en (salvo el administrador)
    Producto "*" --> "1" Categoria
    Producto "*" -- "*" Proveedor : lo vende
    Stock "*" --> "1" Producto
    Stock "*" --> "1" Ubicacion
    Stock "1" *-- "*" MovimientoStock : libro inmutable
    FiltroProductos ..> Producto : busca
```

Los perfiles y las ubicaciones se diferencian en **qué pueden hacer**, no en sus
datos: las rutas y los services preguntan `usuario.puede_vender()` o
`ubicacion.puede_despachar()`, nunca comparan el tipo con un `if`. Las fábricas
`crear_usuario` y `crear_ubicacion` arman la clase según el texto guardado.

## 6. Capas

```mermaid
flowchart LR
    F["Front<br/>React + Vite"] -- "HTTP /api<br/>token Bearer" --> A["api<br/>rutas_* y dependencias<br/>(permisos por capacidad)"]
    A --> S["servicios<br/>casos de uso<br/>(transacciones)"]
    S --> D["dominio<br/>reglas y patrones<br/>(no conoce a nadie)"]
    S --> P["persistencia<br/>DAO + esquema.sql<br/>(UNIQUE, CHECK, triggers)"]
    P --> B[("SQLite")]
```

Cada validación está en tres lugares: el **formato** en el dominio, lo que
**consulta la base** en el service, y **UNIQUE, CHECK, claves foráneas y
triggers** en la base.
