// Etiqueta de color para los estados de bultos, remitos, pedidos y órdenes.
// Solo presenta: qué transiciones son válidas lo decide el backend (State).

const COLOR = {
  PREPARADO: "gris", PRECINTADO: "azul", EN_TRANSITO: "naranja", RECIBIDO: "violeta",
  VERIFICADO: "verde", RECHAZADO: "rojo", VERIFICADO_CON_RECHAZOS: "amarillo",
  ABIERTO: "gris", CERRADO: "azul", ABIERTA: "gris", CERRADA: "azul",
  PENDIENTE: "naranja", CONSOLIDADO: "verde",
};

export default function Estado({ valor }) {
  return <span className={`estado estado-${COLOR[valor] ?? "gris"}`}>{valor.replaceAll("_", " ")}</span>;
}
