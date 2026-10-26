// Pantalla de entrada: usuario y contraseña. Es lo único que se ve sin sesión.
// Si la sesión venció, muestra por qué volviste acá.
// Acá NO se decide qué ve cada perfil: eso lo arma App con las capacidades
// que devuelve el back.
import { useState } from "react";

import { api } from "../api.js";

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

  return (
    <main className="pantalla-login">
      <form className="tarjeta-login" onSubmit={entrar}>
        <div className="marca">
          <span className="marca-logo">V</span>
          <div><strong>Ventas e Inventario</strong><span>TP DAO · Tema 3</span></div>
        </div>
        <h1>Entrar</h1>
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
      </form>
    </main>
  );
}
