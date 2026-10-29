# Guía para el oral: patrones y decisiones del TP

Cada integrante tiene que poder explicar los cuatro patrones (State, Strategy,
Template Method y Singleton) y defender las decisiones de diseño. Esta guía arma la
explicación en el orden en que conviene contarla: **qué problema hay → cómo
lo resuelve el patrón → dónde está en el código → qué preguntas pueden venir**.

Material de apoyo: [diagramas.md](diagramas.md) (clases y estados, con imágenes
en `docs/img/`), [patrones.md](patrones.md) (tabla de todos los patrones) y
[guion_demo.md](guion_demo.md) (la demo de 5 minutos).

---

## 1. Patrón State: el ciclo de vida del bulto

### El problema
Un bulto pasa por **Preparado → Precintado → En tránsito → Recibido →
Verificado / Rechazado**, y en cada estado se pueden hacer cosas distintas:
solo se agregan productos mientras está Preparado, solo se despacha si está
Precintado, solo se verifica si fue Recibido.

Sin el patrón, cada método del bulto tendría una cadena de `if`:

```python
def despachar(self):
    if self.estado == "PRECINTADO":
        self.estado = "EN_TRANSITO"
    else:
        raise TransicionDeEstadoInvalida(...)
```

Las reglas de todos los estados quedan mezcladas en una sola clase, y
agregar un estado obliga a tocar todos los métodos.

### La solución
El bulto **guarda un objeto estado y le delega cada acción**. Cada estado es
una clase que sabe qué acciones permite y a qué estado pasa.

| Pieza del patrón | En el TP |
|---|---|
| **Contexto** | `Bulto` en `backend/dominio/logistica.py` |
| **Estado abstracto** | `EstadoBulto` en `backend/dominio/estados_bulto.py` |
| **Estados concretos** | `Preparado`, `Precintado`, `EnTransito`, `Recibido`, `Verificado`, `Rechazado` |

- `EstadoBulto` declara todas las acciones (`agregar_item`, `precintar`,
  `despachar`, `recibir`, `verificar`) y **por defecto todas lanzan
  `TransicionDeEstadoInvalida`**. Cada estado redefine solo las que permite.
  Por eso `Verificado` y `Rechazado` casi no tienen código: no permiten nada.
- El `Bulto` no decide nada: `despachar()` es una sola línea,
  `self.estado_actual.despachar(self)`.
- **Quien cambia el estado es el estado**: `Precintado.despachar` hace
  `bulto.cambiar_estado(EnTransito())`.
- `cambiar_estado` es el **único lugar** donde cambia el estado, y siempre
  deja un registro en el historial. Así la trazabilidad no se puede olvidar.

```
Preparado ──precintar──▶ Precintado ──despachar──▶ EnTransito ──recibir──▶ Recibido ──verificar──┬──▶ Verificado
   ↺ agregar/quitar productos                                                                    └──▶ Rechazado
```

### Dos detalles para lucirse
1. **`habilita_venta()` es polimorfismo puro.** Por defecto devuelve
   `False` y solo `Verificado` devuelve `True`. El servicio de recepción
   pregunta `bulto.habilita_venta()`, no compara `estado == "VERIFICADO"`.
2. **Persistencia del estado.** En la base se guarda el texto
   (`"PRECINTADO"`) y al leer, `crear_estado(nombre)` vuelve a armar el
   objeto con un diccionario `ESTADOS_BULTO` (una fábrica simple). El
   historial es inmutable **en la base**: triggers rechazan UPDATE y DELETE
   (`esquema.sql`, tabla `historial_bultos`).

### Preguntas que pueden venir
- **¿Por qué el Bulto no es abstracto con subclases BultoPreparado, etc.?**
  Porque un objeto no puede cambiar de clase: el bulto tendría que
  destruirse y crearse de nuevo, y perdería su identidad y su historial. Con
  State el bulto es siempre el mismo objeto; lo que se reemplaza es su estado.
- **¿Por qué las acciones de `EstadoBulto` no son `@abstractmethod`?**
  Porque obligaría a cada estado a escribir todas las acciones solo para
  lanzar el error. Abstracto es solo `nombre`, que cada estado tiene distinto.
- **¿Qué pasa si se intenta despachar un bulto Preparado?** El Bulto le
  delega a `Preparado`, que no redefine `despachar`, así que se ejecuta el
  de `EstadoBulto` y lanza `TransicionDeEstadoInvalida` (la api responde 409).
- **¿Cómo agregarían un estado nuevo, por ejemplo "Devuelto al CD"?** Una
  clase nueva que herede de `EstadoBulto`, redefinir en `Rechazado` la
  acción que lleva a ella y sumarla a `ESTADOS_BULTO`. El Bulto no se toca.

