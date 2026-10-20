// Pantalla de Stock: existencias de cada ubicación, compra al CD (lo único que
// mete mercadería desde afuera) y el libro de movimientos de cada producto.
// A una sucursal el stock le entra SOLO por bultos verificados (pantalla Logística).
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import EncabezadoPantalla from "../componentes/EncabezadoPantalla.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { fecha } from "../formato.js";

const COMPRA_VACIA = { producto_id: "", cantidad: "", referencia: "" };

export default function Stock() {
  const catalogos = useCatalogos();
  const [ubicacionId, setUbicacionId] = useState("");
  const [existencias, setExistencias] = useState([]);
  const [compra, setCompra] = useState(COMPRA_VACIA);
  const [movimientos, setMovimientos] = useState(null); // { producto, filas }
  const { aviso, ejecutar, limpiar } = useAviso();

  const ubicacion = catalogos.ubicacion(Number(ubicacionId));

  // Arranca mostrando el CD
  useEffect(() => {
    if (!ubicacionId && catalogos.ubicacionesActivas.length) {
      const cd = catalogos.ubicacionesActivas.find((u) => u.puede_despachar) ?? catalogos.ubicacionesActivas[0];
      setUbicacionId(String(cd.id));
    }
  }, [catalogos.ubicacionesActivas.length]);

  const cargar = () => ubicacionId && ejecutar(async () => setExistencias(await api.listar(`/stock/${ubicacionId}`)));
  useEffect(() => { cargar(); setMovimientos(null); }, [ubicacionId]);

  async function comprar(evento) {
    evento.preventDefault();
    const ok = await ejecutar(
      () => api.crear("/stock/ingresar", { ubicacion_id: ubicacionId, ...compra }),
      "Compra registrada en el CD",
    );
    if (ok) { setCompra(COMPRA_VACIA); cargar(); }
  }

  async function verMovimientos(fila) {
    await ejecutar(async () => setMovimientos({
      producto: fila.nombre,
      filas: await api.listar(`/stock/${ubicacionId}/${fila.producto_id}/movimientos`),
    }));
  }

  return (
    <section>
      <EncabezadoPantalla id="stock" icono="📦" titulo="Stock"
        descripcion="Cuánto hay de cada producto en cada lugar. Al CD la mercadería entra por compras; a los locales, solo por bultos verificados."
        pasos={[
          "Elegí una ubicación para ver sus existencias. En rojo, lo que está bajo el mínimo.",
          "Con el CD elegido aparece el formulario para registrar una compra a un proveedor.",
          "«Movimientos» muestra cada entrada y salida del producto: compras, despachos, recepciones, ventas y devoluciones.",
        ]} />
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <div className="barra-filtro">
        <label>Ubicación
          <select value={ubicacionId} onChange={(e) => setUbicacionId(e.target.value)}>
            {catalogos.ubicacionesActivas.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
          </select>
        </label>
      </div>

      {/* Se pregunta por la capacidad (como el backend), no por el tipo */}
      {ubicacion?.puede_despachar && (
        <form className="formulario" onSubmit={comprar}>
          <label>Producto comprado
            <select value={compra.producto_id} onChange={(e) => setCompra({ ...compra, producto_id: e.target.value })}>
              <option value="">— elegir —</option>
              {catalogos.productosActivos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}
            </select>
          </label>
          <label>Cantidad
            <input value={compra.cantidad} onChange={(e) => setCompra({ ...compra, cantidad: e.target.value })}
              placeholder="Entero > 0 (ej: 100)" />
          </label>
          <label>Referencia (opcional)
            <input value={compra.referencia} onChange={(e) => setCompra({ ...compra, referencia: e.target.value })}
              placeholder="Ej: Factura A-0001" />
          </label>
          <div className="acciones"><button type="submit">Registrar compra</button></div>
        </form>
      )}
      {ubicacion && !ubicacion.puede_despachar && (
        <p className="nota">A una sucursal la mercadería le entra solo por bultos verificados (pestaña Logística).</p>
      )}

      <div className="tabla-scroll">
        <table>
          <thead>
            <tr><th>Código</th><th>Producto</th><th className="num">Cantidad</th><th className="num">Mínimo</th><th></th><th></th></tr>
          </thead>
          <tbody>
            {existencias.map((f) => (
              <tr key={f.producto_id}>
                <td><code>{f.codigo}</code></td>
                <td>{f.nombre}</td>
                <td className="num">{f.cantidad}</td>
                <td className="num">{f.stock_minimo}</td>
                <td>{f.bajo_minimo && <span className="estado estado-rojo">Bajo mínimo</span>}</td>
                <td className="botones-fila">
                  <button className="secundario" onClick={() => verMovimientos(f)}>Movimientos</button>
                </td>
              </tr>
            ))}
            {existencias.length === 0 && <tr><td colSpan="6" className="vacio">Sin productos</td></tr>}
          </tbody>
        </table>
      </div>

      {movimientos && (
        <div className="panel">
          <h3>Movimientos de “{movimientos.producto}” en {ubicacion?.nombre}
            <button className="boton-cerrar" onClick={() => setMovimientos(null)} aria-label="Cerrar">×</button>
          </h3>
          <table>
            <thead><tr><th>Fecha</th><th>Tipo</th><th className="num">Cantidad</th><th>Referencia</th></tr></thead>
            <tbody>
              {movimientos.filas.map((m, i) => (
                <tr key={i}>
                  <td>{fecha(m.fecha)}</td>
                  <td>{m.tipo}</td>
                  <td className={`num ${m.cantidad < 0 ? "negativo" : ""}`}>{m.cantidad > 0 ? `+${m.cantidad}` : m.cantidad}</td>
                  <td>{m.referencia || "—"}</td>
                </tr>
              ))}
              {movimientos.filas.length === 0 && <tr><td colSpan="4" className="vacio">Sin movimientos</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
