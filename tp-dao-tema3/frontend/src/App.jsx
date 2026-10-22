// Estructura general del front: menú lateral a la izquierda y la pantalla
// elegida a la derecha. Se navega con estado de React (sin router): son pocas
// pantallas y no hace falta otra dependencia. Cada área tiene su color (tema-*).
import { useState } from "react";

import Categorias from "./pantallas/Categorias.jsx";
import Inicio from "./pantallas/Inicio.jsx";
import Logistica from "./pantallas/Logistica.jsx";
import Productos from "./pantallas/Productos.jsx";
import Proveedores from "./pantallas/Proveedores.jsx";
import Reportes from "./pantallas/Reportes.jsx";
import Stock from "./pantallas/Stock.jsx";
import Ubicaciones from "./pantallas/Ubicaciones.jsx";
import Ventas from "./pantallas/Ventas.jsx";

const GRUPOS = [
  {
    titulo: "Operación",
    pantallas: [
      { clave: "inicio", icono: "🏠", titulo: "Inicio", tema: "tema-lavanda", Pantalla: Inicio },
      { clave: "ventas", icono: "🛒", titulo: "Vender", tema: "tema-durazno", Pantalla: Ventas },
      { clave: "logistica", icono: "🚚", titulo: "Envíos a locales", tema: "tema-cielo", Pantalla: Logistica },
      { clave: "stock", icono: "📦", titulo: "Stock", tema: "tema-menta", Pantalla: Stock },
      { clave: "reportes", icono: "📊", titulo: "Reportes", tema: "tema-rosa", Pantalla: Reportes },
    ],
  },
  {
    titulo: "Datos",
    pantallas: [
      { clave: "productos", icono: "🧃", titulo: "Productos", tema: "tema-manteca", Pantalla: Productos },
      { clave: "categorias", icono: "🏷️", titulo: "Categorías", tema: "tema-manteca", Pantalla: Categorias },
      { clave: "proveedores", icono: "🤝", titulo: "Proveedores", tema: "tema-manteca", Pantalla: Proveedores },
      { clave: "ubicaciones", icono: "🏬", titulo: "Locales y CD", tema: "tema-manteca", Pantalla: Ubicaciones },
    ],
  },
];

const TODAS = GRUPOS.flatMap((g) => g.pantallas);

export default function App() {
  const [activa, setActiva] = useState("inicio");
  const { Pantalla, tema } = TODAS.find((p) => p.clave === activa);

  function irA(clave) {
    setActiva(clave);
    window.scrollTo({ top: 0 });
  }

  return (
    <div className="app">
      <nav className="lateral" aria-label="Secciones">
        <div className="marca">
          <span className="marca-logo">V</span>
          <div><strong>Ventas e Inventario</strong><span>TP DAO · Tema 3</span></div>
        </div>
        {GRUPOS.map((grupo) => (
          <div key={grupo.titulo} className="grupo-menu">
            <div className="grupo-menu-titulo">{grupo.titulo}</div>
            {grupo.pantallas.map((p) => (
              <button key={p.clave} className={`item-menu ${p.tema} ${p.clave === activa ? "activo" : ""}`}
                onClick={() => irA(p.clave)} aria-current={p.clave === activa ? "page" : undefined}>
                <span className="icono-menu" aria-hidden="true">{p.icono}</span> {p.titulo}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <main className={`contenido ${tema}`}>
        {/* key: al cambiar de pantalla arranca de cero */}
        <Pantalla key={activa} irA={irA} />
      </main>
    </div>
  );
}
