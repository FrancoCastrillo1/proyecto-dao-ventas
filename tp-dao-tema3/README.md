# TP DAO – Tema 3: Sistema de Ventas e Inventario

Sistema para un **Centro de Distribución (CD)** que abastece a varios **locales**:
maneja maestros, stock por ubicación, reposición CD → locales (pedidos, órdenes,
remitos y bultos precintados) y ventas en los locales (cobros, comprobantes y
devoluciones). Se entra con usuario y contraseña, y cada perfil
(administrador, CD o local) ve y hace solo lo suyo.

## Integrantes

- Maragliano, Geronimo – 411910
- Castrillo, Franco – Legajo
- Maraboli, Nicolás – Legajo
- Caldo, Juan Pedro – Legajo

## Organización del proyecto

```
tp-dao-tema3/
├── backend/          → todo el backend en Python, separado en capas
│   ├── dominio/      → clases del negocio puras (sin base de datos ni web)
│   ├── persistencia/ → acceso a SQLite con patrón DAO, esquema y migraciones
│   ├── servicios/    → casos de uso: coordinan dominio + persistencia
│   ├── api/          → endpoints web (FastAPI) y permisos por perfil
│   └── datos/        → seed.py (datos de prueba) y crear_admin.py
├── tests/            → pruebas con pytest (dominio, services, base y api)
├── frontend/         → interfaz en React + Vite (gráficos de los reportes con Recharts)
└── docs/             → guía del oral, diagramas, patrones, demo y checklist
```

La regla de oro: cada capa solo conoce a la de abajo.
`api` → `servicios` → `dominio` + `persistencia`. El dominio no conoce a nadie.

## Cómo levantar el proyecto

Se necesitan **Python 3.10+** y **Node 18+**. Todos los comandos se corren
desde la carpeta `tp-dao-tema3/`.

