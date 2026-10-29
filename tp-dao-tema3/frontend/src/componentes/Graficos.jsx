// Gráficos de los reportes y los tableros, hechos con Recharts. Solo dibujan lo
// que les pasan ya calculado: las cuentas las hace el backend.
//
// GraficoBarras: una sola serie (sin leyenda: el título dice qué es), en miel;
// los valores negativos (ej. un producto que se vende a pérdida), en rojo.
// Los de los tableros comparan dos o más series: llevan leyenda, y los colores
// salen de SERIES (validados para que se distingan también con daltonismo).
// Grilla y ejes tenues para que resalten los datos.
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter,
  ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";

const COLORES = { serie: "#c98a1b", negativo: "#b23a3a", grilla: "#ece3d3", eje: "#d6c9b3", rotulo: "#8a7862" };
// La serie principal en miel; la que se compara, en azul petróleo; lo anterior, gris
export const SERIES = { principal: "#c98a1b", segunda: "#0082a0", anterior: "#b3a58f" };
const ALTO_POR_FILA = 34;
const ROTULOS = { fill: COLORES.rotulo, fontSize: 12 };

// datos: [{ nombre, valor, detalle? }]. formato: cómo se muestra un valor en el
// globito (pesos, horas...); formatoEje, en el eje (por defecto, el número corto).
// horizontal: barras acostadas, para nombres largos (productos, locales); van
// de mayor a menor. Las verticales son para el tiempo y respetan el orden.
export function GraficoBarras({ titulo, datos, formato = String, formatoEje = numeroCorto, horizontal = false, accion }) {
  // Una sola barra no compara nada: para eso está la tarjeta de arriba
  if (datos.length < 2) return null;
  if (horizontal) datos = [...datos].sort((a, b) => b.valor - a.valor);
  const marcas = marcasRedondas(datos.map((d) => d.valor));
  const alto = horizontal ? datos.length * ALTO_POR_FILA + 40 : 240;
  const ejeValor = { tick: ROTULOS, tickFormatter: formatoEje, axisLine: false, tickLine: false,
    ticks: marcas, domain: [marcas[0], marcas.at(-1)] };
  const ejeNombre = { dataKey: "nombre", tick: ROTULOS, axisLine: { stroke: COLORES.eje }, tickLine: false, interval: 0 };

  return (
    <figure className="tarjeta-grafico">
      <figcaption><span>{titulo}</span>{accion}</figcaption>
      <ResponsiveContainer width="100%" height={alto}>
        <BarChart data={datos} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={COLORES.grilla} horizontal={!horizontal} vertical={horizontal} />
          {horizontal ? (<>
            <XAxis type="number" {...ejeValor} />
            <YAxis type="category" width={150} {...ejeNombre} />
          </>) : (<>
            <XAxis {...ejeNombre} />
            <YAxis width={72} {...ejeValor} />
          </>)}
          <Tooltip cursor={{ fill: "rgba(42, 120, 214, 0.08)" }} content={<Globito formato={formato} />} />
          {/* radio solo en la punta de la barra; Recharts lo da vuelta solo en las negativas */}
          <Bar dataKey="valor" maxBarSize={28} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} isAnimationActive={false}>
            {datos.map((d) => <Cell key={d.nombre} fill={d.valor < 0 ? COLORES.negativo : COLORES.serie} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}

function Globito({ active, payload, formato }) {
  if (!active || !payload?.length) return null;
  const { nombre, valor, detalle } = payload[0].payload;
  return (
    <div className="globito-grafico">
      <span>{nombre}</span>
      <strong>{formato(valor)}</strong>
      {detalle && <small>{detalle}</small>}
    </div>
  );
}

// Marcas del eje en números redondos (1, 2, 2,5 o 5 por una potencia de 10),
// siempre incluyendo el 0 para que las barras arranquen de la base
function marcasRedondas(valores) {
  const minimo = Math.min(0, ...valores);
  const maximo = Math.max(0, ...valores) || (minimo < 0 ? 0 : 1);  // todo en 0: un eje de 0 a 1
  const crudo = (maximo - minimo) / 4;
  const potencia = 10 ** Math.floor(Math.log10(crudo));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= crudo);
  const marcas = [];
  for (let marca = Math.floor(minimo / paso) * paso; marca < maximo + paso / 2; marca += paso) marcas.push(Number(marca.toPrecision(12)));
  return marcas;
}

// En el eje no entran "$ 1.234.567,00": se acorta a "1,2 M" (la unidad la dice
// el título; el valor exacto está en el globito y en la tabla)
function numeroCorto(valor) {
  const absoluto = Math.abs(valor);
  if (absoluto >= 1_000_000) return `${(valor / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 })} M`;
  if (absoluto >= 10_000) return `${(valor / 1_000).toLocaleString("es-AR", { maximumFractionDigits: 0 })} mil`;
  return valor.toLocaleString("es-AR", { maximumFractionDigits: 1 });
}

// ------------------------------------------------------------ De los tableros

const LEYENDA = { iconType: "circle", iconSize: 9, wrapperStyle: { fontSize: 13, color: COLORES.rotulo, paddingTop: 6 } };

// Globito de varias series: el nombre del punto y el valor de cada serie
function GlobitoSeries({ active, payload, label, formato, series }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="globito-grafico">
      <span>{payload[0].payload.titulo ?? label}</span>
      {series.map((s) => {
        const valor = payload[0].payload[s.clave];
        return (
          <small key={s.clave} className="globito-serie">
            <i style={{ background: s.color }} /> {s.nombre}: <strong>{valor === null || valor === undefined ? "—" : formato(valor)}</strong>
          </small>
        );
      })}
    </div>
  );
}

