// Confirmación de acciones que no se pueden deshacer (despachar, verificar,
// dar de baja): un panel con el resumen de lo que va a pasar y los botones
// Confirmar / Cancelar. Se muestra fijo en el centro, así se ve siempre.
// Acá NO va lógica de ninguna entidad: cada pantalla arma el resumen.
import { useState } from "react";

export function useConfirmacion() {
  const [pedido, setPedido] = useState(null); // { titulo, detalle, textoConfirmar, peligro, accion }

  return {
    pedido,
    // Muestra el panel; la acción se ejecuta recién si el usuario confirma
    pedir: (datos, accion) => setPedido({ ...datos, accion }),
    confirmar: () => {
      const { accion } = pedido;
      setPedido(null);
      accion();
    },
    cancelar: () => setPedido(null),
  };
}

export function Confirmacion({ confirmacion }) {
  const { pedido, confirmar, cancelar } = confirmacion;
  if (!pedido) return null;
  return (
    <div className="fondo-confirmacion" onClick={cancelar}>
      <div className="confirmacion" role="alertdialog" aria-modal="true" aria-labelledby="titulo-confirmacion"
        onClick={(e) => e.stopPropagation()}>
        <h3 id="titulo-confirmacion">{pedido.titulo}</h3>
        <div className="detalle-confirmacion">{pedido.detalle}</div>
        <div className="acciones">
          <button className={pedido.peligro ? "peligro-lleno" : ""} onClick={confirmar} autoFocus>
            {pedido.textoConfirmar ?? "Confirmar"}
          </button>
          <button className="secundario" onClick={cancelar}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}
