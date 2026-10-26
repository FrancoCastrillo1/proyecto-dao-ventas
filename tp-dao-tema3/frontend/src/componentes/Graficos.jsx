// Gráfico de barras de los reportes, hecho con Recharts. Solo dibuja lo que le
// pasan ya calculado: las cuentas las hace el backend y el agrupado, la
// pantalla. Va siempre arriba de la tabla, que sigue siendo la vista exacta.
//
// Una sola serie por gráfico (sin leyenda: el título dice qué es), en azul; si
// hay valores negativos (ej. un producto que se vende a pérdida), esas barras
// van en rojo. Grilla y ejes tenues para que resalten los datos.
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const COLORES = { serie: "#2a78d6", negativo: "#e34948", grilla: "#e1e0d9", eje: "#c3c2b7", rotulo: "#898781" };
const ALTO_POR_FILA = 34;
const ROTULOS = { fill: COLORES.rotulo, fontSize: 12 };

// datos: [{ nombre, valor, detalle? }]. formato: cómo se muestra un valor en el
// globito (pesos, horas...); formatoEje, en el eje (por defecto, el número corto).
// horizontal: barras acostadas, para nombres largos (productos, locales); van
// de mayor a menor. Las verticales son para el tiempo y respetan el orden.
export function GraficoBarras({ titulo, datos, formato = String, formatoEje = numeroCorto, horizontal = false }) {
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
      <figcaption>{titulo}</figcaption>
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

// Suma los valores de las filas que caen en el mismo grupo, en el orden en que aparecen
export function agrupar(filas, nombreDe, valorDe) {
  const grupos = new Map();
  for (const fila of filas) {
    const nombre = nombreDe(fila);
    grupos.set(nombre, (grupos.get(nombre) ?? 0) + Number(valorDe(fila)));
  }
  return [...grupos].map(([nombre, valor]) => ({ nombre, valor }));
}
