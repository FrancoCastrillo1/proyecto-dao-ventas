# Presentación de la entrega preliminar (29/10)

Guía para mostrarle el TP al profe (10 a 15 minutos), las preguntas para
hacerle y lo que conviene profundizar después. Lo que se evalúa según la
consigna: **el ciclo de vida del bulto y sus estados (críticamente, en el
modelo)**, al menos **2 patrones** y al menos **4 reportes no triviales**.

## Antes de la clase

1. `.venv\Scripts\python -m pip install -r requirements.txt` (se sumaron `httpx` y `fpdf2`).
2. `.venv\Scripts\python -m backend.datos.seed --reiniciar` (borra la base local y carga el escenario de ejemplo).
3. Levantar back (`.venv\Scripts\python -m uvicorn backend.main:app --reload`) y front (`cd frontend` → `npm run dev`).
4. Tener abierto http://localhost:5173, [diagramas.md](diagramas.md) (o las imágenes de `docs/img/`) y, como plan B, Swagger en http://127.0.0.1:8000/docs.
5. Usuarios de prueba (contraseña de todos `tpdao2026`): `admin`, `cd.central`, `centro`, `norte`, `sur`.
6. Repartir las partes: cada integrante presenta una y todos tienen que poder explicar los tres patrones (ver [guia_oral.md](guia_oral.md) y [patrones.md](patrones.md)).

## Guion (10 a 15 minutos)

| # | Qué mostrar | Tiempo | Qué decir |
|---|---|---|---|
| 1 | Pantalla de entrada y los tres perfiles | 1 min | Un comercio con locales que se abastecen de un CD en bultos precintados; solo se vende lo verificado. Administrador, CD y local: cada uno ve y hace solo lo suyo. |
| 2 | **Diagrama de estados del bulto** y de clases de logística | 2 min | El ciclo de vida en el modelo: patrón State, cada estado permite solo su paso, historial inmutable con quién hizo cada cambio. |
| 3 | **Demo en vivo** | 5 min | La de [guion_demo.md](guion_demo.md): recibir y verificar, pedir, preparar y despachar con llegada estimada, un bulto rechazado, y una venta con su PDF. |
| 4 | Patrones en el código | 2 min | `estados_bulto.py` (State), `medios_pago.py` (Strategy), `documentos.py` (Template Method). Tabla de [patrones.md](patrones.md). |
| 5 | Reportes | 1-2 min | Mermas (el bulto rechazado), más vendidos (el yogur en promo da margen negativo), existencias bajo mínimo y tiempos de tránsito. |
| 6 | Arquitectura y validaciones | 1 min | Capas `api → servicios → dominio + persistencia`; cada validación en tres lugares. `tests/test_validaciones_consigna.py` y `pytest` (754 tests). |

Consejos: mostrar funcionando y abrir el código solo en los patrones; cerrar
con "estas son las decisiones provisorias, ¿qué opina?".

## Preguntas para el profe (por impacto)

1. **Tecnología:** el enunciado menciona Flask + Jinja2 y usamos FastAPI + React. ¿Está bien?
2. **Ingreso al local:** el stock entra cuando se termina de verificar el remito completo (solo los bultos verificados). ¿O bulto por bulto?
3. **Bulto rechazado:** ¿merma (como está) o vuelve al CD? ¿Bloquea el remito entero?
4. **Descuento en el CD:** hoy al despachar. ¿Espera una reserva al preparar el bulto?
5. **Recepción:** hoy se verifica el precinto. ¿Espera también control de cantidades contra el remito?
6. **Patrones:** ¿cuentan State, Strategy y Template Method? ¿El DAO y las fábricas suman o son parte de la arquitectura?
7. **Proveedores:** el modelo del grupo decía uno por producto; implementamos muchos a muchos. ¿Le parece bien?
8. **Reportes:** ¿los 5 le parecen no triviales? ¿Espera gráficos o exportar?
9. **Perfiles:** sumamos un administrador aparte del CD. ¿Le parece bien el reparto?

## Dónde nos pueden corregir

- El Remito usa constantes, no State. Respuesta: su ciclo es lineal y no cambia de comportamiento por estado; State ahí sería sobrediseño.
- No se reserva stock: se pueden preparar bultos sin stock y falla recién al despachar (sin dejar nada a medias).
- Las compras al CD no se asocian a un proveedor (es el paso 8 del plan).
- Los reportes son tablas, sin gráficos ni exportación (paso 9).

## Qué profundizar después (por prioridad)

1. Ajustar según lo que responda el profe.
2. Arreglos de usabilidad del recorrido (paso 1d: errores sin el código y al lado de cada campo, etc.).
3. **Compras a proveedores** con la factura en PDF (paso 8).
4. **Reportes por perfil con gráficos** (paso 9): al CD, los de logística (locales que más devuelven o rechazan).
5. **Envíos demorados y reposición sugerida** (paso 10; la llegada estimada y "Pedir" ya están).
6. Limpieza: `Decimal` en los precios de Producto y sin nombres con guion bajo inicial (paso 11).
