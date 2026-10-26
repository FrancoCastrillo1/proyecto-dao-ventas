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

El seed carga 10 productos, 3 proveedores, el CD y 3 locales, compras, una
orden de reposición (un remito verificado, uno con un bulto rechazado y uno en
camino), 8 ventas, 2 devoluciones y **un usuario de cada perfil**. Solo carga
si la base está vacía; `--reiniciar` borra la base local y la vuelve a cargar.

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
| **Template Method** | `dominio/documentos.py` | `DocumentoComercial.armar()` fija cómo se arma un documento; el comprobante de venta y la nota de crédito completan solo sus pasos |
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
| `existencias` | Stock por ubicación, productos bajo mínimo y valorización del inventario a costo |
| `mermas` | Bultos rechazados por precinto: qué se perdió, cuánto vale y la tasa de rechazo por local |
| `tiempos-transito` | Horas entre que el bulto sale del CD y llega al local, según el historial |

Un local ve solo los suyos; el administrador y el CD, los de toda la red.

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
