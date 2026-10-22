// Encabezado de cada pantalla: ícono, título, una línea que dice para qué sirve
// y, a la derecha, el botón de la acción principal (ej. "+ Nuevo producto").
// Acá NO va lógica de ninguna entidad.

export default function Cabecera({ icono, titulo, subtitulo, children }) {
  return (
    <header className="cabecera">
      <div className="cabecera-icono" aria-hidden="true">{icono}</div>
      <div className="cabecera-textos">
        <h1>{titulo}</h1>
        {subtitulo && <p>{subtitulo}</p>}
      </div>
      {children && <div className="cabecera-acciones">{children}</div>}
    </header>
  );
}
