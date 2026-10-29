// Los 7 reportes de detalle (/reportes/...): los abre el "Ver detalle" de un
// gráfico de los tableros. Cada uno muestra su resumen, sus tarjetas, un
// gráfico y la tabla exacta (la que va al PDF). Las cuentas las hace el back;
// acá solo se muestran.
// Acá NO se decide qué tablero abre cada reporte (eso es Tableros.jsx) ni se
// piden los datos (eso es la pantalla Reportes).
import Icono from "../../componentes/Icono.jsx";
import { Vacio } from "../../componentes/Controles.jsx";
import { GraficoBarras, agrupar } from "../../componentes/Graficos.jsx";
import { fecha, nombreMedio, pesos, porcentaje } from "../../formato.js";

// requiere: la capacidad que hace falta para verlo (los de ventas, el CD no los
// ve; los más pedidos son de toda la red: CD y administrador). fechas / lugar:
// qué filtros usa ("sucursal" o "ubicacion"). ranking: se elige cuántos mostrar.
export const REPORTES = {
  "ventas": { titulo: "Ventas", pregunta: "¿Cuánto se vendió, dónde y cómo se cobró?", fechas: true, lugar: "sucursal", requiere: "ve_ventas" },
  "productos-mas-vendidos": { titulo: "Más vendidos", pregunta: "¿Qué productos se venden más y cuánto dejan?", fechas: true, lugar: "sucursal", ranking: true, requiere: "ve_ventas" },
  "devoluciones": { titulo: "Devoluciones", pregunta: "¿Qué se devuelve, cuánto y por qué?", fechas: true, lugar: "sucursal", requiere: "ve_ventas" },
  "productos-mas-pedidos": { titulo: "Más pedidos", pregunta: "¿Qué piden más los locales y alcanza lo que hay en el CD?", fechas: true, lugar: "sucursal", ranking: true, requiere: "ve_toda_la_red" },
  "existencias": { titulo: "Existencias", pregunta: "¿Cuánto hay, qué falta reponer y qué está parado?", lugar: "ubicacion" },
  "mermas": { titulo: "Mermas", pregunta: "¿Cuántos bultos llegaron con el precinto roto y cuánto se perdió?", fechas: true, lugar: "sucursal" },
  "tiempos-transito": { titulo: "Tiempos de envío", pregunta: "¿Cuánto tarda un bulto del CD a cada local?", fechas: true, lugar: "sucursal" },
};

// Los filtros propios de cada reporte (además de fechas y lugar)
export function FiltrosDelReporte({ clave, filtros, cambiar }) {
  const reporte = REPORTES[clave];
  return (<>
    {clave === "ventas" && (
      <label>Ver por
        <select value={filtros.agrupar} onChange={cambiar("agrupar")}>
          <option value="dia">Día</option><option value="mes">Mes</option><option value="total">Todo junto</option>
        </select>
      </label>
    )}
    {reporte.ranking && (
      <label>Mostrar
        <select value={filtros.limite} onChange={cambiar("limite")}>
          <option value="5">Top 5</option><option value="10">Top 10</option><option value="20">Top 20</option><option value="100">Todos</option>
        </select>
      </label>
    )}
    {clave === "existencias" && (
      <label className="check">
        <input type="checkbox" checked={filtros.solo_bajo_minimo} onChange={cambiar("solo_bajo_minimo")} /> Solo lo que falta reponer
      </label>
    )}
  </>);
}

export function parametrosDelReporte(clave, filtros) {
  const parametros = new URLSearchParams();
  if (clave === "ventas") parametros.set("agrupar", filtros.agrupar);
  if (REPORTES[clave].ranking) parametros.set("limite", filtros.limite);
  if (clave === "existencias" && filtros.solo_bajo_minimo) parametros.set("solo_bajo_minimo", "true");
  return parametros;
}

