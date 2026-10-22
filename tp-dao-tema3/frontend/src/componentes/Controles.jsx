// Controles chicos que se repiten en todas las pantallas: buscador, botones
// segmentados (filtros de una sola opción), el estado vacío con su acción y la
// fila de "Cargando…". Acá NO va lógica de ninguna entidad.

export function Buscador({ valor, alCambiar, placeholder = "Buscar…" }) {
  return (
    <div className="buscador">
      <input type="search" value={valor} onChange={(e) => alCambiar(e.target.value)} placeholder={placeholder}
        aria-label={placeholder} />
    </div>
  );
}

// opciones: [{ valor, texto, contador? }]
export function Segmentado({ opciones, valor, alCambiar, etiqueta }) {
  return (
    <div className="segmentado" role="radiogroup" aria-label={etiqueta}>
      {opciones.map((o) => (
        <button key={String(o.valor)} type="button" role="radio" aria-checked={o.valor === valor}
          className={o.valor === valor ? "activo" : ""} onClick={() => alCambiar(o.valor)}>
          {o.texto}
          {o.contador !== undefined && <span className="contador">{o.contador}</span>}
        </button>
      ))}
    </div>
  );
}

// Lo que se ve cuando una lista está vacía: qué es y cómo empezar
export function Vacio({ icono, titulo, texto, accion, alAccionar }) {
  return (
    <div className="vacio-grande">
      <span className="icono-vacio" aria-hidden="true">{icono}</span>
      <strong>{titulo}</strong>
      {texto && <p>{texto}</p>}
      {accion && <button onClick={alAccionar}>{accion}</button>}
    </div>
  );
}

export function Cargando() {
  return <div className="cargando">Cargando…</div>;
}

// Filtra por texto sin importar mayúsculas ni tildes
export function coincide(texto, busqueda) {
  const normalizar = (t) => (t ?? "").toString().normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  return normalizar(texto).includes(normalizar(busqueda));
}
