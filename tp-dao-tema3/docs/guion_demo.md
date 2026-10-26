# Guion de la demo (5 minutos)

Un recorrido en vivo que muestra el circuito completo con los tres perfiles,
un bulto **rechazado** y una venta. Está armado sobre el estado exacto del
seed, así que hay que arrancar con la base recién cargada.

## Antes de empezar (5 minutos antes)

1. `.venv\Scripts\python -m backend.datos.seed --reiniciar` (borra la base local y carga el escenario).
2. Terminal 1: `.venv\Scripts\python -m uvicorn backend.main:app --reload`
3. Terminal 2: `cd frontend` → `npm run dev` → abrir http://localhost:5173
4. Tener a mano: contraseña de todos `tpdao2026`; [diagramas.md](diagramas.md) abierto en otra pestaña (o las imágenes de `docs/img/`).
5. Plan B si falla el front: http://127.0.0.1:8000/docs (botón **Authorize** con el token de `POST /auth/login`).

## El recorrido

| Min | Quién | Qué hacer | Qué decir |
|---|---|---|---|
| 0:00 | — | Mostrar la pantalla de **Entrar** | "Un comercio con un Centro de Distribución que abastece a sus locales. Hay tres perfiles: administrador, CD y local. Cada uno ve solo lo suyo." |
| 0:20 | `sur` | Entrar. Mostrar **Para hacer**: "Recibir el envío #3" y "Pedir N productos bajo el mínimo" | "La bandeja la arma el back según lo que puede hacer el usuario: es polimorfismo, no hay un `if perfil`." |
| 0:40 | `sur` | Tocar **Recibir →**, abrir el envío, **Marcar como recibido**, escribir `PS-001`, **Sí**, **Verificar** | "Esto es el patrón State: el bulto pasa por Preparado, Precintado, En tránsito, Recibido y Verificado. Cada estado permite solo su paso; el resto tira error. Recién ahora la mercadería entra al stock vendible." Mostrar los pasos dibujados y el **Historial**. |
| 1:30 | `sur` | Ir a Inicio → **Pedir →** (sale ya cargado) → **Crear pedido**. Salir | "Lo que falta para llegar al mínimo se precarga solo." |
| 1:50 | `cd.central` | Entrar. **Preparar →** desde la bandeja → **Preparar 1 pedido** → abrir el remito de Sur → **Cargar lo que falta** → **Armar bulto** → precinto `PS-DEMO` → **Precintar** | "El CD consolida los pedidos en una orden y arma un remito por local. No puede mandar más de lo pedido y el precinto no se repite." |
| 2:40 | `cd.central` | Mostrar **Llegada estimada** (mañana 12:00) → **Despachar** → confirmar. Salir | "Al despachar sale el stock del CD, todo en una transacción. El CD dice cuándo llega; si se pasa, el envío figura Demorado." |
| 3:00 | `sur` | Entrar → Envíos → abrir el envío nuevo → recibir → escribir **`XXX`** (número equivocado) → **Sí** → Verificar → confirmar | "El número no coincide con el que puso el CD: el bulto queda **Rechazado** y su mercadería no entra al stock. Es merma." Mostrar ✕ Rechazado. |
| 3:40 | `sur` | **Vender**: tocar 2 productos, elegir **Efectivo** y después **Crédito** | "Patrón Strategy: cada medio de pago calcula su total (−15 % efectivo, +10 % crédito). La venta no sabe con qué le pagan; el total lo calcula el back." |
| 4:10 | `sur` | **Cobrar** → **⬇ Descargar PDF** y abrirlo | "Patrón Template Method: el comprobante y la nota de crédito se arman con la misma plantilla y cada uno completa sus pasos." |
| 4:40 | `admin` | (Si queda tiempo) Reportes → **⚠️ Mermas** | "El bulto que rechazamos recién ya aparece con su valor perdido." |
| 5:00 | — | Cerrar | "Las 5 validaciones de la consigna están en tres lugares —dominio, service y base— y las prueba `tests/test_validaciones_consigna.py`. Son 754 tests." |

## Si preguntan

- **¿Dónde está el ciclo de vida del bulto en el modelo?** `backend/dominio/estados_bulto.py` y el diagrama de estados en [diagramas.md](diagramas.md).
- **¿Qué patrones usaron y por qué?** [patrones.md](patrones.md), con la tabla "qué problema resuelve / qué pasaba sin él".
- **¿Cómo saben quién hizo cada cosa?** Cada operación graba el usuario; el historial del bulto lo muestra (el DAO lo graba, el State no se tocó).
- **¿Qué pasa si fuerzan la api?** El back controla los permisos aunque el front esconda los botones: un local que pide algo de otro local recibe 403.
