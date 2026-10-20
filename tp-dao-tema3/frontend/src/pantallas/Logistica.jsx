// Pantalla de Logística: el circuito completo de reposición CD → sucursal.
//   1. Pedido de una sucursal        2. El CD consolida pedidos en una orden
//   3. Un remito por sucursal         4. Bultos: precintar, despachar, recibir, verificar
// Cada bulto muestra solo las acciones de su estado (patrón State del backend),
// y el backend igual rechaza cualquier transición inválida.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import Estado from "../componentes/Estado.jsx";
import LineasProductos, { aItems, LINEA_VACIA } from "../componentes/LineasProductos.jsx";
import { fecha } from "../formato.js";

export default function Logistica() {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const [pedidos, setPedidos] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [remitos, setRemitos] = useState([]);
  const [remitoAbierto, setRemitoAbierto] = useState(null);

  // Formularios
  const [sucursalPedido, setSucursalPedido] = useState("");
  const [lineasPedido, setLineasPedido] = useState([{ ...LINEA_VACIA }]);
  const [seleccionados, setSeleccionados] = useState([]);

  const cargar = () => ejecutar(async () => {
    setPedidos(await api.listar("/pedidos"));
    setOrdenes(await api.listar("/ordenes"));
    const lista = await api.listar("/remitos");
    setRemitos(lista);
    setRemitoAbierto((actual) => (actual ? lista.find((r) => r.id === actual.id) ?? null : null));
  });
  useEffect(() => { cargar(); }, []);

  // Ejecuta una acción y, si sale bien, recarga todo
  async function accion(hacer, textoExito) {
    if (await ejecutar(hacer, textoExito)) await cargar();
  }

  async function crearPedido(evento) {
    evento.preventDefault();
    await accion(() => api.crear("/pedidos", { sucursal_id: sucursalPedido, items: aItems(lineasPedido) }), "Pedido creado");
    setLineasPedido([{ ...LINEA_VACIA }]);
  }

  async function crearOrden() {
    await accion(() => api.crear("/ordenes", { pedido_ids: seleccionados }), "Pedidos consolidados en una orden");
    setSeleccionados([]);
  }

  const alternar = (id) => setSeleccionados((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const pendientes = pedidos.filter((p) => p.estado === "PENDIENTE");
  const tieneRemito = (ordenId, sucursalId) => remitos.some((r) => r.orden_id === ordenId && r.destino_id === sucursalId);

  return (
    <section>
      <h2>Logística: reposición CD → sucursales</h2>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      {/* ---------------------------------------------------------- 1. Pedido */}
      <h3 className="paso">1 · Pedido de una sucursal</h3>
      <form className="formulario formulario-ancho" onSubmit={crearPedido}>
        <label>Sucursal que pide
          <select value={sucursalPedido} onChange={(e) => setSucursalPedido(e.target.value)}>
            <option value="">— elegir —</option>
            {catalogos.sucursales.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
          </select>
        </label>
        <LineasProductos lineas={lineasPedido} alCambiar={setLineasPedido} productos={catalogos.productosActivos} />
        <div className="acciones"><button type="submit">Crear pedido</button></div>
      </form>

      {/* --------------------------------------------------- 2. Consolidación */}
      <h3 className="paso">2 · El CD consolida los pedidos pendientes en una orden</h3>
      <div className="tabla-scroll">
        <table>
          <thead><tr><th></th><th>Pedido</th><th>Sucursal</th><th>Fecha</th><th>Productos</th></tr></thead>
          <tbody>
            {pendientes.map((p) => (
              <tr key={p.id}>
                <td><input type="checkbox" checked={seleccionados.includes(p.id)} onChange={() => alternar(p.id)}
                  aria-label={`Elegir pedido ${p.id}`} /></td>
                <td>#{p.id}</td>
                <td>{catalogos.nombreUbicacion(p.sucursal_id)}</td>
                <td>{fecha(p.fecha)}</td>
                <td>{p.items.map((i) => `${i.cantidad} × ${catalogos.nombreProducto(i.producto_id)}`).join(", ")}</td>
              </tr>
            ))}
            {pendientes.length === 0 && <tr><td colSpan="5" className="vacio">No hay pedidos pendientes</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="barra-filtro">
        <button onClick={crearOrden} disabled={seleccionados.length === 0}>
          Consolidar {seleccionados.length || ""} pedido{seleccionados.length === 1 ? "" : "s"} en una orden
        </button>
      </div>

      {/* ----------------------------------------------------- 3. Órdenes */}
      <h3 className="paso">3 · Órdenes: un remito por cada sucursal</h3>
      <div className="tabla-scroll">
        <table>
          <thead><tr><th>Orden</th><th>Fecha</th><th>Estado</th><th>A preparar</th><th>Remitos por sucursal</th></tr></thead>
          <tbody>
            {ordenes.map((o) => (
              <tr key={o.id}>
                <td>#{o.id}</td>
                <td>{fecha(o.fecha)}</td>
                <td><Estado valor={o.estado} /></td>
                <td>{o.total_por_producto.map((i) => `${i.cantidad} × ${catalogos.nombreProducto(i.producto_id)}`).join(", ")}</td>
                <td className="botones-fila botones-izquierda">
                  {[...new Set(o.pedidos.map((p) => p.sucursal_id))].map((sucursalId) => (
                    tieneRemito(o.id, sucursalId)
                      ? <span key={sucursalId} className="nota">✓ {catalogos.nombreUbicacion(sucursalId)}</span>
                      : <button key={sucursalId} className="secundario"
                          onClick={() => accion(() => api.crear("/remitos", { orden_id: o.id, destino_id: sucursalId }),
                            "Remito creado")}>
                          Remito para {catalogos.nombreUbicacion(sucursalId)}
                        </button>
                  ))}
                </td>
              </tr>
            ))}
            {ordenes.length === 0 && <tr><td colSpan="5" className="vacio">Todavía no hay órdenes</td></tr>}
          </tbody>
        </table>
      </div>

      {/* ----------------------------------------------------- 4. Remitos */}
      <h3 className="paso">4 · Remitos y bultos</h3>
      <div className="tabla-scroll">
        <table>
          <thead><tr><th>Remito</th><th>Orden</th><th>Destino</th><th>Estado</th><th className="num">Bultos</th><th></th></tr></thead>
          <tbody>
            {remitos.map((r) => (
              <tr key={r.id} className={remitoAbierto?.id === r.id ? "fila-seleccionada" : ""}>
                <td>#{r.id}</td>
                <td>#{r.orden_id}</td>
                <td>{catalogos.nombreUbicacion(r.destino_id)}</td>
                <td><Estado valor={r.estado} /></td>
                <td className="num">{r.bultos.length}</td>
                <td className="botones-fila"><button className="secundario" onClick={() => setRemitoAbierto(r)}>Abrir</button></td>
              </tr>
            ))}
            {remitos.length === 0 && <tr><td colSpan="6" className="vacio">Todavía no hay remitos</td></tr>}
          </tbody>
        </table>
      </div>

      {remitoAbierto && (
        <PanelRemito remito={remitoAbierto} catalogos={catalogos} accion={accion} alCerrar={() => setRemitoAbierto(null)} />
      )}
    </section>
  );
}

// ------------------------------------------------------------ Panel del remito

function PanelRemito({ remito, catalogos, accion, alCerrar }) {
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);
  const abierto = remito.estado === "ABIERTO";

  async function agregarBulto(evento) {
    evento.preventDefault();
    await accion(() => api.crear(`/remitos/${remito.id}/bultos`, { items: aItems(lineas) }), "Bulto armado (Preparado)");
    setLineas([{ ...LINEA_VACIA }]);
  }

  return (
    <div className="panel">
      <h3>Remito #{remito.id}: {catalogos.nombreUbicacion(remito.origen_id)} → {catalogos.nombreUbicacion(remito.destino_id)}
        <Estado valor={remito.estado} />
        <button className="boton-cerrar" onClick={alCerrar} aria-label="Cerrar">×</button>
      </h3>

      {abierto && (
        <form className="formulario formulario-ancho" onSubmit={agregarBulto}>
          <span className="nota">Armar un bulto (no se puede mandar algo que no se pidió ni más de lo pedido):</span>
          <LineasProductos lineas={lineas} alCambiar={setLineas} productos={catalogos.productosActivos} />
          <div className="acciones">
            <button type="submit">Armar bulto</button>
            <button type="button" className="secundario"
              onClick={() => accion(() => api.accion(`/remitos/${remito.id}/despachar`), "Remito despachado: el stock salió del CD")}>
              Despachar remito
            </button>
          </div>
        </form>
      )}

      {remito.bultos.map((b) => <FilaBulto key={b.id} bulto={b} catalogos={catalogos} accion={accion} />)}
      {remito.bultos.length === 0 && <p className="vacio">El remito todavía no tiene bultos</p>}
    </div>
  );
}

// -------------------------------------------------------------- Un bulto

function FilaBulto({ bulto, catalogos, accion }) {
  const [precinto, setPrecinto] = useState("");
  const [leido, setLeido] = useState("");
  const [intacto, setIntacto] = useState(true);
  const [verHistorial, setVerHistorial] = useState(false);

  async function verificar() {
    await accion(
      () => api.crear(`/bultos/${bulto.id}/verificar`, { nro_leido: leido, intacto }),
      "Verificación registrada (el stock entra al local cuando se termina de verificar todo el remito)",
    );
  }

  return (
    <div className="bulto">
      <div className="bulto-cabecera">
        <strong>Bulto #{bulto.id}</strong>
        <Estado valor={bulto.estado} />
        {bulto.nro_precinto && <span className="nota">Precinto: <code>{bulto.nro_precinto}</code></span>}
        {bulto.habilita_venta && <span className="nota">✓ habilita venta</span>}
        <span className="nota">{bulto.items.map((i) => `${i.cantidad} × ${catalogos.nombreProducto(i.producto_id)}`).join(", ")}</span>
      </div>

      {/* Solo las acciones del estado actual */}
      <div className="bulto-acciones">
        {bulto.estado === "PREPARADO" && (<>
          <input value={precinto} onChange={(e) => setPrecinto(e.target.value)} placeholder="Nº de precinto (ej: P-001)" />
          <button onClick={() => accion(() => api.crear(`/bultos/${bulto.id}/precintar`, { nro_precinto: precinto }), "Bulto precintado")}>
            Precintar
          </button>
        </>)}
        {bulto.estado === "EN_TRANSITO" && (
          <button onClick={() => accion(() => api.accion(`/bultos/${bulto.id}/recibir`), "Bulto recibido en la sucursal")}>
            Recibir en la sucursal
          </button>
        )}
        {bulto.estado === "RECIBIDO" && (<>
          <input value={leido} onChange={(e) => setLeido(e.target.value)} placeholder="Precinto leído al recibir" />
          <label className="check-bajas">
            <input type="checkbox" checked={intacto} onChange={(e) => setIntacto(e.target.checked)} /> Precinto intacto
          </label>
          <button onClick={verificar}>Verificar</button>
        </>)}
        <button className="secundario" onClick={() => setVerHistorial(!verHistorial)}>
          {verHistorial ? "Ocultar historial" : "Historial"}
        </button>
      </div>

      {verHistorial && (
        <ol className="historial">
          {bulto.historial.map((h, i) => (
            <li key={i}>
              <span className="nota">{fecha(h.fecha_hora)}</span> {h.estado_anterior.replaceAll("_", " ")} → <Estado valor={h.estado_nuevo} />
              {h.observacion && <em> · {h.observacion}</em>}
            </li>
          ))}
          {bulto.historial.length === 0 && <li className="vacio">Recién armado: todavía no cambió de estado</li>}
        </ol>
      )}
    </div>
  );
}
