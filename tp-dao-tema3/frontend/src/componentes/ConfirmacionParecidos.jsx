// Aviso "¿es un duplicado?" que se muestra antes de guardar si ya existe un
// nombre parecido (ej: "Bebida" cuando existe "Bebidas"). No es una regla:
// el usuario puede guardar igual. El parecido lo calcula el backend
// (GET <ruta>/parecidos). Acá NO va lógica de ninguna entidad.
import { useState } from "react";

import { api } from "../api.js";

export function useParecidos() {
  const [pendiente, setPendiente] = useState(null); // { parecidos, continuar }

  // Consulta parecidos; si no hay, ejecuta continuar() directo. Si hay, deja
  // el guardado pendiente hasta que el usuario confirme o cancele.
  async function verificar(ruta, filtro, excluirId, continuar) {
    const parametros = new URLSearchParams(filtro);
    if (excluirId) parametros.set("excluir_id", excluirId);
    let parecidos = [];
    try {
      parecidos = await api.listar(`${ruta}/parecidos?${parametros}`);
    } catch {
      // Si la consulta falla se sigue igual: es solo una ayuda y el alta valida todo
    }
    if (parecidos.length === 0) return continuar();
    setPendiente({ parecidos, continuar });
  }

  function confirmar() {
    const { continuar } = pendiente;
    setPendiente(null);
    continuar();
  }

  return { pendiente, verificar, confirmar, descartar: () => setPendiente(null) };
}

export function ConfirmacionParecidos({ pendiente, alConfirmar, alCancelar }) {
  if (!pendiente) return null;
  return (
    <div className="aviso aviso-advertencia" role="alert">
      <strong>¿Es un duplicado?</strong>
      <span>Ya existe algo parecido: {pendiente.parecidos.map((p) => `“${p.nombre}”`).join(", ")}</span>
      <div className="botones-aviso">
        <button onClick={alConfirmar}>Guardar igual</button>
        <button className="secundario" onClick={alCancelar}>Cancelar</button>
      </div>
    </div>
  );
}
