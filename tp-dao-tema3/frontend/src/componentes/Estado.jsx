// Etiqueta de color para los estados de bultos, remitos, pedidos y órdenes,
// con un nombre en lenguaje común y, al pasar el mouse, qué significa.
// Solo presenta: qué transiciones son válidas lo decide el backend (State).

const ESTADOS = {
  // Bulto
  PREPARADO: { color: "gris", nombre: "Preparado", que: "Armado en el CD, todavía abierto" },
  PRECINTADO: { color: "azul", nombre: "Precintado", que: "Cerrado con su precinto, listo para salir" },
  EN_TRANSITO: { color: "naranja", nombre: "En tránsito", que: "Salió del CD y viaja al local" },
  RECIBIDO: { color: "violeta", nombre: "Recibido", que: "Llegó al local, falta revisar el precinto" },
  VERIFICADO: { color: "verde", nombre: "Verificado", que: "Precinto correcto: la mercadería se puede vender" },
  RECHAZADO: { color: "rojo", nombre: "Rechazado", que: "Precinto violado: la mercadería no se vende (merma)" },
  // Remito
  ABIERTO: { color: "gris", nombre: "Abierto", que: "Se le pueden agregar bultos" },
  CERRADO: { color: "azul", nombre: "Cerrado", que: "Listo para despachar" },
  VERIFICADO_CON_RECHAZOS: { color: "amarillo", nombre: "Verificado con rechazos", que: "Llegó, pero algún bulto se rechazó" },
  // Orden y pedido
  ABIERTA: { color: "gris", nombre: "Abierta", que: "Admite pedidos" },
  CERRADA: { color: "azul", nombre: "Cerrada", que: "Ya consolidó sus pedidos" },
  PENDIENTE: { color: "naranja", nombre: "Pendiente", que: "Esperando que el CD lo consolide en una orden" },
  CONSOLIDADO: { color: "verde", nombre: "Consolidado", que: "Ya está en una orden del CD" },
};

// Qué hacer con un bulto según su estado (pista para el usuario)
export const PROXIMO_PASO_BULTO = {
  PREPARADO: "Escribí el número del precinto físico que le pusiste al bulto y tocá «Precintar».",
  PRECINTADO: "Listo para salir. Cuando todos los bultos estén precintados, tocá «Despachar remito».",
  EN_TRANSITO: "Está viajando. Cuando llegue al local, tocá «Recibir en la sucursal».",
  RECIBIDO: "Leé el número del precinto, marcá si está sano y tocá «Verificar».",
  VERIFICADO: "Listo: esta mercadería ya se puede vender en el local.",
  RECHAZADO: "El precinto no coincidía o estaba roto: esta mercadería no se vende.",
};

export default function Estado({ valor }) {
  const estado = ESTADOS[valor] ?? { color: "gris", nombre: valor.replaceAll("_", " "), que: "" };
  return <span className={`estado estado-${estado.color}`} title={estado.que}>{estado.nombre}</span>;
}
