// Pantalla de Categorías: listado con buscador, alta y edición en un panel
// lateral, baja lógica (con confirmación) y reactivación.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { Confirmacion, useConfirmacion } from "../componentes/Confirmacion.jsx";
import { ConfirmacionParecidos, useParecidos } from "../componentes/ConfirmacionParecidos.jsx";
import { Buscador, Cargando, coincide, Segmentado, Vacio } from "../componentes/Controles.jsx";
import { textoBaja } from "../componentes/Bajas.jsx";

export default function Categorias() {
  const [categorias, setCategorias] = useState(null);  // null = cargando; trae también las dadas de baja
  const [busqueda, setBusqueda] = useState("");
  const [verActivas, setVerActivas] = useState(true);
  const [editando, setEditando] = useState(null);      // null = cerrado; {} = nueva; categoría = editar
  const { aviso, ejecutar, limpiar } = useAviso();
  const confirmacion = useConfirmacion();

  const cargar = () => ejecutar(async () => setCategorias(await api.listar("/categorias?incluir_bajas=true")));
  useEffect(() => { cargar(); }, []);

  function pedirBaja(c) {
    confirmacion.pedir({ titulo: `¿Dar de baja «${c.nombre}»?`, textoConfirmar: "Dar de baja", peligro: true, detalle: textoBaja },
      async () => {
        if (await ejecutar(() => api.borrar(`/categorias/${c.id}`), `«${c.nombre}» dada de baja`)) { setEditando(null); cargar(); }
      });
  }

  async function reactivar(c) {
    if (await ejecutar(() => api.accion(`/categorias/${c.id}/reactivar`), `«${c.nombre}» vuelve a estar activa`)) cargar();
  }

  const deBaja = (categorias ?? []).filter((c) => !c.activo).length;
  const visibles = (categorias ?? []).filter((c) => c.activo === verActivas && coincide(c.nombre, busqueda));

  return (
    <section>
      <Cabecera icono="etiqueta" titulo="Categorías" subtitulo="Agrupan los productos: Bebidas, Almacén, Limpieza…">
        <button onClick={() => setEditando({})}>+ Nueva categoría</button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <Confirmacion confirmacion={confirmacion} />

      <div className="barra">
        <Buscador valor={busqueda} alCambiar={setBusqueda} placeholder="Buscar categoría" />
        <Segmentado etiqueta="Mostrar" valor={verActivas} alCambiar={setVerActivas} opciones={[
          { valor: true, texto: "Activas", contador: (categorias?.length ?? 0) - deBaja },
          { valor: false, texto: "De baja", contador: deBaja },
        ]} />
      </div>

      {categorias === null ? <Cargando /> : visibles.length === 0 ? (
        busqueda ? <Vacio icono="buscar" titulo={`Nada coincide con «${busqueda}»`} />
          : verActivas ? <Vacio icono="etiqueta" titulo="Todavía no hay categorías" texto="Creá la primera para poder cargar productos."
            accion="+ Nueva categoría" alAccionar={() => setEditando({})} />
            : <Vacio icono="nuevo" titulo="No hay categorías dadas de baja" />
      ) : (
        <div className="tarjeta-tabla">
          <table>
            <thead><tr><th>Nombre</th><th></th></tr></thead>
            <tbody>
              {visibles.map((c) => (
                <tr key={c.id} className={c.activo ? "fila-clic" : "fila-baja"} onClick={c.activo ? () => setEditando(c) : undefined}>
                  <td><strong>{c.nombre}</strong></td>
                  <td><div className="acciones-fila">
                    {c.activo
                      ? <button className="fantasma chico">Editar</button>
                      : <button className="secundario chico" onClick={() => reactivar(c)}>Reactivar</button>}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <CajonCategoria categoria={editando} ejecutar={ejecutar} alCerrar={() => setEditando(null)}
          alGuardar={() => { setEditando(null); cargar(); }} alDarDeBaja={() => pedirBaja(editando)} />
      )}
    </section>
  );
}

function CajonCategoria({ categoria, ejecutar, alCerrar, alGuardar, alDarDeBaja }) {
  const [nombre, setNombre] = useState(categoria.nombre ?? "");
  const parecidos = useParecidos();
  const nueva = !categoria.id;

  // Antes de guardar se consulta si hay nombres parecidos ("¿es un duplicado?")
  function guardar(evento) {
    evento.preventDefault();
    parecidos.verificar("/categorias", { nombre }, categoria.id, async () => {
      const ok = nueva
        ? await ejecutar(() => api.crear("/categorias", { nombre }), `Categoría «${nombre.trim()}» creada`)
        : await ejecutar(() => api.modificar(`/categorias/${categoria.id}`, { nombre }), "Cambios guardados");
      if (ok) alGuardar();
    });
  }

  return (
    <Cajon titulo={nueva ? "Nueva categoría" : categoria.nombre} alCerrar={alCerrar}
      pie={<>
        {!nueva && <button className="peligro izquierda" onClick={alDarDeBaja}>Dar de baja</button>}
        <button className="secundario" onClick={alCerrar}>Cancelar</button>
        <button type="submit" form="form-categoria" disabled={!nombre.trim()}>{nueva ? "Crear" : "Guardar"}</button>
      </>}>
      <form id="form-categoria" className="campos" onSubmit={guardar}>
        <label>Nombre<input autoFocus value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej: Bebidas" /></label>
      </form>
      <ConfirmacionParecidos pendiente={parecidos.pendiente} alConfirmar={parecidos.confirmar} alCancelar={parecidos.descartar} />
    </Cajon>
  );
}
