// Panel lateral ("cajón") que se abre desde la derecha para crear, editar o ver
// el detalle de algo, sin perder la lista de atrás. Se cierra con la X, con
// Escape o tocando afuera. Acá NO va lógica de ninguna entidad.
import { useEffect } from "react";

export default function Cajon({ titulo, subtitulo, alCerrar, pie, ancho = false, children }) {
  useEffect(() => {
    const alApretar = (e) => { if (e.key === "Escape") alCerrar(); };
    window.addEventListener("keydown", alApretar);
    return () => window.removeEventListener("keydown", alApretar);
  }, [alCerrar]);

  return (
    <div className="fondo-cajon" onClick={alCerrar}>
      <aside className={`cajon ${ancho ? "ancho" : ""}`} role="dialog" aria-modal="true" aria-label={titulo}
        onClick={(e) => e.stopPropagation()}>
        <div className="cajon-cabecera">
          <div>
            <h2>{titulo}</h2>
            {subtitulo && <p>{subtitulo}</p>}
          </div>
          <button className="boton-cerrar" onClick={alCerrar} aria-label="Cerrar">×</button>
        </div>
        <div className="cajon-cuerpo">{children}</div>
        {pie && <div className="cajon-pie">{pie}</div>}
      </aside>
    </div>
  );
}