export default function Detalle({ clave, datos, filtros }) {
  return (<>
    <Resumen frases={datos.resumen} />
    {clave === "ventas" && <ReporteVentas datos={datos} agrupado={filtros.agrupar} />}
    {clave === "productos-mas-vendidos" && <ReporteMasVendidos datos={datos} />}
    {clave === "devoluciones" && <ReporteDevoluciones datos={datos} />}
    {clave === "productos-mas-pedidos" && <ReporteMasPedidos datos={datos} />}
    {clave === "existencias" && <ReporteExistencias datos={datos} />}
    {clave === "mermas" && <ReporteMermas datos={datos} />}
    {clave === "tiempos-transito" && <ReporteTransito datos={datos} />}
  </>);
}

// Lo importante del reporte en dos o tres frases (las arma el back)
function Resumen({ frases }) {
  if (!frases?.length) return null;
  return (
    <div className="resumen-reporte tema-miel">
      <span className="tarea-icono"><Icono nombre="idea" tamano={18} /></span>
      <div>
        <strong>Resumen</strong>
        <ul>{frases.map((frase) => <li key={frase}>{frase}</li>)}</ul>
      </div>
    </div>
  );
}

// La última tarjeta es el total y va destacada
function Tarjetas({ items }) {
  return (
    <div className="tarjetas">
      {items.map(([titulo, valor], i) => (
        <div key={titulo} className={`tarjeta ${i === items.length - 1 ? "destacada" : ""}`}><span>{titulo}</span><strong>{valor}</strong></div>
      ))}
    </div>
  );
}

function Tabla({ children }) {
  return <div className="tarjeta-tabla"><table>{children}</table></div>;
}

const SIN_DATOS = <Vacio icono="buscar" titulo="No hay datos para estos filtros" texto="Probá con otras fechas o con todos los locales." />;
const unidades = (n) => `${n} u.`;

// "2026-10-20" → "20/10"; "2026-10" → "10/2026"
function periodoCorto(periodo) {
  const [anio, mes, dia] = periodo.split("-");
  return dia ? `${dia}/${mes}` : `${mes}/${anio}`;
}

function ReporteVentas({ datos, agrupado }) {
  // Por día o mes: cómo evoluciona el ingreso. Todo junto: cómo se cobró.
  const porTiempo = agrupado !== "total";
  const grafico = porTiempo
    ? agrupar(datos.filas, (f) => periodoCorto(f.periodo), (f) => f.neto)
    : agrupar(datos.filas, (f) => nombreMedio(f.medio_pago), (f) => f.neto);
  return (<>
    <Tarjetas items={[
      ["Ventas", datos.cantidad_ventas], ["Vendido", pesos(datos.total_vendido)],
      ["Devuelto", pesos(datos.total_devuelto)], ["Ingreso neto", pesos(datos.total_neto)],
    ]} />
    {datos.filas.length === 0 ? SIN_DATOS : (<>
      <GraficoBarras titulo={porTiempo ? `Ingreso neto por ${agrupado === "dia" ? "día" : "mes"} ($)` : "Ingreso neto por medio de pago ($)"}
        datos={grafico} formato={pesos} horizontal={!porTiempo} />
      <Tabla>
        <thead><tr><th>Período</th><th>Local</th><th>Medio de pago</th><th className="num">Ventas</th>
          <th className="num">Vendido</th><th className="num">Devuelto</th><th className="num">Neto</th></tr></thead>
        <tbody>
          {datos.filas.map((f, i) => (
            <tr key={i}><td>{f.periodo}</td><td>{f.sucursal}</td><td>{nombreMedio(f.medio_pago)}</td><td className="num">{f.cantidad_ventas}</td>
              <td className="num">{pesos(f.vendido)}</td><td className="num">{pesos(f.devuelto)}</td><td className="num"><strong>{pesos(f.neto)}</strong></td></tr>
          ))}
        </tbody>
      </Tabla>
    </>)}
  </>);
}

