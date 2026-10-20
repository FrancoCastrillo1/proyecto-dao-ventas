// Cartel de éxito / error compartido por todas las pantallas, y el hook
// useAviso que ejecuta una acción contra la api y atrapa su error. Así las
// pantallas no repiten try/catch. Acá NO va lógica de ninguna entidad.
import { useState } from "react";

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
  async function ejecutar(accion, textoExito) {
    try {
      await accion();
      setAviso(textoExito ? { tipo: "exito", texto: textoExito } : null);
      return true;
    } catch (error) {
      setAviso({ tipo: "error", status: error.status, texto: error.message });
      return false;
    }
  }

  return { aviso, ejecutar, limpiar: () => setAviso(null) };
}

export function Aviso({ aviso, alCerrar }) {
  if (!aviso) return null;
  const error = aviso.tipo === "error";
  const titulo = error ? `⚠ ${TIPO_DE_ERROR[aviso.status] || "No se pudo completar"}:` : "✓ Listo:";
  return (
    <div className={`aviso aviso-${aviso.tipo}`} role="alert">
      <strong>{titulo}</strong>
      <span>{aviso.texto}</span>
      {error && aviso.status > 0 && <span className="codigo-error">código {aviso.status}</span>}
      <button className="boton-cerrar" onClick={alCerrar} aria-label="Cerrar">×</button>
    </div>
  );
}
