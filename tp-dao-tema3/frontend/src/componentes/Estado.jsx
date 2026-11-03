// Etiqueta de color para los estados de bultos, remitos, pedidos y órdenes,
// con un nombre en lenguaje común, y los pasos del bulto dibujados (el patrón
// State a la vista). Solo presenta: qué transiciones son válidas lo decide el backend.
import { Fragment } from "react";

const ESTADOS = {
  // Bulto
  PREPARADO: { color: "gris", nombre: "Preparado", que: "Armado en el CD, todavía abierto" },
  PRECINTADO: { color: "azul", nombre: "Precintado", que: "Cerrado con su precinto, listo para salir" },
  EN_TRANSITO: { color: "naranja", nombre: "En camino", que: "Salió del CD y viaja al local" },
  RECIBIDO: { color: "violeta", nombre: "Recibido", que: "Llegó al local, falta revisar el precinto" },
  VERIFICADO: { color: "verde", nombre: "Verificado", que: "Precinto correcto: la mercadería se puede vender" },
  RECHAZADO: { color: "rojo", nombre: "En merma", que: "Precinto violado: volvió al CD como merma y falta revisarlo" },
  REINTEGRADO: { color: "verde", nombre: "Reintegrado", que: "El CD lo revisó y la mercadería volvió a su stock" },
  DESCARTADO: { color: "gris", nombre: "Descartado", que: "El CD lo revisó y la mercadería se tiró" },
  // Remito
  ABIERTO: { color: "gris", nombre: "Armando", que: "Se le pueden agregar bultos" },
  CERRADO: { color: "azul", nombre: "Listo", que: "Listo para despachar" },
  VERIFICADO_CON_RECHAZOS: { color: "amarillo", nombre: "Entregado con rechazos", que: "Llegó, pero algún bulto se rechazó" },
  // Orden y pedido
  ABIERTA: { color: "gris", nombre: "Abierta", que: "Admite pedidos" },
  CERRADA: { color: "azul", nombre: "Consolidada", que: "Ya juntó sus pedidos" },
  PENDIENTE: { color: "naranja", nombre: "Pendiente", que: "Esperando que el CD lo consolide en una orden" },
  CONSOLIDADO: { color: "verde", nombre: "En preparación", que: "Ya está en una orden del CD" },
};

export default function Estado({ valor }) {
  const estado = ESTADOS[valor] ?? { color: "gris", nombre: valor.replaceAll("_", " "), que: "" };
  return <span className={`estado estado-${estado.color}`} title={estado.que}>{estado.nombre}</span>;
}

// Los pasos que recorre un bulto, en orden. El último es Verificado; si el
// precinto llegó roto, el camino sigue por la merma: Rechazado → revisión en el
// CD → Reintegrado o Descartado.
const PASOS_BULTO = ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"];
export const ESTADOS_MERMA = ["RECHAZADO", "REINTEGRADO", "DESCARTADO"];

function pasosDe(estado) {
  if (!ESTADOS_MERMA.includes(estado)) {
    const actual = PASOS_BULTO.indexOf(estado);
    return PASOS_BULTO.map((paso, i) => ({
      clave: paso, nombre: ESTADOS[paso].nombre,
      clase: i < actual || estado === "VERIFICADO" ? "hecho" : i === actual ? "actual" : "",
    }));
  }
  const previos = PASOS_BULTO.slice(0, 4).map((paso) => ({ clave: paso, nombre: ESTADOS[paso].nombre, clase: "hecho" }));
  const revision = {
    RECHAZADO: { clave: "REVISION", nombre: "Revisión en el CD", clase: "actual" },
    REINTEGRADO: { clave: "REINTEGRADO", nombre: "Reintegrado", clase: "hecho" },
    DESCARTADO: { clave: "DESCARTADO", nombre: "Descartado", clase: "rechazado" },
  }[estado];
  return [...previos, { clave: "RECHAZADO", nombre: "Rechazado", clase: "rechazado" }, revision];
}

export function PasosBulto({ estado }) {
  return (
    <div className="pasos-bulto" aria-label={`Estado: ${ESTADOS[estado]?.nombre}`}>
      {pasosDe(estado).map((paso, i) => (
        <Fragment key={paso.clave}>
          {i > 0 && <span className="linea-paso" />}
          <span className={`paso-bulto ${paso.clase}`}>
            <span className="punto">{paso.clase === "hecho" ? "✓" : paso.clase === "rechazado" ? "✕" : i + 1}</span>
            {paso.nombre}
          </span>
        </Fragment>
      ))}
    </div>
  );
}
