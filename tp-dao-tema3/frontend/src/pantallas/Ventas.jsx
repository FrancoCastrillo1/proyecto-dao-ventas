// Pantalla de Ventas: vender (uno o más productos) con un medio de pago,
// ver el comprobante, devolver productos de una venta registrada y ver la caja
// de cada local. Los medios de pago y sus recargos/descuentos vienen del
// backend (patrón Strategy): el front no los conoce.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import LineasProductos, { aItems, LINEA_VACIA } from "../componentes/LineasProductos.jsx";
import { fecha, pesos } from "../formato.js";

export default function Ventas() {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const [medios, setMedios] = useState([]);
  const [ventas, setVentas] = useState([]);
  const [caja, setCaja] = useState(null);
  const [sucursal, setSucursal] = useState("");
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);
  const [medio, setMedio] = useState("");
  const [entregado, setEntregado] = useState("");
  const [ultima, setUltima] = useState(null);
  const [abierta, setAbierta] = useState(null);

  const locales = catalogos.ubicacionesActivas.filter((u) => u.puede_vender);

  useEffect(() => { ejecutar(async () => setMedios(await api.listar("/ventas/medios-pago"))); }, []);

  const cargar = () => ejecutar(async () => {
    const lista = await api.listar(`/ventas${sucursal ? `?sucursal_id=${sucursal}` : ""}`);
    setVentas([...lista].reverse());
    setAbierta((actual) => (actual ? lista.find((v) => v.id === actual.id) ?? null : null));
    setCaja(sucursal ? await api.obtener(`/caja/${sucursal}`) : null);
  });
  useEffect(() => { cargar(); }, [sucursal]);

  async function vender(evento) {
    evento.preventDefault();
    let venta = null;
    const ok = await ejecutar(async () => {
      venta = await api.crear("/ventas", {
        sucursal_id: sucursal, items: aItems(lineas), medio_pago: medio,
        monto_entregado: medio === "EFECTIVO" && entregado !== "" ? entregado : null,
      });
    }, "Venta registrada");
    if (ok) {
      setUltima(venta);
      setLineas([{ ...LINEA_VACIA }]);
      setEntregado("");
      cargar();
    }
  }

  const etiquetaMedio = (m) => {
    const ajuste = m.porcentaje_ajuste;
    return `${m.nombre}${ajuste < 0 ? ` (${ajuste}% descuento)` : ajuste > 0 ? ` (+${ajuste}% recargo)` : ""}`;
  };

  return (
    <section>
      <h2>Ventas</h2>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <form className="formulario formulario-ancho" onSubmit={vender}>
        <label>Sucursal
          <select value={sucursal} onChange={(e) => setSucursal(e.target.value)}>
            <option value="">— elegir —</option>
            {locales.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
          </select>
        </label>
        <LineasProductos lineas={lineas} alCambiar={setLineas} productos={catalogos.productosActivos} />
        <label>Medio de pago
          <select value={medio} onChange={(e) => setMedio(e.target.value)}>
            <option value="">— elegir —</option>
            {medios.map((m) => <option key={m.nombre} value={m.nombre}>{etiquetaMedio(m)}</option>)}
          </select>
        </label>
        {medio === "EFECTIVO" && (
          <label>Monto entregado (opcional, para el vuelto)
            <input value={entregado} onChange={(e) => setEntregado(e.target.value)} placeholder="Ej: 5000" />
          </label>
        )}
        <div className="acciones"><button type="submit">Vender</button></div>
      </form>

      {ultima && (
        <div className="panel comprobante">
          <h3>Comprobante {ultima.comprobante}
            <button className="boton-cerrar" onClick={() => setUltima(null)} aria-label="Cerrar">×</button>
          </h3>
          <DetalleVenta venta={ultima} catalogos={catalogos} />
        </div>
      )}

      {caja && (
        <div className="tarjetas">
          {Object.entries(caja.por_medio).map(([nombre, importe]) => (
            <div key={nombre} className="tarjeta"><span>{nombre}</span><strong>{pesos(importe)}</strong></div>
          ))}
          <div className="tarjeta tarjeta-total"><span>Caja de {catalogos.nombreUbicacion(caja.sucursal_id)}</span>
            <strong>{pesos(caja.saldo)}</strong></div>
        </div>
      )}

      <div className="tabla-scroll">
        <table>
          <thead>
            <tr><th>Comprobante</th><th>Fecha</th><th>Sucursal</th><th>Medio</th>
              <th className="num">Total</th><th className="num">Reintegrado</th><th></th></tr>
          </thead>
          <tbody>
            {ventas.map((v) => (
              <tr key={v.id} className={abierta?.id === v.id ? "fila-seleccionada" : ""}>
                <td><code>{v.comprobante}</code></td>
                <td>{fecha(v.fecha)}</td>
                <td>{catalogos.nombreUbicacion(v.sucursal_id)}</td>
                <td>{v.medio_pago}</td>
                <td className="num">{pesos(v.total)}</td>
                <td className="num">{v.total_reintegrado ? pesos(v.total_reintegrado) : "—"}</td>
                <td className="botones-fila"><button className="secundario" onClick={() => setAbierta(v)}>Ver / devolver</button></td>
              </tr>
            ))}
            {ventas.length === 0 && <tr><td colSpan="7" className="vacio">No hay ventas{sucursal ? " en esta sucursal" : ""}</td></tr>}
          </tbody>
        </table>
      </div>

      {abierta && (
        <PanelVenta venta={abierta} catalogos={catalogos} ejecutar={ejecutar} alCambiar={cargar} alCerrar={() => setAbierta(null)} />
      )}
    </section>
  );
}

