# Patrones de diseño del TP

La consigna pide al menos 2 patrones. Usamos **tres patrones del libro (GoF)**
—State, Strategy y Template Method— más fábricas simples y DAO. Para cada uno:
dónde está, qué problema resuelve y qué habría pasado sin él. La explicación
larga de State y Strategy está en [guia_oral.md](guia_oral.md); los diagramas,
en [diagramas.md](diagramas.md).

## Resumen

| Patrón | Dónde | Qué problema resuelve | Sin el patrón |
|---|---|---|---|
| **State** | `dominio/estados_bulto.py` (estados) y `Bulto` en `dominio/logistica.py` (contexto) | El bulto se comporta distinto según su etapa: solo se precinta si está Preparado, solo se despacha si está Precintado, solo se verifica si fue Recibido. Cada estado es una clase que permite solo lo suyo y decide a cuál pasa | Cada método del bulto con una cadena de `if self.estado == ...`; las reglas de todos los estados mezcladas y un estado nuevo obliga a tocar todos los métodos |
| **Strategy** | `dominio/medios_pago.py` (estrategias) y `Venta.cobrar()` en `dominio/ventas.py` (contexto) | Cada medio de pago calcula distinto el total (efectivo −15 %, crédito +10 %) y el vuelto (solo efectivo). La venta recibe una estrategia y le delega el cálculo sin saber cuál es | `if medio == "EFECTIVO"` en la venta para el total, otro para el vuelto, y lo mismo en la cotización; un medio nuevo toca la venta |
| **Template Method** | `DocumentoComercial.armar()` en `dominio/documentos.py`; hijas `ComprobanteVenta`, `NotaCredito` y `RemitoDocumento` | El comprobante, la nota de crédito y el remito se arman igual (encabezado, renglones, totales, notas) y cambian solo en el contenido. El método plantilla fija el orden y cada hija completa los pasos; `notas()`, `columnas()` y `etiqueta_responsable()` son ganchos con valor por defecto (el remito los usa para mostrar bulto y precinto, y "Preparó") | Tres funciones casi iguales que repiten el encabezado y los totales; un cambio de formato hay que hacerlo tres veces |
| **Fábrica simple** | `crear_estado`, `crear_medio_pago`, `crear_ubicacion`, `crear_usuario` | En la base se guarda un texto ("PRECINTADO", "EFECTIVO", "CD", "SUCURSAL"); la fábrica es el único lugar que sabe qué clase corresponde a cada texto (un diccionario nombre → clase) | Un `if` por cada texto en cada DAO que lee esos objetos |
| **DAO** | `persistencia/dao_*.py` | Todo el SQL de cada entidad en una clase. El service decide; el DAO guarda y trae | SQL repartido en los services; cambiar la base obliga a tocar las reglas |

## Otras ideas de diseño que vale la pena mencionar

| Idea | Dónde | Por qué |
|---|---|---|
| **Polimorfismo por capacidades** | `Usuario` (`puede_vender()`, `puede_preparar_envios()`…) y `Ubicacion` (`puede_despachar()`…) | Los perfiles y las ubicaciones se diferencian en qué pueden hacer. La api pregunta `requiere("puede_vender")` y el front arma el menú con las capacidades: no hay ningún `if perfil ==`. Un perfil nuevo es una clase más |
| **Objeto filtro** | `FiltroProductos` en `dominio/maestros.py` | Junta los criterios de búsqueda y valida que tengan sentido ("desde" no mayor que "hasta"); el DAO lo traduce a SQL |
| **Separar el contenido de cómo se dibuja** | `ContenidoDocumento` (dominio) y `servicios/documentos_pdf.py` | El dominio decide qué dice el documento; el PDF lo dibuja uno solo para todos. Cambiar fpdf2 por otra librería no toca el dominio |

## Preguntas que pueden venir

- **¿State y Strategy no son lo mismo?** En los dos un objeto delega en otro.
  En State el delegado **cambia solo** (el estado decide el siguiente) y
  representa una etapa del bulto. En Strategy la estrategia **la elige quien
  usa la venta** y no cambia sola: es una forma intercambiable de calcular.
- **¿Y Template Method frente a Strategy?** Template Method usa **herencia**: la
  plantilla está en la clase padre y las hijas completan pasos. Strategy usa
  **composición**: la venta tiene una estrategia y se la puede cambiar sin
  heredar de nada.
- **¿Por qué el remito no usa State?** Su ciclo es lineal (abierto → en
  tránsito → verificado) y no cambia de comportamiento según el estado. State
  ahí sería sobrediseño; alcanzan constantes y validaciones en sus métodos.
- **¿Por qué el CD no es un Singleton?** "Un solo CD activo" es una regla del
  negocio sobre los datos, no una restricción técnica de un objeto. Se valida
  en el service y con un índice único parcial en la base; puede haber CDs
  dados de baja.
- **¿Cómo agregarían un medio de pago, un estado o un documento nuevo?** Una
  clase más que herede de `MedioPago`, `EstadoBulto` o `DocumentoComercial`,
  y sumarla a su fábrica si la tiene. La venta, el bulto y la plantilla no se
  tocan (hay un test que crea un "Presupuesto" solo definiendo los pasos).
