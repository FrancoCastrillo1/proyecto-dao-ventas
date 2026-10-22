# Recorrido del front: checklist de prueba

Para probar la app en el navegador, pantalla por pantalla, con los datos del seed.
Cada ítem tiene dos partes: **Hacé** (lo que tocás) y **Debería** (lo que tenés
que ver). Si lo que ves no coincide, anotá el número del ítem.

Andá en orden: algunos pasos usan lo que creaste en uno anterior.

## Antes de empezar

1. Desde `tp-dao-tema3`: `.venv\Scripts\python -m backend.datos.seed --reiniciar` (**borra la base local** y carga el escenario).
2. Terminal 1: `.venv\Scripts\python -m uvicorn backend.main:app --reload`
3. Terminal 2: `cd frontend` → `npm run dev` → abrir http://localhost:5173

**Qué trae el seed:**
- 10 productos y 3 proveedores.
- *CD Central* y 3 locales: *Sucursal Centro*, *Sucursal Norte* y *Sucursal Sur*.
- 300 unidades de cada producto en el CD.
- Tres envíos: Centro entregado, Norte entregado con un bulto rechazado, y Sur **en camino** (precinto `PS-001`).
- 8 ventas y 2 devoluciones.

**Cómo está armada la pantalla:**
- A la izquierda está el menú. "Operación" es el día a día; "Datos" son los maestros.
- Arriba a la derecha de cada pantalla está el botón de lo principal que se hace ahí (`+ Nuevo…`).
- Crear, editar o ver el detalle de algo abre un **panel a la derecha**. Se cierra con la ×, con Escape o tocando afuera.
- Los mensajes de "✓ Listo" o "⚠ …" aparecen **arriba al centro**.

---

## 1. Inicio

- [ CHECK] **1.1 Hacé:** abrí la app.
  **Debería:** verse 4 tarjetas con números (ventas de hoy, pedidos sin preparar, envíos en camino, faltantes para reponer) y abajo 4 accesos rápidos.
   (Mejorar el front los titulos se ven re chiquitos)
- [ check] **1.2 Hacé:** tocá cada tarjeta y cada acceso rápido.
  **Debería:** llevarte a la pantalla de lo que dice (Vender, Envíos, Stock, Reportes).
- [CHECK ] **1.3 Hacé:** apagá el backend y recargá la página.
  **Debería:** aparecer "No hay conexión con el sistema", con el comando para levantarlo.

## 2. Locales y CD (Datos → Locales y CD)

- [ CHECK] **2.1 Hacé:** entrá a la pantalla.
  **Debería:** verse *CD Central* con la etiqueta "Despacha", y los 3 locales con "Vende" y "Recibe". (esto igual hay que cambiarlo porque tendriamos que manejar los perfiles de sucursales y de cd)
- [check ] **2.2 Hacé:** tocá "Locales" y después "CD" en el filtro de arriba.
  **Debería:** la lista muestra solo ese tipo.
- [ CHECK ] **2.3 Hacé:** "+ Nueva ubicación", elegí la tarjeta **Centro de Distribución**, nombre "CD Sur", y Crear.
  **Debería:** salir un error que diga que ya existe un Centro de Distribución activo. El panel queda abierto con lo que escribiste. (si vamos a tener solo 1 centro de distribucion deberiamos ni dar la oportunidad de crearlo)
- [CHECK ] **2.4 Hacé:** "+ Nueva ubicación" → Local → "Sucursal Oeste", dirección "Oeste 10" → Crear.
  **Debería:** salir "✓ Listo: «Sucursal Oeste» creada", y aparece en la lista. ( que aparezca un boton de confirmar la creacion de la sucursal)
- [ FALLO ] **2.5 Hacé:** creá otra con el nombre "sucursal oeste".
  **Debería:** salir un error de nombre repetido (no importan las mayúsculas ni las tildes). (esto falla ya que yo cree chacabuco y local chacabuco y me dejo, habria que revvisar esto de ultima que puedan compartir nombre pero no direccion)
- [ CHECK ] **2.6 Hacé:** creá otra con el nombre "Sucursal Oest".
  **Debería:** aparecer dentro del panel el cartel amarillo "¿Es un duplicado?". "Cancelar" no guarda nada; "Guardar igual" la crea.
