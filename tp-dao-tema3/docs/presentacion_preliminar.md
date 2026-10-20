# Presentación de la entrega preliminar

Guía para mostrarle el TP al profe (10 a 15 minutos), las preguntas para
hacerle y lo que conviene profundizar después. Lo que se evalúa según la
consigna: **el ciclo de vida del bulto y sus estados (críticamente, en el
modelo)**, al menos **2 patrones** y al menos **4 reportes no triviales**.

## Antes de la clase

1. `.venv\Scripts\python -m backend.datos.seed --reiniciar` (borra la base local y carga el escenario de ejemplo).
2. Levantar back (`.venv\Scripts\python -m uvicorn backend.main:app --reload`) y front (`cd frontend` → `npm run dev`).
3. Tener abierto http://localhost:5173 y, como plan B, Swagger en http://127.0.0.1:8000/docs.
4. Repartir las partes: cada integrante presenta una y todos tienen que poder explicar State y Strategy (ver `guia_oral.md`).

## Guion

| # | Qué mostrar | Tiempo | Qué decir |
|---|---|---|---|
| 1 | Pantalla de Inicio | 30 s | Un comercio con locales que reciben mercadería de un CD en bultos precintados; solo se vende lo verificado. |
| 2 | Arquitectura | 1 min | Capas `api → servicios → dominio + persistencia`. El dominio no conoce la base ni la web: las reglas se prueban solas. |
| 3 | **Logística en vivo** | 4-5 min | Pedido → orden → remito → bultos → precintar → despachar → recibir → verificar. Verificar un bulto con el precinto correcto y otro con un número equivocado: mostrar el historial del rechazado y que el stock del local sube solo con el verificado. |
| 4 | Patrón State en el código | 2 min | `backend/dominio/estados_bulto.py`: el bulto delega en su estado y cada estado permite solo lo suyo. Mostrar el error al despachar un bulto sin precintar. |
| 5 | Ventas | 2 min | Vender lo mismo en efectivo y en crédito y comparar totales (Strategy: la venta no sabe con qué le pagan). Hacer una devolución. |
| 6 | Reportes | 2 min | Mermas (el bulto rechazado), más vendidos (el yogur en promo da margen negativo) y existencias bajo mínimo. |
| 7 | Validaciones | 1 min | `tests/test_validaciones_consigna.py` (un test por validación de la consigna) y correr `pytest`. |

Consejos: mostrar funcionando y abrir el código solo en los patrones; cerrar
con "estas son las decisiones provisorias, ¿qué opina?".

## Preguntas para el profe (por impacto)

1. **Tecnología:** el enunciado menciona Flask + Jinja2 y usamos FastAPI + React. ¿Está bien?
2. **Ingreso al local:** el stock entra cuando se termina de verificar el remito completo (solo los bultos verificados). ¿O bulto por bulto?
3. **Bulto rechazado:** ¿merma (como está) o vuelve al CD? ¿Bloquea el remito entero?
4. **Descuento en el CD:** hoy al despachar. ¿Espera una reserva al preparar el bulto?
5. **Recepción:** hoy se verifica el precinto. ¿Espera también control de cantidades contra el remito?
6. **Patrones:** ¿cuentan State y Strategy? ¿El DAO suma o es parte de la arquitectura?
7. **Proveedores:** el modelo del grupo decía uno por producto; implementamos muchos a muchos. ¿Le parece bien?
8. **Reportes:** ¿los 5 le parecen no triviales? ¿Espera gráficos o exportar?
9. **Usuarios:** ¿hace falta registrar quién hizo cada acción?

## Dónde nos pueden corregir

- No hay usuarios: el historial dice qué y cuándo, no quién.
- El Remito usa constantes, no State. Respuesta: su ciclo es lineal y no cambia de comportamiento por estado; State ahí sería sobrediseño.
- No se reserva stock: se pueden preparar bultos sin stock y falla recién al despachar (sin dejar nada a medias).
- Ningún proceso opcional todavía.
- No hay diagramas, y el ciclo de vida se evalúa "en el modelo".

## Qué profundizar después (por prioridad)

1. **Diagramas de clases y de estados del bulto** (lo que más pesa en la evaluación).
2. Ajustar según lo que responda el profe.
3. **Un proceso opcional bien hecho:** órdenes de compra sugeridas por faltantes (usa stock mínimo, el reporte de existencias y los proveedores por producto). Segunda opción: inventario físico y conciliación (con movimientos AJUSTE).
4. Control de cantidades en la recepción, si lo pide.
5. Registrar el usuario en historial, ventas y movimientos.
6. Menores: Decimal en los precios de Producto, gráficos en reportes, eliminación física de maestros.
