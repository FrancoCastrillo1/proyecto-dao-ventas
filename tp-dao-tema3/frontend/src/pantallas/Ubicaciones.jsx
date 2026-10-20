// Pantalla de Ubicaciones (Sucursales y Centro de Distribución): alta,
// modificación, baja lógica y listado con filtro por tipo. Muestra las
// capacidades de cada una (puede vender / despachar / recibir) que vienen del
// polimorfismo del backend. No se valida nada acá: los errores los muestra el backend.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import EncabezadoPantalla from "../componentes/EncabezadoPantalla.jsx";
import { ConfirmacionParecidos, useParecidos } from "../componentes/ConfirmacionParecidos.jsx";
import { CheckBajas, EtiquetaBaja } from "../componentes/Bajas.jsx";

const VACIO = { tipo: "SUCURSAL", nombre: "", direccion: "" };
const NOMBRE_TIPO = { SUCURSAL: "Sucursal", CD: "Centro de Distribución" };

function Capacidad({ si }) {
  return <span className={si ? "si" : "no"}>{si ? "✓" : "✗"}</span>;
}

export default function Ubicaciones() {
  const [ubicaciones, setUbicaciones] = useState([]);
  const [filtroTipo, setFiltroTipo] = useState("");
  const [form, setForm] = useState(VACIO);
  const [editandoId, setEditandoId] = useState(null);
  const [verBajas, setVerBajas] = useState(false);
  const { aviso, ejecutar, limpiar } = useAviso();
  const parecidos = useParecidos();

  const cargar = () => ejecutar(async () => {
    const parametros = new URLSearchParams({ incluir_bajas: verBajas });
    if (filtroTipo) parametros.set("tipo", filtroTipo);
    setUbicaciones(await api.listar(`/ubicaciones?${parametros}`));
  });
  useEffect(() => { cargar(); }, [filtroTipo, verBajas]);

  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  function cancelar() {
    parecidos.descartar();
    setEditandoId(null);
    setForm(VACIO);
  }

  function editar(u) {
    setEditandoId(u.id);
    setForm({ tipo: u.tipo, nombre: u.nombre, direccion: u.direccion });
  }

  // Antes de guardar se consulta si hay nombres parecidos ("¿es un duplicado?")
  function guardar(evento) {
    evento.preventDefault();
    parecidos.verificar("/ubicaciones", { nombre: form.nombre }, editandoId, enviar);
  }

  async function enviar() {
    const datos = { nombre: form.nombre, direccion: form.direccion };
    // Al modificar no se manda el tipo: una ubicación no cambia de clase
    const ok = editandoId
      ? await ejecutar(() => api.modificar(`/ubicaciones/${editandoId}`, datos), "Ubicación modificada")
      : await ejecutar(() => api.crear("/ubicaciones", { tipo: form.tipo, ...datos }), "Ubicación creada");
    if (ok) { cancelar(); cargar(); }
  }

  async function darDeBaja(u) {
    if (await ejecutar(() => api.borrar(`/ubicaciones/${u.id}`), `"${u.nombre}" dada de baja`)) cargar();
  }

  async function reactivar(u) {
    if (await ejecutar(() => api.accion(`/ubicaciones/${u.id}/reactivar`), `"${u.nombre}" reactivada`)) cargar();
  }

  return (
    <section>
      <EncabezadoPantalla id="ubicaciones" icono="🏬" titulo="Sucursales y Centro de Distribución"
        descripcion="El CD guarda y despacha la mercadería; las sucursales (locales) la reciben y la venden. Hay un solo CD activo."
        pasos={[
          "Creá primero el Centro de Distribución y después las sucursales.",
          "Las columnas Vende, Despacha y Recibe muestran qué puede hacer cada una.",
          "El tipo (sucursal o CD) no se puede cambiar después de crearla.",
        ]} />
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <ConfirmacionParecidos pendiente={parecidos.pendiente} alConfirmar={parecidos.confirmar}
        alCancelar={parecidos.descartar} />

      <form className="formulario" onSubmit={guardar}>
        <label>Tipo
          <select value={form.tipo} onChange={cambiar("tipo")} disabled={!!editandoId}
            title={editandoId ? "El tipo no se puede modificar" : ""}>
            <option value="SUCURSAL">Sucursal</option>
            <option value="CD">Centro de Distribución</option>
          </select>
        </label>
        <label>Nombre<input value={form.nombre} onChange={cambiar("nombre")} placeholder="Ej: Local Centro" /></label>
        <label>Dirección
          <input value={form.direccion} onChange={cambiar("direccion")} placeholder="Ej: San Martín 100" />
        </label>
        <div className="acciones">
          <button type="submit">{editandoId ? "Guardar cambios" : "Crear"}</button>
          {editandoId && <button type="button" className="secundario" onClick={cancelar}>Cancelar</button>}
        </div>
      </form>

      <div className="barra-filtro">
        <CheckBajas valor={verBajas} alCambiar={setVerBajas} />
        <label>Filtrar por tipo
          <select value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
            <option value="">Todas</option>
            <option value="SUCURSAL">Sucursales</option>
            <option value="CD">Centro de Distribución</option>
          </select>
        </label>
      </div>

      <div className="tabla-scroll">
        <table>
          <thead>
            <tr><th>Tipo</th><th>Nombre</th><th>Dirección</th>
              <th className="centro">Vende</th><th className="centro">Despacha</th><th className="centro">Recibe</th><th></th></tr>
          </thead>
          <tbody>
            {ubicaciones.map((u) => (
              <tr key={u.id} className={u.activo ? "" : "fila-baja"}>
                <td><span className={`etiqueta etiqueta-${u.tipo.toLowerCase()}`}>{NOMBRE_TIPO[u.tipo]}</span></td>
                <td>{u.nombre}{!u.activo && <EtiquetaBaja />}</td>
                <td>{u.direccion}</td>
                <td className="centro"><Capacidad si={u.puede_vender} /></td>
                <td className="centro"><Capacidad si={u.puede_despachar} /></td>
                <td className="centro"><Capacidad si={u.puede_recibir} /></td>
                <td className="botones-fila">
                  {u.activo ? (<>
                    <button className="secundario" onClick={() => editar(u)}>Editar</button>
                    <button className="peligro" onClick={() => darDeBaja(u)}>Dar de baja</button>
                  </>) : <button onClick={() => reactivar(u)}>Reactivar</button>}
                </td>
              </tr>
            ))}
            {ubicaciones.length === 0 && <tr><td colSpan="7" className="vacio">No hay ubicaciones activas</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
