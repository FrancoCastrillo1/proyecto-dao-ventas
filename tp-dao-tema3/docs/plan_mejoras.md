# Plan de mejoras – TP DAO Tema 3

Si la conversación con Claude se corta o se limpia, se retoma desde este archivo:
mirar el primer paso sin tachar, sus notas y las "Decisiones tomadas".

## Pasos

Del 1 al 7 son para la entrega del **29/10/2026**; del 8 al 11, para después.

- [x] ~~**1. Recorrido del front.** Sin cambiar código: checklist para probar la app en el navegador proceso por proceso con el seed cargado, y marcar los problemas de usabilidad que ya se ven en el código.~~
  - Hecho el 22/10: `docs/recorrido_front.md` (checklist por proceso y 15 problemas de usabilidad, 3 de gravedad alta). Los problemas que ningún paso resuelve quedan para sumar a un paso (ver la última columna de esa tabla).
- [x] ~~**1b. Arreglos de usabilidad.** Arreglar los problemas que encontró el recorrido del paso 1.~~
  - Hecho el 22/10 en la rama `feature/usabilidad`: 13 de los 15 problemas de `docs/recorrido_front.md`, más la cotización de la venta en el back (`POST /ventas/cotizar`). Quedan: elegir el local a mano (lo resuelven los pasos 2 y 3) y el stock disponible al hacer un pedido.
- [x] ~~**1c. Rediseño del front.** Que la interfaz se entienda sola, sin recuadros de instrucciones, y el checklist en formato "Hacé → Debería".~~
  - Hecho el 22/10 en la rama `feature/usabilidad`: menú lateral, panel lateral para crear/editar/ver, Inicio con indicadores, Vender como punto de venta, Envíos como tablero por etapas con los pasos del bulto dibujados, filtros que se aplican solos. Solo front (más los tests de la cotización del 1b). Probado de punta a punta en Chrome headless.
- [ ] **1d. Arreglos del recorrido de Geronimo** (probó del 1 al 8 el 23/10; las notas están en `docs/recorrido_front.md`). Lo que no resuelven los perfiles:
  - Errores: que no muestren el código (400, 409) y que digan qué está mal; los de formato, al lado de cada campo y no solo en el aviso de arriba.
  - Producto: el formulario permite 0 en precio y costo, pero el back exige mayor a 0 (que coincidan).
  - Ubicaciones: no ofrecer crear un CD si ya hay uno activo; ¿dirección única? (pueden repetir nombre parecido, no dirección).
  - Pedido: la cantidad no se entiende (falta etiqueta); confirmar antes de crear el pedido; detalle descargable en PDF (con el paso 5).
  - Bulto: al armarlo, ofrecer solo los productos que pidió el local.
  - Proveedor: crear un producto desde "Productos que vende".
  - Títulos más grandes en todo el front.
  - Notas de la prueba del paso 3 (23/10):
    - **CD:** no le sirven las ventas ni los reportes de ventas (solo envía y despacha). Que vea reportes de logística, por ejemplo los locales que más devuelven o rechazan mercadería. Se junta con el paso 9 (reportes por perfil).
    - **CD, compras:** al registrar una compra, poder adjuntar el PDF de la factura. Se junta con el paso 8 (compras a proveedores).
    - **Local, stock:** que "Reponer" sea un botón que abra el pedido al CD ya cargado con lo que falta (hasta el mínimo). Se junta con el paso 10 (reposición sugerida).
