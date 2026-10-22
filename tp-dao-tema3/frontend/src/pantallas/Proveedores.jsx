// Pantalla de Proveedores: listado con buscador; alta y edición en un panel
// lateral, donde también se eligen los productos que vende (relación muchos a
// muchos con Productos); baja lógica con confirmación y reactivación.
// No se valida nada acá a propósito: los errores los muestra el backend.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import { textoBaja } from "../componentes/Bajas.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { Confirmacion, useConfirmacion } from "../componentes/Confirmacion.jsx";
import { ConfirmacionParecidos, useParecidos } from "../componentes/ConfirmacionParecidos.jsx";
import { Buscador, Cargando, coincide, Segmentado, Vacio } from "../componentes/Controles.jsx";

const VACIO = { cuit: "", razon_social: "", telefono: "", email: "" };

export default function Proveedores() {
  const [proveedores, setProveedores] = useState(null);  // null = cargando; trae también los dados de baja
  const [busqueda, setBusqueda] = useState("");
  const [verActivos, setVerActivos] = useState(true);
  const [editando, setEditando] = useState(null);        // null = cerrado; {} = nuevo; proveedor = editar
  const { aviso, ejecutar, limpiar } = useAviso();
  const confirmacion = useConfirmacion();

  const cargar = () => ejecutar(async () => setProveedores(await api.listar("/proveedores?incluir_bajas=true")));
  useEffect(() => { cargar(); }, []);

  function pedirBaja(p) {
    confirmacion.pedir({ titulo: `¿Dar de baja «${p.razon_social}»?`, textoConfirmar: "Dar de baja", peligro: true, detalle: textoBaja },
      async () => {
        if (await ejecutar(() => api.borrar(`/proveedores/${p.id}`), `«${p.razon_social}» dado de baja`)) { setEditando(null); cargar(); }
      });
  }

  async function reactivar(p) {
    if (await ejecutar(() => api.accion(`/proveedores/${p.id}/reactivar`), `«${p.razon_social}» vuelve a estar activo`)) cargar();
  }

  const deBaja = (proveedores ?? []).filter((p) => !p.activo).length;
  const visibles = (proveedores ?? [])
    .filter((p) => p.activo === verActivos)
    .filter((p) => coincide(p.razon_social, busqueda) || coincide(p.cuit, busqueda));

  return (
    <section>
      <Cabecera icono="🤝" titulo="Proveedores" subtitulo="Las empresas que le venden mercadería al comercio">
        <button onClick={() => setEditando({})}>+ Nuevo proveedor</button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <Confirmacion confirmacion={confirmacion} />

      <div className="barra">
        <Buscador valor={busqueda} alCambiar={setBusqueda} placeholder="Buscar por nombre o CUIT" />
        <Segmentado etiqueta="Mostrar" valor={verActivos} alCambiar={setVerActivos} opciones={[
          { valor: true, texto: "Activos", contador: (proveedores?.length ?? 0) - deBaja },
          { valor: false, texto: "De baja", contador: deBaja },
        ]} />
      </div>

      {proveedores === null ? <Cargando /> : visibles.length === 0 ? (
        busqueda ? <Vacio icono="🔍" titulo={`Nada coincide con «${busqueda}»`} />
          : verActivos ? <Vacio icono="🤝" titulo="Todavía no hay proveedores" accion="+ Nuevo proveedor" alAccionar={() => setEditando({})} />
            : <Vacio icono="✨" titulo="No hay proveedores dados de baja" />
      ) : (
        <div className="tarjeta-tabla">
          <table>
            <thead><tr><th>Proveedor</th><th>Teléfono</th><th>Email</th><th></th></tr></thead>
            <tbody>
              {visibles.map((p) => (
                <tr key={p.id} className={p.activo ? "fila-clic" : "fila-baja"} onClick={p.activo ? () => setEditando(p) : undefined}>
                  <td><strong>{p.razon_social}</strong><span className="secundario-texto">CUIT {p.cuit}</span></td>
                  <td>{p.telefono ?? "—"}</td>
                  <td>{p.email ?? "—"}</td>
                  <td><div className="acciones-fila">
                    {p.activo
                      ? <button className="fantasma chico">Editar y productos</button>
                      : <button className="secundario chico" onClick={() => reactivar(p)}>Reactivar</button>}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <CajonProveedor key={editando.id ?? "nuevo"} proveedor={editando} ejecutar={ejecutar} alCerrar={() => setEditando(null)}
          alGuardar={(creado) => { cargar(); setEditando(creado ?? null); }} alDarDeBaja={() => pedirBaja(editando)} />
      )}
    </section>
  );
}

function CajonProveedor({ proveedor, ejecutar, alCerrar, alGuardar, alDarDeBaja }) {
  const nuevo = !proveedor.id;
  const [form, setForm] = useState(nuevo ? VACIO
    : { cuit: proveedor.cuit, razon_social: proveedor.razon_social, telefono: proveedor.telefono ?? "", email: proveedor.email ?? "" });
  const parecidos = useParecidos();
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  // Antes de guardar se consulta si hay nombres parecidos ("¿es un duplicado?")
  function guardar(evento) {
    evento.preventDefault();
    parecidos.verificar("/proveedores", { razon_social: form.razon_social }, proveedor.id, async () => {
      const datos = { razon_social: form.razon_social, telefono: form.telefono, email: form.email };
      let creado = null;
      // Al modificar no se manda el CUIT: es la identidad del proveedor
      const ok = nuevo
        ? await ejecutar(async () => { creado = await api.crear("/proveedores", { cuit: form.cuit, ...datos }); },
          "Proveedor creado: ahora elegí qué productos vende")
        : await ejecutar(() => api.modificar(`/proveedores/${proveedor.id}`, datos), "Cambios guardados");
      // Al crear, el panel queda abierto con el proveedor nuevo para asignarle productos
      if (ok) alGuardar(creado);
    });
  }

  return (
    <Cajon titulo={nuevo ? "Nuevo proveedor" : proveedor.razon_social}
      subtitulo={nuevo ? null : `CUIT ${proveedor.cuit}`} alCerrar={alCerrar}
      pie={<>
        {!nuevo && <button className="peligro izquierda" onClick={alDarDeBaja}>Dar de baja</button>}
        <button className="secundario" onClick={alCerrar}>{nuevo ? "Cancelar" : "Cerrar"}</button>
        <button type="submit" form="form-proveedor">{nuevo ? "Crear proveedor" : "Guardar datos"}</button>
      </>}>
      <form id="form-proveedor" className="campos" onSubmit={guardar}>
        {nuevo && (
          <label>CUIT
            <input autoFocus value={form.cuit} onChange={cambiar("cuit")} placeholder="Ej: 20-12345678-6" />
            <span className="ayuda-campo">11 dígitos, con o sin guiones. No se puede repetir ni cambiar después.</span>
          </label>
        )}
        <label>Razón social<input value={form.razon_social} onChange={cambiar("razon_social")} placeholder="Ej: Distribuidora Sur SA" /></label>
        <div className="campos-2">
          <label><span>Teléfono <span className="ayuda-campo">(opcional)</span></span>
            <input value={form.telefono} onChange={cambiar("telefono")} placeholder="Ej: 11-4444-5555" />
          </label>
          <label><span>Email <span className="ayuda-campo">(opcional)</span></span>
            <input value={form.email} onChange={cambiar("email")} placeholder="ventas@empresa.com" />
          </label>
        </div>
      </form>
      <ConfirmacionParecidos pendiente={parecidos.pendiente} alConfirmar={parecidos.confirmar} alCancelar={parecidos.descartar} />

      {!nuevo && <ProductosDelProveedor proveedor={proveedor} ejecutar={ejecutar} />}
    </Cajon>
  );
}

// Los productos que vende el proveedor: se agregan y se quitan al toque
function ProductosDelProveedor({ proveedor, ejecutar }) {
  const [suyos, setSuyos] = useState(null);
  const [todos, setTodos] = useState([]);
  const [aAgregar, setAAgregar] = useState("");

  const cargar = () => ejecutar(async () => {
    setSuyos(await api.listar(`/proveedores/${proveedor.id}/productos`));
    setTodos(await api.listar("/productos"));
  });
  useEffect(() => { cargar(); }, []);

  async function agregar() {
    if (await ejecutar(() => api.asociar(`/proveedores/${proveedor.id}/productos/${aAgregar}`), "Producto agregado")) {
      setAAgregar("");
      cargar();
    }
  }

  async function quitar(producto) {
    if (await ejecutar(() => api.borrar(`/proveedores/${proveedor.id}/productos/${producto.id}`), `«${producto.nombre}» quitado`)) cargar();
  }

  const disponibles = todos.filter((p) => !(suyos ?? []).some((s) => s.id === p.id));

  return (
    <div className="seccion-cajon">
      <h3>Productos que vende {suyos && <span className="nota">({suyos.length})</span>}</h3>
      <div className="linea" style={{ marginBottom: 10 }}>
        <select value={aAgregar} onChange={(e) => setAAgregar(e.target.value)} aria-label="Producto para agregar">
          <option value="">{disponibles.length ? "Elegí un producto para agregar" : "Ya vende todos los productos"}</option>
          {disponibles.map((p) => <option key={p.id} value={p.id}>{p.nombre} ({p.codigo})</option>)}
        </select>
        <button onClick={agregar} disabled={!aAgregar}>Agregar</button>
      </div>
      {suyos === null ? <Cargando /> : suyos.length === 0 ? <p className="vacio-chico">Todavía no vende ningún producto.</p> : (
        <div className="tarjeta-tabla">
          <table>
            <tbody>
              {suyos.map((p) => (
                <tr key={p.id}>
                  <td>{p.nombre}<span className="secundario-texto">{p.codigo}</span></td>
                  <td><div className="acciones-fila"><button className="peligro chico" onClick={() => quitar(p)}>Quitar</button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
