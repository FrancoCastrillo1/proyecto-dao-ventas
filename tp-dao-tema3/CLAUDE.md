# TP DAO – Tema 3: contexto para Claude

## Quién soy
Geronimo Maragliano, estudiante. TP grupal de DAO con Franco Castrillo,
Nicolas Maraboli y Juan Pedro Caldo. Hablame en castellano rioplatense.
Tengo que poder defender todo en el oral: explicá el porqué de cada cosa.

## La consigna, resumida
Comercio minorista con varios locales que se abastecen de un **Centro de
Distribución (CD)**. Los locales piden reposición, el CD arma **bultos con
remito y precinto**, los despacha y el local los recibe verificando el
precinto. **Nada entra a stock vendible sin verificación.**

- **7 procesos obligatorios:** sucursales y CD; productos, categorías, precios,
  mínimos y proveedores; consolidar pedidos en una orden de reposición;
  empaquetar en bultos con remito y precinto; despacho; recepción verificando
  el precinto; ventas con cobro, medio de pago, comprobante y devoluciones.
- **5 validaciones:** stock disponible en el local solo con remito y bulto
  Verificados (precinto roto → Rechazado); trazabilidad inmutable de estados del
  bulto (Preparado, Precintado, En tránsito, Recibido, Verificado/Rechazado); no
  vender más que el stock disponible; sin productos ni proveedores duplicados;
  devoluciones solo de ventas registradas.
- **Evaluación:** mínimo 2 patrones de diseño y 4 reportes no triviales. El
  ciclo de vida del bulto se evalúa "críticamente en el modelo".
- **Entrega preliminar: 29/10/2026**, con los 7 procesos funcionando.

## Repo y tecnología
- GitHub: https://github.com/FrancoCastrillo1/proyecto-dao-ventas (todo en `main`).
  El repo git está en la carpeta padre `proyecto-dao-ventas/`; el código, en `tp-dao-tema3/`.
- Backend: Python + FastAPI + SQLite. Frontend: React + Vite (proxy `/api`). Tests: pytest.
- Capas: `api` → `servicios` → `dominio` + `persistencia`. El dominio no conoce a nadie.

```
backend/dominio/       maestros.py, estados_bulto.py (State), logistica.py, stock.py,
                       ventas.py, medios_pago.py (Strategy), dinero.py, excepciones.py
backend/persistencia/  esquema.sql, conexion.py (transacciones + migración), dao_*.py
backend/servicios/     maestros, stock, reposicion, recepcion, ventas, reportes
backend/api/           rutas_maestros, rutas_stock, rutas_logistica, rutas_ventas, rutas_reportes
backend/datos/seed.py  datos de prueba
frontend/src/          api.js, componentes/, pantallas/
docs/                  guia_oral.md, presentacion_preliminar.md
```

## Qué hizo cada uno
| Parte | Autor |
|---|---|
| Base del proyecto y Categoría | Franco |
| Patrón State del Bulto | Geronimo |
| Historial inmutable, tests del bulto, `habilita_venta()` | Nicolás |
| Maestros: Producto (SKU), Proveedor (CUIT, N:M con Producto), Ubicacion → Sucursal/CD, duplicados sin tildes, parecidos, reactivar | Geronimo |
| Stock: `Stock`, `MovimientoStock`, transacciones, `validar_ubicacion_para` | Nicolás y Franco |
| Dominio de logística: `DetalleBulto`, `PedidoReposicion`, `OrdenReposicion`, `Remito` | Juan Pedro |
| Ventas: Strategy de medios de pago, `Decimal`/centavos, comprobante, devoluciones, caja | Franco |
| Logística pasos 7 a 10 (tablas, DAO, servicios, endpoints) | Geronimo |
| Cierre: reportes, seed, validaciones, front de procesos, README, guías | Geronimo |

## Decisiones de diseño
- **State:** el `Bulto` delega en `estado_actual`; `EstadoBulto` lanza
  `TransicionDeEstadoInvalida` por defecto y cada estado redefine lo suyo. El
  estado cambia solo por `cambiar_estado()`, que registra el historial. En la
  base se guarda el texto y `crear_estado()` vuelve a armar el objeto.
- **Fábricas simples** (diccionario nombre → clase): `crear_estado`, `crear_medio_pago`, `crear_ubicacion`, `crear_usuario`.
- **Template Method:** `DocumentoComercial` (comprobante de venta y nota de crédito), desde el paso 5.
- **Inmutabilidad en la base:** triggers que rechazan UPDATE y DELETE en
  `historial_bultos`, `movimientos_stock` y `movimientos_caja`.
- **Stock del CD:** se descuenta al despachar el remito, en una transacción.
- **Ingreso al local:** cuando se termina de verificar el remito completo, solo
  de los bultos con `habilita_venta()` (el PDF del grupo decía bulto por bulto;
  se cambia en un método de `recepcion_service.py`).