- [CHECK ] **2.7 Hacé:** tocá la fila de un local.
  **Debería:** abrirse el panel para editar el nombre y la dirección. El tipo **no** aparece, porque no se puede cambiar.
- [ CHECK] **2.8 Hacé:** en el panel de "Sucursal Oeste" tocá "Dar de baja" y confirmá.
  **Debería:** desaparecer de "Activas" y aparecer en "De baja" (el número del filtro cambia). Ahí, "Reactivar" la vuelve a "Activas".



  deberiamos hacer un perfil ADMINISTRADOR que permita hacer esto, crear lcoales, cd, dar de baja, editarlos etc hay que ver bien

## 3. Categorías y productos (Datos)

- [ check] **3.1 Hacé:** en Categorías, "+ Nueva categoría" → "lacteos" → Crear.
  **Debería:** salir un error de que ya existe (*Lácteos*), aunque no tenga tilde ni mayúscula. (si deja esta bien, pero aparece error 409, un usuario normal no va a entender que es error 409)
- [check ] **3.2 Hacé:** escribí "lim" en el buscador.
  **Debería:** quedar solo *Limpieza*.
- [ check] **3.3 Hacé:** en Productos, mirá la lista.
  **Debería:** verse los 10 del seed; *Yogur Bebible 1L (promo)* tiene la ganancia en rojo (se vende por debajo del costo).
- [check ] **3.4 Hacé:** elegí "Bebidas" en el desplegable de categorías y buscá "cola".
  **Debería:** quedar solo *Gaseosa Cola 2.25L*.
- [check ] **3.5 Hacé:** "+ Nuevo producto" con código `beb-001` y el resto completo → Crear producto.
  **Debería:** salir un error de código repetido (se guarda en mayúsculas, así que choca con BEB-001).
- [check ] **3.6 Hacé:** "+ Nuevo producto" con precio `-5`.
  **Debería:** salir "Revisá los datos: …" diciendo que el precio tiene que ser mayor a cero. (en el desplegable sale un cartel que dice mayor o IGUAL a 0 cuando pones los dos en 0 el de costo y precio de venta aparece una notificacion arriba que dicer MAYOR a 0, Deberiamos poner las notificaciones en el desplegable mayor a 0 )
- [ Check ] **3.7 Hacé:** "+ Nuevo producto" con todo vacío → Crear producto.
  **Debería:** salir un solo mensaje con lo que falta: "Categoría: es obligatorio · Precio de venta: es obligatorio · Costo: es obligatorio". (el mensaje deberia salir en cada lugar donde tengo que llenar)
- [Check] **3.8 Hacé:** tocá la fila de *Aceite de Girasol*.
  **Debería:** abrirse el panel sin el campo código (el código va en el subtítulo y no se cambia), y abajo "Quién lo vende" con *Mayorista Norte SA*.

## 4. Proveedores (Datos → Proveedores)

- [check ] **4.1 Hacé:** "+ Nuevo proveedor" con CUIT `20-12345678-5`. (funciona pero de vuelta, primero no explica q esta mal, y ademas tira el numero del codigo 400 que un usuario no sabe q es )
  **Debería:** salir un error de CUIT inválido (el dígito verificador no da). 
- [check ] **4.2 Hacé:** lo mismo con `20-12345678-6`. (funciona pero de vuelta,tira el numero del codigo 400 que un usuario no sabe q es)
  **Debería:** salir un error de que ya existe (es *Distribuidora Sur SA*).
- [check ] **4.3 Hacé:** creá uno con un CUIT válido nuevo, por ejemplo `20-30111222-0`.
  **Debería:** salir "Proveedor creado: ahora elegí qué productos vende". El panel **no se cierra**: queda abierto con la sección "Productos que vende (0)".
  (estaria bueno cuando sale el que productos vende, poder crear un producto desde ahi, asi no hay que crearlo previamente o crear el proovedor y despues crear el producto)
- [ check] **4.4 Hacé:** elegí un producto en el desplegable y tocá "Agregar".
  **Debería:** el producto pasa a la lista de abajo y **desaparece del desplegable**, así no se puede asignar dos veces.
- [check] **4.5 Hacé:** "Quitar" en ese producto.
  **Debería:** volver al desplegable.

## 5. Pedido de un local y preparación (Operación → Envíos a locales)

