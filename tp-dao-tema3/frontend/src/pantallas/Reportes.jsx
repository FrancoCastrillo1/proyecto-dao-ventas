// Pantalla de Reportes: los 7 reportes del backend (/reportes/...) con sus
// filtros. Cada cambio de filtro vuelve a consultar solo. Las cuentas las hace
// el backend; acá solo se muestran, con un gráfico arriba de cada tabla.
// Cada perfil ve los suyos según sus capacidades (el CD, los de logística; el
// local y el administrador, también los de ventas). Un local ve solo lo suyo
// (lo filtra el back), así que no se le muestra el filtro de local.
// "Descargar PDF" pide el mismo reporte, con los mismos filtros, en PDF.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import Icono from "../componentes/Icono.jsx";
import { puede } from "../componentes/Permisos.js";
import { Cargando, Segmentado, Vacio } from "../componentes/Controles.jsx";
import { GraficoBarras, agrupar } from "../componentes/Graficos.jsx";
import { fecha, nombreMedio, pesos, porcentaje } from "../formato.js";

// requiere: la capacidad que hace falta para ver el reporte (los de ventas, el
// CD no los ve; los más pedidos son de toda la red: CD y administrador).
// ranking: se elige cuántos mostrar (top 5, 10...). El primero que pueda ver
// cada perfil es el que se abre.
const REPORTES = [
  { valor: "ventas", texto: <><Icono nombre="plata" tamano={16} /> Ventas</>, pregunta: "¿Cuánto se vendió, dónde y cómo se cobró?", fechas: true, sucursal: true, requiere: "ve_ventas" },
  { valor: "productos-mas-vendidos", texto: <><Icono nombre="trofeo" tamano={16} /> Más vendidos</>, pregunta: "¿Qué productos se venden más y cuánto dejan?", fechas: true, sucursal: true, ranking: true, requiere: "ve_ventas" },
  { valor: "devoluciones", texto: <><Icono nombre="devolucion" tamano={16} /> Devoluciones</>, pregunta: "¿Qué se devuelve, cuánto y por qué?", fechas: true, sucursal: true, requiere: "ve_ventas" },
  { valor: "productos-mas-pedidos", texto: <><Icono nombre="pedido" tamano={16} /> Más pedidos</>, pregunta: "¿Qué piden más los locales y alcanza lo que hay en el CD?", fechas: true, sucursal: true, ranking: true, requiere: "ve_toda_la_red" },
  { valor: "existencias", texto: <><Icono nombre="caja" tamano={16} /> Existencias</>, pregunta: "¿Cuánto hay, cuánto vale y qué falta reponer?", ubicacion: true },
  { valor: "mermas", texto: <><Icono nombre="alerta" tamano={16} /> Mermas</>, pregunta: "¿Cuántos bultos llegaron con el precinto roto y cuánto se perdió?", fechas: true, sucursal: true },
  { valor: "tiempos-transito", texto: <><Icono nombre="reloj" tamano={16} /> Tiempos de envío</>, pregunta: "¿Cuánto tarda un bulto del CD a cada local?", fechas: true, sucursal: true },
];

const FILTROS_INICIALES = { desde: "", hasta: "", sucursal_id: "", ubicacion_id: "", agrupar: "dia", limite: "10", solo_bajo_minimo: false };

// Los filtros que aplican a este reporte, como parámetros de la URL
function parametrosDe(reporte, filtros) {
  const parametros = new URLSearchParams();
  if (reporte.fechas) {
    if (filtros.desde) parametros.set("desde", filtros.desde);
    if (filtros.hasta) parametros.set("hasta", filtros.hasta);
  }
  if (reporte.sucursal && filtros.sucursal_id) parametros.set("sucursal_id", filtros.sucursal_id);
  if (reporte.ubicacion && filtros.ubicacion_id) parametros.set("ubicacion_id", filtros.ubicacion_id);
  if (reporte.valor === "ventas") parametros.set("agrupar", filtros.agrupar);
  if (reporte.ranking) parametros.set("limite", filtros.limite);
  if (reporte.valor === "existencias" && filtros.solo_bajo_minimo) parametros.set("solo_bajo_minimo", "true");
  return parametros;
}