- **Bulto rechazado:** merma, no vuelve al CD (provisorio).
- **Remito:** ABIERTO, CERRADO, EN_TRANSITO, VERIFICADO, VERIFICADO_CON_RECHAZOS
  (constantes: su ciclo es lineal).
- **Logística:** no se manda más de lo pedido, precinto único, un remito por
  destino en cada orden, la orden sale del CD activo.
- **Baja lógica** con reactivación; la eliminación física quedó pendiente
  (solo si nunca se usó).

## Reportes (`GET /reportes/...`)
`ventas` (período, local, medio de pago), `productos-mas-vendidos` (con margen),
`existencias` (bajo mínimo y valorización), `mermas` (bultos rechazados),
`tiempos-transito` (CD → local según el historial).

## Cómo se levanta (desde `tp-dao-tema3/`)
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m backend.datos.seed --reiniciar       # BORRA la base local y carga datos de ejemplo
.venv\Scripts\python -m uvicorn backend.main:app --reload    # http://127.0.0.1:8000/docs
cd frontend; npm install; npm run dev                        # http://localhost:5173
.venv\Scripts\python -m pytest
```
`TP_DAO_DB` permite apuntar a otra base.

## Plan vigente
**`docs/plan_mejoras.md`**: los pasos con casillas, cómo trabajamos y las decisiones tomadas. Si la conversación se corta, retomar desde ahí (primer paso sin tachar).

## Pendiente
- Preguntas al profe: Flask + Jinja2 (enunciado) vs FastAPI + React; ingreso
  bulto por bulto o por remito; rechazado merma o vuelve al CD; reserva de stock
  al preparar; control de cantidades en la recepción; DAO como patrón;
  proveedores N:M vs uno por producto; usuarios.
- Próximos pasos (al 26/10 están hechos los pasos 1 a 7 y el 1e del plan, los
  5 a 7 y el 1e sin commitear): repensar las devoluciones, 1d (arreglos del
  recorrido), compras a proveedores con factura en PDF (8), reportes nuevos por
  perfil y exportables (9; los gráficos ya están), envíos demorados y reposición
  sugerida (10), limpieza (11). También: control de cantidades en la recepción y
  eliminación física de maestros. Ver `docs/plan_mejoras.md`.
- Ramas: `feature/usuarios` (pasos 2 y 3, para el pull request a `main`) y
  `feature/productos` (pasos 4 a 7, sale de `feature/usuarios`).

## Cómo trabajamos los pasos
- Cuando te diga lo que quiero hacer, no empieces a codear. Primero mirá el código y después usá la herramienta AskUserQuestion para darme las opciones de cada decisión: hasta 4 por pregunta, la recomendada primero con "(Recomendada)", y una línea de qué implica cada una. Si una opción suma un patrón de diseño, decilo.
- Si hay varias decisiones, mandalas en el mismo formulario (hasta 4 preguntas), o de a una si una depende de la otra.
- Cuando elija, explicame en una tabla corta por qué esa opción y qué se descarta de las otras, para defenderlo en el oral. Después codeá.
- Si una decisión ya está en "Decisiones tomadas", no la preguntes.
- Respetá las capas: api → servicios → dominio + persistencia. El dominio no importa nada de las otras capas. Cada archivo nuevo arranca con el comentario de qué va y qué no va en él.
- Nada de nombres con guion bajo inicial, salvo el atributo que respalda una @property.
- Validaciones en tres lugares: formato en el dominio, lo que consulta la base en el service, y UNIQUE, CHECK, claves foráneas y triggers en la base.
- Si cambiás esquema.sql, agregá la migración en conexion.py para no romper bases existentes.
- Todo cambio lleva tests. Al terminar corré .venv\Scripts\python -m pytest y mostrame el resultado.
- Al cerrar el paso: tabla con archivo, qué cambió y por qué; qué tengo que probar a mano; un mensaje de commit sugerido; y agregá a "Decisiones tomadas" lo que elegí. No avances al paso siguiente.

## Decisiones tomadas
- Tres perfiles: Administrador (sin ubicación), Centro de Distribución (hay uno solo) y Local (puede haber muchos). (23/10: antes era "sin administrador".)
- Los maestros y los usuarios los maneja el Administrador; el CD solo opera.
- Se entra con usuario y contraseña (23/10).
- El local de ventas, pedidos, recepción y reportes sale del usuario logueado, nunca del formulario.

### Paso 3: usuarios y perfiles (decidido el 20/10)
- Login con usuario y contraseña (`POST /auth/login` → token en `Authorization: Bearer`). Todas las rutas obtienen el usuario por una sola dependencia, `usuario_actual` (en `api/dependencias.py`). Hecho el 23/10.
- `Usuario` abstracto con `UsuarioAdministrador` (sin ubicación), `UsuarioCD` y `UsuarioSucursal`, en una sola tabla con columna `perfil` y la fábrica `crear_usuario` (como `Ubicacion`). Cada perfil responde sus capacidades; nada de `if perfil ==`.
- El perfil tiene que coincidir con el tipo de ubicación (CD con el CD, local con una sucursal), validado en el dominio (`validar_ubicacion`), el service y un trigger.
- Pertenencia: el administrador y el CD ven toda la red; el local, solo lo suyo (se controla en la api con `exigir_que_sea_suyo`). Productos, categorías y ubicaciones los consultan todos; proveedores, el administrador y el CD.
- Baja lógica de usuarios con reactivar.
- `usuario_id` en ventas, devoluciones, remitos, movimientos de stock e historial del bulto. En el historial lo graba el DAO con el usuario que le pasa el service (el patrón State no se toca).
- Tests de rutas con `TestClient`, agregando `httpx` como dependencia de desarrollo.
- El perfil se llama `SUCURSAL` en el código (igual que el tipo de ubicación; en pantalla puede decir "Local"). El trigger exige perfil = tipo de la ubicación.
- `usuario_id` también en pedidos (quién pidió) y órdenes (quién consolidó), además de la lista anterior. En remitos, quién lo armó.
- Permisos: una dependencia por ruta que exige la capacidad (ej. `Depends(requiere("puede_vender"))`), no por router ni con decorador propio.
- Acceso a algo de otro local: 403 con mensaje claro ("Ese remito no es de tu local"), no 404.
- El perfil y la ubicación de un usuario no se modifican (igual que el tipo de una ubicación).
- Autenticación: contraseña con `hashlib.pbkdf2_hmac` y sal (iteraciones en `config.py`, menos en los tests); token opaco con `secrets.token_urlsafe`, guardando su hash y con vencimiento; login con JSON (no formulario, para no sumar `python-multipart`); `backend.datos.crear_admin` para el primer administrador. Seed: `admin`, `cd.central`, `centro`, `norte`, `sur`, contraseña `tpdao2026`.

### Paso 3 del plan: front por perfil (decidido el 23/10)
- Pantalla de login propia; el token en `sessionStorage`, manejado solo por `api.js`; un 401 con sesión abierta vuelve al login.
- El menú se arma con las `capacidades` de `/auth/yo` (cada pantalla dice qué capacidad requiere); nada de `if perfil ==` en el front.
- El local no se elige en el front: lo pone el back. Pantalla de Usuarios para el administrador.

### Paso 4 del plan: reglas del producto y filtros (decidido el 23/10)
- Dos productos activos no se llaman igual (nombre normalizado; índice único parcial). Uno de baja libera el nombre.
- Un producto con stock no se da de baja (dominio con el dato, service que cuenta, trigger en la base).
- `GET /productos` filtra en el back con `FiltroProductos` (dominio): texto, categoría, proveedor (solo quien ve proveedores) y rango de precio.

### Paso 6 del plan: bandeja de tareas y llegada estimada (decidido el 23/10)
- `GET /tareas` arma los pendientes según las capacidades (CD prepara; local recibe, verifica y repone). "Pedir" abre el pedido precargado hasta el mínimo; también desde Stock.
- Transporte: solo la llegada estimada (día y hora), obligatoria al despachar (dominio, trigger). `Remito.esta_demorado()`.

### Paso 1e del plan: arreglos de la prueba del 26/10 (decidido el 26/10)
- Capacidad `ve_ventas` (admin y local sí, CD no): rutas de ventas, caja, comprobantes y reportes de ventas/más vendidos; el front esconde lo mismo.
- Remito en PDF (`GET /remitos/{id}/remito.pdf`) con el mismo Template Method: `RemitoDocumento` y los ganchos `columnas()` y `etiqueta_responsable()`. Solo despachado.
- Proveedores opcionales (uno o varios) al crear el producto, en la misma transacción.
- Gráficos de los reportes con Recharts (`componentes/Graficos.jsx`): barras de una serie, rojo para negativos, sin gráfico si hay una sola barra.
- Efectivo solo números; el comprobante no muestra vuelto; mensaje claro al devolver de más.
- Pendiente: repensar las devoluciones.

### Paso 5 del plan: comprobante y nota de crédito en PDF (decidido el 23/10)
- PDF en el back con fpdf2; lo descarga quien puede ver la venta.
- **Template Method** (`dominio/documentos.py`): `DocumentoComercial.armar()` fija el orden; `ComprobanteVenta` y `NotaCredito` completan los pasos. El dibujo del PDF (`servicios/documentos_pdf.py`) no sabe qué documento es.
- Nota de crédito correlativa por local (`nro_nota_credito`, trigger de unicidad, migración). Datos del comercio en `config.py`; quién atendió, del `usuario_id`.