---

## 2. Patrón Strategy: los medios de pago

### El problema
Cada medio de pago cobra distinto: efectivo tiene 15 % de descuento y da
vuelto, crédito tiene 10 % de recargo, débito y transferencia cobran el
precio de lista. Sin el patrón, la venta tendría un `if medio == "EFECTIVO"`
para el total, otro para el vuelto, y así con cada medio nuevo.

### La solución
Cada medio de pago es una **estrategia intercambiable** con la misma interfaz.
La venta recibe una y le delega el cálculo, sin saber cuál es.

| Pieza del patrón | En el TP |
|---|---|
| **Contexto** | `Venta` en `backend/dominio/ventas.py` |
| **Estrategia abstracta** | `MedioPago` en `backend/dominio/medios_pago.py` |
| **Estrategias concretas** | `Efectivo`, `Debito`, `Credito`, `Transferencia` |

```python
def cobrar(self, medio, monto_entregado=None):
    total = medio.calcular_total(self.subtotal)
    vuelto = medio.calcular_vuelto(total, monto_entregado)
```

- `MedioPago` define `porcentaje_ajuste` (abstracto) y los métodos
  `calcular_total` y `calcular_vuelto`, con un comportamiento por defecto.
- `Efectivo` es el único que redefine `calcular_vuelto`: valida que lo
  entregado alcance (`PagoInsuficiente`) y calcula el vuelto.
- `crear_medio_pago("EFECTIVO")` arma la estrategia a partir del texto que
  llega de la api o de la base, con el diccionario `MEDIOS_PAGO`.

### Preguntas que pueden venir
- **¿Cómo agregarían MercadoPago con 5 % de recargo?** Una clase más que
  herede de `MedioPago` con `nombre` y `porcentaje_ajuste`, y sumarla a
  `MEDIOS_PAGO`. La Venta no cambia. Ese es el punto del patrón.
- **¿Qué diferencia hay entre State y Strategy, si se ven parecidos?** En
  los dos un objeto delega en otro. En **State** el objeto delegado **cambia
  solo** (el estado decide a cuál pasar) y representa en qué etapa está el
  bulto. En **Strategy** la estrategia **la elige quien usa la venta** y no
  cambia sola: es una forma intercambiable de hacer un cálculo.
- **¿Por qué la plata es `Decimal` y no `float`?** Porque con `float`,
  `0.1 + 0.2` da `0.30000000000000004` y los descuentos dejan diferencias de
  centavos. En la base se guarda en centavos (enteros).

---

## 3. Patrón Template Method: comprobante, nota de crédito y remito

### El problema
Cada venta tiene su comprobante, cada devolución su nota de crédito y cada
envío su remito, los tres en PDF. Se arman igual —datos del comercio y del
local, número, renglones, totales y notas al pie— y cambian solo en el
contenido. Con funciones sueltas, el encabezado y los totales se repiten y un
cambio de formato se hace tres veces.

### La solución
Una clase abstracta define el **método plantilla** con el orden fijo y llama a
pasos que cada hija completa.

| Pieza del patrón | En el TP |
|---|---|
| **Clase abstracta con el método plantilla** | `DocumentoComercial.armar()` en `backend/dominio/documentos.py` |
| **Pasos comunes (heredados)** | `encabezado()`, `notas_comunes()` |
| **Pasos que redefine cada hija** | `titulo()`, `codigo()`, `fecha()`, `renglones()`, `totales()`, `prefijo_archivo()` |
| **Ganchos (hooks)** | `notas()` (por defecto, ninguna), `columnas()` (por defecto Producto, Cant., Precio, Importe) y `etiqueta_responsable()` (por defecto "Atendió"): tienen un valor por defecto y un documento los redefine solo si lo necesita |
| **Clases concretas** | `ComprobanteVenta`, `NotaCredito`, `RemitoDocumento` |

- El **remito** (sumado el 26/10) fue la prueba de que el patrón sirve: se
  agregó una hija nueva y `armar()` no se tocó. Redefine los ganchos para
  mostrar bulto y precinto en vez de precio, y "Preparó" en vez de "Atendió".
  Se descarga recién despachado, porque antes no es definitivo.

- `armar()` devuelve un `ContenidoDocumento` (qué dice el papel). El PDF lo
  dibuja `servicios/documentos_pdf.py` con fpdf2, **sin saber qué documento
  es**: el dominio no conoce la librería.
- La nota de crédito se numera correlativa por local como el comprobante
  (`NC 0002-00000001`), y en la base un trigger impide repetir el número.

### Preguntas que pueden venir
- **¿En qué se diferencia de Strategy?** Template Method usa **herencia**: la
  plantilla está en el padre y las hijas completan pasos. Strategy usa
  **composición**: la venta tiene una estrategia que se puede cambiar.
