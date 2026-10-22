// Qué puede hacer el usuario que entró, según las capacidades que devuelve el
// back (/auth/yo y /auth/login). El front NO decide permisos: solo pregunta
// para mostrar u ocultar botones. Si alguien fuerza un pedido, el back lo
// rechaza igual (403). Acá NO va lógica de ninguna entidad.

export function puede(usuario, capacidad) {
  return Boolean(usuario?.capacidades?.includes(capacidad));
}

// Para pantallas que se ven si el usuario tiene AL MENOS UNA de las capacidades
export function puedeAlguna(usuario, capacidades) {
  return !capacidades || capacidades.some((c) => puede(usuario, c));
}

// Cómo se presenta el usuario arriba del menú
export function descripcionDelPerfil(usuario) {
  if (!usuario.ubicacion_id) return "Administrador";
  return usuario.ubicacion_nombre ?? "";
}