function DetalleVenta({ venta, catalogos }) {
  return (
    <>
      <table>
        <thead><tr><th>Producto</th><th className="num">Cantidad</th><th className="num">Precio</th><th className="num">Subtotal</th></tr></thead>
        <tbody>
          {venta.detalles.map((d) => (
            <tr key={d.producto_id}>
              <td>{catalogos.nombreProducto(d.producto_id)}</td>
              <td className="num">{d.cantidad}</td>
              <td className="num">{pesos(d.precio_unitario)}</td>
              <td className="num">{pesos(d.subtotal)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="totales">
        Subtotal {pesos(venta.subtotal)} · {venta.medio_pago} ({venta.porcentaje_ajuste}%) · <strong>Total {pesos(venta.total)}</strong>
        {venta.vuelto > 0 && <> · Vuelto {pesos(venta.vuelto)}</>}
      </p>
    </>
  );
}

function PanelVenta({ venta, catalogos, ejecutar, alCambiar, alCerrar }) {
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);
  const [motivo, setMotivo] = useState("");
  const vendidos = venta.detalles.map((d) => catalogos.productos.find((p) => p.id === d.producto_id)).filter(Boolean);

  async function devolver(evento) {
    evento.preventDefault();
    const ok = await ejecutar(
      () => api.crear(`/ventas/${venta.id}/devoluciones`, { items: aItems(lineas), motivo }),
      "Devolución registrada: el stock volvió al local y se reintegró el dinero",
    );
    if (ok) { setLineas([{ ...LINEA_VACIA }]); setMotivo(""); alCambiar(); }
  }

  return (
    <div className="panel">
      <h3>Venta {venta.comprobante} · {catalogos.nombreUbicacion(venta.sucursal_id)}
        <button className="boton-cerrar" onClick={alCerrar} aria-label="Cerrar">×</button>
      </h3>
      <DetalleVenta venta={venta} catalogos={catalogos} />

      {venta.devoluciones.length > 0 && (
        <ul>
          {venta.devoluciones.map((d) => (
            <li key={d.id}>{fecha(d.fecha)} · {d.motivo} · {pesos(d.importe)} · {d.detalles.map((x) =>
              `${x.cantidad} × ${catalogos.nombreProducto(x.producto_id)}`).join(", ")}</li>
          ))}
        </ul>
      )}

      <form className="formulario formulario-ancho" onSubmit={devolver}>
        <span className="nota">Devolver productos de esta venta:</span>
        <LineasProductos lineas={lineas} alCambiar={setLineas} productos={vendidos} />
        <label>Motivo<input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej: Producto vencido" /></label>
        <div className="acciones"><button type="submit">Registrar devolución</button></div>
      </form>
    </div>
  );
}