- [x] ~~**2. Usuarios y perfiles en el back.** Que el back separe las funciones de cada perfil y registre quién hizo cada operación.~~
  - Administrador (sin ubicación): locales, CD, productos, categorías, proveedores y usuarios; ve los reportes de toda la red. No opera.
  - Local: pedir reposición, ver sus pedidos y remitos, recibir y verificar los bultos de su local, vender, devolver, caja, ver su stock y el catálogo, reportes de su local.
  - CD: compras, consolidar pedidos, armar y precintar bultos, remitos, despachar, stock del CD, reportes de toda la red.
  - Opciones a dar: cómo modelar el perfil, cómo autenticar y guardar la sesión, y dónde controlar los permisos.
  - **Hecho el 23/10 en la rama `feature/usuarios` (681 tests).** Ojo: desde acá todas las rutas piden token, así que el front no anda hasta el paso 3.
    - [x] a) Dominio: `Usuario` abstracto con `UsuarioCD` y `UsuarioSucursal`, capacidades, `validar_ubicacion`, `puede_ver_ubicacion`, fábrica `crear_usuario`, baja y reactivación (commit `98be82d`).
    - [x] b) Tabla `usuarios`, triggers de perfil, `usuario_id` en las 7 tablas de operaciones, migración y `UsuarioDAO` (commit `a27e1c1`). Probado con la base real.
    - [x] a') Tercer perfil: `UsuarioAdministrador` sin ubicación; los maestros pasan del CD al administrador. La tabla `usuarios` se reconstruye (migración) para admitirlo y guardar la contraseña.
    - [x] c) `UsuarioService` y `AuthService` (PBKDF2 con sal, token con vencimiento, logout), dependencia `usuario_actual` y rutas `/auth` y `/usuarios`.
    - [x] d) Permisos en todas las rutas (`requiere(...)`), pertenencia (403 "Ese remito no es de tu local"), `usuario_id` grabado en cada operación y tests con un cliente de cada perfil.
    - [x] e) Seed con `admin`, `cd.central`, `centro`, `norte` y `sur` (contraseña `tpdao2026`), y `backend.datos.crear_admin` para el primer administrador de una base vacía.
- [x] ~~**3. Front por perfil.** Pantalla de login, y que cada perfil (administrador, CD, local) vea solo sus pantallas, sin elegir el local a mano.~~
  - Hecho el 23/10 en la rama `feature/usuarios`: login, menú por capacidades, Vender/Envíos/Stock/Reportes según el perfil, pantalla de Usuarios. Probado de punta a punta en Chrome con los tres perfiles (sección 0 de `docs/recorrido_front.md`).
- [ ] **4. Reglas del producto y filtros.** Restringir lo que se puede cargar como producto y buscar productos con filtros. Opciones: qué reglas (varias) y cómo filtrar.
- [ ] **5. Comprobante descargable** de cada venta y nota de crédito de cada devolución. Un local solo descarga los suyos. Opciones: formato y librería.
- [ ] **6. Bandeja de tareas y transporte.** Inicio muestra los pendientes de cada perfil y lleva a la pantalla donde se resuelve cada uno; el CD registra el transporte de cada remito al despacharlo. Opciones: qué tareas mostrar a cada perfil (varias) y qué datos del transporte guardar.
- [ ] **7. Cierre para el 29/10:** diagrama de clases, diagrama de estados del bulto, `docs/guia_oral.md` y `docs/presentacion_preliminar.md` actualizados con las decisiones nuevas, y README con los usuarios de prueba. Opciones: cómo armar los diagramas. Al final, correr todos los tests y levantar todo desde cero con el seed.
- [ ] **8. Compras a proveedores.** El CD registra compras y la mercadería entra a su stock; no se le compra a un proveedor un producto que no provee. Opciones: cómo modelar la compra y cómo actualizar el costo del producto.
- [ ] **9. Reportes nuevos con gráficos exportables**, y que cada perfil vea solo los suyos. Entre los nuevos, los locales que más devuelven mercadería. Opciones: qué reportes (varios), librería de gráficos y formato de exportación.
- [ ] **10. Envíos demorados y reposición sugerida:** el CD ve qué envíos vienen atrasados y el sistema le sugiere qué reponer a cada local.
- [ ] **11. Limpieza:** precios de Producto como `Decimal`, y ninguna función que arranque con guion bajo. Mostrar la lista de cambios antes de renombrar.

## Cómo trabajamos

