// Pantalla de Categorías: alta, modificación, baja lógica y listado.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";

export default function Categorias() {
  const [categorias, setCategorias] = useState([]);
  const [nombre, setNombre] = useState("");
  const [editandoId, setEditandoId] = useState(null);
  const { aviso, ejecutar, limpiar } = useAviso();

  const cargar = () => ejecutar(async () => setCategorias(await api.listar("/categorias")));
  useEffect(() => { cargar(); }, []);

  function cancelar() {
    setEditandoId(null);
    setNombre("");
  }

  async function guardar(evento) {
    evento.preventDefault();
    const ok = editandoId
      ? await ejecutar(() => api.modificar(`/categorias/${editandoId}`, { nombre }), "Categoría modificada")
      : await ejecutar(() => api.crear("/categorias", { nombre }), "Categoría creada");
    if (ok) { cancelar(); cargar(); }
  }

  async function darDeBaja(categoria) {
    if (await ejecutar(() => api.borrar(`/categorias/${categoria.id}`), `"${categoria.nombre}" dada de baja`)) cargar();
  }

  return (
    <section>
      <h2>Categorías</h2>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      <form className="formulario" onSubmit={guardar}>
        <label>Nombre<input value={nombre} onChange={(e) => setNombre(e.target.value)} /></label>
        <div className="acciones">
          <button type="submit">{editandoId ? "Guardar cambios" : "Crear"}</button>
          {editandoId && <button type="button" className="secundario" onClick={cancelar}>Cancelar</button>}
        </div>
      </form>

      <table>
        <thead><tr><th>Id</th><th>Nombre</th><th></th></tr></thead>
        <tbody>
          {categorias.map((c) => (
            <tr key={c.id}>
              <td>{c.id}</td>
              <td>{c.nombre}</td>
              <td className="botones-fila">
                <button className="secundario" onClick={() => { setEditandoId(c.id); setNombre(c.nombre); }}>Editar</button>
                <button className="peligro" onClick={() => darDeBaja(c)}>Dar de baja</button>
              </td>
            </tr>
          ))}
          {categorias.length === 0 && <tr><td colSpan="3" className="vacio">No hay categorías activas</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
