// Tarjetas de indicadores de los tableros: el valor, contra qué se compara y
// cuánto cambió, con una flecha verde si mejoró y naranja si empeoró. Las
// cuentas (y cuándo una variación no tiene sentido) las hace el back; acá solo
// se escriben.
// Acá NO se calcula ningún indicador.
import Icono from "./Icono.jsx";
import { pesos } from "../formato.js";

const NUMERO = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 });

// Horas en lo más legible: minutos, horas o días
export function duracion(horas) {
  if (horas === null || horas === undefined) return "—";
  if (horas < 1) return `${Math.round(horas * 60)} min`;
  if (horas < 48) return `${NUMERO.format(horas)} h`;
  return `${NUMERO.format(horas / 24)} días`;
}

export function valorSegun(tipo, valor) {
  if (valor === null || valor === undefined) return "—";
  if (tipo === "pesos") return pesos(valor);
  if (tipo === "porcentaje") return `${NUMERO.format(valor)} %`;
  if (tipo === "horas") return duracion(valor);
  return NUMERO.format(valor);
}

function Cambio({ indicador, contra }) {
  const { cambio, en_puntos: enPuntos, anterior, tipo } = indicador;
  if (anterior === null || anterior === undefined) return null;
  if (cambio === null || cambio === undefined) {
    return <small className="cambio neutro">Sin datos para comparar</small>;
  }
  const signo = cambio > 0 ? "+" : "";
  const sentido = cambio > 0 ? "sube" : cambio < 0 ? "baja" : "igual";
  return (
    <small className={`cambio ${cambio > 0 ? "mejor" : cambio < 0 ? "peor" : "neutro"}`}
      title={`${contra}: ${valorSegun(tipo, anterior)}`}>
      <Icono nombre={sentido} tamano={14} />
      {signo}{NUMERO.format(cambio)}{enPuntos ? " pts" : " %"}
      <span className="contra"> vs. {valorSegun(tipo, anterior)}</span>
    </small>
  );
}

// contra: con qué se compara, para el globito ("Período anterior")
export default function Indicadores({ indicadores, contra = "Período anterior" }) {
  return (
    <div className="tarjetas indicadores">
      {indicadores.map((indicador) => (
        <div key={indicador.titulo} className="tarjeta">
          <span>{indicador.titulo}</span>
          <strong>{valorSegun(indicador.tipo, indicador.valor)}</strong>
          <Cambio indicador={indicador} contra={contra} />
        </div>
      ))}
    </div>
  );
}
