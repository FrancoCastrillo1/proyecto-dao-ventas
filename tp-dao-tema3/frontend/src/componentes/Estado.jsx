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
  RECHAZADO: { color: "rojo", nombre: "Rechazado", que: "Precinto violado: la mercadería no se vende (merma)" },
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

// Los pasos que recorre un bulto, en orden. El último es Verificado o Rechazado.
const PASOS_BULTO = ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"];

export function PasosBulto({ estado }) {
  const rechazado = estado === "RECHAZADO";
  const actual = rechazado ? PASOS_BULTO.length - 1 : PASOS_BULTO.indexOf(estado);
  return (
    <div className="pasos-bulto" aria-label={`Estado: ${ESTADOS[estado]?.nombre}`}>
      {PASOS_BULTO.map((paso, i) => {
        const clase = i < actual ? "hecho" : i === actual ? (rechazado ? "rechazado" : "actual") : "";
        const nombre = i === PASOS_BULTO.length - 1 && rechazado ? "Rechazado" : ESTADOS[paso].nombre;
        return (
          <Fragment key={paso}>
            {i > 0 && <span className="linea-paso" />}
            <span className={`paso-bulto ${clase}`}>
              <span className="punto">{i < actual ? "✓" : rechazado && i === actual ? "✕" : i + 1}</span>
              {nombre}
            </span>
          </Fragment>
        );
      })}
    </div>
  );
}