- **¿Cómo agregarían un presupuesto?** Una hija más que defina los pasos;
  `armar()` y el dibujo del PDF no se tocan (hay un test que lo hace).
- **¿Por qué el PDF no está en el dominio?** Porque es cómo se ve, no una
  regla: el dominio arma el contenido y otra capa lo dibuja.

---

## 3b. Patrón Singleton: la base de datos

### El problema
Toda la app trabaja sobre **una misma base**. Antes, cada DAO guardaba su
propia ruta y llamaba a una función suelta para abrir la conexión: la
configuración (dónde está el archivo, activar las claves foráneas, leer las
filas por nombre de columna) no tenía un dueño.

### La solución
**Singleton** asegura que de una clase haya **una sola instancia** y da un
único punto de acceso a ella.

| Pieza del patrón | En el TP |
|---|---|
| **La clase con una sola instancia** | `BaseDeDatos` en `backend/persistencia/conexion.py` |
| **Cómo se garantiza que sea una** | `__new__` (lo que Python llama para crear el objeto): la primera vez la crea y la guarda en `BaseDeDatos.unica`; las siguientes devuelve esa. Un candado (`threading.Lock`) evita que dos hilos la creen a la vez |
| **Punto de acceso** | `BaseDeDatos.instancia()` (o `BaseDeDatos()`, que da la misma) |
| **Qué hace** | Sabe dónde está la base (`ruta`), entrega conexiones configuradas siempre igual (`conexion()`), abre transacciones (`transaccion()`) y crea o migra las tablas (`crear_tablas()`) |
| **Quién la usa** | Todos los DAOs: `BaseDeDatos.instancia().conexion(self.db_path)`; `main.py` y el seed para crear las tablas |

- **Lo que hay una sola vez es el objeto, no la conexión:** cada operación
  pide la suya. FastAPI atiende varios pedidos a la vez en distintos hilos, y
  una sola conexión de SQLite compartida mezclaría las transacciones.

### Preguntas que pueden venir
- **¿Por qué no una sola conexión para toda la app?** Por los hilos: si una
  venta falla y hace rollback, desharía también lo que estaba guardando un
  despacho en la misma conexión. Hay un test que verifica que cada pedido de
  conexión es una distinta.
- **¿Qué críticas tiene el Singleton?** Es estado global y complica los
  tests. Por eso la instancia acepta otra ruta al pedir la conexión: los
  tests usan bases temporales sin tocar la de la app.
- **¿Por qué el CD no es un Singleton?** "Un solo CD activo" es una regla del
  negocio sobre los datos (se valida en el service y con un índice único en la
  base), no una restricción técnica de un objeto.

---

## 4. Usuarios y perfiles: polimorfismo por capacidades

### El problema
Hay tres perfiles: **administrador** (maneja los datos: locales, productos,
proveedores, usuarios), **CD** (compra, prepara y despacha) y **local** (pide,
recibe, vende). Cada uno puede hacer cosas distintas y ver solo lo suyo.

### La solución
`Usuario` es abstracta, con `UsuarioAdministrador`, `UsuarioCD` y
`UsuarioSucursal` (`backend/dominio/usuarios.py`). Cada perfil **responde qué
puede hacer**: `puede_vender()`, `puede_preparar_envios()`,
`puede_gestionar_maestros()`, `ve_toda_la_red()`… Por defecto todo da `False`
y cada hija redefine lo suyo (igual que los estados del bulto).

- La api pide la capacidad en cada ruta: `Depends(requiere("puede_vender"))`
  (`backend/api/dependencias.py`). Si algo es de otro local: 403 "Ese remito
  no es de tu local".
- El front arma el menú con las capacidades que devuelve `/auth/yo`.
- **No hay ningún `if perfil == ...`**: un perfil nuevo es una clase más.
- El local de una venta o un pedido sale del usuario que entró, nunca del
  formulario.
- Login con contraseña: hash PBKDF2 con sal (nunca en texto) y un token del
  que la base guarda solo el hash, con vencimiento de 10 horas.
- Cada operación graba quién la hizo (`usuario_id`); en el historial del
  bulto lo graba el DAO, así el patrón State no se tocó.

---

