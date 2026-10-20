// Estructura general del front: encabezado y pestañas. Cada pestaña es una
// pantalla de src/pantallas. Se navega con estado de React (sin router): son
// pocas pantallas y no hace falta otra dependencia.
// Las pestañas se agrupan en "Operación" (los procesos del negocio) y
// "Maestros" (los datos de referencia).
import { useState } from "react";

import Categorias from "./pantallas/Categorias.jsx";
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
      { clave: "stock", titulo: "Stock", Pantalla: Stock },
      { clave: "logistica", titulo: "Logística", Pantalla: Logistica },
      { clave: "ventas", titulo: "Ventas", Pantalla: Ventas },
      { clave: "reportes", titulo: "Reportes", Pantalla: Reportes },
    ],
  },
  {
    titulo: "Maestros",
    pestanias: [
      { clave: "categorias", titulo: "Categorías", Pantalla: Categorias },
      { clave: "productos", titulo: "Productos", Pantalla: Productos },
      { clave: "proveedores", titulo: "Proveedores", Pantalla: Proveedores },
      { clave: "ubicaciones", titulo: "Sucursales y CD", Pantalla: Ubicaciones },
    ],
  },
];

const TODAS = GRUPOS.flatMap((g) => g.pestanias);

export default function App() {
  const [activa, setActiva] = useState("logistica");
  const { Pantalla } = TODAS.find((p) => p.clave === activa);

  return (
    <div className="contenedor">
      <header>
        <h1>TP DAO · Ventas e Inventario</h1>
        <nav className="pestanias">
          {GRUPOS.map((grupo) => (
            <div key={grupo.titulo} className="grupo-pestanias">
              <span className="grupo-titulo">{grupo.titulo}</span>
              {grupo.pestanias.map((p) => (
                <button key={p.clave} className={p.clave === activa ? "activa" : ""} onClick={() => setActiva(p.clave)}>
                  {p.titulo}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </header>
      <main>
        {/* key: al cambiar de pestaña la pantalla arranca de cero */}
        <Pantalla key={activa} />
      </main>
    </div>
  );
}
