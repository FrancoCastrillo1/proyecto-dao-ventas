# Guía para el oral: State, Strategy y las decisiones del TP

Cada integrante tiene que poder explicar los dos patrones y defender las
decisiones de diseño. Esta guía arma la explicación en el orden en que
conviene contarla: **qué problema hay → cómo lo resuelve el patrón → dónde
está en el código → qué preguntas pueden venir**.

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

## 3. Otras decisiones que conviene saber defender

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

## 4. Para practicar antes del oral
1. Correr `.venv\Scripts\python -m backend.datos.seed --reiniciar` y levantar
   back y front.
2. En **Logística**, abrir el remito de la Sucursal Sur (en tránsito):
   recibir el bulto y verificarlo con el precinto correcto. Ver cómo el
   historial suma los registros y el stock del local aumenta.
3. Intentar verificar con otro número de precinto en un remito nuevo y ver
   el rechazo en el reporte de **Mermas**.
4. En **Ventas**, vender lo mismo con efectivo y con crédito y comparar los
   totales: es la Strategy funcionando.
5. Abrir `estados_bulto.py` y `medios_pago.py` y explicarlos en voz alta
   con la tabla "Pieza del patrón → En el TP".
