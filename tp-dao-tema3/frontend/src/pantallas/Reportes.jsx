// Pantalla de Reportes: arriba, los tableros (/tableros/...) para ver la
// situación de un vistazo; cada gráfico tiene un "Ver detalle" que abre uno de
// los 7 reportes (/reportes/...) con su resumen y su tabla, en la misma
// pantalla y con los mismos filtros, y "Volver" regresa al tablero.
// Cada perfil ve lo suyo según sus capacidades: se abre el primer tablero que
// puede ver (administrador → Ejecutivo, local → Ventas, CD → Abastecimiento) y
// solo aparecen los "Ver detalle" de los reportes que puede ver. Un local ve
// solo lo suyo (lo fija el back), así que no se le muestra el filtro de lugar.
// "Descargar PDF" baja lo que se está viendo: el tablero entero (con todos sus
// gráficos) o el reporte de detalle.
// Acá NO se calcula nada: las cuentas las hace el back.
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Aviso, useAviso } from "../componentes/Aviso.jsx";
import Cabecera from "../componentes/Cabecera.jsx";
import { useCatalogos } from "../componentes/Catalogos.js";
import { Cargando, Segmentado } from "../componentes/Controles.jsx";
import Icono from "../componentes/Icono.jsx";
import AtajosPeriodo, { fechasDe } from "../componentes/Periodo.jsx";
import { puede } from "../componentes/Permisos.js";
import Detalle, { FiltrosDelReporte, REPORTES, parametrosDelReporte } from "./reportes/Detalles.jsx";
import Tablero, { COMPARACIONES, TABLEROS } from "./reportes/Tableros.jsx";

const filtrosIniciales = () => ({
  ...fechasDe("Últimos 30 días"), comparar: "anterior", lugar: "",
  agrupar: "dia", limite: "10", solo_bajo_minimo: false,
});

// "2026-10-29" → "29/10/2026", sin pasar por Date (que lo leería en hora de
// Greenwich y en Argentina mostraría el día anterior)
const diaLargo = (texto) => texto.split("-").reverse().join("/");

