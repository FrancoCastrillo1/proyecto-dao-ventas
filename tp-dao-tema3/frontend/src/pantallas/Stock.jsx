// Pantalla de Stock: existencias de cada ubicación, compra al CD (lo único que
// mete mercadería desde afuera) y el libro de movimientos de cada producto.
// A un local el stock le entra SOLO por bultos verificados (pantalla Envíos).
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { Buscador, Cargando, coincide, Segmentado, Vacio } from "../componentes/Controles.jsx";
import { fecha } from "../formato.js";

const COMPRA_VACIA = { producto_id: "", cantidad: "", referencia: "" };

// Nombre común de cada tipo de movimiento (en la base se guarda el código)
const TIPO_MOVIMIENTO = {
  COMPRA: "Compra a proveedor", DESPACHO: "Despacho a un local", RECEPCION: "Recepción de un bulto",
  VENTA: "Venta", DEVOLUCION: "Devolución de un cliente", AJUSTE: "Ajuste manual",
};

export default function Stock({ irA }) {
  const catalogos = useCatalogos();
  const [ubicacionId, setUbicacionId] = useState(null);
  const [existencias, setExistencias] = useState(null);  // null = cargando
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState("todos");
  const [comprando, setComprando] = useState(false);
  const [movimientos, setMovimientos] = useState(null); // { fila, lista }
  const { aviso, ejecutar, limpiar } = useAviso();

  const ubicacion = catalogos.ubicacion(ubicacionId);

  // Arranca mostrando el CD
  useEffect(() => {
    if (ubicacionId === null && catalogos.ubicacionesActivas.length) {
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
  const visibles = (existencias ?? [])
    .filter((f) => filtro === "todos" || f.bajo_minimo)
    .filter((f) => coincide(f.nombre, busqueda) || coincide(f.codigo, busqueda));

  return (
    <section>
      <Cabecera icono="📦" titulo="Stock" subtitulo="Cuánto hay de cada producto en cada lugar">
        {/* Se pregunta por la capacidad (como el backend), no por el tipo */}
        {ubicacion?.puede_despachar && <button onClick={() => setComprando(true)}>+ Registrar compra</button>}
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <div className="barra">
        <Segmentado etiqueta="Ubicación" valor={ubicacionId} alCambiar={setUbicacionId}
          opciones={catalogos.ubicacionesActivas.map((u) => ({ valor: u.id, texto: `${u.puede_despachar ? "🏭" : "🏬"} ${u.nombre}` }))} />
      </div>
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
          <button className="fantasma chico" onClick={() => irA("logistica")}>Ir a Envíos →</button>
        </p>
      )}

      {existencias === null ? <Cargando /> : visibles.length === 0 ? (
        filtro === "bajo" && !busqueda
          ? <Vacio icono="🎉" titulo="Nada bajo el mínimo" texto="Todos los productos de esta ubicación tienen stock suficiente." />
          : <Vacio icono="🔍" titulo="No hay productos para mostrar" texto={busqueda ? "Probá con otra búsqueda." : "Esta ubicación todavía no tiene productos."} />
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
                  <td>{f.bajo_minimo && <span className="estado estado-rojo">Reponer</span>}</td>
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
      () => api.crear("/stock/ingresar", { ubicacion_id: ubicacion.id, ...compra }),
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