### 1. Backend (la primera vez)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m backend.datos.seed      # carga datos de prueba (opcional)
```

El seed carga 10 productos, 3 proveedores, el CD y 3 locales, **un usuario de
cada perfil** y **90 días de operación de prueba hasta hoy** (nada a futuro):
unas 950 ventas a distintas horas, unas 40 devoluciones con distintos motivos y
los pedidos de reposición de cada local (cada 4 a 6 días) con su envío: el CD
los consolida, arma los bultos y los despacha a la tarde, y el local los recibe
al otro día; algunos llegan demorados o con un bulto con el precinto roto. Hoy
deja además 8 ventas, 2 devoluciones, un envío a Sur en camino, un pedido sin
preparar y otro en preparación. Tarda unos 30 segundos. Solo carga si la base está vacía; `--reiniciar` borra la base
local y la vuelve a cargar.

Sin el seed, el primer administrador se crea con
`.venv\Scripts\python -m backend.datos.crear_admin <usuario> "<Nombre completo>"`
(pide la contraseña sin mostrarla); después él crea los demás usuarios.

### 2. Backend (cada vez) — terminal 1

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

Queda en http://127.0.0.1:8000. En http://127.0.0.1:8000/docs está la
documentación interactiva (Swagger): hacer `POST /auth/login`, copiar el
`token` y pegarlo en el botón **Authorize**.

### 3. Frontend — terminal 2

```powershell
cd frontend
npm install      # solo la primera vez
npm run dev
```

Abrir http://localhost:5173. El backend tiene que estar corriendo.

### Tests

```powershell
.venv\Scripts\python -m pytest
```

## Usuarios de prueba

Los carga el seed. La contraseña de todos es **`tpdao2026`**.

| Usuario | Perfil | Qué hace |
|---|---|---|
| `admin` | Administrador (sin ubicación) | Locales, CD, productos, categorías, proveedores y usuarios. Ve toda la red; no opera |
| `cd.central` | Centro de Distribución | Compras, preparar pedidos, armar y precintar bultos, despachar. Ve toda la red |
| `centro`, `norte`, `sur` | Local | Pedir reposición, recibir y verificar envíos, vender y devolver. Ve solo su local |

## Los 7 procesos obligatorios

| # | Proceso | Dónde |
|---|---|---|
| 1 | Sucursales y Centro de Distribución | `/ubicaciones` · pantalla *Locales y CD* (administrador) |
| 2 | Productos, categorías, precios, mínimos y proveedores | `/productos` (con filtros), `/categorias`, `/proveedores` · pantallas de *Datos* (administrador) |
| 3 | Consolidar pedidos de los locales en una orden | `POST /pedidos` (local), `POST /ordenes` (CD) · pantalla *Envíos* |
| 4 | Empaquetar en bultos con remito y precinto | `POST /remitos`, `POST /remitos/{id}/bultos`, `POST /bultos/{id}/precintar` (CD) |
| 5 | Despacho desde el CD | `POST /remitos/{id}/despachar` con la llegada estimada (descuenta el stock del CD) |
| 6 | Recepción verificando el precinto | `POST /bultos/{id}/recibir`, `POST /bultos/{id}/verificar` (local destino) |
| 7 | Ventas, cobros, comprobante y devoluciones | `/ventas`, `/ventas/{id}/devoluciones`, `/caja/{local}`, comprobante y nota de crédito en PDF · pantalla *Vender* |

**Además:** login y permisos por perfil (`/auth`, `/usuarios`), bandeja de
tareas en Inicio (`GET /tareas`), pedido precargado con lo que falta, y envíos
demorados según la llegada estimada.

## Patrones de diseño

| Patrón | Dónde | Para qué |
|---|---|---|
| **State** | `dominio/estados_bulto.py` + `Bulto` en `dominio/logistica.py` | El bulto delega cada acción en su estado (Preparado, Precintado, En tránsito, Recibido, Verificado, Rechazado); cada estado permite solo sus transiciones |
| **Strategy** | `dominio/medios_pago.py` | Cada medio de pago (efectivo, débito, crédito, transferencia) calcula su descuento o recargo y su vuelto; la Venta no sabe con qué le pagan |
| **Template Method** | `dominio/documentos.py` | `DocumentoComercial.armar()` fija cómo se arma un documento; el comprobante de venta, la nota de crédito y el remito completan solo sus pasos |
| **Singleton** | `persistencia/conexion.py` | Una sola `BaseDeDatos` sabe dónde está la base, configura cada conexión y crea las tablas; cada operación le pide su propia conexión |
| **Fábrica simple** | `crear_estado`, `crear_medio_pago`, `crear_ubicacion`, `crear_usuario` | Vuelve a armar el objeto correcto a partir del texto guardado en la base |
| **DAO** | `persistencia/dao_*.py` | Todo el SQL de cada entidad en un solo lugar |

Los perfiles de usuario y los tipos de ubicación se diferencian por **lo que
pueden hacer** (`puede_vender()`, `puede_despachar()`…): ni la api ni el
front comparan el perfil con un `if`.

## Documentación

| Archivo | Qué tiene |
|---|---|
| [docs/diagramas.md](docs/diagramas.md) | Diagramas de estados (bulto y remito), de clases y de capas, en Mermaid. Imágenes en `docs/img/` |
| [docs/patrones.md](docs/patrones.md) | Cada patrón: dónde está, qué resuelve y qué pasaba sin él |
| [docs/guia_oral.md](docs/guia_oral.md) | La explicación de los patrones y las decisiones, con las preguntas que pueden venir |
| [docs/guion_demo.md](docs/guion_demo.md) | La demo de 5 minutos, paso a paso |
| [docs/presentacion_preliminar.md](docs/presentacion_preliminar.md) | Guion de la entrega y preguntas para el profe |
| [docs/recorrido_front.md](docs/recorrido_front.md) | Checklist para probar todo desde el navegador |
| [docs/plan_mejoras.md](docs/plan_mejoras.md) | El plan por pasos y las decisiones tomadas |

## Validaciones de la consigna

Cada una está probada de punta a punta en `tests/test_validaciones_consigna.py`
y está en tres lugares: dominio, service y base.

| Validación | Cómo se cumple |
|---|---|
| El stock no está disponible en el local hasta que el remito y el bulto estén verificados; precinto roto → Rechazado | El stock entra recién cuando se termina de verificar el remito, solo de los bultos que `habilita_venta()`. A un local no se le puede comprar directo |
| Trazabilidad inmutable de estados del bulto | Patrón State + tabla `historial_bultos` con triggers que rechazan UPDATE y DELETE (igual para los libros de stock y caja), con quién hizo cada cambio |
| No vender más que el stock disponible y verificado | `Stock.egresar` lanza `StockInsuficiente` dentro de la transacción de la venta |
| Sin productos ni proveedores duplicados | Código (SKU) único, y dos productos activos no se llaman igual; CUIT del proveedor único y con dígito verificador. En el service y con índices únicos en la base |
| Devoluciones solo de ventas registradas | `Venta.devolver`: solo de lo vendido, dentro del plazo y por lo cobrado; cada una con su nota de crédito |

## Reportes (`GET /reportes/...` · pantalla *Reportes*)

| Reporte | Qué muestra |
|---|---|
| `ventas` | Ventas, devoluciones e ingreso neto por período (día/mes/total), local y medio de pago |
| `productos-mas-vendidos` | Ranking por unidades, con ingreso, costo y margen (ganancia o pérdida) con los precios del momento de la venta |
| `existencias` | Stock por ubicación, productos bajo mínimo, días sin salir (stock parado) y valorización del inventario a costo |
| `productos-mas-pedidos` | Lo que más piden los locales al CD: unidades, pedidos, locales, cuánto falta preparar y si alcanza el stock del CD |
| `devoluciones` | Qué se devuelve, qué parte de lo vendido, el motivo más repetido y cuánto se reintegró por motivo |

Son 5 (la consigna pide al menos 4 no triviales). Cada perfil ve los que le sirven: el CD no ve los de ventas (ventas, más
vendidos, devoluciones) y "más pedidos" lo ven solo el CD y el administrador.
Un local ve solo lo suyo; el administrador y el CD, toda la red. Todos tienen
un gráfico y se descargan en PDF (`?formato=pdf`, botón "Descargar PDF").
Cada uno trae un resumen de dos o tres frases con lo importante (lo arma el
back, así la pantalla y el PDF dicen lo mismo), y en pantalla hay atajos de
período: hoy, últimos 7 días, este mes y el mes pasado.

## Tableros (`GET /tableros/...` · pantalla *Reportes*)

La pantalla Reportes abre con los tableros: indicadores comparados contra el
período anterior (o el mismo del año pasado) y gráficos. Cada gráfico tiene
**"Ver detalle"**, que abre el reporte que lo explica (tabla, resumen y PDF).
Hay uno por perfil y cada perfil abre el suyo (según sus capacidades puede ver
otros: el administrador ve los tres, el local también el de abastecimiento con
sus pedidos y su stock). El tablero también se descarga en PDF con todos sus
gráficos.

| Tablero | Quién | Qué muestra | Ver detalle abre |
|---|---|---|---|
| Ejecutivo | Administrador | Ventas, ganancia, margen y tickets con su variación; evolución contra el período comparado; ranking de locales (clic → ventas de ese local); ventas y ganancia por categoría | Ventas, Más vendidos |
| Ventas del local | Local (el suyo) y administrador | Tickets, ticket promedio, artículos por ticket; ventas por día en pesos o unidades; mapa de calor día × hora; categorías; lo que más se devuelve | Ventas, Más vendidos, Devoluciones |
| Abastecimiento | CD, administrador y local (sus pedidos y su stock) | Pedidos por estado y local; tiempo del pedido a la mercadería verificada (según el historial del bulto); lo más pedido (CD y admin); stock parado por última salida y lo que falta reponer | Más pedidos, Existencias |

El seed carga 90 días de **operación de prueba** hasta hoy (inventada, con
semilla fija) para que los reportes y los tableros tengan qué mostrar. Para
fecharla atrasa el **reloj del dominio** (`dominio/reloj.py`) mientras carga;
la api nunca lo toca.

## Decisiones de diseño

| Tema | Decisión | Estado |
|---|---|---|
| Descuento de stock en el CD | Al despachar el remito, no al preparar los bultos | Provisoria: consultar al profe |
| Ingreso al local | Cuando se termina de verificar el remito completo, solo de los bultos verificados | Se cambia en un método de `recepcion_service.py` |
| Bulto rechazado | Queda como merma: no vuelve al CD | Provisoria: consultar al profe |
| Perfiles | Administrador (sin ubicación), CD (uno solo) y local; el local de cada operación sale del usuario | |
| Contraseñas | PBKDF2 con sal; de cada sesión se guarda solo el hash del token, que vence a las 10 horas | |
| Dinero | `Decimal` en ventas y caja (en la base, centavos) | |
| Proveedor por producto | Muchos a muchos | Confirmar que sea decisión del grupo |
| Tecnología | FastAPI + React | El enunciado menciona Flask + Jinja2: confirmar con el profe |
| Baja de maestros | Baja lógica con reactivación; un producto con stock no se da de baja | |
| Transporte | Solo la llegada estimada (día y hora), obligatoria al despachar | |
