// Atajos de período ("Hoy", "Últimos 7 días", "Este mes"...): solo completan
// "desde" y "hasta" de los filtros; el back recibe las mismas fechas de
// siempre. Los usan Reportes y Tableros.
// Acá NO va lógica del negocio: qué se hace con las fechas lo decide el back.

// Una fecha como la pide el input ("2026-10-29"), en la hora local: toISOString
// daría la fecha de Greenwich, que a la noche ya es el día siguiente
export function diaIso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Cada atajo devuelve [desde, hasta]; "Todo" deja las fechas vacías
const ATAJOS = [
  { texto: "Hoy", rango: (hoy) => [hoy, hoy] },
  { texto: "Últimos 7 días", rango: (hoy) => [new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 6), hoy] },
  { texto: "Últimos 30 días", rango: (hoy) => [new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 29), hoy], soloTableros: true },
  { texto: "Este mes", rango: (hoy) => [new Date(hoy.getFullYear(), hoy.getMonth(), 1), hoy] },
  { texto: "Mes pasado", rango: (hoy) => [new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1), new Date(hoy.getFullYear(), hoy.getMonth(), 0)] },
  { texto: "Todo", rango: () => null, sinTableros: true },
];

export function fechasDe(texto) {
  const rango = ATAJOS.find((a) => a.texto === texto).rango(new Date());
  return rango ? { desde: diaIso(rango[0]), hasta: diaIso(rango[1]) } : { desde: "", hasta: "" };
}

// enTablero: un tablero siempre mira un período (sin "Todo"), y suma "Últimos 30 días"
export default function AtajosPeriodo({ filtros, alCambiar, enTablero = false }) {
  const atajos = ATAJOS.filter((a) => (enTablero ? !a.sinTableros : !a.soloTableros));
  return (
    <div className="atajos">
      <span>Período:</span>
      {atajos.map((atajo) => {
        const fechas = fechasDe(atajo.texto);
        const activo = fechas.desde === filtros.desde && fechas.hasta === filtros.hasta;
        return (
          <button key={atajo.texto} className={`chip ${activo ? "activo" : ""}`} aria-pressed={activo}
            onClick={() => alCambiar(fechas)}>{atajo.texto}</button>
        );
      })}
    </div>
  );
}
