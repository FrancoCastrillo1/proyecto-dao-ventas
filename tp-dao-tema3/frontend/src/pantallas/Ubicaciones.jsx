// Pantalla de Locales y Centro de Distribución: listado con filtro por tipo,
// alta y edición en un panel lateral, baja lógica y reactivación. Muestra qué
// puede hacer cada una (vender / despachar / recibir), que viene del
// polimorfismo del backend. No se valida nada acá: los errores los muestra el backend.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import { textoBaja } from "../componentes/Bajas.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { Confirmacion, useConfirmacion } from "../componentes/Confirmacion.jsx";
import { ConfirmacionParecidos, useParecidos } from "../componentes/ConfirmacionParecidos.jsx";
import { Cargando, Segmentado, Vacio } from "../componentes/Controles.jsx";

const TIPOS = {
  SUCURSAL: { icono: "🏬", nombre: "Local", que: "Recibe mercadería del CD y la vende" },
  CD: { icono: "🏭", nombre: "Centro de Distribución", que: "Compra, guarda y despacha a los locales. Hay uno solo activo." },
};

export default function Ubicaciones() {
  const [ubicaciones, setUbicaciones] = useState(null);  // null = cargando; trae también las dadas de baja
  const [tipo, setTipo] = useState("");
  const [verActivas, setVerActivas] = useState(true);
  const [editando, setEditando] = useState(null);        // null = cerrado; {} = nueva; ubicación = editar
  const { aviso, ejecutar, limpiar } = useAviso();
  const confirmacion = useConfirmacion();

  const cargar = () => ejecutar(async () => setUbicaciones(await api.listar("/ubicaciones?incluir_bajas=true")));
  useEffect(() => { cargar(); }, []);

  function pedirBaja(u) {
    confirmacion.pedir({ titulo: `¿Dar de baja «${u.nombre}»?`, textoConfirmar: "Dar de baja", peligro: true, detalle: textoBaja },
      async () => {
        if (await ejecutar(() => api.borrar(`/ubicaciones/${u.id}`), `«${u.nombre}» dada de baja`)) { setEditando(null); cargar(); }
      });
  }

  async function reactivar(u) {
    if (await ejecutar(() => api.accion(`/ubicaciones/${u.id}/reactivar`), `«${u.nombre}» vuelve a estar activa`)) cargar();
  }

  const lista = ubicaciones ?? [];
  const deBaja = lista.filter((u) => !u.activo).length;
  const visibles = lista.filter((u) => u.activo === verActivas && (!tipo || u.tipo === tipo));
  const hayCD = lista.some((u) => u.activo && u.tipo === "CD");

  return (
    <section>
      <Cabecera icono="🏬" titulo="Locales y CD" subtitulo="El CD despacha la mercadería; los locales la reciben y la venden">
        <button onClick={() => setEditando({})}>+ Nueva ubicación</button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <Confirmacion confirmacion={confirmacion} />

      <div className="barra">
        <Segmentado etiqueta="Tipo" valor={tipo} alCambiar={setTipo} opciones={[
          { valor: "", texto: "Todas" }, { valor: "SUCURSAL", texto: "🏬 Locales" }, { valor: "CD", texto: "🏭 CD" },
        ]} />
        <Segmentado etiqueta="Mostrar" valor={verActivas} alCambiar={setVerActivas} opciones={[
          { valor: true, texto: "Activas", contador: lista.length - deBaja },
          { valor: false, texto: "De baja", contador: deBaja },
        ]} />
      </div>

      {ubicaciones === null ? <Cargando /> : visibles.length === 0 ? (
        !verActivas ? <Vacio icono="✨" titulo="No hay ubicaciones dadas de baja" />
          : lista.length === 0
            ? <Vacio icono="🏭" titulo="Empezá por el Centro de Distribución" texto="Después creá los locales que se abastecen de él."
              accion="+ Nueva ubicación" alAccionar={() => setEditando({ tipo: "CD" })} />
            : <Vacio icono="🔍" titulo="No hay ubicaciones de este tipo" />
      ) : (
        <div className="tarjeta-tabla">
          <table>
            <thead><tr><th>Nombre</th><th>Tipo</th><th>Qué puede hacer</th><th></th></tr></thead>
            <tbody>
              {visibles.map((u) => (
                <tr key={u.id} className={u.activo ? "fila-clic" : "fila-baja"} onClick={u.activo ? () => setEditando(u) : undefined}>
                  <td><strong>{u.nombre}</strong><span className="secundario-texto">{u.direccion}</span></td>
                  <td>{TIPOS[u.tipo].icono} {TIPOS[u.tipo].nombre}</td>
                  <td><div className="capacidades">
                    {u.puede_vender && <span className="etiqueta estado-naranja">Vende</span>}
                    {u.puede_despachar && <span className="etiqueta estado-azul">Despacha</span>}
                    {u.puede_recibir && <span className="etiqueta estado-verde">Recibe</span>}
                  </div></td>
                  <td><div className="acciones-fila">
                    {u.activo
                      ? <button className="fantasma chico">Editar</button>
                      : <button className="secundario chico" onClick={() => reactivar(u)}>Reactivar</button>}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <CajonUbicacion ubicacion={editando} hayCD={hayCD} ejecutar={ejecutar} alCerrar={() => setEditando(null)}
          alGuardar={() => { setEditando(null); cargar(); }} alDarDeBaja={() => pedirBaja(editando)} />
      )}
    </section>
  );
}

function CajonUbicacion({ ubicacion, hayCD, ejecutar, alCerrar, alGuardar, alDarDeBaja }) {
  const nueva = !ubicacion.id;
  const [form, setForm] = useState({ tipo: ubicacion.tipo ?? (hayCD ? "SUCURSAL" : "CD"), nombre: ubicacion.nombre ?? "", direccion: ubicacion.direccion ?? "" });
  const parecidos = useParecidos();
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  // Antes de guardar se consulta si hay nombres parecidos ("¿es un duplicado?")
  function guardar(evento) {
    evento.preventDefault();
    parecidos.verificar("/ubicaciones", { nombre: form.nombre }, ubicacion.id, async () => {
      const datos = { nombre: form.nombre, direccion: form.direccion };
      // Al modificar no se manda el tipo: una ubicación no cambia de clase
      const ok = nueva
        ? await ejecutar(() => api.crear("/ubicaciones", { tipo: form.tipo, ...datos }), `«${form.nombre.trim()}» creada`)
        : await ejecutar(() => api.modificar(`/ubicaciones/${ubicacion.id}`, datos), "Cambios guardados");
      if (ok) alGuardar();
    });
  }

  return (
    <Cajon titulo={nueva ? "Nueva ubicación" : ubicacion.nombre}
      subtitulo={nueva ? null : `${TIPOS[ubicacion.tipo].icono} ${TIPOS[ubicacion.tipo].nombre}`} alCerrar={alCerrar}
      pie={<>
        {!nueva && <button className="peligro izquierda" onClick={alDarDeBaja}>Dar de baja</button>}
        <button className="secundario" onClick={alCerrar}>Cancelar</button>
        <button type="submit" form="form-ubicacion">{nueva ? "Crear" : "Guardar"}</button>
      </>}>
      <form id="form-ubicacion" className="campos" onSubmit={guardar}>
        {nueva && (
          <div>
            <span className="etiqueta-campo">¿Qué es?</span>
            <div className="opciones-grandes">
              {Object.entries(TIPOS).map(([clave, t]) => (
                <button type="button" key={clave} className={`opcion-grande ${form.tipo === clave ? "activo" : ""}`}
                  onClick={() => setForm({ ...form, tipo: clave })}>
                  <span className="opcion-icono">{t.icono}</span>
                  <strong>{t.nombre}</strong>
                  <small>{t.que}</small>
                </button>
              ))}
            </div>
            <span className="ayuda-campo">No se puede cambiar después.</span>
          </div>
        )}
        <label>Nombre<input value={form.nombre} onChange={cambiar("nombre")} placeholder={form.tipo === "CD" ? "Ej: CD Central" : "Ej: Local Centro"} /></label>
        <label>Dirección<input value={form.direccion} onChange={cambiar("direccion")} placeholder="Ej: San Martín 100" /></label>
      </form>
      <ConfirmacionParecidos pendiente={parecidos.pendiente} alConfirmar={parecidos.confirmar} alCancelar={parecidos.descartar} />
    </Cajon>
  );
}