- En cada paso, antes de codear, mirar el código y usar AskUserQuestion para dar las opciones de cada decisión: hasta 4 por pregunta, la recomendada primero con "(Recomendada)", y una línea de qué implica cada una. Si una opción suma un patrón de diseño, decirlo.
- Si un paso tiene varias decisiones, mandarlas juntas en el mismo formulario (hasta 4 preguntas), o de a una si una depende de otra.
- Cuando elija, explicar en una tabla corta por qué esa opción y qué se descarta de las otras. Después codear.
- No preguntar lo que ya está en "Decisiones tomadas".
- Capas: api → servicios → dominio + persistencia. El dominio no conoce a nadie. Cada archivo arranca con un comentario que dice qué va y qué no va en él.
- Nada de nombres con guion bajo inicial, salvo el atributo que respalda una @property.
- Validaciones en tres lugares: el formato en el dominio, lo que consulta la base en el service, y UNIQUE, CHECK, claves foráneas y triggers en la base.
- Si se cambia `esquema.sql`, agregar la migración en `conexion.py` para no romper bases existentes.
- Todo cambio lleva tests. Al terminar cada paso, correr `.venv\Scripts\python -m pytest` y mostrar el resultado.
- Al cerrar cada paso: tabla con archivo, qué cambió y por qué; qué probar a mano; y un mensaje de commit sugerido. Tachar el paso en este archivo, sumar a "Decisiones tomadas" lo elegido y frenar. No arrancar el paso siguiente hasta que diga "seguí".

## Decisiones tomadas

### Generales
- Tres perfiles: Administrador (sin ubicación), Centro de Distribución (hay uno solo) y Local (puede haber muchos). Decidido el 23/10; antes era "sin administrador".
- Se entra con usuario y contraseña (decidido el 23/10; antes era "se elige el perfil").
- Los maestros (productos, categorías, proveedores, locales) y los usuarios los maneja el Administrador. El CD solo opera.
- El local de las ventas, los pedidos, la recepción y los reportes sale del usuario logueado, nunca del formulario.
- Un usuario de local trabaja solo con su local.

### Paso 3: front por perfil (decidido el 23/10)
- **Entrada:** pantalla de login propia; sin sesión no se ve nada más. Si el back responde 401 con una sesión abierta (venció o la cerraron), el front vuelve solo al login y dice por qué.
- **Sesión:** el token se guarda en `sessionStorage` (sobrevive a recargar, se borra al cerrar la pestaña). Lo maneja solo `api.js`, que lo manda en `Authorization: Bearer` en cada pedido.
- **Menú:** cada pantalla dice qué capacidad necesita (`requiere`) y se muestran las que el usuario tiene, según `capacidades` de `/auth/yo`. Ningún `if perfil ==` en el front; el back igual controla todo (403).
- El local ya no se elige en Vender ni en el pedido: lo pone el back. Stock y Reportes muestran el selector de ubicación solo a quien ve toda la red.
- Pantalla de **Usuarios** para el administrador: alta (perfil, dónde trabaja, contraseña), nombre, cambio de contraseña, baja y reactivar. El CD se asigna solo (hay uno).

### Paso 1b: arreglos de usabilidad (decidido el 22/10)
- Acciones irreversibles (despachar, verificar, dar de baja): panel de confirmación dentro de la página con el resumen de lo que va a pasar (componente `Confirmacion`), no `confirm()` nativo.
- Avisos: flotantes, fijos abajo a la derecha (un solo cambio en `Aviso`); el de éxito se va solo, el de error queda.
- Total antes de vender: cotización en el back (`POST /ventas/cotizar`), que usa el mismo cálculo del dominio que la venta (Strategy) sin guardar nada. El front no repite la regla.
- Los arreglos van en la rama `feature/usabilidad`, separada de `feature/usuarios`.

