// Configuración de Vite. El proxy reenvía todo lo que empieza con /api al
// backend (FastAPI), sacándole el /api. Así el navegador cree que front y api
// están en el mismo origen y no hace falta configurar CORS en el backend.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: BACKEND,
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api/, ""),
      },
    },
  },
});
