// Pantalla de Proveedores: alta, modificación, baja lógica, listado y la
// relación muchos a muchos con Productos (asignar / quitar).
// No se valida nada acá a propósito: los errores los muestra el backend.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import EncabezadoPantalla from "../componentes/EncabezadoPantalla.jsx";
import { ConfirmacionParecidos, useParecidos } from "../componentes/ConfirmacionParecidos.jsx";
import { CheckBajas, EtiquetaBaja } from "../componentes/Bajas.jsx";

const VACIO = { cuit: "", razon_social: "", telefono: "", email: "" };

export default function Proveedores() {
  const [proveedores, setProveedores] = useState([]);
  const [form, setForm] = useState(VACIO);
  const [editandoId, setEditandoId] = useState(null);
  const [verBajas, setVerBajas] = useState(false);
  const [seleccionado, setSeleccionado] = useState(null); // proveedor cuyos productos se gestionan
  const [suyos, setSuyos] = useState([]);                 // productos que ya provee
  const [todos, setTodos] = useState([]);                 // todos los productos activos
  const [aAsignar, setAAsignar] = useState("");
  const { aviso, ejecutar, limpiar } = useAviso();
  const parecidos = useParecidos();

  const cargar = () => ejecutar(async () => setProveedores(await api.listar(`/proveedores?incluir_bajas=${verBajas}`)));
  useEffect(() => { cargar(); }, [verBajas]);

  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  function cancelar() {
    parecidos.descartar();
    setEditandoId(null);
    setForm(VACIO);
  }

  function editar(p) {
    setEditandoId(p.id);
    setForm({ cuit: p.cuit, razon_social: p.razon_social, telefono: p.telefono ?? "", email: p.email ?? "" });
  }

  // Antes de guardar se consulta si hay nombres parecidos ("¿es un duplicado?")
  function guardar(evento) {
    evento.preventDefault();
    parecidos.verificar("/proveedores", { razon_social: form.razon_social }, editandoId, enviar);
  }

  async function enviar() {
    const datos = { razon_social: form.razon_social, telefono: form.telefono, email: form.email };
    // Al modificar no se manda el CUIT: es la identidad del proveedor
    const ok = editandoId
      ? await ejecutar(() => api.modificar(`/proveedores/${editandoId}`, datos), "Proveedor modificado")
      : await ejecutar(() => api.crear("/proveedores", { cuit: form.cuit, ...datos }), "Proveedor creado");
    if (ok) { cancelar(); cargar(); }
  }

  async function darDeBaja(p) {
    if (await ejecutar(() => api.borrar(`/proveedores/${p.id}`), `"${p.razon_social}" dado de baja`)) {
      if (seleccionado?.id === p.id) setSeleccionado(null);
      cargar();
    }
  }

  async function reactivar(p) {
    if (await ejecutar(() => api.accion(`/proveedores/${p.id}/reactivar`), `"${p.razon_social}" reactivado`)) cargar();
  }

  // ---- Relación con productos

  async function cargarProductosDe(proveedor) {
    await ejecutar(async () => {
      setSuyos(await api.listar(`/proveedores/${proveedor.id}/productos`));
      setTodos(await api.listar("/productos"));
    });
  }

  function gestionarProductos(p) {
    setSeleccionado(p);
    setAAsignar("");
    cargarProductosDe(p);
  }

  async function asignar() {
    // Sin chequear duplicados acá: si ya lo provee, el backend responde 409
    const ok = await ejecutar(
      () => api.asociar(`/proveedores/${seleccionado.id}/productos/${aAsignar || 0}`),
      "Producto asignado",
    );
    if (ok) cargarProductosDe(seleccionado);
  }

  async function quitar(producto) {
    const ok = await ejecutar(
      () => api.borrar(`/proveedores/${seleccionado.id}/productos/${producto.id}`),
      `"${producto.nombre}" quitado`,
    );
    if (ok) cargarProductosDe(seleccionado);
  }

  return (
    <section>
      <EncabezadoPantalla id="proveedores" icono="🤝" titulo="Proveedores"
        descripcion="Las empresas que le venden mercadería al comercio. Se identifican por su CUIT, que no se puede repetir."
        pasos={[
          "Cargá CUIT y razón social (teléfono y email son opcionales).",
          "Tocá «Productos» en un proveedor para indicar qué productos vende.",
          "Un producto puede tener varios proveedores y un proveedor muchos productos.",
        ]} />
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <ConfirmacionParecidos pendiente={parecidos.pendiente} alConfirmar={parecidos.confirmar}
        alCancelar={parecidos.descartar} />

      <form className="formulario" onSubmit={guardar}>
        <label>CUIT
          <input value={form.cuit} onChange={cambiar("cuit")} placeholder="11 dígitos (ej: 20-12345678-6)"
            disabled={!!editandoId} title={editandoId ? "El CUIT no se puede modificar" : ""} />
        </label>
        <label>Razón social
          <input value={form.razon_social} onChange={cambiar("razon_social")} placeholder="Ej: Distribuidora Sur SA" />
        </label>
        <label>Teléfono (opcional)
          <input value={form.telefono} onChange={cambiar("telefono")} placeholder="Ej: 11-4444-5555" />
        </label>
        <label>Email (opcional)
          <input value={form.email} onChange={cambiar("email")} placeholder="ej: ventas@empresa.com" />
        </label>
        <div className="acciones">
          <button type="submit">{editandoId ? "Guardar cambios" : "Crear"}</button>
          {editandoId && <button type="button" className="secundario" onClick={cancelar}>Cancelar</button>}
        </div>
      </form>

      <div className="barra-filtro"><CheckBajas valor={verBajas} alCambiar={setVerBajas} /></div>

      <div className="tabla-scroll">
        <table>
          <thead><tr><th>CUIT</th><th>Razón social</th><th>Teléfono</th><th>Email</th><th></th></tr></thead>
          <tbody>
            {proveedores.map((p) => (
              <tr key={p.id} className={`${seleccionado?.id === p.id ? "fila-seleccionada" : ""} ${p.activo ? "" : "fila-baja"}`}>
                <td><code>{p.cuit}</code></td>
                <td>{p.razon_social}{!p.activo && <EtiquetaBaja />}</td>
                <td>{p.telefono ?? "—"}</td>
                <td>{p.email ?? "—"}</td>
                <td className="botones-fila">
                  {p.activo ? (<>
                    <button className="secundario" onClick={() => gestionarProductos(p)}>Productos</button>
                    <button className="secundario" onClick={() => editar(p)}>Editar</button>
                    <button className="peligro" onClick={() => darDeBaja(p)}>Dar de baja</button>
                  </>) : <button onClick={() => reactivar(p)}>Reactivar</button>}
                </td>
              </tr>
            ))}
            {proveedores.length === 0 && <tr><td colSpan="5" className="vacio">No hay proveedores activos</td></tr>}
          </tbody>
        </table>
      </div>

      {seleccionado && (
        <div className="panel">
          <h3>Productos que provee “{seleccionado.razon_social}”
            <button className="boton-cerrar" onClick={() => setSeleccionado(null)} aria-label="Cerrar">×</button>
          </h3>
          <div className="barra-filtro">
            <select value={aAsignar} onChange={(e) => setAAsignar(e.target.value)}>
              <option value="">— elegir producto —</option>
              {todos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}
            </select>
            <button onClick={asignar}>Asignar</button>
          </div>
          <table>
            <thead><tr><th>Código</th><th>Nombre</th><th></th></tr></thead>
            <tbody>
              {suyos.map((p) => (
                <tr key={p.id}>
                  <td><code>{p.codigo}</code></td>
                  <td>{p.nombre}</td>
                  <td className="botones-fila"><button className="peligro" onClick={() => quitar(p)}>Quitar</button></td>
                </tr>
              ))}
              {suyos.length === 0 && <tr><td colSpan="3" className="vacio">Todavía no provee ningún producto</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