// Líneas para la evolución en el tiempo. series: [{ clave, nombre, color, punteada? }]
// (la del período anterior, punteada y en gris, para que no compita con la actual)
export function GraficoLineas({ titulo, datos, series, formato = String, formatoEje = numeroCorto, alto = 260, accion }) {
  if (datos.length < 2) return null;
  const marcas = marcasRedondas(datos.flatMap((d) => series.map((s) => Number(d[s.clave] ?? 0))));
  return (
    <figure className="tarjeta-grafico">
      <figcaption><span>{titulo}</span>{accion}</figcaption>
      <ResponsiveContainer width="100%" height={alto}>
        <LineChart data={datos} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={COLORES.grilla} vertical={false} />
          <XAxis dataKey="etiqueta" tick={ROTULOS} axisLine={{ stroke: COLORES.eje }} tickLine={false} minTickGap={18} />
          <YAxis width={72} tick={ROTULOS} tickFormatter={formatoEje} axisLine={false} tickLine={false}
            ticks={marcas} domain={[marcas[0], marcas.at(-1)]} />
          <Tooltip content={<GlobitoSeries formato={formato} series={series} />} cursor={{ stroke: COLORES.eje }} />
          {series.length > 1 && <Legend {...LEYENDA} />}
          {series.map((s) => (
            <Line key={s.clave} dataKey={s.clave} name={s.nombre} stroke={s.color} strokeWidth={2}
              strokeDasharray={s.punteada ? "5 4" : undefined} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </figure>
  );
}

// Barras acostadas de dos (o más) series una al lado de la otra, ej. ventas y
// ganancia por local. alClic: para ir al detalle de una fila (el local).
export function GraficoBarrasDobles({ titulo, datos, series, formato = String, alClic, apiladas = false, ayuda, accion }) {
  if (datos.length === 0) return null;
  const valores = datos.flatMap((d) => (apiladas ? [series.reduce((suma, s) => suma + Number(d[s.clave] ?? 0), 0)]
    : series.map((s) => Number(d[s.clave] ?? 0))));
  const marcas = marcasRedondas(valores);
  const alto = datos.length * (apiladas ? ALTO_POR_FILA : ALTO_POR_FILA * 1.5) + 70;
  return (
    <figure className={`tarjeta-grafico ${alClic ? "con-clic" : ""}`}>
      <figcaption><span>{titulo}{ayuda && <small> · {ayuda}</small>}</span>{accion}</figcaption>
      <ResponsiveContainer width="100%" height={alto}>
        <BarChart data={datos} layout="vertical" margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={COLORES.grilla} horizontal={false} />
          <XAxis type="number" tick={ROTULOS} tickFormatter={numeroCorto} axisLine={false} tickLine={false}
            ticks={marcas} domain={[marcas[0], marcas.at(-1)]} />
          <YAxis type="category" dataKey="nombre" width={150} tick={ROTULOS} axisLine={{ stroke: COLORES.eje }} tickLine={false} interval={0} />
          <Tooltip cursor={{ fill: "rgba(201, 138, 27, 0.08)" }} content={<GlobitoSeries formato={formato} series={series} />} />
          <Legend {...LEYENDA} />
          {series.map((s, i) => (
            <Bar key={s.clave} dataKey={s.clave} name={s.nombre} fill={s.color} maxBarSize={apiladas ? 26 : 16}
              stackId={apiladas ? "uno" : undefined} isAnimationActive={false}
              onClick={alClic ? (barra) => alClic(barra.payload ?? barra) : undefined}
              radius={!apiladas || i === series.length - 1 ? [0, 4, 4, 0] : 0}
              stroke={apiladas ? "#fffdf9" : undefined} strokeWidth={apiladas ? 1 : 0} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}

// Dispersión: cada punto es un producto (x unidades, y margen %, tamaño la
// ganancia). Las dos líneas de corte separan los cuatro cuadrantes.
export function GraficoDispersion({ titulo, puntos, corteX, corteY, colorDe, formatoX = String, formatoY = String, detalle, accion }) {
  if (puntos.length === 0) return null;
  const mayor = Math.max(...puntos.map((p) => Math.abs(p.tamano)), 1);
  return (
    <figure className="tarjeta-grafico">
      <figcaption><span>{titulo}</span>{accion}</figcaption>
      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 16, right: 24, bottom: 18, left: 0 }}>
          <CartesianGrid stroke={COLORES.grilla} />
          <XAxis type="number" dataKey="x" name="Unidades" tick={ROTULOS} tickFormatter={formatoX} axisLine={{ stroke: COLORES.eje }}
            tickLine={false} label={{ value: "Unidades vendidas →", position: "insideBottom", offset: -10, fill: COLORES.rotulo, fontSize: 12 }} />
          <YAxis type="number" dataKey="y" name="Margen" width={64} tick={ROTULOS} tickFormatter={formatoY} axisLine={false}
            tickLine={false} label={{ value: "Margen ↑", angle: -90, position: "insideLeft", fill: COLORES.rotulo, fontSize: 12, dy: 30 }} />
          <ZAxis type="number" dataKey="tamano" range={[60, 600]} domain={[0, mayor]} />
          <ReferenceLine x={corteX} stroke={COLORES.eje} strokeDasharray="4 4" />
          <ReferenceLine y={corteY} stroke={COLORES.eje} strokeDasharray="4 4" />
          <ReferenceLine y={0} stroke={COLORES.negativo} strokeOpacity={0.35} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<GlobitoPunto detalle={detalle} />} />
          <Scatter data={puntos.map((p) => ({ ...p, tamano: Math.abs(p.tamano) }))} isAnimationActive={false}>
            {puntos.map((p) => <Cell key={p.nombre} fill={colorDe(p)} fillOpacity={0.8} stroke="#fffdf9" strokeWidth={2} />)}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </figure>
  );
}

function GlobitoPunto({ active, payload, detalle }) {
  if (!active || !payload?.length) return null;
  const punto = payload[0].payload;
  return (
    <div className="globito-grafico">
      <span>{punto.nombre}</span>
      {detalle(punto).map((linea) => <small key={linea}>{linea}</small>)}
    </div>
  );
}

// Suma los valores de las filas que caen en el mismo grupo, en el orden en que aparecen
export function agrupar(filas, nombreDe, valorDe) {
  const grupos = new Map();
  for (const fila of filas) {
    const nombre = nombreDe(fila);
    grupos.set(nombre, (grupos.get(nombre) ?? 0) + Number(valorDe(fila)));
  }
  return [...grupos].map(([nombre, valor]) => ({ nombre, valor }));
}
