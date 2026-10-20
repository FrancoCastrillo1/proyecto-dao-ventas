// Estructura general del front: encabezado y pestañas. Cada pestaña es una
// pantalla de src/pantallas. Se navega con estado de React (sin router): son
// pocas pantallas y no hace falta otra dependencia.
// Las pestañas se agrupan en "Operación" (los procesos del negocio) y
// "Maestros" (los datos de referencia). Cada área tiene su color (tema-*).
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
    pestanias: [
      { clave: "inicio", icono: "🏠", titulo: "Inicio", tema: "tema-lavanda", Pantalla: Inicio },
      { clave: "stock", icono: "📦", titulo: "Stock", tema: "tema-menta", Pantalla: Stock },
      { clave: "logistica", icono: "🚚", titulo: "Logística", tema: "tema-cielo", Pantalla: Logistica },
      { clave: "ventas", icono: "🛒", titulo: "Ventas", tema: "tema-durazno", Pantalla: Ventas },
      { clave: "reportes", icono: "📊", titulo: "Reportes", tema: "tema-rosa", Pantalla: Reportes },
    ],
  },
  {
    titulo: "Maestros",
    pestanias: [
      { clave: "categorias", icono: "🏷️", titulo: "Categorías", tema: "tema-manteca", Pantalla: Categorias },
      { clave: "productos", icono: "🧃", titulo: "Productos", tema: "tema-manteca", Pantalla: Productos },
      { clave: "proveedores", icono: "🤝", titulo: "Proveedores", tema: "tema-manteca", Pantalla: Proveedores },
      { clave: "ubicaciones", icono: "🏬", titulo: "Sucursales y CD", tema: "tema-manteca", Pantalla: Ubicaciones },
    ],
  },
];

const TODAS = GRUPOS.flatMap((g) => g.pestanias);

export default function App() {
  const [activa, setActiva] = useState("inicio");
  const { Pantalla, tema } = TODAS.find((p) => p.clave === activa);

  function irA(clave) {
    setActiva(clave);
    window.scrollTo({ top: 0 });
  }

  return (
    <div className="contenedor">
      <header>
        <div className="cabecera-app">
          <h1>Ventas e Inventario</h1>
          <p>TP DAO · Tema 3</p>
        </div>
        <nav className="pestanias" aria-label="Secciones">
          {GRUPOS.map((grupo) => (
            <div key={grupo.titulo} className="grupo-pestanias">
              <span className="grupo-titulo">{grupo.titulo}</span>
              {grupo.pestanias.map((p) => (
                <button key={p.clave} className={`${p.tema} ${p.clave === activa ? "activa" : ""}`}
                  onClick={() => irA(p.clave)} aria-current={p.clave === activa ? "page" : undefined}>
                  <span aria-hidden="true">{p.icono}</span> {p.titulo}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </header>
      <main className={tema}>
        {/* key: al cambiar de pestaña la pantalla arranca de cero */}
        <Pantalla key={activa} irA={irA} />
      </main>
    </div>
  );
}
