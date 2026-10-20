// Pantalla de Reportes: los 5 reportes del backend (/reportes/...) con sus
// filtros. Las cuentas las hace el backend; acá solo se muestran.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { fecha, pesos, porcentaje } from "../formato.js";

const REPORTES = [
  { clave: "ventas", titulo: "Ventas por período, local y medio de pago", fechas: true, sucursal: true },
  { clave: "productos-mas-vendidos", titulo: "Productos más vendidos y margen", fechas: true, sucursal: true },
  { clave: "existencias", titulo: "Existencias y productos bajo mínimo", ubicacion: true },
  { clave: "mermas", titulo: "Bultos rechazados y mermas", fechas: true, sucursal: true },
  { clave: "tiempos-transito", titulo: "Tiempo de tránsito CD → locales", fechas: true, sucursal: true },
];

export default function Reportes() {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const [clave, setClave] = useState("ventas");
  const [filtros, setFiltros] = useState({ desde: "", hasta: "", sucursal_id: "", ubicacion_id: "", agrupar: "dia",
    limite: "10", solo_bajo_minimo: false });
  const [datos, setDatos] = useState(null);

  const reporte = REPORTES.find((r) => r.clave === clave);
  const cambiar = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function consultar() {
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
    await ejecutar(async () => setDatos(await api.obtener(`/reportes/${clave}?${parametros}`)));
  }
  useEffect(() => { consultar(); }, [clave]);

  return (
    <section>
      <h2>Reportes</h2>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <nav className="selector-reportes">
        {REPORTES.map((r) => (
          <button key={r.clave} className={r.clave === clave ? "" : "secundario"} onClick={() => setClave(r.clave)}>{r.titulo}</button>
        ))}
      </nav>

      <div className="barra-filtro">
        {reporte.fechas && (<>
          <label>Desde<input type="date" value={filtros.desde} onChange={cambiar("desde")} /></label>
          <label>Hasta<input type="date" value={filtros.hasta} onChange={cambiar("hasta")} /></label>
        </>)}
        {reporte.sucursal && (
          <label>Sucursal
            <select value={filtros.sucursal_id} onChange={cambiar("sucursal_id")}>
              <option value="">Todas</option>
              {catalogos.sucursales.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </label>
        )}
        {reporte.ubicacion && (<>
          <label>Ubicación
            <select value={filtros.ubicacion_id} onChange={cambiar("ubicacion_id")}>
              <option value="">Todas</option>
              {catalogos.ubicacionesActivas.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </label>
          <label className="check-bajas">
            <input type="checkbox" checked={filtros.solo_bajo_minimo} onChange={cambiar("solo_bajo_minimo")} /> Solo bajo mínimo
          </label>
        </>)}
        {clave === "ventas" && (
          <label>Agrupar por
            <select value={filtros.agrupar} onChange={cambiar("agrupar")}>
              <option value="dia">Día</option><option value="mes">Mes</option><option value="total">Total del período</option>
            </select>
          </label>
        )}
        {clave === "productos-mas-vendidos" && (
          <label>Cuántos<input value={filtros.limite} onChange={cambiar("limite")} placeholder="1 a 100" /></label>
        )}
        <button onClick={consultar}>Consultar</button>
      </div>

      {datos && clave === "ventas" && <ReporteVentas datos={datos} />}
      {datos && clave === "productos-mas-vendidos" && <ReporteMasVendidos datos={datos} />}
      {datos && clave === "existencias" && <ReporteExistencias datos={datos} />}
      {datos && clave === "mermas" && <ReporteMermas datos={datos} />}
      {datos && clave === "tiempos-transito" && <ReporteTransito datos={datos} />}
    </section>
  );
}

function Tarjetas({ items }) {
  return (
    <div className="tarjetas">
      {items.map(([titulo, valor], i) => (
        <div key={titulo} className={`tarjeta ${i === items.length - 1 ? "tarjeta-total" : ""}`}><span>{titulo}</span><strong>{valor}</strong></div>
      ))}
    </div>
  );
}

function Vacio({ columnas, texto = "No hay datos para estos filtros" }) {
  return <tr><td colSpan={columnas} className="vacio">{texto}</td></tr>;
}

function ReporteVentas({ datos }) {
  return (<>
    <Tarjetas items={[
      ["Ventas", datos.cantidad_ventas], ["Vendido", pesos(datos.total_vendido)],
      ["Devuelto", pesos(datos.total_devuelto)], ["Ingreso neto", pesos(datos.total_neto)],
    ]} />
    <div className="tabla-scroll"><table>
      <thead><tr><th>Período</th><th>Sucursal</th><th>Medio de pago</th><th className="num">Ventas</th>
        <th className="num">Vendido</th><th className="num">Devuelto</th><th className="num">Neto</th></tr></thead>
      <tbody>
        {datos.filas.map((f, i) => (
          <tr key={i}><td>{f.periodo}</td><td>{f.sucursal}</td><td>{f.medio_pago}</td><td className="num">{f.cantidad_ventas}</td>
            <td className="num">{pesos(f.vendido)}</td><td className="num">{pesos(f.devuelto)}</td><td className="num">{pesos(f.neto)}</td></tr>
        ))}
        {datos.filas.length === 0 && <Vacio columnas={7} />}
      </tbody>
    </table></div>
  </>);
}

function ReporteMasVendidos({ datos }) {
  return (<>
    <Tarjetas items={[["Ingreso", pesos(datos.total_ingreso)], ["Margen total", pesos(datos.total_margen)]]} />
    <div className="tabla-scroll"><table>
      <thead><tr><th>#</th><th>Código</th><th>Producto</th><th className="num">Unidades</th><th className="num">Ingreso</th>
        <th className="num">Costo</th><th className="num">Margen</th><th className="num">Margen %</th></tr></thead>
      <tbody>
        {datos.filas.map((f, i) => (
          <tr key={f.producto_id}><td>{i + 1}</td><td><code>{f.codigo}</code></td><td>{f.nombre}</td><td className="num">{f.unidades}</td>
            <td className="num">{pesos(f.ingreso)}</td><td className="num">{pesos(f.costo)}</td>
            <td className={`num ${f.margen < 0 ? "negativo" : ""}`}>{pesos(f.margen)}</td>
            <td className={`num ${f.margen < 0 ? "negativo" : ""}`}>{porcentaje(f.margen_porcentaje)}</td></tr>
        ))}
        {datos.filas.length === 0 && <Vacio columnas={8} />}
      </tbody>
    </table></div>
  </>);
}

function ReporteExistencias({ datos }) {
  const tarjetas = Object.entries(datos.valorizado_por_ubicacion).map(([nombre, valor]) => [nombre, pesos(valor)]);
  return (<>
    <Tarjetas items={[...tarjetas, ["Bajo mínimo", datos.productos_bajo_minimo], ["Inventario valorizado", pesos(datos.valorizado_total)]]} />
    <div className="tabla-scroll"><table>
      <thead><tr><th>Ubicación</th><th>Código</th><th>Producto</th><th className="num">Cantidad</th><th className="num">Mínimo</th>
        <th className="num">Faltante</th><th className="num">Valorizado</th></tr></thead>
      <tbody>
        {datos.filas.map((f, i) => (
          <tr key={i} className={f.bajo_minimo ? "fila-alerta" : ""}><td>{f.ubicacion}</td><td><code>{f.codigo}</code></td><td>{f.nombre}</td>
            <td className="num">{f.cantidad}</td><td className="num">{f.stock_minimo}</td>
            <td className="num">{f.faltante || "—"}</td><td className="num">{pesos(f.valorizado)}</td></tr>
        ))}
        {datos.filas.length === 0 && <Vacio columnas={7} />}
      </tbody>
    </table></div>
  </>);
}

function ReporteMermas({ datos }) {
  return (<>
    <Tarjetas items={[["Valor perdido", pesos(datos.valor_perdido_total)]]} />
    <div className="tabla-scroll"><table>
      <thead><tr><th>Sucursal</th><th className="num">Bultos verificados</th><th className="num">Rechazados</th>
        <th className="num">Tasa de rechazo</th><th className="num">Unidades perdidas</th><th className="num">Valor perdido</th></tr></thead>
      <tbody>
        {datos.por_sucursal.map((s) => (
          <tr key={s.sucursal_id}><td>{s.sucursal}</td><td className="num">{s.bultos_verificados}</td><td className="num">{s.bultos_rechazados}</td>
            <td className="num">{porcentaje(s.tasa_rechazo)}</td><td className="num">{s.unidades_perdidas}</td>
            <td className="num">{pesos(s.valor_perdido)}</td></tr>
        ))}
        {datos.por_sucursal.length === 0 && <Vacio columnas={6} texto="No hay bultos verificados ni rechazados" />}
      </tbody>
    </table></div>
    <h3>Detalle de lo rechazado</h3>
    <div className="tabla-scroll"><table>
      <thead><tr><th>Fecha</th><th>Sucursal</th><th>Remito</th><th>Bulto</th><th>Precinto</th><th>Producto</th>
        <th className="num">Cantidad</th><th className="num">Valor</th><th>Motivo</th></tr></thead>
      <tbody>
        {datos.filas.map((f, i) => (
          <tr key={i}><td>{fecha(f.fecha_rechazo)}</td><td>{f.sucursal}</td><td>#{f.remito_id}</td><td>#{f.bulto_id}</td>
            <td><code>{f.nro_precinto}</code></td><td>{f.nombre}</td><td className="num">{f.cantidad}</td>
            <td className="num">{pesos(f.valor_perdido)}</td><td>{f.observacion}</td></tr>
        ))}
        {datos.filas.length === 0 && <Vacio columnas={9} texto="No hubo bultos rechazados" />}
      </tbody>
    </table></div>
  </>);
}

function ReporteTransito({ datos }) {
  const horas = (h) => (h === null || h === undefined ? "—" : `${h.toLocaleString("es-AR")} h`);
  return (<>
    <Tarjetas items={[["Bultos recibidos", datos.bultos], ["Promedio general", horas(datos.horas_promedio_general)]]} />
    <div className="tabla-scroll"><table>
      <thead><tr><th>Sucursal</th><th className="num">Bultos</th><th className="num">Promedio</th><th className="num">Mínimo</th>
        <th className="num">Máximo</th></tr></thead>
      <tbody>
        {datos.filas.map((f) => (
          <tr key={f.sucursal_id}><td>{f.sucursal}</td><td className="num">{f.bultos}</td><td className="num">{horas(f.horas_promedio)}</td>
            <td className="num">{horas(f.horas_minimo)}</td><td className="num">{horas(f.horas_maximo)}</td></tr>
        ))}
        {datos.filas.length === 0 && <Vacio columnas={5} texto="Todavía no se recibió ningún bulto" />}
      </tbody>
    </table></div>
  </>);
}
