// Editor de líneas "producto + cantidad" que usan el pedido, el bulto, la
// venta y la devolución. No valida nada: las reglas (cantidad positiva, no
// más de lo pedido, stock suficiente...) las controla el backend.

export const LINEA_VACIA = { producto_id: "", cantidad: "1" };

// Convierte las líneas del formulario en los items que espera la api
export function aItems(lineas) {
  return lineas.filter((l) => l.producto_id !== "").map((l) => ({ producto_id: l.producto_id, cantidad: l.cantidad }));
}

export default function LineasProductos({ lineas, alCambiar, productos }) {
  const cambiar = (i, campo, valor) => alCambiar(lineas.map((l, j) => (i === j ? { ...l, [campo]: valor } : l)));
  const quitar = (i) => alCambiar(lineas.filter((_, j) => j !== i));

  return (
    <div className="lineas">
      {lineas.map((linea, i) => (
        <div className="linea" key={i}>
          <select value={linea.producto_id} onChange={(e) => cambiar(i, "producto_id", e.target.value)}>
            <option value="">— producto —</option>
            {productos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}
          </select>
          <input className="cantidad" value={linea.cantidad} onChange={(e) => cambiar(i, "cantidad", e.target.value)}
            placeholder="Cant." aria-label="Cantidad" />
          {lineas.length > 1 && (
            <button type="button" className="secundario" onClick={() => quitar(i)} aria-label="Quitar línea">×</button>
          )}
        </div>
      ))}
      <button type="button" className="secundario" onClick={() => alCambiar([...lineas, { ...LINEA_VACIA }])}>
        + Agregar producto
      </button>
    </div>
  );
}
