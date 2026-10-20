// Encabezado de cada pantalla: ícono, título, para qué sirve y un "¿Cómo se
// usa?" plegable con los pasos, pensado para alguien que nunca usó el sistema.
// Recuerda si se plegó (en el navegador); si no puede guardarlo, arranca abierto.
import { useState } from "react";

function leer(clave) {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function guardar(clave, valor) {
  try {
    localStorage.setItem(clave, valor);
  } catch {
    // Sin almacenamiento disponible: no pasa nada, solo no se recuerda
  }
}

export default function EncabezadoPantalla({ id, icono, titulo, descripcion, pasos }) {
  const clave = `ayuda-${id}`;
  const [abierta, setAbierta] = useState(leer(clave) !== "cerrada");

  function alternar(evento) {
    const ahora = evento.currentTarget.open;
    setAbierta(ahora);
    guardar(clave, ahora ? "abierta" : "cerrada");
  }

  return (
    <div className="encabezado-pantalla">
      <div className="titulo">
        <span className="icono" aria-hidden="true">{icono}</span>
        <h2>{titulo}</h2>
      </div>
      <p className="descripcion">{descripcion}</p>
      {pasos && (
        <details className="ayuda" open={abierta} onToggle={alternar}>
          <summary>¿Cómo se usa?</summary>
          <ol>{pasos.map((paso, i) => <li key={i}>{paso}</li>)}</ol>
        </details>
      )}
    </div>
  );
}
