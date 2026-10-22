// Pantalla de envíos CD → locales, como un tablero por etapas:
//   Pedidos de locales → Armando en el CD → En camino → Entregados.
// Cada tarjeta dice qué hay que hacer y al tocarla se abre el remito en un panel
// lateral, donde cada bulto muestra sus pasos (patrón State a la vista) y solo
// el botón del paso que sigue. El backend igual rechaza cualquier transición
// inválida. Despachar y verificar no se pueden deshacer: piden confirmación.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { Confirmacion, useConfirmacion } from "../componentes/Confirmacion.jsx";
import { Cargando } from "../componentes/Controles.jsx";
import Estado, { PasosBulto } from "../componentes/Estado.jsx";
import LineasProductos, { aItems, LINEA_VACIA } from "../componentes/LineasProductos.jsx";
import { fecha } from "../formato.js";

const ENTREGADOS = ["VERIFICADO", "VERIFICADO_CON_RECHAZOS"];

export default function Logistica() {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const confirmacion = useConfirmacion();
  const [pedidos, setPedidos] = useState(null);
  const [ordenes, setOrdenes] = useState([]);
  const [remitos, setRemitos] = useState(null);
  const [seleccionados, setSeleccionados] = useState([]);
  const [remitoAbierto, setRemitoAbierto] = useState(null);
  const [nuevoPedido, setNuevoPedido] = useState(false);
  const [verTodosEntregados, setVerTodosEntregados] = useState(false);

  const cargar = () => ejecutar(async () => {
    setPedidos(await api.listar("/pedidos?estado=PENDIENTE"));
    setOrdenes(await api.listar("/ordenes"));
    const lista = [...(await api.listar("/remitos"))].reverse();  // los más nuevos primero
    setRemitos(lista);
    setRemitoAbierto((actual) => (actual ? lista.find((r) => r.id === actual.id) ?? null : null));
  });
  useEffect(() => { cargar(); }, []);

  // Ejecuta una acción y, si sale bien, recarga todo. Devuelve si salió bien.
  async function accion(hacer, textoExito) {
    const ok = await ejecutar(hacer, textoExito);
    if (ok) await cargar();
    return ok;
  }

  // Consolida los pedidos elegidos en una orden y arma un remito por local, de una vez
  async function preparar() {
    const ok = await ejecutar(async () => {
      const orden = await api.crear("/ordenes", { pedido_ids: seleccionados });
      for (const destino of [...new Set(orden.pedidos.map((p) => p.sucursal_id))]) {
        await api.crear("/remitos", { orden_id: orden.id, destino_id: destino });
      }
    }, "Listo: se armó un remito por local en «Armando en el CD»");
    setSeleccionados([]);
    await cargar();
    return ok;
  }

  // Órdenes con algún local que todavía no tiene remito (por si algo quedó a medias)
  const sinRemito = ordenes.flatMap((o) => [...new Set(o.pedidos.map((p) => p.sucursal_id))]
    .filter((destino) => !(remitos ?? []).some((r) => r.orden_id === o.id && r.destino_id === destino))
    .map((destino) => ({ orden: o, destino })));

  const armando = (remitos ?? []).filter((r) => r.estado === "ABIERTO" || r.estado === "CERRADO");
  const enCamino = (remitos ?? []).filter((r) => r.estado === "EN_TRANSITO");
  const entregados = (remitos ?? []).filter((r) => ENTREGADOS.includes(r.estado));
  const alternar = (id) => setSeleccionados((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const resumen = (items) => items.map((i) => `${i.cantidad} × ${catalogos.nombreProducto(i.producto_id)}`).join(", ");

  return (
    <section>
      <Cabecera icono="🚚" titulo="Envíos a locales" subtitulo="La mercadería viaja del CD a los locales en bultos precintados">
        <button onClick={() => setNuevoPedido(true)}>+ Nuevo pedido</button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <Confirmacion confirmacion={confirmacion} />

      {remitos === null ? <Cargando /> : (
        <div className="tablero">
          {/* ------------------------------------------------ Pedidos */}
          <div className="columna">
            <div className="columna-titulo">📝 Pedidos de locales <span className="contador">{pedidos?.length ?? 0}</span></div>
            <p className="columna-ayuda">Elegí los que vas a preparar juntos.</p>
            {(pedidos ?? []).map((p) => (
              <div key={p.id} className="ficha">
                <label>
                  <input type="checkbox" checked={seleccionados.includes(p.id)} onChange={() => alternar(p.id)} />
                  <span>
                    <strong>{catalogos.nombreUbicacion(p.sucursal_id)}</strong>
                    <span className="secundario-texto">Pedido #{p.id} · {fecha(p.fecha)}</span>
                  </span>
                </label>
                <span className="ficha-detalle">{resumen(p.items)}</span>
              </div>
            ))}
            {pedidos?.length === 0 && <p className="columna-vacia">No hay pedidos esperando.</p>}
            {seleccionados.length > 0 && (
              <button onClick={preparar}>Preparar {seleccionados.length} pedido{seleccionados.length === 1 ? "" : "s"} →</button>
            )}
          </div>

          {/* ------------------------------------------- Armando en el CD */}
          <div className="columna">
            <div className="columna-titulo">📦 Armando en el CD <span className="contador">{armando.length + sinRemito.length}</span></div>
            {sinRemito.map(({ orden, destino }) => (
              <div key={`${orden.id}-${destino}`} className="ficha">
                <div className="ficha-titulo">{catalogos.nombreUbicacion(destino)}<span className="numero-ficha">Orden #{orden.id}</span></div>
                <span className="ficha-detalle">Falta crear el remito de este local.</span>
                <button className="secundario chico"
                  onClick={() => accion(() => api.crear("/remitos", { orden_id: orden.id, destino_id: destino }), "Remito creado")}>
                  Crear remito
                </button>
              </div>
            ))}
            {armando.map((r) => (
              <FichaRemito key={r.id} remito={r} catalogos={catalogos} alAbrir={() => setRemitoAbierto(r)}
                accion={siguienteEnArmado(r)} />
            ))}
            {armando.length + sinRemito.length === 0 && <p className="columna-vacia">Nada en preparación.</p>}
          </div>

          {/* --------------------------------------------------- En camino */}
          <div className="columna">
            <div className="columna-titulo">🚚 En camino <span className="contador">{enCamino.length}</span></div>
            {enCamino.map((r) => {
              const listos = r.bultos.filter((b) => ["VERIFICADO", "RECHAZADO"].includes(b.estado)).length;
              return (
                <FichaRemito key={r.id} remito={r} catalogos={catalogos} alAbrir={() => setRemitoAbierto(r)}
                  accion="Recibir y verificar →" progreso={listos / r.bultos.length}
                  detalle={`${listos} de ${r.bultos.length} bultos revisados`} />
              );
            })}
            {enCamino.length === 0 && <p className="columna-vacia">No hay envíos viajando.</p>}
          </div>

          {/* --------------------------------------------------- Entregados */}
          <div className="columna">
            <div className="columna-titulo">✅ Entregados <span className="contador">{entregados.length}</span></div>
            {(verTodosEntregados ? entregados : entregados.slice(0, 4)).map((r) => {
              const rechazados = r.bultos.filter((b) => b.estado === "RECHAZADO").length;
              return (
                <FichaRemito key={r.id} remito={r} catalogos={catalogos} alAbrir={() => setRemitoAbierto(r)}
                  accion="Ver detalle" detalle={rechazados ? `⚠ ${rechazados} bulto${rechazados === 1 ? "" : "s"} rechazado${rechazados === 1 ? "" : "s"}` : "Todo llegó bien"} />
              );
            })}
            {entregados.length > 4 && (
              <button className="fantasma chico" onClick={() => setVerTodosEntregados(!verTodosEntregados)}>
                {verTodosEntregados ? "Ver menos" : `Ver los ${entregados.length}`}
              </button>
            )}
            {entregados.length === 0 && <p className="columna-vacia">Todavía no se entregó nada.</p>}
          </div>
        </div>
      )}

      {nuevoPedido && (
        <CajonNuevoPedido catalogos={catalogos} accion={accion} alCerrar={() => setNuevoPedido(false)} />
      )}
      {remitoAbierto && (
        <CajonRemito key={remitoAbierto.id} remito={remitoAbierto} orden={ordenes.find((o) => o.id === remitoAbierto.orden_id)}
          catalogos={catalogos} accion={accion} confirmacion={confirmacion} alCerrar={() => setRemitoAbierto(null)} />
      )}
    </section>
  );
}

// Qué hay que hacer con un remito que se está armando
function siguienteEnArmado(remito) {
  if (remito.bultos.length === 0) return "Armar bultos →";
  const sinPrecintar = remito.bultos.filter((b) => b.estado === "PREPARADO").length;
  if (sinPrecintar > 0) return `Precintar ${sinPrecintar} bulto${sinPrecintar === 1 ? "" : "s"} →`;
  return "Listo para despachar →";
}

function FichaRemito({ remito, catalogos, alAbrir, accion, progreso, detalle }) {
  return (
    <button className="ficha" onClick={alAbrir}>
      <div className="ficha-titulo">{catalogos.nombreUbicacion(remito.destino_id)}<span className="numero-ficha">Remito #{remito.id}</span></div>
      <span className="ficha-detalle">
        {detalle ?? `${remito.bultos.length} bulto${remito.bultos.length === 1 ? "" : "s"}`}
      </span>
      {progreso !== undefined && <div className="progreso"><span style={{ width: `${Math.round(progreso * 100)}%` }} /></div>}
      <span className="ficha-accion">{accion}</span>
    </button>
  );
}

// --------------------------------------------------------------- Nuevo pedido

function CajonNuevoPedido({ catalogos, accion, alCerrar }) {
  const [sucursal, setSucursal] = useState("");
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);

  async function crear() {
    if (await accion(() => api.crear("/pedidos", { sucursal_id: sucursal, items: aItems(lineas) }), "Pedido creado")) alCerrar();
  }

  return (
    <Cajon titulo="Nuevo pedido de reposición" subtitulo="Un local le pide mercadería al CD" alCerrar={alCerrar}
      pie={<>
        <button className="secundario" onClick={alCerrar}>Cancelar</button>
        <button onClick={crear} disabled={!sucursal || aItems(lineas).length === 0}>Crear pedido</button>
      </>}>
      <label>¿Qué local pide?
        <select value={sucursal} onChange={(e) => setSucursal(e.target.value)}>
          <option value="">Elegí un local</option>
          {catalogos.sucursales.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
        </select>
      </label>
      <div className="seccion-cajon">
        <h3>¿Qué necesita?</h3>
        <LineasProductos lineas={lineas} alCambiar={setLineas} productos={catalogos.productosActivos} />
      </div>
    </Cajon>
  );
}

// ------------------------------------------------------------ Detalle del remito

// Lo que pidió el local destino en la orden, lo que ya va en los bultos y lo que falta
function avanceDelRemito(remito, orden) {
  const pedido = {};
  for (const p of orden?.pedidos ?? []) {
    if (p.sucursal_id !== remito.destino_id) continue;
    for (const i of p.items) pedido[i.producto_id] = (pedido[i.producto_id] ?? 0) + i.cantidad;
  }
  const enviado = Object.fromEntries(remito.total_por_producto.map((i) => [i.producto_id, i.cantidad]));
  return Object.keys(pedido).map((id) => ({
    producto_id: Number(id), pedido: pedido[id], enviado: enviado[id] ?? 0, falta: pedido[id] - (enviado[id] ?? 0),
  }));
}

function CajonRemito({ remito, orden, catalogos, accion, confirmacion, alCerrar }) {
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);
  const armando = remito.estado === "ABIERTO";
  const avance = avanceDelRemito(remito, orden);
  const faltante = avance.filter((a) => a.falta > 0);

  async function armarBulto() {
    if (await accion(() => api.crear(`/remitos/${remito.id}/bultos`, { items: aItems(lineas) }), "Bulto armado: ahora precintalo")) {
      setLineas([{ ...LINEA_VACIA }]);
    }
  }

  function despachar() {
    confirmacion.pedir({
      titulo: `¿Despachar a ${catalogos.nombreUbicacion(remito.destino_id)}?`,
      textoConfirmar: "Despachar",
      detalle: (<>
        <p>Salen del CD {remito.bultos.length} bulto{remito.bultos.length === 1 ? "" : "s"} con:</p>
        <ul>{remito.total_por_producto.map((i) => <li key={i.producto_id}>{i.cantidad} × {catalogos.nombreProducto(i.producto_id)}</li>)}</ul>
        <p>El stock sale del CD en este momento. <strong>No se puede deshacer.</strong></p>
      </>),
    }, async () => { if (await accion(() => api.accion(`/remitos/${remito.id}/despachar`), "Despachado: el envío está en camino")) alCerrar(); });
  }

  const sinPrecintar = remito.bultos.filter((b) => b.estado === "PREPARADO").length;

  return (
    <Cajon ancho titulo={`${catalogos.nombreUbicacion(remito.origen_id)} → ${catalogos.nombreUbicacion(remito.destino_id)}`}
      subtitulo={`Remito #${remito.id} · ${fecha(remito.fecha)}`} alCerrar={alCerrar}
      pie={armando ? (<>
        {remito.bultos.length === 0 && <span className="nota">Armá al menos un bulto para poder despachar.</span>}
        {sinPrecintar > 0 && <span className="nota">Precintá todos los bultos para poder despachar.</span>}
        <button onClick={despachar} disabled={remito.bultos.length === 0 || sinPrecintar > 0}>Despachar →</button>
      </>) : <button className="secundario" onClick={alCerrar}>Cerrar</button>}>

      <div><Estado valor={remito.estado} /></div>

      {armando && avance.length > 0 && (
        <div className="seccion-cajon">
          <h3>Lo que pidió el local</h3>
          <div className="tarjeta-tabla">
            <table className="avance">
              <thead><tr><th>Producto</th><th className="num">Pidió</th><th className="num">En bultos</th><th className="num">Falta</th></tr></thead>
              <tbody>
                {avance.map((a) => (
                  <tr key={a.producto_id}>
                    <td>{catalogos.nombreProducto(a.producto_id)}</td>
                    <td className="num">{a.pedido}</td>
                    <td className="num">{a.enviado}</td>
                    <td className={`num ${a.falta > 0 ? "falta" : "completo"}`}>{a.falta > 0 ? a.falta : "✓"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {armando && faltante.length > 0 && (
        <div className="seccion-cajon">
          <h3>Armar un bulto</h3>
          <div className="campos">
            <LineasProductos lineas={lineas} alCambiar={setLineas} productos={catalogos.productosActivos} />
            <div className="acciones-fila" style={{ justifyContent: "flex-start" }}>
              <button className="secundario" onClick={() => setLineas(faltante.map((a) => ({ producto_id: String(a.producto_id), cantidad: String(a.falta) })))}>
                Cargar lo que falta
              </button>
              <button onClick={armarBulto} disabled={aItems(lineas).length === 0}>Armar bulto</button>
            </div>
          </div>
        </div>
      )}

      <div className="seccion-cajon">
        <h3>Bultos ({remito.bultos.length})</h3>
        <div className="campos">
          {remito.bultos.map((b) => <Bulto key={b.id} bulto={b} catalogos={catalogos} accion={accion} confirmacion={confirmacion} />)}
          {remito.bultos.length === 0 && <p className="vacio-chico">Todavía no hay bultos. Armá el primero con «Cargar lo que falta».</p>}
        </div>
      </div>
    </Cajon>
  );
}

// ------------------------------------------------------------------- Un bulto

function Bulto({ bulto, catalogos, accion, confirmacion }) {
  const [precinto, setPrecinto] = useState("");
  const [leido, setLeido] = useState("");
  const [sano, setSano] = useState(null);  // sin respuesta hasta que se elige
  const [verHistorial, setVerHistorial] = useState(false);

  function verificar() {
    confirmacion.pedir({
      titulo: `¿Verificar el bulto #${bulto.id}?`,
      textoConfirmar: "Verificar",
      peligro: !sano,
      detalle: (<>
        <p>Precinto leído: <code>{leido.trim()}</code> · ¿Llegó sano?: <strong>{sano ? "Sí" : "No"}</strong></p>
        <p>Si el número no es el que se puso en el CD o el precinto no llegó sano, el bulto queda <strong>Rechazado</strong> y
          su mercadería no se vende. <strong>No se puede deshacer.</strong></p>
      </>),
    }, () => accion(() => api.crear(`/bultos/${bulto.id}/verificar`, { nro_leido: leido, intacto: sano }),
      "Bulto revisado (la mercadería entra al local cuando se revisan todos los bultos)"));
  }

  return (
    <div className="bulto">
      <div className="bulto-cabecera">
        <strong>Bulto #{bulto.id}</strong>
        {bulto.nro_precinto && <span className="nota">Precinto <code>{bulto.nro_precinto}</code></span>}
        <button className="fantasma chico" style={{ marginLeft: "auto" }} onClick={() => setVerHistorial(!verHistorial)}>
          {verHistorial ? "Ocultar historial" : "Historial"}
        </button>
      </div>
      <PasosBulto estado={bulto.estado} />
      <span className="bulto-contenido">{bulto.items.map((i) => `${i.cantidad} × ${catalogos.nombreProducto(i.producto_id)}`).join(", ")}</span>

      {bulto.estado === "PREPARADO" && (
        <div className="bulto-accion">
          <label>Número del precinto que le pusiste
            <input value={precinto} onChange={(e) => setPrecinto(e.target.value)} placeholder="Ej: P-001" />
          </label>
          <button onClick={() => accion(() => api.crear(`/bultos/${bulto.id}/precintar`, { nro_precinto: precinto }), "Bulto precintado")}
            disabled={precinto.trim() === ""}>Precintar</button>
        </div>
      )}
      {bulto.estado === "EN_TRANSITO" && (
        <div className="bulto-accion">
          <span className="nota" style={{ flex: 1 }}>¿Llegó al local?</span>
          <button onClick={() => accion(() => api.accion(`/bultos/${bulto.id}/recibir`), "Bulto recibido: ahora revisá el precinto")}>
            Marcar como recibido
          </button>
        </div>
      )}
      {bulto.estado === "RECIBIDO" && (
        <div className="bulto-accion">
          <label>Número que se lee en el precinto
            <input value={leido} onChange={(e) => setLeido(e.target.value)} placeholder="Copialo del precinto" />
          </label>
          <div>
            <span className="ayuda-campo">¿Llegó sano?</span>
            <div className="opciones-si-no">
              <button className={sano === true ? "" : "secundario"} onClick={() => setSano(true)}>Sí</button>
              <button className={sano === false ? "peligro-lleno" : "secundario"} onClick={() => setSano(false)}>No</button>
            </div>
          </div>
          <button onClick={verificar} disabled={leido.trim() === "" || sano === null}>Verificar</button>
        </div>
      )}

      {verHistorial && (
        <ol className="historial">
          {bulto.historial.map((h, i) => (
            <li key={i}>{fecha(h.fecha_hora)} · {h.estado_anterior.replaceAll("_", " ").toLowerCase()} → <Estado valor={h.estado_nuevo} />
              {h.observacion && <em> · {h.observacion}</em>}</li>
          ))}
          {bulto.historial.length === 0 && <li>Recién armado.</li>}
        </ol>
      )}
    </div>
  );
}