La pantalla es un tablero con 4 columnas, en el orden en que viaja la mercadería:
**Pedidos de locales → Armando en el CD → En camino → Entregados**.

- [check ] **5.1 Hacé:** entrá a la pantalla.
  **Debería:**
  - *Sucursal Sur* en "En camino";
  - *Centro* y *Norte* en "Entregados" (Norte con "⚠ 1 bulto rechazado");
  - la columna de pedidos vacía.
- [ check] **5.2 Hacé:** "+ Nuevo pedido", sin elegir local.
  **Debería:** el botón "Crear pedido" estar deshabilitado. (en el perfil del local se deberia de pedir)
- [check ] **5.3 Hacé:** elegí *Sucursal Norte*, *Lavandina 1L*, cantidad 10 → Crear pedido.
  **Debería:** salir "Pedido creado"; aparece una tarjeta en "Pedidos de locales" con "10 × Lavandina 1L". (cuando creamos el pedido en cantidad sale un uno y alguien podria no entender que la cantidad va ahi, segundo, deberiamos pedir confirmacion de la generacion del pedido y que se haga un detalle extraible a pdf)
- [ check] **5.4 Hacé:** tildá el pedido.
  **Debería:** aparecer el botón "Preparar 1 pedido →".
- [ check] **5.5 Hacé:** tocá "Preparar 1 pedido →".
  **Debería:** el pedido sale de la primera columna y aparece en "Armando en el CD" como "Sucursal Norte · 0 bultos · Armar bultos →".
  (Por detrás se creó la orden de reposición y un remito por local.)
  (funciona pero como vnego diciendo habria que ir manejando esto en perfiles diferentes)

## 6. Bultos con remito y precinto (Envíos, columna "Armando en el CD")

- [ check ] **6.1 Hacé:** tocá la tarjeta de *Sucursal Norte*.
  **Debería:** abrirse el remito, con una tabla "Lo que pidió el local": Lavandina, Pidió 10, En bultos 0, Falta 10. 
- [check ] **6.2 Hacé:** en "Armar un bulto" elegí Lavandina, cantidad 6 → Armar bulto.
  **Debería:**
  - salir "Bulto armado: ahora precintalo";
  - en la tabla, Falta queda en 4;
  - en "Bultos" aparece el bulto con sus pasos: **Preparado** marcado y Precintado → En camino → Recibido → Verificado por delante.
- [check ] **6.3 Hacé:** armá otro bulto con 6 Lavandinas.
  **Debería:** salir un error de que se pidieron 10 y se mandarían 12.
- [chejc ] **6.4 Hacé:** armá un bulto con un producto que no se pidió.
  **Debería:** salir un error de que ese producto no fue pedido. (no le veo mucho sentido, que directamente ni aparezca otro tipo de productos)
- [ check] **6.5 Hacé:** tocá "Cargar lo que falta" → Armar bulto.
  **Debería:** cargarse sola la línea "Lavandina, 4". Al armar, la columna Falta muestra ✓ y la sección "Armar un bulto" desaparece.
- [check ] **6.6 Hacé:** mirá el pie del panel.
  **Debería:** estar deshabilitado "Despachar →", con el texto "Precintá todos los bultos para poder despachar".
- [check] **6.7 Hacé:** en un bulto, precinto `PC-001` → Precintar.
  **Debería:** salir un error de que ese precinto ya se usó (es del seed).
- [ check] **6.8 Hacé:** precintá los dos bultos con `PN-100` y `PN-101`.
  **Debería:** cada bulto pasar a **Precintado** en sus pasos.
- [ check] **6.9 Hacé:** "Historial" en un bulto.
  **Debería:** verse "preparado → Precintado" con fecha y hora.

## 7. Despacho

- [check ] **7.1 Hacé:** antes de despachar, en Stock → *CD Central*, anotá cuántas *Lavandina 1L* hay.
  **Debería:** verse un número (llamalo X).
- [check ] **7.2 Hacé:** volvé al remito y tocá "Despachar →".
  **Debería:** aparecer "¿Despachar a Sucursal Norte?", con la lista "10 × Lavandina 1L" y "No se puede deshacer". "Cancelar" no hace nada.
- [check ] **7.3 Hacé:** confirmá "Despachar".
  **Debería:** salir "Despachado: el envío está en camino"; el panel se cierra y la tarjeta pasa a "En camino" con una barra de progreso en 0 de 2.
