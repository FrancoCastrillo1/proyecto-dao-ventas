// Pantalla de Stock: existencias de cada ubicación, compra al CD (lo único que
// mete mercadería desde afuera) y el libro de movimientos de cada producto.
// A un local el stock le entra SOLO por bultos verificados (pantalla Envíos).
// Un local ve solo su stock; quien ve toda la red elige la ubicación. Comprar,
// solo quien tiene la capacidad (el CD), y entra a SU ubicación.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import Icono from "../componentes/Icono.jsx";
import { Buscador, Cargando, coincide, Segmentado, Vacio } from "../componentes/Controles.jsx";
import { puede } from "../componentes/Permisos.js";
import { fecha } from "../formato.js";

const COMPRA_VACIA = { producto_id: "", cantidad: "", referencia: "" };

// Nombre común de cada tipo de movimiento (en la base se guarda el código)
const TIPO_MOVIMIENTO = {
  COMPRA: "Compra a proveedor", DESPACHO: "Despacho a un local", RECEPCION: "Recepción de un bulto",
  VENTA: "Venta", DEVOLUCION: "Devolución de un cliente", AJUSTE: "Ajuste manual",
};

export default function Stock({ irA, puedeIr, usuario }) {
  const catalogos = useCatalogos();
  const [ubicacionId, setUbicacionId] = useState(null);
  const [existencias, setExistencias] = useState(null);  // null = cargando
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState("todos");
  const [comprando, setComprando] = useState(false);
  const [movimientos, setMovimientos] = useState(null); // { fila, lista }
  const { aviso, ejecutar, limpiar } = useAviso();

  const ubicacion = catalogos.ubicacion(ubicacionId);
  const veTodaLaRed = puede(usuario, "ve_toda_la_red");

  // Arranca en la ubicación del usuario; el administrador (que no tiene), en el CD
  useEffect(() => {
    if (ubicacionId !== null) return;
    if (usuario.ubicacion_id) { setUbicacionId(usuario.ubicacion_id); return; }
    if (catalogos.ubicacionesActivas.length) {
      const cd = catalogos.ubicacionesActivas.find((u) => u.puede_despachar) ?? catalogos.ubicacionesActivas[0];
      setUbicacionId(cd.id);
    }
  }, [catalogos.ubicacionesActivas.length]);

  const cargar = () => ubicacionId && ejecutar(async () => setExistencias(await api.listar(`/stock/${ubicacionId}`)));
  useEffect(() => { setExistencias(null); cargar(); }, [ubicacionId]);

  async function verMovimientos(fila) {
    await ejecutar(async () => setMovimientos({
      fila, lista: await api.listar(`/stock/${ubicacionId}/${fila.producto_id}/movimientos`),
    }));
  }

  const bajoMinimo = (existencias ?? []).filter((f) => f.bajo_minimo).length;
  // Un local puede pedir lo que le falta: abre el pedido al CD ya cargado (hasta el mínimo)
  const puedePedir = puede(usuario, "puede_pedir_reposicion") && ubicacionId === usuario.ubicacion_id && puedeIr("logistica");
  const pedir = (filas) => irA("logistica", {
    pedido: filas.map((f) => ({ producto_id: f.producto_id, cantidad: f.stock_minimo - f.cantidad })),
  });
  const visibles = (existencias ?? [])
    .filter((f) => filtro === "todos" || f.bajo_minimo)
    .filter((f) => coincide(f.nombre, busqueda) || coincide(f.codigo, busqueda));

  return (
    <section>
      <Cabecera icono="caja" titulo="Stock"
        subtitulo={veTodaLaRed ? "Cuánto hay de cada producto en cada lugar" : `Lo que hay en ${ubicacion?.nombre ?? "tu local"}`}>
        {/* Se pregunta por la capacidad del usuario (como el backend), no por su perfil */}
        {puede(usuario, "puede_comprar") && ubicacionId === usuario.ubicacion_id &&
          <button onClick={() => setComprando(true)}>+ Registrar compra</button>}
        {puedePedir && bajoMinimo > 0 &&
          <button onClick={() => pedir(existencias.filter((f) => f.bajo_minimo))}>Pedir lo que falta ({bajoMinimo})</button>}
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      {veTodaLaRed && (
        <div className="barra">
          <Segmentado etiqueta="Ubicación" valor={ubicacionId} alCambiar={setUbicacionId}
            opciones={catalogos.ubicacionesActivas.map((u) => ({ valor: u.id, texto: <><Icono nombre={u.puede_despachar ? "cd" : "local"} tamano={16} /> {u.nombre}</> }))} />
        </div>
      )}
      <div className="barra">
        <Buscador valor={busqueda} alCambiar={setBusqueda} placeholder="Buscar producto o código" />
        <Segmentado etiqueta="Mostrar" valor={filtro} alCambiar={setFiltro} opciones={[
          { valor: "todos", texto: "Todos", contador: existencias?.length },
          { valor: "bajo", texto: "Bajo el mínimo", contador: bajoMinimo },
        ]} />
      </div>

      {ubicacion && !ubicacion.puede_despachar && (
        <p className="nota" style={{ marginBottom: 12 }}>
          A este local la mercadería le entra cuando verifica un envío del CD.{" "}
          {puedeIr("logistica") && <button className="fantasma chico" onClick={() => irA("logistica")}>Ir a Envíos →</button>}
        </p>
      )}

      {existencias === null ? <Cargando /> : visibles.length === 0 ? (
        filtro === "bajo" && !busqueda
          ? <Vacio icono="festejo" titulo="Nada bajo el mínimo" texto="Todos los productos de esta ubicación tienen stock suficiente." />
          : <Vacio icono="buscar" titulo="No hay productos para mostrar" texto={busqueda ? "Probá con otra búsqueda." : "Esta ubicación todavía no tiene productos."} />
      ) : (
        <div className="tarjeta-tabla">
          <table>
            <thead>
              <tr><th>Producto</th><th className="num">Hay</th><th className="num">Mínimo</th><th></th><th></th></tr>
            </thead>
            <tbody>
              {visibles.map((f) => (
                <tr key={f.producto_id} className={f.bajo_minimo ? "fila-alerta" : ""}>
                  <td>{f.nombre}<span className="secundario-texto">{f.codigo}</span></td>
                  <td className="num"><strong>{f.cantidad}</strong></td>
                  <td className="num">{f.stock_minimo}</td>
                  <td>{f.bajo_minimo && (puedePedir
                    ? <button className="estado estado-rojo boton-estado" onClick={() => pedir([f])} title="Pedirle al CD lo que falta">Reponer →</button>
                    : <span className="estado estado-rojo">Reponer</span>)}</td>
                  <td><div className="acciones-fila">
                    <button className="fantasma chico" onClick={() => verMovimientos(f)}>Ver movimientos</button>
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {comprando && (
        <CajonCompra ubicacion={ubicacion} catalogos={catalogos} ejecutar={ejecutar}
          alCerrar={() => setComprando(false)} alGuardar={() => { setComprando(false); cargar(); }} />
      )}

      {movimientos && (
        <Cajon titulo={movimientos.fila.nombre} subtitulo={`Entradas y salidas en ${ubicacion?.nombre}`}
          alCerrar={() => setMovimientos(null)}>
          <div className="tarjetas">
            <div className="tarjeta destacada"><span>Hay ahora</span><strong>{movimientos.fila.cantidad}</strong></div>
            <div className="tarjeta"><span>Mínimo</span><strong>{movimientos.fila.stock_minimo}</strong></div>
          </div>
          {movimientos.lista.length === 0 ? <p className="vacio-chico">Todavía no tuvo movimientos.</p> : (
            <div className="tarjeta-tabla">
              <table>
                <thead><tr><th>Cuándo</th><th>Qué pasó</th><th className="num">Cantidad</th></tr></thead>
                <tbody>
                  {movimientos.lista.map((m, i) => (
                    <tr key={i}>
                      <td>{fecha(m.fecha)}</td>
                      <td>{TIPO_MOVIMIENTO[m.tipo] ?? m.tipo}{m.referencia && <span className="secundario-texto">{m.referencia}</span>}</td>
                      <td className={`num ${m.cantidad < 0 ? "negativo" : "positivo"}`}>{m.cantidad > 0 ? `+${m.cantidad}` : m.cantidad}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Cajon>
      )}
    </section>
  );
}

function CajonCompra({ ubicacion, catalogos, ejecutar, alCerrar, alGuardar }) {
  const [compra, setCompra] = useState(COMPRA_VACIA);
  const cambiar = (campo) => (e) => setCompra({ ...compra, [campo]: e.target.value });

  async function guardar(evento) {
    evento.preventDefault();
    const ok = await ejecutar(
      () => api.crear("/stock/ingresar", compra),   // entra al CD del usuario
      `Compra registrada: entraron ${compra.cantidad} al ${ubicacion.nombre}`,
    );
    if (ok) alGuardar();
  }

  return (
    <Cajon titulo="Registrar una compra" subtitulo={`Mercadería que llega de un proveedor al ${ubicacion.nombre}`} alCerrar={alCerrar}
      pie={<>
        <button className="secundario" onClick={alCerrar}>Cancelar</button>
        <button type="submit" form="form-compra" disabled={!compra.producto_id || !compra.cantidad}>Registrar compra</button>
      </>}>
      <form id="form-compra" className="campos" onSubmit={guardar}>
        <label>Producto
          <select value={compra.producto_id} onChange={cambiar("producto_id")}>
            <option value="">Elegí un producto</option>
            {catalogos.productosActivos.map((p) => <option key={p.id} value={p.id}>{p.nombre} ({p.codigo})</option>)}
          </select>
        </label>
        <label>Cantidad
          <input type="number" min="1" step="1" value={compra.cantidad} onChange={cambiar("cantidad")} placeholder="Ej: 100" />
        </label>
        <label><span>Factura o remito del proveedor <span className="ayuda-campo">(opcional)</span></span>
          <input value={compra.referencia} onChange={cambiar("referencia")} placeholder="Ej: Factura A-0001" />
        </label>
      </form>
    </Cajon>
  );
}
