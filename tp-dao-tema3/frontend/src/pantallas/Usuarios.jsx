// Pantalla de Usuarios (solo el administrador): listado con buscador y filtro
// por perfil; alta en un panel lateral (perfil, dónde trabaja y contraseña),
// cambio de nombre y de contraseña, baja lógica con confirmación y reactivación.
// El perfil, el nombre de usuario y el lugar de trabajo no se cambian después.
// No se valida nada acá a propósito: los errores los muestra el backend.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import Cajon from "../componentes/Cajon.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { Confirmacion, useConfirmacion } from "../componentes/Confirmacion.jsx";
import { Buscador, Cargando, coincide, Segmentado, Vacio } from "../componentes/Controles.jsx";

const PERFILES = {
  ADMIN: { icono: "🛡️", nombre: "Administrador", que: "Maneja locales, productos, proveedores y usuarios. Ve toda la red, no opera." },
  CD: { icono: "🏭", nombre: "Centro de Distribución", que: "Compra, arma los envíos y los despacha a los locales." },
  SUCURSAL: { icono: "🏬", nombre: "Local", que: "Pide mercadería, la recibe y vende. Ve solo su local." },
};

export default function Usuarios({ usuario: yo }) {
  const catalogos = useCatalogos();
  const [usuarios, setUsuarios] = useState(null);   // null = cargando; trae también los dados de baja
  const [busqueda, setBusqueda] = useState("");
  const [perfil, setPerfil] = useState("");
  const [verActivos, setVerActivos] = useState(true);
  const [editando, setEditando] = useState(null);   // null = cerrado; {} = nuevo; usuario = editar
  const { aviso, ejecutar, limpiar } = useAviso();
  const confirmacion = useConfirmacion();

  const cargar = () => ejecutar(async () => setUsuarios(await api.listar("/usuarios?incluir_bajas=true")));
  useEffect(() => { cargar(); }, []);

  const dondeTrabaja = (u) => (u.ubicacion_id ? catalogos.nombreUbicacion(u.ubicacion_id) : "Toda la red");

  function pedirBaja(u) {
    confirmacion.pedir({
      titulo: `¿Dar de baja a ${u.nombre_completo}?`, textoConfirmar: "Dar de baja", peligro: true,
      detalle: <p>No va a poder entrar más, y si estaba adentro se le cierra la sesión. Lo que hizo queda registrado
        con su nombre. Se puede volver a activar desde «De baja».</p>,
    }, async () => {
      if (await ejecutar(() => api.borrar(`/usuarios/${u.id}`), `${u.nombre_completo} ya no puede entrar`)) { setEditando(null); cargar(); }
    });
  }

  async function reactivar(u) {
    if (await ejecutar(() => api.accion(`/usuarios/${u.id}/reactivar`), `${u.nombre_completo} puede volver a entrar`)) cargar();
  }

  const lista = usuarios ?? [];
  const deBaja = lista.filter((u) => !u.activo).length;
  const visibles = lista
    .filter((u) => u.activo === verActivos && (!perfil || u.perfil === perfil))
    .filter((u) => coincide(u.nombre_completo, busqueda) || coincide(u.nombre_usuario, busqueda));

  return (
    <section>
      <Cabecera icono="👤" titulo="Usuarios" subtitulo="Quién entra al sistema y qué puede hacer cada uno">
        <button onClick={() => setEditando({})}>+ Nuevo usuario</button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <Confirmacion confirmacion={confirmacion} />

      <div className="barra">
        <Buscador valor={busqueda} alCambiar={setBusqueda} placeholder="Buscar por nombre o usuario" />
        <Segmentado etiqueta="Perfil" valor={perfil} alCambiar={setPerfil} opciones={[
          { valor: "", texto: "Todos" },
          ...Object.entries(PERFILES).map(([clave, p]) => ({ valor: clave, texto: `${p.icono} ${p.nombre}` })),
        ]} />
        <Segmentado etiqueta="Mostrar" valor={verActivos} alCambiar={setVerActivos} opciones={[
          { valor: true, texto: "Activos", contador: lista.length - deBaja },
          { valor: false, texto: "De baja", contador: deBaja },
        ]} />
      </div>

      {usuarios === null ? <Cargando /> : visibles.length === 0 ? (
        busqueda || perfil ? <Vacio icono="🔍" titulo="Ningún usuario coincide" texto="Probá con otra búsqueda u otro perfil." />
          : verActivos ? <Vacio icono="👤" titulo="Todavía no hay usuarios" accion="+ Nuevo usuario" alAccionar={() => setEditando({})} />
            : <Vacio icono="✨" titulo="No hay usuarios dados de baja" />
      ) : (
        <div className="tarjeta-tabla">
          <table>
            <thead><tr><th>Usuario</th><th>Perfil</th><th>Dónde trabaja</th><th></th></tr></thead>
            <tbody>
              {visibles.map((u) => (
                <tr key={u.id} className={u.activo ? "fila-clic" : "fila-baja"} onClick={u.activo ? () => setEditando(u) : undefined}>
                  <td><strong>{u.nombre_completo}</strong>{u.id === yo.id && <span className="etiqueta etiqueta-baja">Vos</span>}
                    <span className="secundario-texto">{u.nombre_usuario}</span></td>
                  <td>{PERFILES[u.perfil].icono} {PERFILES[u.perfil].nombre}</td>
                  <td>{dondeTrabaja(u)}</td>
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
        <CajonUsuario key={editando.id ?? "nuevo"} usuario={editando} catalogos={catalogos} ejecutar={ejecutar}
          dondeTrabaja={dondeTrabaja} alCerrar={() => setEditando(null)}
          alGuardar={() => { setEditando(null); cargar(); }} alDarDeBaja={() => pedirBaja(editando)} />
      )}
    </section>
  );
}

function CajonUsuario({ usuario, catalogos, ejecutar, dondeTrabaja, alCerrar, alGuardar, alDarDeBaja }) {
  const nuevo = !usuario.id;
  const [form, setForm] = useState({
    perfil: usuario.perfil ?? "SUCURSAL", ubicacion_id: "", nombre_usuario: "",
    nombre_completo: usuario.nombre_completo ?? "", contrasena: "",
  });
  const [nuevaContrasena, setNuevaContrasena] = useState("");
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  const cd = catalogos.ubicacionesActivas.find((u) => u.puede_despachar);
  const locales = catalogos.ubicacionesActivas.filter((u) => u.puede_vender);

  // El CD es uno solo: no hace falta elegirlo
  const ubicacionElegida = form.perfil === "CD" ? cd?.id : form.perfil === "SUCURSAL" ? Number(form.ubicacion_id) || null : null;

  async function guardar(evento) {
    evento.preventDefault();
    const ok = nuevo
      ? await ejecutar(() => api.crear("/usuarios", { ...form, ubicacion_id: ubicacionElegida }),
        `Usuario «${form.nombre_usuario.trim().toLowerCase()}» creado: ya puede entrar`)
      : await ejecutar(() => api.modificar(`/usuarios/${usuario.id}`, { nombre_completo: form.nombre_completo }), "Cambios guardados");
    if (ok) alGuardar();
  }

  async function cambiarContrasena() {
    if (await ejecutar(() => api.modificar(`/usuarios/${usuario.id}/contrasena`, { contrasena: nuevaContrasena }),
      "Contraseña cambiada: tiene que volver a entrar con la nueva")) setNuevaContrasena("");
  }

  return (
    <Cajon titulo={nuevo ? "Nuevo usuario" : usuario.nombre_completo}
      subtitulo={nuevo ? null : `${usuario.nombre_usuario} · ${PERFILES[usuario.perfil].nombre} · ${dondeTrabaja(usuario)}`}
      alCerrar={alCerrar}
      pie={<>
        {!nuevo && <button className="peligro izquierda" onClick={alDarDeBaja}>Dar de baja</button>}
        <button className="secundario" onClick={alCerrar}>Cancelar</button>
        <button type="submit" form="form-usuario">{nuevo ? "Crear usuario" : "Guardar"}</button>
      </>}>
      <form id="form-usuario" className="campos" onSubmit={guardar}>
        {nuevo && (<>
          <div>
            <span className="etiqueta-campo">¿Qué perfil tiene?</span>
            <div className="opciones-grandes tres">
              {Object.entries(PERFILES).map(([clave, p]) => (
                <button type="button" key={clave} className={`opcion-grande ${form.perfil === clave ? "activo" : ""}`}
                  onClick={() => setForm({ ...form, perfil: clave })}>
                  <span className="opcion-icono">{p.icono}</span>
                  <strong>{p.nombre}</strong>
                  <small>{p.que}</small>
                </button>
              ))}
            </div>
            <span className="ayuda-campo">El perfil y el lugar de trabajo no se pueden cambiar después.</span>
          </div>
          {form.perfil === "SUCURSAL" && (
            <label>¿En qué local trabaja?
              <select value={form.ubicacion_id} onChange={cambiar("ubicacion_id")}>
                <option value="">Elegí un local</option>
                {locales.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </select>
            </label>
          )}
          {form.perfil === "CD" && <p className="nota">Trabaja en {cd ? <strong>{cd.nombre}</strong> : "el CD (todavía no hay uno activo)"}.</p>}
        </>)}
        <label>Nombre completo<input autoFocus={!nuevo} value={form.nombre_completo} onChange={cambiar("nombre_completo")} placeholder="Ej: Ana López" /></label>
        {nuevo && (<>
          <label>Usuario (con el que entra)
            <input value={form.nombre_usuario} onChange={cambiar("nombre_usuario")} placeholder="Ej: ana.lopez" autoComplete="off" />
            <span className="ayuda-campo">Entre 3 y 30 letras, números, punto o guion. No se puede repetir.</span>
          </label>
          <label>Contraseña
            <input type="password" value={form.contrasena} onChange={cambiar("contrasena")} autoComplete="new-password" />
            <span className="ayuda-campo">Al menos 8 caracteres. Pasásela a la persona: después la puede cambiar el administrador.</span>
          </label>
        </>)}
      </form>

      {!nuevo && (
        <div className="seccion-cajon">
          <h3>Cambiar la contraseña</h3>
          <div className="linea">
            <input type="password" value={nuevaContrasena} onChange={(e) => setNuevaContrasena(e.target.value)}
              placeholder="Nueva contraseña (8 caracteres o más)" autoComplete="new-password" aria-label="Nueva contraseña" />
            <button className="secundario" onClick={cambiarContrasena} disabled={!nuevaContrasena}>Cambiar</button>
          </div>
          <p className="ayuda-campo espacio-arriba-chico">Si estaba adentro, se le cierra la sesión.</p>
        </div>
      )}
    </Cajon>
  );
}