function ReporteMasVendidos({ datos }) {
  return (<>
    <Tarjetas items={[["Ingreso", pesos(datos.total_ingreso)], ["Ganancia (margen)", pesos(datos.total_margen)]]} />
    {datos.filas.length === 0 ? SIN_DATOS : (<>
      {/* el ranking en unidades; la ganancia de cada uno, en el globito y en la tabla (en rojo si se vende a pérdida) */}
      <GraficoBarras titulo="Unidades vendidas por producto" formato={unidades} horizontal
        datos={datos.filas.map((f) => ({ nombre: f.nombre, valor: f.unidades,
          detalle: `Ganancia ${pesos(f.margen)} · margen ${porcentaje(f.margen_porcentaje)}` }))} />
      <Tabla>
        <thead><tr><th>#</th><th>Producto</th><th className="num">Unidades</th><th className="num">Ingreso</th>
          <th className="num">Costo</th><th className="num">Ganancia</th><th className="num">Margen</th></tr></thead>
        <tbody>
          {datos.filas.map((f, i) => (
            <tr key={f.producto_id}>
              <td>{i + 1}</td>
              <td>{f.nombre}<span className="secundario-texto">{f.codigo}</span></td>
              <td className="num"><strong>{f.unidades}</strong></td>
              <td className="num">{pesos(f.ingreso)}</td><td className="num">{pesos(f.costo)}</td>
              <td className={`num ${f.margen < 0 ? "negativo" : ""}`}>{pesos(f.margen)}</td>
              <td className={`num ${f.margen < 0 ? "negativo" : ""}`}>{porcentaje(f.margen_porcentaje)}</td>
            </tr>
          ))}
        </tbody>
      </Tabla>
    </>)}
  </>);
}

function ReporteDevoluciones({ datos }) {
  return (<>
    <Tarjetas items={[["Devoluciones", datos.cantidad_devoluciones], ["Unidades devueltas", datos.unidades_devueltas],
      ["Reintegrado", pesos(datos.total_reintegrado)]]} />
    {datos.filas.length === 0
      ? <Vacio icono="listo" titulo="Sin devoluciones" texto="No se devolvió nada con estos filtros." />
      : (<>
        <GraficoBarras titulo="Unidades devueltas por producto" formato={unidades} horizontal
          datos={datos.filas.map((f) => ({ nombre: f.nombre, valor: f.unidades,
            detalle: `${porcentaje(f.porcentaje_devuelto)} de lo vendido · sobre todo por "${f.motivo_principal}"` }))} />
        <Tabla>
          <thead><tr><th>Producto</th><th className="num">Devueltas</th><th className="num">Vendidas</th>
            <th className="num">% devuelto</th><th className="num">Reintegrado</th><th>Motivo principal</th></tr></thead>
          <tbody>
            {datos.filas.map((f) => (
              <tr key={f.producto_id}><td>{f.nombre}<span className="secundario-texto">{f.codigo}</span></td>
                <td className="num"><strong>{f.unidades}</strong></td><td className="num">{f.vendidas}</td>
                <td className="num">{porcentaje(f.porcentaje_devuelto)}</td><td className="num">{pesos(f.importe)}</td>
                <td>{f.motivo_principal}</td></tr>
            ))}
          </tbody>
        </Tabla>
        <h2 className="titulo-seccion espacio-arriba">Por qué se devuelve</h2>
        <Tabla>
          <thead><tr><th>Motivo</th><th className="num">Devoluciones</th><th className="num">Reintegrado</th></tr></thead>
          <tbody>
            {datos.por_motivo.map((m) => (
              <tr key={m.motivo}><td>{m.motivo}</td><td className="num">{m.devoluciones}</td><td className="num">{pesos(m.importe)}</td></tr>
            ))}
          </tbody>
        </Tabla>
      </>)}
  </>);
}

