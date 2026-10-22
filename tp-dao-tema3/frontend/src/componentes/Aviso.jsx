// Cartel de éxito / error compartido por todas las pantallas, y el hook
// useAviso que ejecuta una acción contra la api y atrapa su error. Así las
// pantallas no repiten try/catch. Acá NO va lógica de ninguna entidad.
import { useEffect, useState } from "react";

// Qué tipo de regla del backend representa cada código (ver main.py), dicho
// para el usuario. El código queda chiquito al costado (sirve para probar reglas).
const TIPO_DE_ERROR = {
  0: "Sin conexión con el sistema",
  400: "Revisá los datos",
  404: "No se encontró",
  409: "No se puede hacer",
  422: "Falta completar o hay un formato incorrecto",
};

export function useAviso() {
  const [aviso, setAviso] = useState(null);

  // Ejecuta la acción; devuelve true si salió bien. Si falla, muestra el error.
  // Sin textoExito (ej: recargar la lista después de una acción) no toca el
  // aviso, así no borra el "✓ Listo" que acaba de mostrar la acción.
  async function ejecutar(accion, textoExito) {
    try {
      await accion();
      if (textoExito) setAviso({ tipo: "exito", texto: textoExito });
      return true;
    } catch (error) {
      setAviso({ tipo: "error", status: error.status, texto: error.message });
      return false;
    }
  }

  return { aviso, ejecutar, limpiar: () => setAviso(null) };
}

// El aviso es FLOTANTE (fijo abajo a la derecha): se ve aunque la acción se
// haya hecho al final de la página. El de éxito se va solo a los 5 segundos;
// el de error queda hasta que se cierra, para que no se pierda.
export function Aviso({ aviso, alCerrar }) {
  useEffect(() => {
    if (aviso?.tipo !== "exito") return undefined;
    const temporizador = setTimeout(alCerrar, 5000);
    return () => clearTimeout(temporizador);
  }, [aviso]);

  if (!aviso) return null;
  const error = aviso.tipo === "error";
  const titulo = error ? `⚠ ${TIPO_DE_ERROR[aviso.status] || "No se pudo completar"}:` : "✓ Listo:";
  return (
    <div className={`aviso aviso-flotante aviso-${aviso.tipo}`} role="alert">
      <strong>{titulo}</strong>
      <span>{aviso.texto}</span>
      {error && aviso.status > 0 && <span className="codigo-error">código {aviso.status}</span>}
      <button className="boton-cerrar" onClick={alCerrar} aria-label="Cerrar">×</button>
    </div>
  );
}
