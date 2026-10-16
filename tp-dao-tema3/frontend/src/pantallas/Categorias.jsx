// Pantalla de Categorías: alta, modificación, baja lógica y listado.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import { ConfirmacionParecidos, useParecidos } from "../componentes/ConfirmacionParecidos.jsx";
import { CheckBajas, EtiquetaBaja } from "../componentes/Bajas.jsx";

export default function Categorias() {
  const [categorias, setCategorias] = useState([]);
  const [nombre, setNombre] = useState("");
  const [editandoId, setEditandoId] = useState(null);
  const [verBajas, setVerBajas] = useState(false);
  const { aviso, ejecutar, limpiar } = useAviso();
  const parecidos = useParecidos();

  const cargar = () => ejecutar(async () => setCategorias(await api.listar(`/categorias?incluir_bajas=${verBajas}`)));
  useEffect(() => { cargar(); }, [verBajas]);

  function cancelar() {
    parecidos.descartar();
    setEditandoId(null);
    setNombre("");
  }

  // Antes de guardar se consulta si hay nombres parecidos ("¿es un duplicado?")
  function guardar(evento) {
    evento.preventDefault();
    parecidos.verificar("/categorias", { nombre }, editandoId, enviar);
  }

  async function enviar() {
    const ok = editandoId
      ? await ejecutar(() => api.modificar(`/categorias/${editandoId}`, { nombre }), "Categoría modificada")
      : await ejecutar(() => api.crear("/categorias", { nombre }), "Categoría creada");
    if (ok) { cancelar(); cargar(); }
  }

  async function darDeBaja(categoria) {
    if (await ejecutar(() => api.borrar(`/categorias/${categoria.id}`), `"${categoria.nombre}" dada de baja`)) cargar();
  }

  async function reactivar(categoria) {
    if (await ejecutar(() => api.accion(`/categorias/${categoria.id}/reactivar`), `"${categoria.nombre}" reactivada`)) cargar();
  }

  return (
    <section>
      <h2>Categorías</h2>
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <ConfirmacionParecidos pendiente={parecidos.pendiente} alConfirmar={parecidos.confirmar}
        alCancelar={parecidos.descartar} />

      <form className="formulario" onSubmit={guardar}>
        <label>Nombre<input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej: Bebidas" /></label>
        <div className="acciones">
          <button type="submit">{editandoId ? "Guardar cambios" : "Crear"}</button>
          {editandoId && <button type="button" className="secundario" onClick={cancelar}>Cancelar</button>}
        </div>
      </form>

      <div className="barra-filtro"><CheckBajas valor={verBajas} alCambiar={setVerBajas} /></div>

      <table>
        <thead><tr><th>Id</th><th>Nombre</th><th></th></tr></thead>
        <tbody>
          {categorias.map((c) => (
            <tr key={c.id} className={c.activo ? "" : "fila-baja"}>
              <td>{c.id}</td>
              <td>{c.nombre}{!c.activo && <EtiquetaBaja />}</td>
              <td className="botones-fila">
                {c.activo ? (<>
                  <button className="secundario" onClick={() => { setEditandoId(c.id); setNombre(c.nombre); }}>Editar</button>
                  <button className="peligro" onClick={() => darDeBaja(c)}>Dar de baja</button>
                </>) : <button onClick={() => reactivar(c)}>Reactivar</button>}
              </td>
            </tr>
          ))}
          {categorias.length === 0 && <tr><td colSpan="3" className="vacio">No hay categorías activas</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
