# TP DAO – Tema 3: Sistema de Ventas e Inventario

Sistema para un **Centro de Distribución (CD)** que abastece a varios **locales**:
maneja maestros, stock por ubicación, reposición CD → locales (pedidos, órdenes,
remitos y bultos) y ventas en los locales (cobros, comprobantes y devoluciones).

## Integrantes

- Maragliano, Geronimo – 411910
- Apellido, Nombre – Legajo
- Apellido, Nombre – Legajo
- Apellido, Nombre – Legajo

## Organización del proyecto

```
tp-dao-tema3/
├── backend/          → todo el backend en Python, separado en capas
│   ├── dominio/      → clases del negocio puras (sin base de datos ni web)
│   ├── persistencia/ → acceso a SQLite con patrón DAO
│   ├── servicios/    → casos de uso: coordinan dominio + persistencia
│   ├── api/          → endpoints web (FastAPI), solo reciben pedidos y llaman a servicios
│   └── datos/        → seed.py: datos de prueba
├── tests/            → pruebas con pytest de las reglas de negocio
├── frontend/         → interfaz en React + Vite
└── docs/             → guía para el oral
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

El seed carga 10 productos, 3 proveedores, el CD y 3 sucursales, compras,
una orden de reposición (un remito verificado, uno con un bulto rechazado y
uno en tránsito), 8 ventas y 2 devoluciones. Solo carga si la base está
vacía; `--reiniciar` borra la base local y la vuelve a cargar.

### 2. Backend (cada vez) — terminal 1

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

Queda en http://127.0.0.1:8000. En http://127.0.0.1:8000/docs está la
documentación interactiva de la api (Swagger).

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

## Los 7 procesos obligatorios

| # | Proceso | Dónde |
|---|---|---|
| 1 | Sucursales y Centro de Distribución | `/ubicaciones` · pantalla *Sucursales y CD* |
| 2 | Productos, categorías, precios, mínimos y proveedores | `/productos`, `/categorias`, `/proveedores` · pantallas de *Maestros* |
| 3 | Consolidar pedidos de los locales en una orden (origen y destino) | `POST /pedidos`, `POST /ordenes` · pantalla *Logística*, pasos 1 y 2 |
| 4 | Empaquetar en bultos con remito y precinto | `POST /remitos`, `POST /remitos/{id}/bultos`, `POST /bultos/{id}/precintar` |
| 5 | Despacho desde el CD | `POST /remitos/{id}/despachar` (descuenta el stock del CD) |
| 6 | Recepción verificando el precinto | `POST /bultos/{id}/recibir`, `POST /bultos/{id}/verificar` |
| 7 | Ventas, cobros, comprobante y devoluciones | `/ventas`, `/ventas/{id}/devoluciones`, `/caja/{sucursal}` · pantalla *Ventas* |

**Recorrido completo desde /docs:** `POST /stock/ingresar` (compra al CD) →
`POST /pedidos` → `POST /ordenes` → `POST /remitos` → `POST /remitos/{id}/bultos`
→ `POST /bultos/{id}/precintar` → `POST /remitos/{id}/despachar` →
`POST /bultos/{id}/recibir` → `POST /bultos/{id}/verificar` → `POST /ventas` →
`POST /ventas/{id}/devoluciones`.

## Patrones de diseño

| Patrón | Dónde | Para qué |
|---|---|---|
| **State** | `dominio/estados_bulto.py` + `Bulto` en `dominio/logistica.py` | El bulto delega cada acción en su estado (Preparado, Precintado, En tránsito, Recibido, Verificado, Rechazado); cada estado permite solo sus transiciones |
| **Strategy** | `dominio/medios_pago.py` | Cada medio de pago (efectivo, débito, crédito, transferencia) calcula su descuento o recargo y su vuelto; la Venta no sabe con qué le pagan |
| **DAO** | `persistencia/dao_*.py` | Todo el SQL de cada entidad en un solo lugar |

Además se usa una **fábrica simple** (un diccionario nombre → clase) para
volver a armar objetos desde el texto guardado en la base: `crear_estado`
(estados del bulto), `crear_medio_pago` y `crear_ubicacion` (Sucursal o CD,
que heredan de `Ubicacion`).

La explicación detallada para el oral está en [docs/guia_oral.md](docs/guia_oral.md).

## Validaciones de la consigna

Cada una está probada de punta a punta en `tests/test_validaciones_consigna.py`.

| Validación | Cómo se cumple |
|---|---|
| El stock no está disponible en el local hasta que el remito y el bulto estén verificados; precinto roto → Rechazado | El stock entra recién cuando se termina de verificar el remito, solo de los bultos que `habilita_venta()`. A un local no se le puede comprar directo |
| Trazabilidad inmutable de estados del bulto | Patrón State + tabla `historial_bultos` con triggers que rechazan UPDATE y DELETE (igual para los libros de stock y caja) |
| No vender más que el stock disponible y verificado | `Stock.egresar` lanza `StockInsuficiente` dentro de la transacción de la venta |
| Sin productos ni proveedores duplicados | Código (SKU) del producto y CUIT del proveedor (con dígito verificador), en el service y con `UNIQUE` en la base |
| Devoluciones solo de ventas registradas | `Venta.devolver`: solo de lo vendido, dentro del plazo y por lo cobrado |

## Reportes (`GET /reportes/...` · pantalla *Reportes*)

| Reporte | Qué muestra |
|---|---|
| `ventas` | Ventas, devoluciones e ingreso neto por período (día/mes/total), local y medio de pago |
| `productos-mas-vendidos` | Ranking por unidades, con ingreso, costo y margen (ganancia o pérdida) con los precios del momento de la venta |
| `existencias` | Stock por ubicación, productos bajo mínimo y valorización del inventario a costo |
| `mermas` | Bultos rechazados por precinto: qué se perdió, cuánto vale y la tasa de rechazo por sucursal |
| `tiempos-transito` | Horas entre que el bulto sale del CD y llega al local, según el historial |

## Decisiones de diseño

| Tema | Decisión | Estado |
|---|---|---|
| Descuento de stock en el CD | Al despachar el remito, no al preparar los bultos | Provisoria: consultar al profe |
| Ingreso al local | Cuando se termina de verificar el remito completo, solo de los bultos verificados | Se cambia en un método de `recepcion_service.py` |
| Bulto rechazado | Queda como merma: no vuelve al CD | Provisoria: consultar al profe |
| Dinero | `Decimal` en ventas y caja (en la base, centavos) | |
| Proveedor por producto | Muchos a muchos | Confirmar que sea decisión del grupo |
| Tecnología | FastAPI + React | El enunciado menciona Flask + Jinja2: confirmar con el profe |
| Baja de maestros | Baja lógica con reactivación; la eliminación física queda para después | |