export default function Reportes({ usuario }) {
  const catalogos = useCatalogos();
  const { aviso, ejecutar, limpiar } = useAviso();
  const disponibles = TABLEROS.filter((t) => !t.requiere || puede(usuario, t.requiere));
  const [clave, setClave] = useState(disponibles[0].valor);
  const [detalle, setDetalle] = useState(null);           // el reporte abierto con "Ver detalle", o ninguno
  const [filtros, setFiltros] = useState(filtrosIniciales);
  const [datos, setDatos] = useState(null);

  const tablero = disponibles.find((t) => t.valor === clave);
  const reporte = detalle && REPORTES[detalle];
  const veTodaLaRed = puede(usuario, "ve_toda_la_red");
  const cambiar = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  // El filtro de lugar es uno solo: en lo que es de locales se manda como
  // sucursal_id (si es un local), en lo de stock como ubicacion_id
  const tipoLugar = reporte ? reporte.lugar : tablero.lugar;
  const opcionesLugar = tipoLugar === "ubicacion" ? catalogos.ubicacionesActivas : catalogos.sucursales;
  const lugarValido = opcionesLugar.some((u) => String(u.id) === filtros.lugar) ? filtros.lugar : "";

  function parametros() {
    const p = detalle ? parametrosDelReporte(detalle, filtros) : new URLSearchParams();
    if (!reporte || reporte.fechas) {
      if (filtros.desde) p.set("desde", filtros.desde);
      if (filtros.hasta) p.set("hasta", filtros.hasta);
    }
    if (!detalle && tablero.comparar) p.set("comparar", filtros.comparar);
    if (veTodaLaRed && lugarValido) p.set(tipoLugar === "ubicacion" ? "ubicacion_id" : "sucursal_id", lugarValido);
    return p;
  }
  const ruta = () => (detalle ? `/reportes/${detalle}` : `/tableros/${clave}`);
  const vista = `${clave}/${detalle ?? ""}`;

  useEffect(() => {
    setDatos(null);
    ejecutar(async () => setDatos({ vista, actualizado: new Date(), ...(await api.obtener(`${ruta()}?${parametros()}`)) }))
      .then((ok) => { if (!ok) setDatos({ vista, error: true }); });
  }, [clave, detalle, filtros]);

  function descargarPdf() {
    const p = parametros();
    p.set("formato", "pdf");
    ejecutar(() => api.descargar(`${ruta()}?${p}`), detalle ? "Reporte descargado en PDF" : "Tablero descargado en PDF");
  }

  function elegirTablero(nuevo) {
    setDetalle(null);
    setClave(nuevo);
  }

  const detalleDelTablero = {
    puede: (r) => !REPORTES[r].requiere || puede(usuario, REPORTES[r].requiere),
    ver: (r) => { setDetalle(r); window.scrollTo({ top: 0 }); },
  };

  // Del ranking de locales del Ejecutivo al tablero de ventas de ese local
  function verLocal(sucursalId) {
    if (!disponibles.some((t) => t.valor === "ventas")) return;
    setFiltros({ ...filtros, lugar: String(sucursalId) });
    elegirTablero("ventas");
  }

  const listo = datos?.vista === vista && !datos.error;
  return (
    <section>
      <Cabecera icono="grafico" titulo={reporte ? reporte.titulo : "Reportes"} subtitulo={reporte ? reporte.pregunta : tablero.pregunta}>
        <button className="secundario" onClick={descargarPdf} disabled={!listo}>
          <Icono nombre="descargar" tamano={16} /> Descargar PDF
        </button>
      </Cabecera>
      <Aviso aviso={aviso} alCerrar={limpiar} />

      {reporte ? (
        <nav className="migas" aria-label="Dónde estás">
          <button className="fantasma" onClick={() => setDetalle(null)}>
            <Icono nombre="volver" tamano={16} /> Volver al tablero
          </button>
          <span>Reportes › {tablero.titulo} › <strong>{reporte.titulo}</strong></span>
        </nav>
      ) : (
        <div className="barra">
          <Segmentado etiqueta="Tablero" valor={clave} alCambiar={elegirTablero} opciones={disponibles} />
        </div>
      )}

      {(!reporte || reporte.fechas) && (
        <AtajosPeriodo enTablero filtros={filtros} alCambiar={(fechas) => setFiltros({ ...filtros, ...fechas })} />
      )}
      <div className="barra filtros">
        {(!reporte || reporte.fechas) && (<>
          <label>Desde<input type="date" value={filtros.desde} onChange={cambiar("desde")} /></label>
          <label>Hasta<input type="date" value={filtros.hasta} onChange={cambiar("hasta")} /></label>
        </>)}
        {!reporte && tablero.comparar && (
          <label>Comparar con
            <select value={filtros.comparar} onChange={cambiar("comparar")}>
              {Object.entries(COMPARACIONES).map(([valor, texto]) => <option key={valor} value={valor}>{texto}</option>)}
            </select>
          </label>
        )}
        {veTodaLaRed && (
          <label>{tipoLugar === "ubicacion" ? "Ubicación" : "Local"}
            <select value={lugarValido} onChange={cambiar("lugar")}>
              <option value="">{tipoLugar === "ubicacion" ? "Todas" : "Todos los locales"}</option>
              {opcionesLugar.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </label>
        )}
        {reporte && <FiltrosDelReporte clave={detalle} filtros={filtros} cambiar={cambiar} />}
        <button className="fantasma" onClick={() => setFiltros(filtrosIniciales())}>Volver a los últimos 30 días</button>
      </div>

      {listo && datos.periodo && (
        <p className="nota periodo-tablero">
          Del {diaLargo(String(datos.periodo.desde))} al {diaLargo(String(datos.periodo.hasta))} ({datos.periodo.dias} días)
          {datos.periodo.comparar && <> · comparado con el {diaLargo(String(datos.periodo.comparado_desde))} al {diaLargo(String(datos.periodo.comparado_hasta))}</>}
          {" "}· actualizado a las {datos.actualizado.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}
        </p>
      )}
      {reporte && !reporte.fechas && <p className="nota periodo-tablero">Es el stock de hoy: no depende de las fechas.</p>}
      {!reporte && (
        <div className="atajos detalles-del-tablero">
          <span>Reportes de detalle:</span>
          {tablero.reportes.filter(detalleDelTablero.puede).map((r) => (
            <button key={r} className="chip" onClick={() => detalleDelTablero.ver(r)}>{REPORTES[r].titulo}</button>
          ))}
        </div>
      )}

      {datos?.vista !== vista ? <Cargando /> : listo && (
        reporte
          ? <Detalle clave={detalle} datos={datos} filtros={filtros} />
          : <Tablero clave={clave} datos={datos} detalle={detalleDelTablero} alElegirLocal={verLocal} />
      )}
    </section>
  );
}
