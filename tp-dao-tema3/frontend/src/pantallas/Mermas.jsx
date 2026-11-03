// Pantalla de bultos en merma (solo el CD): los bultos que un local rechazó
// porque el precinto llegó roto vuelven directo al CD. Acá el CD revisa la
// mercadería, cuenta en qué estado llegó y decide por el bulto entero si vuelve
// a su stock o se tira. Qué se puede hacer lo decide el backend (patrón State).
// Acá NO va lógica de negocio.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { Confirmacion, useConfirmacion } from "../componentes/Confirmacion.jsx";
import { Cargando, Vacio } from "../componentes/Controles.jsx";
import Icono from "../componentes/Icono.jsx";
import { fecha } from "../formato.js";

export default function Mermas() {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const confirmacion = useConfirmacion();
  const [mermas, setMermas] = useState(null);

  const cargar = () => ejecutar(async () => setMermas(await api.listar("/mermas")));
  useEffect(() => { cargar(); }, []);

  async function accion(hacer, textoExito) {
    const ok = await ejecutar(hacer, textoExito);
    if (ok) await cargar();
    return ok;
  }

  return (
    <section>
      <Cabecera icono="merma" titulo="Mermas"
        subtitulo="Bultos que volvieron de los locales con el precinto roto: revisalos y decidí si vuelven al stock o se tiran" />
      <Aviso aviso={aviso} alCerrar={limpiar} />
      <Confirmacion confirmacion={confirmacion} />

      {mermas === null ? <Cargando /> : mermas.length === 0 ? (
        <Vacio icono="listo" titulo="No hay bultos en merma"
          texto="Cuando un local rechace un bulto por el precinto, va a aparecer acá para que lo revises." />
      ) : (
        <div className="lista-merma">
          {mermas.map((m) => <FichaMerma key={m.bulto.id} merma={m} catalogos={catalogos} accion={accion} confirmacion={confirmacion} />)}
        </div>
      )}
    </section>
  );
}

function FichaMerma({ merma, catalogos, accion, confirmacion }) {
  const [observacion, setObservacion] = useState("");
  const { bulto } = merma;
  const contenido = bulto.items.map((i) => `${i.cantidad} × ${catalogos.nombreProducto(i.producto_id)}`).join(", ");

  function decidir(reintegrar) {
    confirmacion.pedir({
      titulo: reintegrar ? `¿Volver el bulto #${bulto.id} al stock?` : `¿Descartar el bulto #${bulto.id}?`,
      textoConfirmar: reintegrar ? "Volver al stock" : "Descartar todo",
      peligro: !reintegrar,
      detalle: (<>
        <p>{reintegrar ? "Vuelve al stock del CD" : "Se tira toda la mercadería"}: {contenido}.</p>
        <p>Estado: <em>{observacion.trim()}</em></p>
        <p><strong>No se puede deshacer.</strong></p>
      </>),
    }, () => accion(() => api.crear(`/mermas/${bulto.id}/${reintegrar ? "reintegrar" : "descartar"}`, { observacion }),
      reintegrar ? `Bulto #${bulto.id}: la mercadería volvió al stock del CD` : `Bulto #${bulto.id} descartado`));
  }

  return (
    <div className="ficha ficha-merma">
      <div className="ficha-titulo">
        Volvió de {catalogos.nombreUbicacion(merma.local_id)}
        <span className="numero-ficha">Bulto #{bulto.id} · Remito #{merma.remito_id}</span>
      </div>
      <span className="ficha-detalle">
        {merma.rechazado_el && <>Rechazado el {fecha(merma.rechazado_el)} · </>}
        Precinto <code>{bulto.nro_precinto}</code>
      </span>
      <span className="bulto-contenido">{contenido}</span>
      <label>¿En qué estado llegó la mercadería?
        <textarea rows={2} value={observacion} onChange={(e) => setObservacion(e.target.value)}
          placeholder="Ej: cajas sanas, solo el precinto cortado" />
      </label>
      <div className="acciones-fila">
        <button className="peligro-lleno" onClick={() => decidir(false)} disabled={!observacion.trim()}>
          <Icono nombre="tirar" tamano={15} /> Descartar todo
        </button>
        <button onClick={() => decidir(true)} disabled={!observacion.trim()}>
          <Icono nombre="devolucion" tamano={15} /> Volver al stock
        </button>
      </div>
    </div>
  );
}