function ReporteMasPedidos({ datos }) {
  return (<>
    <Tarjetas items={[["Unidades pedidas", datos.total_unidades], ["Sin preparar", datos.total_sin_preparar],
      ["Productos que faltan en el CD", datos.productos_que_faltan]]} />
    {datos.filas.length === 0 ? SIN_DATOS : (<>
      <GraficoBarras titulo="Unidades pedidas por producto" formato={unidades} horizontal
        datos={datos.filas.map((f) => ({ nombre: f.nombre, valor: f.unidades,
          detalle: `${f.pedidos} pedidos de ${f.locales} ${f.locales === 1 ? "local" : "locales"} · en el CD hay ${f.stock_cd}` }))} />
      <Tabla>
        <thead><tr><th>#</th><th>Producto</th><th className="num">Pedidas</th><th className="num">Pedidos</th>
          <th className="num">Locales</th><th className="num">Sin preparar</th><th className="num">En el CD</th>
          <th className="num">Falta</th></tr></thead>
        <tbody>
          {datos.filas.map((f, i) => (
            <tr key={f.producto_id} className={f.falta_en_cd ? "fila-alerta" : ""}>
              <td>{i + 1}</td><td>{f.nombre}<span className="secundario-texto">{f.codigo}</span></td>
              <td className="num"><strong>{f.unidades}</strong></td><td className="num">{f.pedidos}</td>
              <td className="num">{f.locales}</td><td className="num">{f.sin_preparar}</td>
              <td className="num">{f.stock_cd}</td>
              <td className={`num ${f.falta_en_cd ? "falta" : ""}`}>{f.falta_en_cd || "—"}</td></tr>
          ))}
        </tbody>
      </Tabla>
      <p className="nota espacio-arriba">Falta: lo que los locales pidieron y todavía no se preparó, menos lo que hay hoy en el CD. Si aparece un número, con lo que hay no alcanza: hay que comprar.</p>
    </>)}
  </>);
}

// Días sin salir: "nunca" si tiene stock y nunca salió; nada si no hay stock
function diasSinSalir(fila) {
  if (!fila.cantidad) return "—";
  return fila.dias_sin_salir === null ? "Nunca" : fila.dias_sin_salir;
}

function ReporteExistencias({ datos }) {
  const tarjetas = Object.entries(datos.valorizado_por_ubicacion).map(([nombre, valor]) => [nombre, pesos(valor)]);
  return (<>
    <Tarjetas items={[...tarjetas, ["Productos para reponer", datos.productos_bajo_minimo], ["Inventario valorizado", pesos(datos.valorizado_total)]]} />
    {datos.filas.length === 0 ? SIN_DATOS : (<>
      {/* con una sola ubicación el gráfico no compara nada: alcanza con la tarjeta */}
      {tarjetas.length > 1 && (
        <GraficoBarras titulo="Inventario valorizado por ubicación ($)" formato={pesos} horizontal
          datos={Object.entries(datos.valorizado_por_ubicacion).map(([nombre, valor]) => ({ nombre, valor: Number(valor) }))} />
      )}
      <Tabla>
        <thead><tr><th>Ubicación</th><th>Producto</th><th className="num">Hay</th><th className="num">Mínimo</th>
          <th className="num">Falta</th><th className="num">Valor</th><th className="num">Días sin salir</th></tr></thead>
        <tbody>
          {datos.filas.map((f, i) => {
            const parado = f.cantidad > 0 && (f.dias_sin_salir === null || f.dias_sin_salir > 30);
            return (
              <tr key={i} className={f.bajo_minimo || parado ? "fila-alerta" : ""}><td>{f.ubicacion}</td>
                <td>{f.nombre}<span className="secundario-texto">{f.codigo}</span></td>
                <td className="num">{f.cantidad}</td><td className="num">{f.stock_minimo}</td>
                <td className={`num ${f.faltante ? "falta" : ""}`}>{f.faltante || "—"}</td><td className="num">{pesos(f.valorizado)}</td>
                <td className={`num ${parado ? "falta" : ""}`} title={f.ultima_salida ? `Última salida: ${fecha(f.ultima_salida)}` : undefined}>
                  {diasSinSalir(f)}</td></tr>
            );
          })}
        </tbody>
      </Tabla>
      <p className="nota espacio-arriba">Días sin salir: desde la última venta (en un local) o el último despacho (en el CD). En naranja, lo que falta reponer o lleva más de 30 días parado.</p>
    </>)}
  </>);
}

