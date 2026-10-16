// Piezas compartidas para ver y reactivar lo que se dio de baja (la baja es
// lógica: el registro sigue existiendo). Acá NO va lógica de ninguna entidad.

export function CheckBajas({ valor, alCambiar }) {
  return (
    <label className="check-bajas">
      <input type="checkbox" checked={valor} onChange={(e) => alCambiar(e.target.checked)} />
      Mostrar dados de baja
    </label>
  );
}

export function EtiquetaBaja() {
  return <span className="etiqueta etiqueta-baja">De baja</span>;
}