### Paso 1c: rediseño del front (22/10, lo decidió Claude a pedido de Geronimo)
- La interfaz se explica sola: se sacaron los recuadros de "cómo se usa" de cada pantalla. En su lugar: el botón principal arriba a la derecha, estados vacíos que dicen qué hacer, botones deshabilitados hasta que el formulario está completo y textos en lenguaje común ("En camino", "Armando", "Reponer").
- Menú lateral con dos grupos: Operación (Inicio, Vender, Envíos, Stock, Reportes) y Datos (los maestros).
- Crear, editar y ver detalle en un **panel lateral** (`Cajon`), sin perder la lista de atrás. "Dar de baja" va dentro del panel; "Reactivar", en la pestaña "De baja".
- Logística como **tablero de 4 columnas** (Pedidos → Armando → En camino → Entregados). "Preparar" consolida la orden y arma un remito por local de una vez. Cada bulto muestra sus pasos (el patrón State a la vista) y solo el botón del paso que sigue.
- Vender como **punto de venta**: productos como tarjetas, ticket con − / +, medios de pago como botones y "Cobrar $ total".
- Filtros y búsqueda en el navegador sobre la lista completa (son pocos datos); los reportes se vuelven a consultar solos al cambiar un filtro.
- Avisos arriba al centro (abajo a la derecha tapaban el panel lateral). Recargar la lista después de una acción ya no borra el "✓ Listo".

### Paso 2: usuarios y perfiles (decidido el 20/10; administrador y login, el 23/10)
- **Modelo del perfil:** `Usuario` abstracto con `UsuarioAdministrador`, `UsuarioCD` y `UsuarioSucursal`, en una sola tabla con columna `perfil` y la fábrica `crear_usuario` (como `Ubicacion`). Cada perfil responde sus capacidades; nada de `if perfil ==`.
- El perfil se llama `SUCURSAL` en el código (igual que el tipo de ubicación; en pantalla dice "Local"). El perfil tiene que coincidir con el tipo de la ubicación: validado en el dominio (`validar_ubicacion`), el service y un trigger.
- El perfil y la ubicación de un usuario no se modifican. Baja lógica de usuarios con reactivar.
- **Administrador:** no pertenece a ninguna ubicación (`trabaja_en_una_ubicacion()` da False; CHECK en la base). Maneja maestros y usuarios y ve toda la red, pero no opera. No se puede dar de baja al último administrador activo.
- **Pertenencia:** el administrador y el CD ven toda la red (stock y reportes de cualquier ubicación); el local, solo lo suyo. Productos, categorías y ubicaciones los consultan todos; proveedores, el administrador y el CD (`puede_consultar_proveedores`).
- **Quién hizo cada operación:** `usuario_id` en pedidos (quién pidió), órdenes (quién consolidó), remitos (quién lo armó), historial del bulto, movimientos de stock, ventas y devoluciones. En el historial lo graba el DAO con el usuario que le pasa el service (el patrón State no se toca).
- **Dónde se controlan los permisos:** una dependencia de FastAPI por ruta que exige la capacidad (ej. `Depends(requiere("puede_vender"))`), en `api/dependencias.py`. La pertenencia también se controla en la api (`exigir_que_sea_suyo`), preguntándole al usuario `puede_ver_ubicacion()`: los services reciben solo el `usuario_id` para grabarlo. Algo de otro local responde 403 con mensaje claro.
- **Identificación:** login con usuario y contraseña (`POST /auth/login`), que devuelve un token; las rutas lo reciben en `Authorization: Bearer <token>`. Todas obtienen el usuario por una sola dependencia, `usuario_actual`. (El encabezado provisorio `X-Usuario` no se llegó a usar.)
- Tests de rutas con `TestClient`, agregando `httpx` como dependencia de desarrollo.
- **Autenticación:** contraseña con `hashlib.pbkdf2_hmac` (SHA-256) y sal al azar, guardada como `iteraciones$hash` (300.000 iteraciones en `config.py`, 1.000 en los tests); token opaco con `secrets.token_urlsafe` del que se guarda solo el hash, con vencimiento de 10 horas; login con JSON; un único mensaje "Usuario o contraseña incorrectos" para no revelar qué usuarios existen. Dar de baja o cambiar la contraseña cierra las sesiones del usuario.
- El local del pedido, la venta y la compra sale del usuario: si el formulario manda otro, se ignora. En listados y reportes, un local que pide otro local recibe 403.
- Usuarios de una base de antes del login quedan sin contraseña y no entran hasta que el administrador les ponga una.