function ReporteMermas({ datos }) {
  return (<>
    <Tarjetas items={[["Bultos rechazados", datos.por_sucursal.reduce((suma, s) => suma + s.bultos_rechazados, 0)],
      ["Valor perdido", pesos(datos.valor_perdido_total)]]} />
    {datos.por_sucursal.length === 0
      ? <Vacio icono="listo" titulo="Sin mermas" texto="No hay bultos verificados ni rechazados con estos filtros." />
      : (<>
        <GraficoBarras titulo="Valor perdido por local ($)" formato={pesos} horizontal
          datos={datos.por_sucursal.map((s) => ({ nombre: s.sucursal, valor: Number(s.valor_perdido),
            detalle: `${s.bultos_rechazados} de ${s.bultos_verificados + s.bultos_rechazados} bultos rechazados (${porcentaje(s.tasa_rechazo)})` }))} />
        <Tabla>
          <thead><tr><th>Local</th><th className="num">Bultos verificados</th><th className="num">Rechazados</th>
            <th className="num">% rechazo</th><th className="num">Unidades perdidas</th><th className="num">Valor perdido</th></tr></thead>
          <tbody>
            {datos.por_sucursal.map((s) => (
              <tr key={s.sucursal_id}><td>{s.sucursal}</td><td className="num">{s.bultos_verificados}</td><td className="num">{s.bultos_rechazados}</td>
                <td className="num">{porcentaje(s.tasa_rechazo)}</td><td className="num">{s.unidades_perdidas}</td>
                <td className="num">{pesos(s.valor_perdido)}</td></tr>
            ))}
          </tbody>
        </Tabla>
      </>)}
    {datos.filas.length > 0 && (<>
      <h2 className="titulo-seccion espacio-arriba">Qué se perdió</h2>
      <Tabla>
        <thead><tr><th>Fecha</th><th>Local</th><th>Bulto</th><th>Producto</th>
          <th className="num">Cantidad</th><th className="num">Valor</th><th>Motivo</th></tr></thead>
        <tbody>
          {datos.filas.map((f, i) => (
            <tr key={i}><td>{fecha(f.fecha_rechazo)}</td><td>{f.sucursal}</td>
              <td>#{f.bulto_id}<span className="secundario-texto">Remito #{f.remito_id} · <code>{f.nro_precinto}</code></span></td>
              <td>{f.nombre}</td><td className="num">{f.cantidad}</td>
              <td className="num">{pesos(f.valor_perdido)}</td><td>{f.observacion}</td></tr>
          ))}
        </tbody>
      </Tabla>
    </>)}
  </>);
}

function ReporteTransito({ datos }) {
  // Menos de una hora se lee mejor en minutos ("17 min" y no "0,28 h")
  const horas = (h) => (h === null || h === undefined ? "—"
    : h < 1 ? `${Math.round(h * 60)} min` : `${h.toLocaleString("es-AR")} h`);
  return (<>
    <Tarjetas items={[["Bultos recibidos", datos.bultos], ["Promedio general", horas(datos.horas_promedio_general)]]} />
    {datos.filas.length === 0
      ? <Vacio icono="camion" titulo="Todavía no se recibió ningún bulto" texto="Cuando un local reciba un envío, acá vas a ver cuánto tardó." />
      : (<>
        <GraficoBarras titulo="Tiempo promedio del CD a cada local" formato={horas} formatoEje={horas} horizontal
          datos={datos.filas.map((f) => ({ nombre: f.sucursal, valor: Number(f.horas_promedio),
            detalle: `${f.bultos} bultos · entre ${horas(f.horas_minimo)} y ${horas(f.horas_maximo)}` }))} />
        <Tabla>
          <thead><tr><th>Local</th><th className="num">Bultos</th><th className="num">Promedio</th><th className="num">Más rápido</th>
            <th className="num">Más lento</th></tr></thead>
          <tbody>
            {datos.filas.map((f) => (
              <tr key={f.sucursal_id}><td>{f.sucursal}</td><td className="num">{f.bultos}</td><td className="num"><strong>{horas(f.horas_promedio)}</strong></td>
                <td className="num">{horas(f.horas_minimo)}</td><td className="num">{horas(f.horas_maximo)}</td></tr>
            ))}
          </tbody>
        </Tabla>
      </>)}
  </>);
}
