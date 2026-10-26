// Pantalla de Ventas, como un punto de venta: se tocan los productos para
// sumarlos al ticket y se cobra con un medio de pago. El local es el del
// usuario que entró (lo decide el back, no se elige acá). El total
// lo calcula el back mientras se arma el ticket (POST /ventas/cotizar), con el
// mismo cálculo que la venta real (Strategy de medios de pago): el front no
// conoce los descuentos. Abajo: las ventas del local, su caja y las devoluciones.
// El comprobante y las notas de crédito se descargan en PDF (los arma el back).
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { Buscador, Cargando, coincide, Vacio } from "../componentes/Controles.jsx";
import LineasProductos, { aItems, LINEA_VACIA } from "../componentes/LineasProductos.jsx";
import { fecha, nombreMedio, pesos } from "../formato.js";

export default function Ventas({ usuario }) {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const [medios, setMedios] = useState([]);
  const sucursal = usuario.ubicacion_id;
  const [stock, setStock] = useState({});          // producto_id → cantidad en el local
  const [busqueda, setBusqueda] = useState("");
  const [carrito, setCarrito] = useState([]);      // [{ producto_id, cantidad }]
  const [medio, setMedio] = useState("");
  const [entregado, setEntregado] = useState("");
  const [cotizacion, setCotizacion] = useState(null);
  const [errorCotizacion, setErrorCotizacion] = useState(null);
  const [ventas, setVentas] = useState(null);
  const [caja, setCaja] = useState(null);
  const [comprobante, setComprobante] = useState(null);
  const [abierta, setAbierta] = useState(null);

  useEffect(() => { ejecutar(async () => setMedios(await api.listar("/ventas/medios-pago"))); }, []);

  const cargarLocal = () => ejecutar(async () => {
    const existencias = await api.listar(`/stock/${sucursal}`);
    setStock(Object.fromEntries(existencias.map((e) => [e.producto_id, e.cantidad])));
    setVentas([...(await api.listar(`/ventas?sucursal_id=${sucursal}`))].reverse());
    setCaja(await api.obtener(`/caja/${sucursal}`));
  });
  useEffect(() => { cargarLocal(); }, []);

  // ------------------------------------------------------------- Ticket
  function sumar(productoId, cuanto) {
    setCarrito((actual) => {
      const linea = actual.find((l) => l.producto_id === productoId);
      if (!linea) return cuanto > 0 ? [...actual, { producto_id: productoId, cantidad: cuanto }] : actual;
      return actual
        .map((l) => (l.producto_id === productoId ? { ...l, cantidad: l.cantidad + cuanto } : l))
        .filter((l) => l.cantidad > 0);
    });
  }

  // Cotización en vivo: medio segundo después del último cambio
  const datosVenta = {
    items: carrito, medio_pago: medio,
    monto_entregado: medio === "EFECTIVO" && entregado !== "" ? entregado : null,
  };
  const clave = JSON.stringify(datosVenta);
  useEffect(() => {
    setErrorCotizacion(null);
    if (carrito.length === 0 || !medio) { setCotizacion(null); return undefined; }
    const temporizador = setTimeout(async () => {
      try {
        setCotizacion(await api.crear("/ventas/cotizar", datosVenta));
      } catch (error) {
        setCotizacion(null);
        setErrorCotizacion(error.message);
      }
    }, 400);
    return () => clearTimeout(temporizador);
  }, [clave]);

  function descargarComprobante(venta) {
    ejecutar(() => api.descargar(`/ventas/${venta.id}/comprobante.pdf`), `Comprobante ${venta.comprobante} descargado`);
  }

  async function cobrar() {
    let venta = null;
    if (await ejecutar(async () => { venta = await api.crear("/ventas", datosVenta); }, "Venta registrada")) {
      setComprobante(venta);
      setCarrito([]);
      setEntregado("");
      cargarLocal();
    }
  }

  const productosVisibles = catalogos.productosActivos.filter((p) => coincide(`${p.codigo} ${p.nombre}`, busqueda));
  const subtotalLista = carrito.reduce((suma, l) => suma + l.cantidad * (catalogos.productos.find((p) => p.id === l.producto_id)?.precio_venta ?? 0), 0);

  return (
    <section>
      <Cabecera icono="🛒" titulo={`Vender en ${usuario.ubicacion_nombre ?? "tu local"}`}
        subtitulo="Tocá los productos para sumarlos al ticket y cobrá" />
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <div className="punto-venta">
        {/* ----------------------------------------------- Productos */}
        <div className="catalogo-venta">
          <Buscador valor={busqueda} alCambiar={setBusqueda} placeholder="Buscar producto por nombre o código" />
          <div className="grilla-productos">
            {productosVisibles.map((p) => {
              const hay = stock[p.id] ?? 0;
              const enTicket = carrito.find((l) => l.producto_id === p.id)?.cantidad ?? 0;
              return (
                <button key={p.id} className="producto-venta" onClick={() => sumar(p.id, 1)} disabled={hay === 0}
                  title={hay === 0 ? "No hay stock en este local" : "Sumar al ticket"}>
                  <strong>{p.nombre}</strong>
                  <span className="precio">{pesos(p.precio_venta)}</span>
                  <span className={`stock ${hay === 0 ? "sin" : hay - enTicket < 5 ? "poco" : ""}`}>
                    {hay === 0 ? "Sin stock" : `Hay ${hay}`}{enTicket > 0 && ` · ${enTicket} en el ticket`}
                  </span>
                </button>
              );
            })}
            {productosVisibles.length === 0 && <p className="vacio-chico">No hay productos que coincidan con “{busqueda}”.</p>}
          </div>
        </div>

        {/* -------------------------------------------------- Ticket */}
        <div className="ticket">
          <div className="ticket-cabecera">
            <strong>Ticket</strong>
            {carrito.length > 0 && <button className="fantasma chico" onClick={() => setCarrito([])}>Vaciar</button>}
          </div>
          <div className="ticket-items">
            {carrito.length === 0 && <p className="vacio-chico">Tocá un producto para empezar.</p>}
            {carrito.map((l) => {
              const linea = cotizacion?.lineas.find((x) => x.producto_id === l.producto_id);
              return (
                <div key={l.producto_id} className="item-ticket">
                  <span>
                    <span className="nombre">{catalogos.nombreProducto(l.producto_id)}</span>
                    {linea && !linea.alcanza && <span className="aviso-stock">Solo hay {linea.disponible}</span>}
                  </span>
                  <span className="cantidad-control">
                    <button onClick={() => sumar(l.producto_id, -1)} aria-label="Uno menos">−</button>
                    <span>{l.cantidad}</span>
                    <button onClick={() => sumar(l.producto_id, 1)} aria-label="Uno más">+</button>
                  </span>
                  <span className="num">{linea ? pesos(linea.subtotal) : ""}</span>
                </div>
              );
            })}
          </div>

          <div className="ticket-pago">
            <div className="medios" role="radiogroup" aria-label="Medio de pago">
              {medios.map((m) => (
                <button key={m.nombre} role="radio" aria-checked={medio === m.nombre}
                  className={`medio ${medio === m.nombre ? "activo" : ""}`} onClick={() => setMedio(m.nombre)}>
                  {nombreMedio(m.nombre)}
                  <small>{m.porcentaje_ajuste < 0 ? `${m.porcentaje_ajuste}% desc.` : m.porcentaje_ajuste > 0 ? `+${m.porcentaje_ajuste}% recargo` : "precio de lista"}</small>
                </button>
              ))}
            </div>
            {medio === "EFECTIVO" && (
              <label>¿Con cuánto paga?
                <input type="number" min="0" step="0.01" inputMode="decimal" value={entregado}
                  onChange={(e) => setEntregado(e.target.value)} placeholder="Opcional, para calcular el vuelto" />
              </label>
            )}

            {cotizacion ? (<>
              <div className="renglon"><span>Subtotal</span><span>{pesos(cotizacion.subtotal)}</span></div>
              {cotizacion.porcentaje_ajuste !== 0 && (
                <div className="renglon">
                  <span>{cotizacion.porcentaje_ajuste < 0 ? "Descuento" : "Recargo"} {Math.abs(cotizacion.porcentaje_ajuste)}%</span>
                  <span>{pesos(cotizacion.total - cotizacion.subtotal)}</span>
                </div>
              )}
              <div className="renglon total"><span>Total</span><span>{pesos(cotizacion.total)}</span></div>
              {cotizacion.vuelto > 0 && <div className="renglon vuelto"><span>Vuelto</span><span>{pesos(cotizacion.vuelto)}</span></div>}
              {!cotizacion.alcanza_pago && <p className="atencion-texto">Con lo que entrega no alcanza.</p>}
            </>) : (
              carrito.length > 0 && (
                <div className="renglon total"><span>Total</span><span>{medio ? "…" : pesos(subtotalLista)}</span></div>
              )
            )}
            {errorCotizacion && <p className="atencion-texto">{errorCotizacion}</p>}
            {carrito.length > 0 && !medio && <p className="nota">Elegí cómo paga.</p>}
          </div>

          <div className="ticket-pie">
            <button className="grande" onClick={cobrar}
              disabled={carrito.length === 0 || !medio || !cotizacion || !cotizacion.hay_stock || !cotizacion.alcanza_pago}>
              {cotizacion ? `Cobrar ${pesos(cotizacion.total)}` : "Cobrar"}
            </button>
          </div>
        </div>
      </div>

      {/* ----------------------------------------- Ventas y caja del local */}
      <h2 className="titulo-seccion espacio-arriba">Ventas del local</h2>
      {caja && (
        <div className="tarjetas">
          {Object.entries(caja.por_medio).map(([nombre, importe]) => (
            <div key={nombre} className="tarjeta"><span>{nombreMedio(nombre)}</span><strong>{pesos(importe)}</strong></div>
          ))}
          <div className="tarjeta destacada"><span>Caja total</span><strong>{pesos(caja.saldo)}</strong></div>
        </div>
      )}
      {ventas === null && <Cargando />}
      {ventas?.length === 0 && <Vacio icono="🧾" titulo="Este local todavía no vendió nada" texto="Las ventas que cobres aparecen acá." />}
      {ventas?.length > 0 && (
        <div className="tarjeta-tabla">
          <table>
            <thead><tr><th>Comprobante</th><th>Fecha</th><th>Pago</th><th className="num">Total</th><th className="num">Devuelto</th><th></th></tr></thead>
            <tbody>
              {ventas.map((v) => (
                <tr key={v.id}>
                  <td><code>{v.comprobante}</code></td>
                  <td>{fecha(v.fecha)}</td>
                  <td>{nombreMedio(v.medio_pago)}</td>
                  <td className="num">{pesos(v.total)}</td>
                  <td className="num">{v.total_reintegrado ? pesos(v.total_reintegrado) : "—"}</td>
                  <td><div className="acciones-fila"><button className="secundario chico" onClick={() => setAbierta(v)}>Ver</button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {comprobante && (
        <Cajon titulo={`Comprobante ${comprobante.comprobante}`} subtitulo={`${catalogos.nombreUbicacion(comprobante.sucursal_id)} · ${fecha(comprobante.fecha)}`}
          alCerrar={() => setComprobante(null)} pie={<>
            <button className="secundario" onClick={() => descargarComprobante(comprobante)}>⬇ Descargar PDF</button>
            <button onClick={() => setComprobante(null)}>Listo</button>
          </>}>
          <DetalleVenta venta={comprobante} catalogos={catalogos} />
        </Cajon>
      )}

      {abierta && (
        <CajonVenta key={abierta.id} venta={abierta} catalogos={catalogos} ejecutar={ejecutar}
          alCambiar={async () => { await cargarLocal(); setAbierta(null); }} alCerrar={() => setAbierta(null)}
          alDescargar={() => descargarComprobante(abierta)} />
      )}
    </section>
  );
}

function DetalleVenta({ venta, catalogos }) {
  return (
    <>
      <div className="tarjeta-tabla">
        <table>
          <thead><tr><th>Producto</th><th className="num">Cant.</th><th className="num">Precio</th><th className="num">Subtotal</th></tr></thead>
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
      </div>
      <div className="campos">
        <div className="renglon"><span>Subtotal</span><span>{pesos(venta.subtotal)}</span></div>
        <div className="renglon"><span>Pago: {nombreMedio(venta.medio_pago)} ({venta.porcentaje_ajuste}%)</span><span>{pesos(venta.total - venta.subtotal)}</span></div>
        <div className="renglon total"><span>Total</span><span>{pesos(venta.total)}</span></div>
      </div>
    </>
  );
}

function CajonVenta({ venta, catalogos, ejecutar, alCambiar, alCerrar, alDescargar }) {
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);
  const [motivo, setMotivo] = useState("");
  const vendidos = venta.detalles.map((d) => catalogos.productos.find((p) => p.id === d.producto_id)).filter(Boolean);

  async function devolver() {
    const ok = await ejecutar(
      () => api.crear(`/ventas/${venta.id}/devoluciones`, { items: aItems(lineas), motivo }),
      "Devolución registrada: el producto volvió al local y se reintegró el dinero",
    );
    if (ok) alCambiar();
  }

  return (
    <Cajon titulo={`Venta ${venta.comprobante}`} subtitulo={fecha(venta.fecha)} alCerrar={alCerrar}
      pie={<>
        <button className="secundario izquierda" onClick={alDescargar}>⬇ Comprobante PDF</button>
        <button className="secundario" onClick={alCerrar}>Cerrar</button>
        <button onClick={devolver}>Registrar devolución</button>
      </>}>
      <DetalleVenta venta={venta} catalogos={catalogos} />

      {venta.devoluciones.length > 0 && (
        <div className="seccion-cajon">
          <h3>Devoluciones anteriores</h3>
          <ul className="lista-simple">
            {venta.devoluciones.map((d) => (
              <li key={d.id}>
                {d.nota_credito && <strong>NC {d.nota_credito} · </strong>}
                {fecha(d.fecha)} · {d.motivo} · {pesos(d.importe)} · {d.detalles.map((x) =>
                  `${x.cantidad} × ${catalogos.nombreProducto(x.producto_id)}`).join(", ")}
                {d.nota_credito && (
                  <button className="fantasma chico" onClick={() => ejecutar(
                    () => api.descargar(`/ventas/${venta.id}/devoluciones/${d.id}/nota-credito.pdf`),
                    `Nota de crédito ${d.nota_credito} descargada`)}>⬇ PDF</button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="seccion-cajon">
        <h3>Devolver productos</h3>
        <div className="campos">
          <LineasProductos lineas={lineas} alCambiar={setLineas} productos={vendidos} />
          <label>Motivo<input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej: Producto vencido" /></label>
        </div>
      </div>
    </Cajon>
  );
}