- [check] **7.4 Hacé:** mirá Stock → *CD Central*.
  **Debería:** haber X − 10 Lavandinas. En "Ver movimientos" aparece "Despacho a un local −6" y "−4".

## 8. Recepción verificando el precinto

- [ check] **8.1 Hacé:** abrí la tarjeta de *Sucursal Sur* en "En camino" (es la del seed).
  **Debería:** verse su bulto en **En camino**, con el botón "Marcar como recibido".
- [ check] **8.2 Hacé:** "Marcar como recibido".
  **Debería:** el bulto pasar a **Recibido** y aparecer "Número que se lee en el precinto" con "¿Llegó sano? Sí / No". **Ninguno viene elegido**, y "Verificar" está deshabilitado.
- [ check] **8.3 Hacé:** escribí `PS-001`, tocá "Sí" → Verificar → confirmá.
  **Debería:** el bulto quedar **Verificado** (todos los pasos con ✓); la tarjeta pasa a "Entregados" con "Todo llegó bien".
- [check ] **8.4 Hacé:** Stock → *Sucursal Sur*.
  **Debería:** haber 25 *Agua Mineral* y 40 *Leche Entera*, que llegaron en ese bulto.
- [ check] **8.5 Hacé:** en el envío de Norte del punto 7: recibí los 2 bultos. Verificá uno con `PN-100` y "Sí", y el otro con un número **equivocado** (por ejemplo `XXX`).
  **Debería:**
  - en el equivocado, la confirmación tiene el botón **rojo**;
  - después, el último paso muestra **✕ Rechazado**;
  - la tarjeta pasa a "Entregados" con "⚠ 1 bulto rechazado".
- [ check] **8.6 Hacé:** Stock → *Sucursal Norte* → Lavandina → "Ver movimientos".
  **Debería:** aparecer **solo** la recepción del bulto bueno (6 o 4). La del rechazado **no entró**. (solo aparece el que entro el que fue rechazado ni aparece)
- [check ] **8.7 Hacé:** Reportes → "⚠️ Mermas".
  **Debería:** aparecer el bulto rechazado en "Qué se perdió", con su valor.

## 9. Ventas, cobro, comprobante y devoluciones (Operación → Vender)

- [ ] **9.1 Hacé:** entrá a Vender y elegí *Sucursal Sur* arriba.
  **Debería:** verse los productos como tarjetas con precio y "Hay N". Los que no tienen stock aparecen apagados con "Sin stock" y no se pueden tocar.
- [ ] **9.2 Hacé:** tocá *Agua Mineral*.
  **Debería:** sumarse al ticket de la derecha con − 1 +, y "Elegí cómo paga".
- [ ] **9.3 Hacé:** tocá cada medio de pago.
  **Debería:** el total cambiar solo:
  - Efectivo: $ 1.020 (descuento 15 %);
  - Débito y Transferencia: $ 1.200;
  - Crédito: $ 1.320 (recargo 10 %).
- [ ] **9.4 Hacé:** en Efectivo, "¿Con cuánto paga?" $ 5000.
  **Debería:** aparecer "Vuelto $ 3.980" en verde, y el botón decir "Cobrar $ 1.020,00".
- [ ] **9.5 Hacé:** cambiá a $ 500.
  **Debería:** aparecer "Con lo que entrega no alcanza" y el botón de cobrar quedar deshabilitado.
- [ ] **9.6 Hacé:** tocá + en el ticket hasta pasar lo que hay.
  **Debería:** la tarjeta decir "Hay N · M en el ticket"; al pasarte, abajo del producto aparece en rojo "Solo hay N" y el botón de cobrar se deshabilita.
- [ ] **9.7 Hacé:** dejá 1 agua, $ 5000 en efectivo → Cobrar.
  **Debería:**
  - abrirse el **comprobante** (número, producto, descuento, total y vuelto);
  - el ticket queda vacío;
  - la venta aparece arriba en la lista y la caja sube.
- [ ] **9.8 Hacé:** "Ver" en una venta → devolvé 1 unidad con motivo "Vencido".
  **Debería:** la venta mostrar lo devuelto y la caja bajar.
- [ ] **9.9 Hacé:** intentá devolver más de lo que se vendió.
  **Debería:** salir un error.

## 10. Stock (Operación → Stock)