## 5. Otras decisiones que conviene saber defender

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué capas? | `api` → `servicios` → `dominio` + `persistencia`. El dominio no sabe de base ni de web: se prueba solo y las reglas viven en un único lugar. |
| ¿Qué es el DAO? | Una clase por entidad con todo su SQL. El service decide; el DAO guarda y trae. Si cambia la base, cambian solo los DAO. |
| ¿Sucursal y CD? | Herencia: `Ubicacion` abstracta con `Sucursal` y `CentroDistribucion`. Se diferencian en lo que pueden hacer (`puede_vender`, `puede_despachar`, `puede_recibir`), no en los datos. Una sola tabla con columna `tipo`. |
| ¿Por qué un solo CD activo? | Lo dice la consigna. Es una regla en el service y un índice único parcial en la base, no un Singleton: el CD es un dato del negocio, no un objeto técnico. |
| ¿Cuándo entra el stock al local? | Cuando se termina de verificar el remito completo, solo de los bultos verificados ("el remito y el contenedor verificados"). Un bulto rechazado queda como merma. |
| ¿Cuándo sale del CD? | Al despachar el remito, todo en una transacción: si un producto no alcanza, no se despacha nada. |
| ¿Por qué baja lógica? | Las ventas y los remitos apuntan a los maestros; si se borraran, la historia quedaría rota. Lo dado de baja se puede reactivar. |
| ¿Cómo garantizan las validaciones? | En tres lugares: dominio (formato y estados), service (lo que necesita consultar la base) y base (UNIQUE, CHECK, claves foráneas y triggers). `tests/test_validaciones_consigna.py` prueba las 5 de la consigna. |
| ¿Por qué un administrador aparte? | Administrar los datos y operar son tareas distintas. El administrador no tiene ubicación (lo controla un CHECK en la base) y no se puede dar de baja al último. |
| ¿Productos duplicados? | El código (SKU) es único, y además dos productos **activos** no pueden llamarse igual (sin importar mayúsculas ni tildes): índice único parcial en la base. |
| ¿Se puede dar de baja un producto con stock? | No: quedaría mercadería que no aparece en ninguna lista. Lo controla el dominio con el dato que cuenta el service, y un trigger en la base. |
| ¿Qué datos del transporte guardan? | Solo la llegada estimada (día y hora), obligatoria al despachar. Sirve para que el local sepa cuándo llega y para marcar los envíos demorados. |
| ¿Qué es la bandeja de Inicio? | `GET /tareas` arma lo pendiente según las capacidades del usuario: el CD ve qué preparar y despachar; el local, qué recibir, verificar y reponer (con el pedido ya cargado). |
| ¿Tableros o reportes? | Están en la misma pantalla, Reportes: primero el tablero, para mirar de un vistazo (indicadores comparados y gráficos), y cada gráfico tiene "Ver detalle", que abre el reporte con la tabla exacta, el resumen y el PDF. Es como trabajan las herramientas de BI: panorama primero, detalle a pedido. Cada perfil abre su tablero: el admin el Ejecutivo, el local sus ventas, el CD el abastecimiento. Los 7 reportes de la consigna son los detalles. |
| ¿Cómo dibujan tantos gráficos distintos en el PDF? | Un solo dibujante (`informes_pdf.py`) con una función por tipo de gráfico (barras, líneas, mapa de calor, dispersión), elegida por el tipo del dato (`DIBUJOS`). Qué dice cada PDF lo arma otro archivo (`informes.py` para los reportes, `informes_tableros.py` para los tableros), que no sabe dibujar. |
| ¿Cómo saben que los números de los tableros cierran entre sí? | Todos los gráficos de ventas salen de una sola consulta (las líneas de venta, netas de devoluciones y con el costo del momento), agrupada de distintas formas: como una tabla de hechos de BI. |
| ¿Contra qué comparan? | Lo elige el usuario: los mismos días justo antes o las mismas fechas del año anterior. Lo calcula `Periodo` en el dominio. Si antes fue 0, la variación dice "sin datos" (no un +100 % engañoso), y el margen se compara en puntos. |
| ¿Las ventas de 60 días son reales? | No: son **datos de prueba** del seed, inventados con una semilla fija para que los tableros muestren algo. Pasan por el mismo service que una venta real; solo el seed puede fecharlas, la api nunca recibe la fecha. |
| ¿Un local puede ver los números de otro? | No: el back fija el local con `ubicacion_para_filtrar` (si pide otro, 403). El Ejecutivo exige `ve_resultados_empresa` (solo admin) y el CD no ve márgenes. Esconderlo en el front no alcanza. |

## 6. Para practicar antes del oral
1. Correr `.venv\Scripts\python -m backend.datos.seed --reiniciar` y levantar
   back y front.
2. Hacer la demo de [guion_demo.md](guion_demo.md) entera, cronometrada.
3. Explicar en voz alta los diagramas de [diagramas.md](diagramas.md): el de
   estados del bulto y el de clases de logística.
4. Abrir `estados_bulto.py`, `medios_pago.py` y `documentos.py` y explicarlos
   con la tabla "Pieza del patrón → En el TP" de cada uno.
5. Responder las preguntas de [patrones.md](patrones.md) sin mirar.
