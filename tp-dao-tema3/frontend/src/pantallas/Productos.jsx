// Pantalla de Productos: listado con filtros (texto, categoría, proveedor y
// rango de precio) que resuelve el back (GET /productos con parámetros); alta y
// edición en un panel lateral (que también muestra quién provee el producto),
// baja lógica con confirmación y reactivación.
// No se valida nada acá a propósito: los errores los muestra el backend.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import { textoBaja } from "../componentes/Bajas.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { Confirmacion, useConfirmacion } from "../componentes/Confirmacion.jsx";
import { ConfirmacionParecidos, useParecidos } from "../componentes/ConfirmacionParecidos.jsx";
import { Buscador, Cargando, Segmentado, Vacio } from "../componentes/Controles.jsx";
import { pesos } from "../formato.js";

const VACIO = { codigo: "", nombre: "", categoria_id: "", precio_venta: "", costo: "", stock_minimo: "0" };
const SIN_FILTROS = { texto: "", categoria_id: "", proveedor_id: "", precio_desde: "", precio_hasta: "" };

export default function Productos({ irA }) {
  const [productos, setProductos] = useState(null);  // null = cargando; trae también los dados de baja
  const [categorias, setCategorias] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [filtros, setFiltros] = useState(SIN_FILTROS);
  const [verActivos, setVerActivos] = useState(true);
  const [editando, setEditando] = useState(null);    // null = cerrado; {} = nuevo; producto = editar
  const { aviso, ejecutar, limpiar } = useAviso();
  const confirmacion = useConfirmacion();

  // Se piden también los dados de baja (para contar las dos pestañas); el
  // resto de los filtros los aplica el back
  const cargar = () => {
    const parametros = new URLSearchParams({ incluir_bajas: true });
    for (const [campo, valor] of Object.entries(filtros)) if (valor !== "") parametros.set(campo, valor);
    return ejecutar(async () => setProductos(await api.listar(`/productos?${parametros}`)));
  };
  useEffect(() => {
    ejecutar(async () => {
      setCategorias(await api.listar("/categorias"));
      setProveedores(await api.listar("/proveedores"));
    });
  }, []);
  // Medio segundo después de dejar de escribir, para no consultar por cada letra
  useEffect(() => {
    const temporizador = setTimeout(cargar, 300);
    return () => clearTimeout(temporizador);
  }, [JSON.stringify(filtros)]);
  const filtrar = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.value });
  const hayFiltros = Object.values(filtros).some((v) => v !== "");

  const nombreCategoria = (id) => categorias.find((c) => c.id === id)?.nombre ?? "(categoría de baja)";

  function pedirBaja(p) {
    confirmacion.pedir({ titulo: `¿Dar de baja «${p.nombre}»?`, textoConfirmar: "Dar de baja", peligro: true, detalle: textoBaja },
      async () => {
        if (await ejecutar(() => api.borrar(`/productos/${p.id}`), `«${p.nombre}» dado de baja`)) { setEditando(null); cargar(); }
      });
  }

  async function reactivar(p) {
    if (await ejecutar(() => api.accion(`/productos/${p.id}/reactivar`), `«${p.nombre}» vuelve a estar activo`)) cargar();
  }

  const deBaja = (productos ?? []).filter((p) => !p.activo).length;
  const visibles = (productos ?? []).filter((p) => p.activo === verActivos);

  return (
    <section>
      <Cabecera icono="🧃" titulo="Productos" subtitulo="Lo que se compra, se reparte y se vende">
        <button onClick={() => setEditando({})} disabled={categorias.length === 0}
          title={categorias.length === 0 ? "Primero creá una categoría" : ""}>+ Nuevo producto</button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <Confirmacion confirmacion={confirmacion} />

      <div className="barra">
        <Buscador valor={filtros.texto} alCambiar={(texto) => setFiltros({ ...filtros, texto })} placeholder="Buscar por nombre o código" />
        <select className="filtro" value={filtros.categoria_id} onChange={filtrar("categoria_id")} aria-label="Categoría">
          <option value="">Todas las categorías</option>
          {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <Segmentado etiqueta="Mostrar" valor={verActivos} alCambiar={setVerActivos} opciones={[
          { valor: true, texto: "Activos", contador: (productos?.length ?? 0) - deBaja },
          { valor: false, texto: "De baja", contador: deBaja },
        ]} />
      </div>
      <div className="barra filtros">
        <label>Proveedor
          <select value={filtros.proveedor_id} onChange={filtrar("proveedor_id")}>
            <option value="">Todos</option>
            {proveedores.map((pr) => <option key={pr.id} value={pr.id}>{pr.razon_social}</option>)}
          </select>
        </label>
        <label>Precio desde
          <input type="number" min="0" value={filtros.precio_desde} onChange={filtrar("precio_desde")} placeholder="$" />
        </label>
        <label>Precio hasta
          <input type="number" min="0" value={filtros.precio_hasta} onChange={filtrar("precio_hasta")} placeholder="$" />
        </label>
        {hayFiltros && <button className="fantasma" onClick={() => setFiltros(SIN_FILTROS)}>Limpiar filtros</button>}
      </div>

      {productos === null ? <Cargando /> : visibles.length === 0 ? (
        hayFiltros ? <Vacio icono="🔍" titulo="Ningún producto coincide con los filtros" texto="Probá con otros valores o tocá «Limpiar filtros»."
          accion="Limpiar filtros" alAccionar={() => setFiltros(SIN_FILTROS)} />
          : !verActivos ? <Vacio icono="✨" titulo="No hay productos dados de baja" />
            : categorias.length === 0
              ? <Vacio icono="🏷️" titulo="Primero creá una categoría" texto="Todo producto pertenece a una categoría."
                accion="Ir a Categorías" alAccionar={() => irA("categorias")} />
              : <Vacio icono="🧃" titulo="Todavía no hay productos" accion="+ Nuevo producto" alAccionar={() => setEditando({})} />
      ) : (
        <div className="tarjeta-tabla">
          <table>
            <thead>
              <tr><th>Producto</th><th>Categoría</th><th className="num">Precio</th><th className="num">Costo</th>
                <th className="num">Ganancia</th><th className="num">Mínimo</th><th></th></tr>
            </thead>
            <tbody>
              {visibles.map((p) => (
                <tr key={p.id} className={p.activo ? "fila-clic" : "fila-baja"} onClick={p.activo ? () => setEditando(p) : undefined}>
                  <td><strong>{p.nombre}</strong><span className="secundario-texto">{p.codigo}</span></td>
                  <td>{nombreCategoria(p.categoria_id)}</td>
                  <td className="num">{pesos(p.precio_venta)}</td>
                  <td className="num">{pesos(p.costo)}</td>
                  <td className={`num ${p.margen_unitario < 0 ? "negativo" : ""}`}>{pesos(p.margen_unitario)}</td>
                  <td className="num">{p.stock_minimo}</td>
                  <td><div className="acciones-fila">
                    {p.activo
                      ? <button className="fantasma chico">Editar</button>
                      : <button className="secundario chico" onClick={() => reactivar(p)}>Reactivar</button>}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <CajonProducto producto={editando} categorias={categorias} ejecutar={ejecutar} irA={irA}
          alCerrar={() => setEditando(null)} alGuardar={() => { setEditando(null); cargar(); }}
          alDarDeBaja={() => pedirBaja(editando)} />
      )}
    </section>
  );
}

function CajonProducto({ producto, categorias, ejecutar, irA, alCerrar, alGuardar, alDarDeBaja }) {
  const nuevo = !producto.id;
  const [form, setForm] = useState(nuevo ? VACIO : { ...producto, categoria_id: String(producto.categoria_id) });
  const [proveedores, setProveedores] = useState(null);
  const parecidos = useParecidos();
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  useEffect(() => {
    if (!nuevo) api.listar(`/productos/${producto.id}/proveedores`).then(setProveedores).catch(() => setProveedores([]));
  }, []);

  // Antes de guardar se consulta si hay nombres parecidos ("¿es un duplicado?")
  function guardar(evento) {
    evento.preventDefault();
    parecidos.verificar("/productos", { nombre: form.nombre }, producto.id, async () => {
      const datos = {
        nombre: form.nombre, categoria_id: form.categoria_id, precio_venta: form.precio_venta,
        costo: form.costo, stock_minimo: form.stock_minimo,
      };
      // Al modificar no se manda el código: es la identidad del producto
      const ok = nuevo
        ? await ejecutar(() => api.crear("/productos", { codigo: form.codigo, ...datos }), `Producto «${form.nombre.trim()}» creado`)
        : await ejecutar(() => api.modificar(`/productos/${producto.id}`, datos), "Cambios guardados");
      if (ok) alGuardar();
    });
  }

  return (
    <Cajon titulo={nuevo ? "Nuevo producto" : producto.nombre} subtitulo={nuevo ? null : `Código ${producto.codigo}`} alCerrar={alCerrar}
      pie={<>
        {!nuevo && <button className="peligro izquierda" onClick={alDarDeBaja}>Dar de baja</button>}
        <button className="secundario" onClick={alCerrar}>Cancelar</button>
        <button type="submit" form="form-producto">{nuevo ? "Crear producto" : "Guardar"}</button>
      </>}>
      <form id="form-producto" className="campos" onSubmit={guardar}>
        {nuevo && (
          <label>Código (SKU)
            <input autoFocus value={form.codigo} onChange={cambiar("codigo")} placeholder="Ej: BEB-001" />
            <span className="ayuda-campo">Identifica al producto. No se puede repetir ni cambiar después.</span>
          </label>
        )}
        <label>Nombre<input value={form.nombre} onChange={cambiar("nombre")} placeholder="Ej: Coca-Cola 500ml" /></label>
        <label>Categoría
          <select value={form.categoria_id} onChange={cambiar("categoria_id")}>
            <option value="">Elegí una categoría</option>
            {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <div className="campos-2">
          <label>Precio de venta
            <input type="number" min="0" step="0.01" value={form.precio_venta} onChange={cambiar("precio_venta")} placeholder="Ej: 1500" />
          </label>
          <label>Costo
            <input type="number" min="0" step="0.01" value={form.costo} onChange={cambiar("costo")} placeholder="Ej: 900" />
          </label>
        </div>
        <label>Stock mínimo
          <input type="number" min="0" step="1" value={form.stock_minimo} onChange={cambiar("stock_minimo")} />
          <span className="ayuda-campo">Si en algún lugar queda menos que esto, aparece como «Reponer».</span>
        </label>
      </form>
      <ConfirmacionParecidos pendiente={parecidos.pendiente} alConfirmar={parecidos.confirmar} alCancelar={parecidos.descartar} />

      {!nuevo && (
        <div className="seccion-cajon">
          <h3>Quién lo vende</h3>
          {proveedores === null ? <Cargando /> : proveedores.length === 0
            ? <p className="nota">Ningún proveedor lo tiene asignado. <button className="fantasma chico" onClick={() => irA("proveedores")}>Asignar en Proveedores →</button></p>
            : <ul className="lista-simple">{proveedores.map((pr) => <li key={pr.id}>{pr.razon_social} <span className="nota">· CUIT {pr.cuit}</span></li>)}</ul>}
        </div>
      )}
    </Cajon>
  );
}