- [ ] **10.1 Hacé:** cambiá de ubicación con los botones de arriba.
  **Debería:** que "+ Registrar compra" aparezca **solo** en *CD Central*. En un local aparece "A este local la mercadería le entra cuando verifica un envío del CD" con el enlace a Envíos.
- [ ] **10.2 Hacé:** en un local, tocá "Bajo el mínimo".
  **Debería:** quedar los productos marcados "Reponer". Si no hay, aparece "🎉 Nada bajo el mínimo".
- [ ] **10.3 Hacé:** en el CD, "+ Registrar compra" → un producto, 50 → Registrar compra.
  **Debería:** salir "Compra registrada: entraron 50 al CD Central"; el número sube y en "Ver movimientos" aparece "Compra a proveedor +50".

## 11. Reportes (Operación → Reportes)

- [ ] **11.1 Hacé:** recorré las 5 pestañas.
  **Debería:** cambiar el subtítulo con la pregunta que responde cada reporte, y verse tarjetas con totales y una tabla.
- [ ] **11.2 Hacé:** en "💰 Ventas", cambiá "Ver por" entre Día, Mes y Todo junto.
  **Debería:** la tabla actualizarse sola (no hay botón Consultar).
- [ ] **11.3 Hacé:** poné una fecha "Desde" de mañana.
  **Debería:** aparecer "No hay datos para estos filtros" y el botón "Limpiar filtros".
- [ ] **11.4 Hacé:** "🏆 Más vendidos".
  **Debería:** verse una barrita por producto, proporcional a las unidades; el yogur tiene la ganancia en rojo.
- [ ] **11.5 Hacé:** "📦 Existencias" con "Solo lo que falta reponer".
  **Debería:** aparecer los faltantes de los locales, con la columna "Falta".

---

## Problemas de usabilidad detectados (pasos 1, 1b y 1c)

Gravedad: **Alta** = puede hacer perder datos o dejar algo mal sin querer; **Media** = confunde o hace perder tiempo; **Baja** = detalle.

| # | Pantalla | Problema | Gravedad | Estado |
|---|---|---|---|---|
| 1 | Envíos | Al verificar con el precinto vacío, el bulto quedaba Rechazado sin vuelta atrás ("intacto" venía tildado) | Alta | Arreglado (1b) |
| 2 | Envíos | Despachar no pedía confirmación, y saca el stock del CD | Alta | Arreglado (1b) |
| 3 | Todas | Los avisos salían arriba de todo y no se veían si la acción estaba abajo | Alta | Arreglado (1b): flotantes |
| 4 | Envíos | Si una acción fallaba, se borraba lo cargado | Media | Arreglado (1b) |
| 5 | Envíos | Al armar un bulto no se veía cuánto pidió el local ni cuánto falta | Media | Arreglado (1b) + "Cargar lo que falta" (1c) |
| 6 | Vender | No se veía el total antes de vender | Media | Arreglado (1b): cotización en vivo |
| 7 | Vender y pedidos | No se veía el stock al elegir el producto | Media | Arreglado en Vender; en pedidos, pendiente |
| 8 | Envíos y Vender | Hay que elegir el local a mano y cualquiera puede hacer todo | Media | Pendiente: paso 2 (usuarios) |
| 9 | Todas | Mientras cargaba, las tablas decían "No hay…" | Media | Arreglado (1b) |
| 10 | Envíos, Stock, Maestros | Los paneles se abrían abajo de todo y "Editar" llenaba un formulario arriba | Media | Arreglado (1c): panel lateral |
| 11 | Envíos | Remitos y órdenes en listas que crecían sin fin | Media | Arreglado (1c): tablero por etapas |
| 12 | Maestros | "Dar de baja" no pedía confirmación | Baja | Arreglado (1b) |
| 13 | Stock | Tipos de movimiento en mayúsculas técnicas | Baja | Arreglado (1b) |
| 14 | Todas | Cada pantalla tenía un recuadro de instrucciones: la interfaz no se explicaba sola | Media | Arreglado (1c): rediseño, sin instrucciones |
| 15 | Todas | Después de cada acción, al recargar la lista se borraba el "✓ Listo" | Media | Arreglado (1c) |
| 16 | Todas | El aviso abajo a la derecha tapaba los botones del panel lateral | Baja | Arreglado (1c): arriba al centro |
