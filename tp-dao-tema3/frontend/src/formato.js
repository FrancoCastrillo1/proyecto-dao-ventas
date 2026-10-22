// Formato de montos y fechas para mostrar (estilo argentino). Acá NO va lógica
// del negocio: los cálculos los hace el backend, esto solo los presenta.

const PESOS = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });

export function pesos(valor) {
  return valor === null || valor === undefined ? "—" : PESOS.format(valor);
}

export function fecha(texto) {
  if (!texto) return "—";
  return new Date(texto).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
}

// Nombre para mostrar de cada medio de pago (en la base se guarda el código)
const MEDIOS = { EFECTIVO: "Efectivo", DEBITO: "Débito", CREDITO: "Crédito", TRANSFERENCIA: "Transferencia" };

export function nombreMedio(codigo) {
  return MEDIOS[codigo?.toUpperCase()] ?? codigo;
}

export function porcentaje(valor) {
  return valor === null || valor === undefined ? "—" : `${valor.toLocaleString("es-AR")} %`;
}
