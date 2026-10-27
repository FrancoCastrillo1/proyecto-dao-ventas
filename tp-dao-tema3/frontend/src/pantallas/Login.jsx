// Pantalla de entrada: usuario y contraseña. Es lo único que se ve sin sesión.
// Si la sesión venció, muestra por qué volviste acá.
// Acá NO se decide qué ve cada perfil: eso lo arma App con las capacidades
// que devuelve el back.
import { useState } from "react";

import { api } from "../api.js";
import Icono from "../componentes/Icono.jsx";

// Los usuarios que carga el seed (backend/datos/seed.py), para que quien corrige
// entre con un clic. En un sistema real esto no iría.
const CLAVE_DE_PRUEBA = "tpdao2026";
const USUARIOS_DE_PRUEBA = [
  { usuario: "admin", perfil: "Administrador" },
  { usuario: "cd.central", perfil: "Centro de Distribución" },
  { usuario: "centro", perfil: "Local Centro" },
  { usuario: "norte", perfil: "Local Norte" },
  { usuario: "sur", perfil: "Local Sur" },
];

export default function Login({ alEntrar, motivo }) {
  const [nombre, setNombre] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState(null);
  const [entrando, setEntrando] = useState(false);

  async function entrar(evento) {
    evento.preventDefault();
    setError(null);
    setEntrando(true);
    try {
      alEntrar(await api.entrar(nombre, contrasena));
    } catch (e) {
      setError(e.message);
      setContrasena("");
    } finally {
      setEntrando(false);
    }
  }

  function usarDePrueba(usuario) {
    setNombre(usuario);
    setContrasena(CLAVE_DE_PRUEBA);
    setError(null);
  }

  return (
    <main className="pantalla-login">
      <section className="login-presentacion">
        <div className="marca">
          <span className="marca-logo"><Icono nombre="caja" tamano={20} /></span>
          <div><strong>Ventas e Inventario</strong><span>TP DAO · Tema 3</span></div>
        </div>
        <div className="login-lema">
          <h2>La mercadería de tu red de locales, de punta a punta.</h2>
          <ul>
            <li><Icono nombre="cd" /> <span><strong>El Centro de Distribución</strong> compra y arma los envíos.</span></li>
            <li><Icono nombre="precinto" /> <span><strong>Los bultos viajan precintados</strong> y el local verifica el precinto al recibirlos.</span></li>
            <li><Icono nombre="carrito" /> <span><strong>El local vende</strong> solo lo que llegó verificado.</span></li>
          </ul>
        </div>
        <span className="login-pie">Python · FastAPI · SQLite · React</span>
      </section>

      <section className="login-formulario">
        <form className="tarjeta-login" onSubmit={entrar}>
          <div>
            <h1>Bienvenido</h1>
            <p className="nota">Entrá con tu usuario para empezar.</p>
          </div>
          {motivo && !error && <p className="aviso aviso-advertencia">{motivo}</p>}
          {error && <p className="aviso aviso-error" role="alert">{error}</p>}
          <label>Usuario
            <input autoFocus autoComplete="username" value={nombre} onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej: centro" />
          </label>
          <label>Contraseña
            <input type="password" autoComplete="current-password" value={contrasena}
              onChange={(e) => setContrasena(e.target.value)} />
          </label>
          <button type="submit" className="grande" disabled={!nombre.trim() || !contrasena || entrando}>
            {entrando ? "Entrando…" : "Entrar"}
          </button>

          <div className="usuarios-prueba">
            <span className="etiqueta-campo">Usuarios de prueba <small>· tocá uno para completar</small></span>
            <div className="chips">
              {USUARIOS_DE_PRUEBA.map((u) => (
                <button key={u.usuario} type="button" className={`chip ${nombre === u.usuario ? "activo" : ""}`}
                  onClick={() => usarDePrueba(u.usuario)} title={u.perfil}>
                  <strong>{u.usuario}</strong><small>{u.perfil}</small>
                </button>
              ))}
            </div>
            <span className="ayuda-campo">Contraseña de todos: <code>{CLAVE_DE_PRUEBA}</code></span>
          </div>
        </form>
      </section>
    </main>
  );
}
