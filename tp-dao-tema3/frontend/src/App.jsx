// Estructura general del front: sin sesión, la pantalla de login; con sesión,
// menú lateral a la izquierda y la pantalla elegida a la derecha. El menú se
// arma con las capacidades del usuario (las responde el back): cada pantalla
// dice qué capacidad necesita, nunca qué perfil. Se navega con estado de React
// (sin router): son pocas pantallas. Cada área tiene su color (tema-*).
import { useEffect, useState } from "react";

import { api, sesion } from "./api.js";
import { descripcionDelPerfil, puedeAlguna } from "./componentes/Permisos.js";
import Categorias from "./pantallas/Categorias.jsx";
import Inicio from "./pantallas/Inicio.jsx";
import Login from "./pantallas/Login.jsx";
import Logistica from "./pantallas/Logistica.jsx";
import Productos from "./pantallas/Productos.jsx";
import Proveedores from "./pantallas/Proveedores.jsx";
import Reportes from "./pantallas/Reportes.jsx";
import Stock from "./pantallas/Stock.jsx";
import Ubicaciones from "./pantallas/Ubicaciones.jsx";
import Usuarios from "./pantallas/Usuarios.jsx";
import Ventas from "./pantallas/Ventas.jsx";

// requiere: la pantalla se muestra si el usuario tiene ALGUNA de esas capacidades
const MAESTROS = ["puede_gestionar_maestros"];
const GRUPOS = [
  {
    titulo: "Operación",
    pantallas: [
      { clave: "inicio", icono: "🏠", titulo: "Inicio", tema: "tema-lavanda", Pantalla: Inicio },
      { clave: "ventas", icono: "🛒", titulo: "Vender", tema: "tema-durazno", Pantalla: Ventas, requiere: ["puede_vender"] },
      { clave: "logistica", icono: "🚚", titulo: "Envíos", tema: "tema-cielo", Pantalla: Logistica,
        requiere: ["puede_preparar_envios", "puede_pedir_reposicion", "puede_recibir"] },
      { clave: "stock", icono: "📦", titulo: "Stock", tema: "tema-menta", Pantalla: Stock },
      { clave: "reportes", icono: "📊", titulo: "Reportes", tema: "tema-rosa", Pantalla: Reportes },
    ],
  },
  {
    titulo: "Datos",
    pantallas: [
      { clave: "productos", icono: "🧃", titulo: "Productos", tema: "tema-manteca", Pantalla: Productos, requiere: MAESTROS },
      { clave: "categorias", icono: "🏷️", titulo: "Categorías", tema: "tema-manteca", Pantalla: Categorias, requiere: MAESTROS },
      { clave: "proveedores", icono: "🤝", titulo: "Proveedores", tema: "tema-manteca", Pantalla: Proveedores, requiere: MAESTROS },
      { clave: "ubicaciones", icono: "🏬", titulo: "Locales y CD", tema: "tema-manteca", Pantalla: Ubicaciones, requiere: MAESTROS },
      { clave: "usuarios", icono: "👤", titulo: "Usuarios", tema: "tema-manteca", Pantalla: Usuarios, requiere: MAESTROS },
    ],
  },
];

// Le suma al usuario el nombre de su ubicación, para mostrarlo arriba del menú
async function conUbicacion(usuario) {
  if (!usuario.ubicacion_id) return usuario;
  try {
    return { ...usuario, ubicacion_nombre: (await api.obtener(`/ubicaciones/${usuario.ubicacion_id}`)).nombre };
  } catch {
    return usuario;
  }
}

export default function App() {
  const [usuario, setUsuario] = useState(undefined);  // undefined = revisando la sesión; null = sin sesión
  const [motivo, setMotivo] = useState(null);          // por qué se volvió al login
  const [activa, setActiva] = useState("inicio");

  useEffect(() => {
    sesion.alVencer((mensaje) => { setUsuario(null); setMotivo(mensaje); });
    // Si quedó una sesión de antes (se recargó la página), se retoma
    if (!sesion.token()) { setUsuario(null); return; }
    api.obtener("/auth/yo").then(conUbicacion).then(setUsuario).catch(() => setUsuario(null));
  }, []);

  async function entrar(nuevo) {
    setMotivo(null);
    setActiva("inicio");
    setUsuario(await conUbicacion(nuevo));
  }

  async function salir() {
    await api.salir().catch(() => {});
    setUsuario(null);
  }

  if (usuario === undefined) return <div className="cargando">Cargando…</div>;
  if (usuario === null) return <Login alEntrar={entrar} motivo={motivo} />;

  const grupos = GRUPOS
    .map((g) => ({ ...g, pantallas: g.pantallas.filter((p) => puedeAlguna(usuario, p.requiere)) }))
    .filter((g) => g.pantallas.length > 0);
  const permitidas = grupos.flatMap((g) => g.pantallas);
  const { Pantalla, tema } = permitidas.find((p) => p.clave === activa) ?? permitidas[0];
  const puedeIr = (clave) => permitidas.some((p) => p.clave === clave);

  function irA(clave) {
    if (!puedeIr(clave)) return;
    setActiva(clave);
    window.scrollTo({ top: 0 });
  }

  return (
    <div className="app">
      <nav className="lateral" aria-label="Secciones">
        <div className="marca">
          <span className="marca-logo">V</span>
          <div><strong>Ventas e Inventario</strong><span>TP DAO · Tema 3</span></div>
        </div>
        <div className="quien-soy">
          <span className="avatar" aria-hidden="true">{usuario.nombre_completo.charAt(0)}</span>
          <div>
            <strong>{usuario.nombre_completo}</strong>
            <span>{descripcionDelPerfil(usuario)}</span>
            <button className="fantasma chico" onClick={salir} title="Cerrar la sesión">Salir</button>
          </div>
        </div>
        {grupos.map((grupo) => (
          <div key={grupo.titulo} className="grupo-menu">
            <div className="grupo-menu-titulo">{grupo.titulo}</div>
            {grupo.pantallas.map((p) => (
              <button key={p.clave} className={`item-menu ${p.tema} ${p.clave === activa ? "activo" : ""}`}
                onClick={() => irA(p.clave)} aria-current={p.clave === activa ? "page" : undefined}>
                <span className="icono-menu" aria-hidden="true">{p.icono}</span> {p.titulo}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <main className={`contenido ${tema}`}>
        {/* key: al cambiar de pantalla arranca de cero */}
        <Pantalla key={activa} irA={irA} puedeIr={puedeIr} usuario={usuario} />
      </main>
    </div>
  );
}
