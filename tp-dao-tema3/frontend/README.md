# Frontend

React + Vite, en JavaScript. Cómo levantarlo: ver el README de `tp-dao-tema3/`.

## Organización

```
frontend/
├── vite.config.js      → proxy: /api/... se reenvía al backend (sin CORS)
└── src/
    ├── api.js          → único lugar que habla con el backend (fetch + errores)
    ├── App.jsx         → encabezado y pestañas
    ├── estilos.css     → estilos de todas las pantallas
    ├── formato.js      → cómo se muestran montos y fechas
    ├── componentes/    → piezas compartidas (avisos, líneas producto + cantidad, estados, catálogos)
    └── pantallas/      → Operación (Stock, Logística, Ventas, Reportes) y Maestros
```

## Decisiones

- **Proxy de Vite en vez de CORS:** el front le pide todo a `/api/...` en su
  propio puerto y Vite lo reenvía a FastAPI. Para el navegador es el mismo
  origen, así que no hay que configurar CORS en el backend.
- **Sin validaciones en el front (por ahora):** las reglas de negocio las
  valida el backend y el front muestra el código HTTP y el mensaje exacto.
  Así se ve cada regla funcionando. Más adelante se pueden sumar validaciones
  en el front como mejora de usabilidad.
- **Sin router:** son pocas pantallas, se navega con el estado de React.
- Para apuntar a otro backend: `BACKEND_URL=http://host:puerto npm run dev`.
