// Único lugar del front que habla con el backend (como un DAO, pero del lado
// del navegador). Las pantallas llaman a api.listar(...), api.crear(...), etc.
// y no saben nada de fetch, JSON ni códigos HTTP. También es el único que
// sabe dónde se guarda el token del login y cómo se manda.
// Acá NO va nada de pantallas ni de estado de React.

// ---------------------------------------------------------------- Sesión
// El token se guarda en sessionStorage: sobrevive a recargar la página, pero
// se borra al cerrar la pestaña (en una caja compartida no queda abierta).
// Puede no estar disponible (modo privado estricto): entonces vive solo en memoria.
const CLAVE_TOKEN = "tp_dao_token";
let tokenEnMemoria = null;
let alVencerSesion = () => {};

export const sesion = {
  token() {
    try { return sessionStorage.getItem(CLAVE_TOKEN) ?? tokenEnMemoria; } catch { return tokenEnMemoria; }
  },
  guardar(token) {
    tokenEnMemoria = token;
    try { sessionStorage.setItem(CLAVE_TOKEN, token); } catch { /* queda en memoria */ }
  },
  borrar() {
    tokenEnMemoria = null;
    try { sessionStorage.removeItem(CLAVE_TOKEN); } catch { /* no había nada guardado */ }
  },
  // La app avisa qué hacer cuando el back dice que la sesión ya no vale (401)
  alVencer(funcion) { alVencerSesion = funcion; },
};

// Error con el código HTTP y el mensaje de la regla de negocio que falló
export class ErrorApi extends Error {
  constructor(status, mensaje) {
    super(mensaje);
    this.status = status;
  }
}

// Nombre que ve el usuario para cada campo que manda el front
const NOMBRE_CAMPO = {
  codigo: "Código", nombre: "Nombre", categoria_id: "Categoría", precio_venta: "Precio de venta",
  costo: "Costo", stock_minimo: "Stock mínimo", cuit: "CUIT", razon_social: "Razón social",
  telefono: "Teléfono", email: "Email", tipo: "Tipo", direccion: "Dirección",
  producto_id: "Producto", cantidad: "Cantidad", sucursal_id: "Sucursal", ubicacion_id: "Ubicación",
  medio_pago: "Medio de pago", monto_entregado: "Monto entregado", motivo: "Motivo", referencia: "Referencia",
  nro_precinto: "Precinto", nro_leido: "Precinto leído", intacto: "Intacto", pedido_ids: "Pedidos",
  orden_id: "Orden", destino_id: "Destino", items: "Productos", limite: "Límite",
  nombre_usuario: "Usuario", nombre_completo: "Nombre completo", contrasena: "Contraseña", perfil: "Perfil",
};

// Qué formato espera cada tipo de error de Pydantic (el "type" que viene en el 422)
const FORMATO_ESPERADO = {
  int_parsing: "tiene que ser un número entero, sin coma (ej: 10)",
  int_from_float: "tiene que ser un número entero, sin coma (ej: 10)",
  float_parsing: "tiene que ser un número; los decimales van con punto (ej: 1500.50)",
  string_type: "tiene que ser un texto",
  missing: "es obligatorio",
};

// Traduce un error de formato de Pydantic a un texto para el usuario
function textoDeFormato(error) {
  const campo = error.loc?.at(-1);
  const nombre = NOMBRE_CAMPO[campo] ?? campo;
  if (error.input === "") return `${nombre}: es obligatorio`;
  return `${nombre}: ${FORMATO_ESPERADO[error.type] ?? error.msg}`;
}

// El backend manda {"detail": "texto"} en los errores de negocio (400/404/409),
// pero Pydantic manda {"detail": [ {loc, type, input, msg}, ... ]} cuando falta un
// campo o el tipo no es el correcto (422). Acá se unifican las dos formas en un texto.
function textoDelError(cuerpo) {
  const detalle = cuerpo?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) return detalle.map(textoDeFormato).join(" · ");
  return "Error desconocido";
}

async function pedir(metodo, ruta, datos) {
  const headers = {};
  if (datos) headers["Content-Type"] = "application/json";
  if (sesion.token()) headers.Authorization = `Bearer ${sesion.token()}`;
  let respuesta;
  try {
    respuesta = await fetch(`/api${ruta}`, { method: metodo, headers, body: datos ? JSON.stringify(datos) : undefined });
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con el backend");
  }

  if (respuesta.status === 204) return null; // OK sin contenido (bajas, asignaciones)

  const cuerpo = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    // Sin JSON: el proxy de Vite no encontró al backend
    if (cuerpo === null) throw new ErrorApi(respuesta.status, "No se pudo conectar con el backend. ¿Está corriendo uvicorn?");
    const error = new ErrorApi(respuesta.status, textoDelError(cuerpo));
    // 401 con una sesión abierta = venció o la cerraron: se vuelve al login
    if (respuesta.status === 401 && sesion.token()) {
      sesion.borrar();
      alVencerSesion(error.message);
    }
    throw error;
  }
  return cuerpo;
}

export const api = {
  // Devuelve el usuario; el token queda guardado para los pedidos que siguen
  async entrar(nombre_usuario, contrasena) {
    const { token, usuario } = await pedir("POST", "/auth/login", { nombre_usuario, contrasena });
    sesion.guardar(token);
    return usuario;
  },
  async salir() {
    try { await pedir("POST", "/auth/logout"); } finally { sesion.borrar(); }
  },
  listar: (ruta) => pedir("GET", ruta),
  obtener: (ruta) => pedir("GET", ruta),
  crear: (ruta, datos) => pedir("POST", ruta, datos),
  modificar: (ruta, datos) => pedir("PUT", ruta, datos),
  borrar: (ruta) => pedir("DELETE", ruta),
  asociar: (ruta) => pedir("POST", ruta),
  accion: (ruta) => pedir("POST", ruta), // acciones sin datos, ej: /categorias/3/reactivar
};