export default function Reportes({ usuario }) {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const disponibles = REPORTES.filter((r) => !r.requiere || puede(usuario, r.requiere));
  const [clave, setClave] = useState(disponibles[0].valor);
  const [filtros, setFiltros] = useState(FILTROS_INICIALES);
  const [datos, setDatos] = useState(null);

  const reporte = disponibles.find((r) => r.valor === clave);
  const veTodaLaRed = puede(usuario, "ve_toda_la_red");
  const cambiar = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const hayFiltros = filtros.desde || filtros.hasta || filtros.sucursal_id || filtros.ubicacion_id || filtros.solo_bajo_minimo;

  useEffect(() => {
    setDatos(null);
    ejecutar(async () => setDatos({ clave, ...(await api.obtener(`/reportes/${clave}?${parametrosDe(reporte, filtros)}`)) }))
      .then((ok) => { if (!ok) setDatos({ clave, error: true }); });  // el error lo muestra el aviso
  }, [clave, filtros]);

  function descargarPdf() {
    const parametros = parametrosDe(reporte, filtros);
    parametros.set("formato", "pdf");
    ejecutar(() => api.descargar(`/reportes/${clave}?${parametros}`), "Reporte descargado en PDF");
  }

  return (
    <section>
      <Cabecera icono="grafico" titulo="Reportes" subtitulo={reporte.pregunta}>
        <button className="secundario" onClick={descargarPdf} disabled={datos?.clave !== clave || datos.error}>
          <Icono nombre="descargar" tamano={16} /> Descargar PDF
        </button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <div className="barra">
        <Segmentado etiqueta="Reporte" valor={clave} alCambiar={setClave} opciones={disponibles} />
      </div>

      <div className="barra filtros">
        {reporte.fechas && (<>
          <label>Desde<input type="date" value={filtros.desde} onChange={cambiar("desde")} /></label>
          <label>Hasta<input type="date" value={filtros.hasta} onChange={cambiar("hasta")} /></label>
        </>)}
        {reporte.sucursal && veTodaLaRed && (
          <label>Local
            <select value={filtros.sucursal_id} onChange={cambiar("sucursal_id")}>
              <option value="">Todos los locales</option>
              {catalogos.sucursales.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </label>
        )}
        {reporte.ubicacion && (<>
          {veTodaLaRed && (
            <label>Ubicación
              <select value={filtros.ubicacion_id} onChange={cambiar("ubicacion_id")}>
                <option value="">Todas</option>
                {catalogos.ubicacionesActivas.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </select>
            </label>
          )}
          <label className="check">
            <input type="checkbox" checked={filtros.solo_bajo_minimo} onChange={cambiar("solo_bajo_minimo")} /> Solo lo que falta reponer
          </label>
        </>)}
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
        {hayFiltros && <button className="fantasma" onClick={() => setFiltros(FILTROS_INICIALES)}>Limpiar filtros</button>}
      </div>

      {datos?.clave !== clave ? <Cargando /> : !datos.error && (<>
        {clave === "ventas" && <ReporteVentas datos={datos} agrupado={filtros.agrupar} />}
        {clave === "productos-mas-vendidos" && <ReporteMasVendidos datos={datos} />}
        {clave === "devoluciones" && <ReporteDevoluciones datos={datos} />}
        {clave === "productos-mas-pedidos" && <ReporteMasPedidos datos={datos} />}
        {clave === "existencias" && <ReporteExistencias datos={datos} />}
        {clave === "mermas" && <ReporteMermas datos={datos} />}
        {clave === "tiempos-transito" && <ReporteTransito datos={datos} />}
      </>)}
    </section>
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

const unidades = (n) => `${n} u.`;

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
          <th className="num">Falta</th><th className="num">Valor</th></tr></thead>
        <tbody>
          {datos.filas.map((f, i) => (
            <tr key={i} className={f.bajo_minimo ? "fila-alerta" : ""}><td>{f.ubicacion}</td>
              <td>{f.nombre}<span className="secundario-texto">{f.codigo}</span></td>
              <td className="num">{f.cantidad}</td><td className="num">{f.stock_minimo}</td>
              <td className={`num ${f.faltante ? "falta" : ""}`}>{f.faltante || "—"}</td><td className="num">{pesos(f.valorizado)}</td></tr>
          ))}
        </tbody>
      </Tabla>
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
            detalle: `${s.bultos_rechazados} de ${s.bultos_verificados} bultos rechazados (${porcentaje(s.tasa_rechazo)})` }))} />
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
