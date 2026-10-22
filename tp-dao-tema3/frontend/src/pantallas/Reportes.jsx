// Pantalla de Reportes: los 5 reportes del backend (/reportes/...) con sus
// filtros. Cada cambio de filtro vuelve a consultar solo. Las cuentas las hace
// el backend; acá solo se muestran. Un local ve solo los suyos (lo filtra el
// back), así que no se le muestra el filtro de local.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { puede } from "../componentes/Permisos.js";
import { Cargando, Segmentado, Vacio } from "../componentes/Controles.jsx";
import { fecha, nombreMedio, pesos, porcentaje } from "../formato.js";

const REPORTES = [
  { valor: "ventas", texto: "💰 Ventas", pregunta: "¿Cuánto se vendió, dónde y cómo se cobró?", fechas: true, sucursal: true },
  { valor: "productos-mas-vendidos", texto: "🏆 Más vendidos", pregunta: "¿Qué productos se venden más y cuánto dejan?", fechas: true, sucursal: true },
  { valor: "existencias", texto: "📦 Existencias", pregunta: "¿Cuánto hay, cuánto vale y qué falta reponer?", ubicacion: true },
  { valor: "mermas", texto: "⚠️ Mermas", pregunta: "¿Cuántos bultos llegaron con el precinto roto y cuánto se perdió?", fechas: true, sucursal: true },
  { valor: "tiempos-transito", texto: "⏱️ Tiempos de envío", pregunta: "¿Cuánto tarda un bulto del CD a cada local?", fechas: true, sucursal: true },
];

const FILTROS_INICIALES = { desde: "", hasta: "", sucursal_id: "", ubicacion_id: "", agrupar: "dia", limite: "10", solo_bajo_minimo: false };

