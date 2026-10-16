// Único lugar del front que habla con el backend (como un DAO, pero del lado
// del navegador). Las pantallas llaman a api.listar(...), api.crear(...), etc.
// y no saben nada de fetch, JSON ni códigos HTTP.
// Acá NO va nada de pantallas ni de estado de React.

// Error con el código HTTP y el mensaje de la regla de negocio que falló
export class ErrorApi extends Error {
  constructor(status, mensaje) {
    super(mensaje);
    this.status = status;
  }
}

// El backend manda {"detail": "texto"} en los errores de negocio (400/404/409),
// pero Pydantic manda {"detail": [ {loc, msg}, ... ]} cuando falta un campo o el
// tipo no es el correcto (422). Acá se unifican las dos formas en un texto.
function textoDelError(cuerpo) {
  const detalle = cuerpo?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) {
    return detalle.map((e) => `${e.loc?.at(-1)}: ${e.msg}`).join(" · ");
  }
  return "Error desconocido";
}

async function pedir(metodo, ruta, datos) {
  let respuesta;
  try {
    respuesta = await fetch(`/api${ruta}`, {
      method: metodo,
      headers: datos ? { "Content-Type": "application/json" } : undefined,
      body: datos ? JSON.stringify(datos) : undefined,
    });
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con el backend");
  }

  if (respuesta.status === 204) return null; // OK sin contenido (bajas, asignaciones)

  const cuerpo = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    // Sin JSON: el proxy de Vite no encontró al backend
    if (cuerpo === null) throw new ErrorApi(respuesta.status, "No se pudo conectar con el backend. ¿Está corriendo uvicorn?");
    throw new ErrorApi(respuesta.status, textoDelError(cuerpo));
  }
  return cuerpo;
}

export const api = {
  listar: (ruta) => pedir("GET", ruta),
  obtener: (ruta) => pedir("GET", ruta),
  crear: (ruta, datos) => pedir("POST", ruta, datos),
  modificar: (ruta, datos) => pedir("PUT", ruta, datos),
  borrar: (ruta) => pedir("DELETE", ruta),
  asociar: (ruta) => pedir("POST", ruta),
};
