// Estructura general del front: encabezado y pestañas. Cada pestaña es una
// pantalla de src/pantallas. Se navega con estado de React (sin router): son
// pocas pantallas y no hace falta otra dependencia.
import { useState } from "react";

import Categorias from "./pantallas/Categorias.jsx";
import Productos from "./pantallas/Productos.jsx";
import Proveedores from "./pantallas/Proveedores.jsx";
import Ubicaciones from "./pantallas/Ubicaciones.jsx";

const PESTANIAS = [
  { clave: "categorias", titulo: "Categorías", Pantalla: Categorias },
  { clave: "productos", titulo: "Productos", Pantalla: Productos },
  { clave: "proveedores", titulo: "Proveedores", Pantalla: Proveedores },
  { clave: "ubicaciones", titulo: "Sucursales y CD", Pantalla: Ubicaciones },
];

export default function App() {
  const [activa, setActiva] = useState("categorias");
  const { Pantalla } = PESTANIAS.find((p) => p.clave === activa);

  return (
    <div className="contenedor">
      <header>
        <h1>TP DAO · Ventas e Inventario</h1>
        <nav className="pestanias">
          {PESTANIAS.map((p) => (
            <button key={p.clave} className={p.clave === activa ? "activa" : ""} onClick={() => setActiva(p.clave)}>
              {p.titulo}
            </button>
          ))}
        </nav>
      </header>
      <main>
        <Pantalla />
      </main>
    </div>
  );
}
