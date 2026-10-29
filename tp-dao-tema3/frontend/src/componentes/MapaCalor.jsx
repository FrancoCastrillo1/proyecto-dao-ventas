// Mapa de calor de las ventas: filas = franjas horarias, columnas = días de la
// semana; cuanto más oscuro, más se vendió. Recharts no trae este gráfico: es
// una grilla de celdas pintadas con un solo color (miel) de claro a oscuro.
// Cada celda dice su valor al pasar el mouse. Recibe todo calculado del back.
// Acá NO se suma nada.
import { pesos } from "../formato.js";

// Del miel más claro al más oscuro (una sola tinta: más oscuro = más ventas)
const CLARO = [251, 239, 213];
const OSCURO = [138, 90, 11];

function colorDe(proporcion) {
  const mezcla = CLARO.map((c, i) => Math.round(c + (OSCURO[i] - c) * proporcion));
  return `rgb(${mezcla.join(", ")})`;
}

export default function MapaCalor({ titulo, mapa, accion }) {
  const maximo = Number(mapa.maximo);
  if (!maximo) return null;
  return (
    <figure className="tarjeta-grafico">
      <figcaption><span>{titulo}</span>{accion}</figcaption>
      <div className="mapa-calor" role="table" aria-label={titulo}>
        <div role="row" className="mapa-fila">
          <span role="columnheader" />
          {mapa.dias.map((dia) => <span key={dia} role="columnheader" className="mapa-dia">{dia}</span>)}
        </div>
        {mapa.filas.map((fila) => (
          <div key={fila.franja} role="row" className="mapa-fila">
            <span role="rowheader" className="mapa-franja">{fila.franja}</span>
            {fila.ventas.map((valor, i) => {
              const proporcion = Number(valor) / maximo;
              return (
                <span key={mapa.dias[i]} role="cell" className="mapa-celda"
                  style={{ background: Number(valor) ? colorDe(0.12 + 0.88 * proporcion) : undefined,
                    color: proporcion > 0.55 ? "#fffdf9" : undefined }}
                  title={`${mapa.dias[i]} ${fila.franja}: ${pesos(valor)} en ${fila.tickets[i]} ${fila.tickets[i] === 1 ? "ticket" : "tickets"}`}>
                  {Number(valor) ? fila.tickets[i] : ""}
                </span>
              );
            })}
          </div>
        ))}
      </div>
      <div className="mapa-leyenda">
        <span>Menos</span>
        <i style={{ background: `linear-gradient(90deg, ${colorDe(0.12)}, ${colorDe(1)})` }} />
        <span>Más ventas ($)</span>
        <span className="mapa-nota">El número de cada celda es la cantidad de tickets</span>
      </div>
    </figure>
  );
}
