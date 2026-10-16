// Pantalla de Productos: alta, modificación, baja lógica, listado con filtro
// por categoría y los proveedores de cada producto.
// No se valida nada acá a propósito: los errores los muestra el backend.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";

const VACIO = { codigo: "", nombre: "", categoria_id: "", precio_venta: "", costo: "", stock_minimo: "0" };

export default function Productos() {
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [filtroCategoria, setFiltroCategoria] = useState("");
  const [form, setForm] = useState(VACIO);
  const [editandoId, setEditandoId] = useState(null);
  const [proveedoresDe, setProveedoresDe] = useState(null); // { producto, proveedores }
  const { aviso, ejecutar, limpiar } = useAviso();

  const cargar = () => ejecutar(async () => {
    const filtro = filtroCategoria ? `?categoria_id=${filtroCategoria}` : "";
    setProductos(await api.listar(`/productos${filtro}`));
    setCategorias(await api.listar("/categorias"));
  });
  useEffect(() => { cargar(); }, [filtroCategoria]);

  const nombreCategoria = (id) => categorias.find((c) => c.id === id)?.nombre ?? `#${id} (dada de baja)`;
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  function cancelar() {
    setEditandoId(null);
    setForm(VACIO);
  }

  function editar(p) {
    setEditandoId(p.id);
    setForm({ ...p, categoria_id: String(p.categoria_id) });
  }

  async function guardar(evento) {
    evento.preventDefault();
    const datos = {
      nombre: form.nombre, categoria_id: form.categoria_id, precio_venta: form.precio_venta,
      costo: form.costo, stock_minimo: form.stock_minimo,
    };
    // Al modificar no se manda el código: es la identidad del producto
    const ok = editandoId
      ? await ejecutar(() => api.modificar(`/productos/${editandoId}`, datos), "Producto modificado")
      : await ejecutar(() => api.crear("/productos", { codigo: form.codigo, ...datos }), "Producto creado");
    if (ok) { cancelar(); cargar(); }
  }

  async function darDeBaja(p) {
    if (await ejecutar(() => api.borrar(`/productos/${p.id}`), `"${p.nombre}" dado de baja`)) cargar();
  }

  async function verProveedores(p) {
    await ejecutar(async () => setProveedoresDe({ producto: p, proveedores: await api.listar(`/productos/${p.id}/proveedores`) }));
  }

  return (
    <section>
      <h2>Productos</h2>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <form className="formulario" onSubmit={guardar}>
        <label>Código (SKU)
          <input value={form.codigo} onChange={cambiar("codigo")} disabled={!!editandoId}
            placeholder="Hasta 20 letras (ej: BEB-001)"
            title={editandoId ? "El código no se puede modificar" : ""} />
        </label>
        <label>Nombre<input value={form.nombre} onChange={cambiar("nombre")} placeholder="Ej: Coca-Cola 500ml" /></label>
        <label>Categoría
          <select value={form.categoria_id} onChange={cambiar("categoria_id")}>
            <option value="">— elegir —</option>
            {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label>Precio de venta
          <input value={form.precio_venta} onChange={cambiar("precio_venta")} placeholder="Número > 0 (ej: 1500.50)" />
        </label>
        <label>Costo
          <input value={form.costo} onChange={cambiar("costo")} placeholder="Número ≥ 0 (ej: 900)" />
        </label>
        <label>Stock mínimo
          <input value={form.stock_minimo} onChange={cambiar("stock_minimo")} placeholder="Entero ≥ 0 (ej: 10)" />
        </label>
        <div className="acciones">
          <button type="submit">{editandoId ? "Guardar cambios" : "Crear"}</button>
          {editandoId && <button type="button" className="secundario" onClick={cancelar}>Cancelar</button>}
        </div>
      </form>

      <div className="barra-filtro">
        <label>Filtrar por categoría
          <select value={filtroCategoria} onChange={(e) => setFiltroCategoria(e.target.value)}>
            <option value="">Todas</option>
            {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
      </div>

      <div className="tabla-scroll">
        <table>
          <thead>
            <tr><th>Código</th><th>Nombre</th><th>Categoría</th><th className="num">Precio</th>
              <th className="num">Costo</th><th className="num">Margen</th><th className="num">Stock mín.</th><th></th></tr>
          </thead>
          <tbody>
            {productos.map((p) => (
              <tr key={p.id}>
                <td><code>{p.codigo}</code></td>
                <td>{p.nombre}</td>
                <td>{nombreCategoria(p.categoria_id)}</td>
                <td className="num">${p.precio_venta.toFixed(2)}</td>
                <td className="num">${p.costo.toFixed(2)}</td>
                <td className={`num ${p.margen_unitario < 0 ? "negativo" : ""}`}>${p.margen_unitario.toFixed(2)}</td>
                <td className="num">{p.stock_minimo}</td>
                <td className="botones-fila">
                  <button className="secundario" onClick={() => verProveedores(p)}>Proveedores</button>
                  <button className="secundario" onClick={() => editar(p)}>Editar</button>
                  <button className="peligro" onClick={() => darDeBaja(p)}>Dar de baja</button>
                </td>
              </tr>
            ))}
            {productos.length === 0 && <tr><td colSpan="8" className="vacio">No hay productos activos</td></tr>}
          </tbody>
        </table>
      </div>

      {proveedoresDe && (
        <div className="panel">
          <h3>Proveedores de “{proveedoresDe.producto.nombre}”
            <button className="boton-cerrar" onClick={() => setProveedoresDe(null)} aria-label="Cerrar">×</button>
          </h3>
          {proveedoresDe.proveedores.length === 0
            ? <p className="vacio">Ningún proveedor activo lo provee. Se asigna desde la pestaña Proveedores.</p>
            : <ul>{proveedoresDe.proveedores.map((pr) => <li key={pr.id}>{pr.razon_social} ({pr.cuit})</li>)}</ul>}
        </div>
      )}
    </section>
  );
}