export default function Reportes({ usuario }) {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const [clave, setClave] = useState("ventas");
  const [filtros, setFiltros] = useState(FILTROS_INICIALES);
  const [datos, setDatos] = useState(null);

  const reporte = REPORTES.find((r) => r.valor === clave);
  const veTodaLaRed = puede(usuario, "ve_toda_la_red");
  const cambiar = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const hayFiltros = filtros.desde || filtros.hasta || filtros.sucursal_id || filtros.ubicacion_id || filtros.solo_bajo_minimo;

  useEffect(() => {
    const parametros = new URLSearchParams();
    if (reporte.fechas) {
      if (filtros.desde) parametros.set("desde", filtros.desde);
      if (filtros.hasta) parametros.set("hasta", filtros.hasta);
    }
    if (reporte.sucursal && filtros.sucursal_id) parametros.set("sucursal_id", filtros.sucursal_id);
    if (reporte.ubicacion && filtros.ubicacion_id) parametros.set("ubicacion_id", filtros.ubicacion_id);
    if (clave === "ventas") parametros.set("agrupar", filtros.agrupar);
    if (clave === "productos-mas-vendidos") parametros.set("limite", filtros.limite);
    if (clave === "existencias" && filtros.solo_bajo_minimo) parametros.set("solo_bajo_minimo", "true");
    setDatos(null);
    ejecutar(async () => setDatos({ clave, ...(await api.obtener(`/reportes/${clave}?${parametros}`)) }))
      .then((ok) => { if (!ok) setDatos({ clave, error: true }); });  // el error lo muestra el aviso
  }, [clave, filtros]);

  return (
    <section>
      <Cabecera icono="📊" titulo="Reportes" subtitulo={reporte.pregunta} />
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <div className="barra">
        <Segmentado etiqueta="Reporte" valor={clave} alCambiar={setClave} opciones={REPORTES} />
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
        {clave === "productos-mas-vendidos" && (
          <label>Mostrar
            <select value={filtros.limite} onChange={cambiar("limite")}>
              <option value="5">Top 5</option><option value="10">Top 10</option><option value="20">Top 20</option><option value="100">Todos</option>
            </select>
          </label>
        )}
        {hayFiltros && <button className="fantasma" onClick={() => setFiltros(FILTROS_INICIALES)}>Limpiar filtros</button>}
      </div>

      {datos?.clave !== clave ? <Cargando /> : !datos.error && (<>
        {clave === "ventas" && <ReporteVentas datos={datos} />}
        {clave === "productos-mas-vendidos" && <ReporteMasVendidos datos={datos} />}
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

const SIN_DATOS = <Vacio icono="🔍" titulo="No hay datos para estos filtros" texto="Probá con otras fechas o con todos los locales." />;

function ReporteVentas({ datos }) {
  return (<>
    <Tarjetas items={[
      ["Ventas", datos.cantidad_ventas], ["Vendido", pesos(datos.total_vendido)],
      ["Devuelto", pesos(datos.total_devuelto)], ["Ingreso neto", pesos(datos.total_neto)],
    ]} />
    {datos.filas.length === 0 ? SIN_DATOS : (
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
    )}
  </>);
}

function ReporteMasVendidos({ datos }) {
  const maximo = Math.max(1, ...datos.filas.map((f) => f.unidades));
  return (<>
    <Tarjetas items={[["Ingreso", pesos(datos.total_ingreso)], ["Ganancia (margen)", pesos(datos.total_margen)]]} />
    {datos.filas.length === 0 ? SIN_DATOS : (
      <Tabla>
        <thead><tr><th>#</th><th>Producto</th><th>Unidades</th><th className="num">Ingreso</th>
          <th className="num">Costo</th><th className="num">Ganancia</th><th className="num">Margen</th></tr></thead>
        <tbody>
          {datos.filas.map((f, i) => (
            <tr key={f.producto_id}>
              <td>{i + 1}</td>
              <td>{f.nombre}<span className="secundario-texto">{f.codigo}</span></td>
              <td><div className="barrita"><span style={{ width: `${(f.unidades / maximo) * 100}%` }} /><b>{f.unidades}</b></div></td>
              <td className="num">{pesos(f.ingreso)}</td><td className="num">{pesos(f.costo)}</td>
              <td className={`num ${f.margen < 0 ? "negativo" : ""}`}>{pesos(f.margen)}</td>
              <td className={`num ${f.margen < 0 ? "negativo" : ""}`}>{porcentaje(f.margen_porcentaje)}</td>
            </tr>
          ))}
        </tbody>
      </Tabla>
    )}
  </>);
}

function ReporteExistencias({ datos }) {
  const tarjetas = Object.entries(datos.valorizado_por_ubicacion).map(([nombre, valor]) => [nombre, pesos(valor)]);
  return (<>
    <Tarjetas items={[...tarjetas, ["Productos para reponer", datos.productos_bajo_minimo], ["Inventario valorizado", pesos(datos.valorizado_total)]]} />
    {datos.filas.length === 0 ? SIN_DATOS : (
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
    )}
  </>);
}

function ReporteMermas({ datos }) {
  return (<>
    <Tarjetas items={[["Bultos rechazados", datos.por_sucursal.reduce((suma, s) => suma + s.bultos_rechazados, 0)],
      ["Valor perdido", pesos(datos.valor_perdido_total)]]} />
    {datos.por_sucursal.length === 0
      ? <Vacio icono="✅" titulo="Sin mermas" texto="No hay bultos verificados ni rechazados con estos filtros." />
      : (
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
      )}
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
  const horas = (h) => (h === null || h === undefined ? "—" : `${h.toLocaleString("es-AR")} h`);
  return (<>
    <Tarjetas items={[["Bultos recibidos", datos.bultos], ["Promedio general", horas(datos.horas_promedio_general)]]} />
    {datos.filas.length === 0
      ? <Vacio icono="🚚" titulo="Todavía no se recibió ningún bulto" texto="Cuando un local reciba un envío, acá vas a ver cuánto tardó." />
      : (
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
      )}
  </>);
}
