// Los cuatro tableros de la pantalla Reportes (/tableros/...): indicadores
// comparados y gráficos para ver la situación de un vistazo. Cada gráfico
// tiene un "Ver detalle" que abre el reporte que lo explica con su tabla
// (Detalles.jsx); así ningún reporte queda suelto y nada se muestra dos veces.
// Las cuentas las hace el back; acá solo se muestran.
// Acá NO se piden los datos (eso es la pantalla Reportes).
import { useState } from "react";

import { Segmentado, Vacio } from "../../componentes/Controles.jsx";
import { GraficoBarras, GraficoBarrasDobles, GraficoDispersion, GraficoLineas, SERIES } from "../../componentes/Graficos.jsx";
import Icono from "../../componentes/Icono.jsx";
import Indicadores, { duracion } from "../../componentes/Indicadores.jsx";
import MapaCalor from "../../componentes/MapaCalor.jsx";
import { fecha, pesos } from "../../formato.js";

// requiere: la capacidad que hace falta. comparar: se elige contra qué se
// compara. lugar: qué filtro de lugar tiene (solo para quien ve toda la red).
// reportes: los de detalle que cuelgan de este tablero (así cada uno de los 7
// se puede abrir aunque su gráfico no se dibuje, ej. con una sola barra).
// El orden decide cuál se abre primero: el administrador cae en Ejecutivo, el
// local en Ventas y el CD en Abastecimiento.
export const TABLEROS = [
  { valor: "ejecutivo", titulo: "Ejecutivo", texto: <><Icono nombre="trofeo" tamano={16} /> Ejecutivo</>, requiere: "ve_resultados_empresa",
    pregunta: "¿Cómo le va a la empresa: cuánto vende, cuánto gana y qué local rinde más?", comparar: true, lugar: "sucursal",
    reportes: ["ventas", "productos-mas-vendidos"] },
  { valor: "ventas", titulo: "Ventas del local", texto: <><Icono nombre="carrito" tamano={16} /> Ventas del local</>, requiere: "ve_ventas",
    pregunta: "¿Cuándo se vende más, cuánto deja cada ticket y qué se devuelve?", comparar: true, lugar: "sucursal",
    reportes: ["ventas", "productos-mas-vendidos", "devoluciones"] },
  { valor: "abastecimiento", titulo: "Abastecimiento", texto: <><Icono nombre="camion" tamano={16} /> Abastecimiento</>,
    pregunta: "¿En qué estado están los pedidos, cuánto tardan y cuánto se pierde?", lugar: "sucursal",
    reportes: ["productos-mas-pedidos", "tiempos-transito", "mermas"] },
  { valor: "productos", titulo: "Productos e inventario", texto: <><Icono nombre="producto" tamano={16} /> Productos e inventario</>,
    pregunta: "¿Qué productos rinden y qué stock falta o está parado?", lugar: "ubicacion",
    reportes: ["productos-mas-vendidos", "existencias"] },
];

export const COMPARACIONES = { anterior: "Período anterior", anio: "Mismo período del año pasado" };

// El botón de cada gráfico que abre su reporte (si el perfil lo puede ver)
function VerDetalle({ reporte, detalle }) {
  if (!detalle.puede(reporte)) return null;
  return (
    <button className="ver-detalle" onClick={() => detalle.ver(reporte)}>
      Ver detalle <Icono nombre="flecha" tamano={14} />
    </button>
  );
}

export default function Tablero({ clave, datos, detalle, alElegirLocal }) {
  if (clave === "ejecutivo") return <TableroEjecutivo datos={datos} detalle={detalle} alElegirLocal={alElegirLocal} />;
  if (clave === "ventas") return <TableroVentas datos={datos} detalle={detalle} />;
  if (clave === "abastecimiento") return <TableroAbastecimiento datos={datos} detalle={detalle} />;
  return <TableroProductos datos={datos} detalle={detalle} />;
}

function Tabla({ children }) {
  return <div className="tarjeta-tabla"><table>{children}</table></div>;
}

const SIN_VENTAS = <Vacio icono="buscar" titulo="No hubo ventas en este período" texto="Probá con otras fechas o con todos los locales." />;
const porcentaje = (valor) => (valor === null || valor === undefined ? "—" : `${valor.toLocaleString("es-AR")} %`);
const unidades = (n) => `${Number(n).toLocaleString("es-AR")} u.`;

// ---------------------------------------------------------------- Ejecutivo
function TableroEjecutivo({ datos, detalle, alElegirLocal }) {
  const comparado = COMPARACIONES[datos.periodo.comparar];
  const ventas = datos.indicadores[0].valor;
  return (<>
    <Indicadores indicadores={datos.indicadores} contra={comparado} />
    {!Number(ventas) ? SIN_VENTAS : (<>
      <GraficoLineas titulo={`Ventas netas por ${datos.evolucion.agrupado === "dia" ? "día" : "semana"} ($)`} formato={pesos}
        accion={<VerDetalle reporte="ventas" detalle={detalle} />}
        datos={datos.evolucion.puntos.map((p) => ({ etiqueta: p.etiqueta, titulo: p.etiqueta, actual: Number(p.actual), anterior: Number(p.anterior) }))}
        series={[{ clave: "actual", nombre: "Este período", color: SERIES.principal },
          { clave: "anterior", nombre: comparado, color: SERIES.anterior, punteada: true }]} />
      <div className="grilla-2">
        <GraficoBarrasDobles titulo="Ranking de locales ($)" ayuda="tocá un local para ver sus ventas" formato={pesos}
          accion={<VerDetalle reporte="ventas" detalle={detalle} />}
          datos={datos.locales.map((l) => ({ nombre: l.sucursal, sucursal_id: l.sucursal_id, ventas: Number(l.ventas), ganancia: Number(l.ganancia) }))}
          series={[{ clave: "ventas", nombre: "Ventas netas", color: SERIES.principal }, { clave: "ganancia", nombre: "Ganancia bruta", color: SERIES.segunda }]}
          alClic={(fila) => alElegirLocal(fila.sucursal_id)} />
        <GraficoBarrasDobles titulo="Ventas y ganancia por categoría ($)" formato={pesos}
          accion={<VerDetalle reporte="productos-mas-vendidos" detalle={detalle} />}
          datos={datos.categorias.map((c) => ({ nombre: c.categoria, ventas: Number(c.ventas), ganancia: Number(c.ganancia) }))}
          series={[{ clave: "ventas", nombre: "Ventas netas", color: SERIES.principal }, { clave: "ganancia", nombre: "Ganancia bruta", color: SERIES.segunda }]} />
      </div>
      <Tabla>
        <thead><tr><th>Categoría</th><th className="num">Ventas netas</th><th className="num">Participación</th>
          <th className="num">Ganancia bruta</th><th className="num">Margen</th></tr></thead>
        <tbody>
          {datos.categorias.map((c) => (
            <tr key={c.categoria}><td>{c.categoria}</td><td className="num">{pesos(c.ventas)}</td>
              <td className="num">{porcentaje(c.participacion)}</td><td className="num">{pesos(c.ganancia)}</td>
              <td className={`num ${c.margen < 0 ? "negativo" : ""}`}>{porcentaje(c.margen)}</td></tr>
          ))}
        </tbody>
      </Tabla>
    </>)}
  </>);
}

// ---------------------------------------------------------- Ventas del local
function TableroVentas({ datos, detalle }) {
  const [medida, setMedida] = useState("ventas");
  const ventas = datos.indicadores[0].valor;
  const comparado = COMPARACIONES[datos.periodo.comparar];
  const devoluciones = datos.devoluciones;
  return (<>
    <Indicadores indicadores={datos.indicadores} contra={comparado} />
    {!Number(ventas) ? SIN_VENTAS : (<>
      <div className="encabezado-grafico">
        <Segmentado etiqueta="Medida" valor={medida} alCambiar={setMedida}
          opciones={[{ valor: "ventas", texto: "En pesos" }, { valor: "unidades", texto: "En unidades" }]} />
      </div>
      <GraficoLineas titulo={medida === "ventas" ? "Ventas netas por día ($)" : "Unidades vendidas por día"}
        formato={medida === "ventas" ? pesos : unidades} accion={<VerDetalle reporte="ventas" detalle={detalle} />}
        datos={datos.por_dia.map((d) => ({ etiqueta: d.etiqueta, valor: Number(d[medida]) }))}
        series={[{ clave: "valor", nombre: medida === "ventas" ? "Ventas netas" : "Unidades", color: SERIES.principal }]} />
      <div className="grilla-2">
        <MapaCalor titulo="¿Cuándo se vende? Ventas por día y horario" mapa={datos.mapa_calor} />
        <GraficoLineas titulo="Ticket promedio por día ($)" formato={pesos} alto={300}
          datos={datos.por_dia.map((d) => ({ etiqueta: d.etiqueta, valor: d.ticket_promedio === null ? null : Number(d.ticket_promedio) }))}
          series={[{ clave: "valor", nombre: "Ticket promedio", color: SERIES.segunda }]} />
      </div>
      <div className="grilla-2">
        <GraficoBarras titulo="Ventas netas por categoría ($)" formato={pesos} horizontal
          accion={<VerDetalle reporte="productos-mas-vendidos" detalle={detalle} />}
          datos={datos.categorias.map((c) => ({ nombre: c.categoria, valor: Number(c.ventas),
            detalle: `${unidades(c.unidades)} · ${porcentaje(c.participacion)} de lo vendido` }))} />
        <figure className="tarjeta-grafico">
          <figcaption><span>Lo que más se devuelve</span><VerDetalle reporte="devoluciones" detalle={detalle} /></figcaption>
          {devoluciones.cantidad === 0
            ? <p className="nota">No hubo devoluciones en este período.</p>
            : (<>
              <p className="nota">{devoluciones.cantidad} {devoluciones.cantidad === 1 ? "devolución" : "devoluciones"} · {unidades(devoluciones.unidades)} · se reintegraron {pesos(devoluciones.reintegrado)}</p>
              <ul className="lista-ranking">
                {devoluciones.productos.map((p) => (
                  <li key={p.producto_id}><span>{p.nombre}<small>{p.motivo_principal}</small></span>
                    <strong>{unidades(p.unidades)}</strong></li>
                ))}
              </ul>
            </>)}
        </figure>
      </div>
    </>)}
  </>);
}

// --------------------------------------------------- Productos e inventario
// Un color por cuadrante: verde lo bueno, naranja lo que hay que revisar
const CUADRANTES = {
  "Estrellas": { color: "#5c9e47", texto: "venden mucho y dejan buen margen" },
  "Mucho volumen, poco margen": { color: "#e0a83a", texto: "se venden, pero dejan poco: revisar el precio" },
  "Buen margen, poca venta": { color: "#0082a0", texto: "dejan bien pero salen poco: darles visibilidad" },
  "A revisar": { color: "#b4521d", texto: "venden poco y dejan poco" },
};

function TableroProductos({ datos, detalle }) {
  const { matriz, ranking, stock } = datos;
  return (<>
    <Indicadores indicadores={datos.indicadores} />
    {ranking && (ranking.length === 0 ? SIN_VENTAS : (<>
      <div className="grilla-2">
        <GraficoBarras titulo="Los más vendidos (unidades)" formato={unidades} horizontal
          accion={<VerDetalle reporte="productos-mas-vendidos" detalle={detalle} />}
          datos={ranking.map((f) => ({ nombre: f.nombre, valor: f.unidades, detalle: `Ganancia ${pesos(f.margen)}` }))} />
        <GraficoDispersion titulo="Matriz volumen × margen (tamaño: ganancia)"
          accion={<VerDetalle reporte="productos-mas-vendidos" detalle={detalle} />}
          puntos={matriz.puntos.map((p) => ({ ...p, x: p.unidades, y: p.margen ?? 0, tamano: Number(p.ganancia) }))}
          corteX={matriz.corte_unidades} corteY={matriz.corte_margen} formatoY={(v) => `${v} %`}
          colorDe={(p) => (p.margen < 0 ? "#b23a3a" : CUADRANTES[p.cuadrante].color)}
          detalle={(p) => [`${p.codigo} · ${p.cuadrante}`, `${unidades(p.unidades)} · margen ${porcentaje(p.margen)}`, `Ganancia ${pesos(p.ganancia)}`]} />
      </div>
      <div className="leyenda-cuadrantes">
        {Object.entries(CUADRANTES).map(([nombre, { color, texto }]) => (
          <div key={nombre}>
            <i style={{ background: color }} />
            <strong>{nombre} ({matriz.puntos.filter((p) => p.cuadrante === nombre).length})</strong>
            <span>{texto}</span>
          </div>
        ))}
        <p className="nota">Cortes de la matriz: la mitad de los productos vende más de {Number(matriz.corte_unidades).toLocaleString("es-AR")} unidades; el margen de todo lo vendido es {porcentaje(matriz.corte_margen)}. En rojo, los que se venden a pérdida.</p>
      </div>
    </>))}

    <h2 className="titulo-seccion espacio-arriba">Stock</h2>
    <div className="grilla-2">
      <GraficoBarras titulo="Valor del stock según su última salida ($)" formato={pesos}
        accion={<VerDetalle reporte="existencias" detalle={detalle} />}
        datos={stock.tramos.map((t) => ({ nombre: t.tramo, valor: Number(t.valor), detalle: `${t.productos} productos · ${unidades(t.unidades)}` }))} />
      {stock.para_reponer.length > 1
        ? <GraficoBarras titulo="Lo que más falta reponer (unidades)" formato={unidades} horizontal
            accion={<VerDetalle reporte="existencias" detalle={detalle} />}
            datos={stock.para_reponer.map((f) => ({ nombre: `${f.nombre} · ${f.ubicacion}`, valor: f.faltante,
              detalle: `Hay ${f.cantidad}, el mínimo es ${f.stock_minimo}` }))} />
        : <Vacio icono="listo" titulo={stock.para_reponer.length ? `Falta reponer ${stock.para_reponer[0].nombre}` : "Nada para reponer"}
            texto="Todo lo demás está por encima de su stock mínimo." />}
    </div>
    <p className="nota">La última salida es la última venta en un local o el último despacho en el CD. El detalle (cada producto en cada lugar, con lo que falta y los días sin salir) está en "Ver detalle".</p>
  </>);
}

// ------------------------------------------------------------ Abastecimiento
const COLOR_ESTADO = {
  "Pendiente": "#b4521d", "En preparación": "#e0a83a", "En camino": "#0082a0",
  "Recibido": "#5c9e47", "Recibido con rechazos": "#93393a",
};
const CLASE_ESTADO = {
  "Pendiente": "estado-naranja", "En preparación": "estado-amarillo", "En camino": "estado-azul",
  "Recibido": "estado-verde", "Recibido con rechazos": "estado-rojo",
};

function TableroAbastecimiento({ datos, detalle }) {
  // Solo los estados que aparecen, así la leyenda no muestra colores de más
  const estados = datos.estados.filter((e) => datos.por_estado.some((f) => f[e] > 0));
  const tiempos = datos.tiempos.length === 0
    ? <Vacio icono="reloj" titulo="Todavía no llegó ningún pedido" texto="Cuando un local verifique lo que recibió, acá se ve cuánto tardó." />
    : datos.tiempos.every((t) => t.horas_promedio < 1 / 60)
    // Todos en menos de un minuto (ej. los datos de prueba, que se cargan de una): no hay barras que comparar
    ? <Vacio icono="reloj" titulo="Todos los pedidos llegaron en menos de un minuto"
        texto="No hay diferencias entre locales para graficar. Pasa con los datos de prueba, que arman y reciben los envíos en el momento." />
    : <GraficoBarras titulo="Tiempo de reposición: del pedido a la mercadería verificada" formato={duracion} formatoEje={duracion} horizontal
        accion={<VerDetalle reporte="tiempos-transito" detalle={detalle} />}
        datos={datos.tiempos.map((t) => ({ nombre: t.sucursal, valor: t.horas_promedio,
          detalle: `${t.pedidos} pedidos · entre ${duracion(t.horas_minimo)} y ${duracion(t.horas_maximo)}` }))} />;
  return (<>
    <Indicadores indicadores={datos.indicadores} />
    {datos.pedidos.length === 0
      ? <Vacio icono="pedido" titulo="No hubo pedidos en este período" texto="Probá con otras fechas." />
      : (<div className="grilla-2">
        <GraficoBarrasDobles titulo="Pedidos por estado y local" apiladas formato={(n) => `${n} pedidos`}
          datos={datos.por_estado.map((f) => ({ nombre: f.sucursal, ...Object.fromEntries(estados.map((e) => [e, f[e]])) }))}
          series={estados.map((e) => ({ clave: e, nombre: e, color: COLOR_ESTADO[e] }))} />
        {tiempos}
      </div>)}
    <div className="grilla-2">
      {datos.mermas.length > 0 && (
        <GraficoBarras titulo="Perdido en bultos rechazados ($)" formato={pesos} horizontal
          accion={<VerDetalle reporte="mermas" detalle={detalle} />}
          datos={datos.mermas.map((m) => ({ nombre: m.sucursal, valor: Number(m.valor_perdido),
            detalle: `${m.bultos_rechazados} de ${m.bultos_verificados + m.bultos_rechazados} bultos rechazados` }))} />
      )}
      {datos.demanda?.length > 0 && (
        <GraficoBarras titulo="Lo que más piden los locales (unidades)" formato={unidades} horizontal
          accion={<VerDetalle reporte="productos-mas-pedidos" detalle={detalle} />}
          datos={datos.demanda.map((f) => ({ nombre: f.nombre, valor: f.unidades,
            detalle: `${f.pedidos} pedidos · en el CD hay ${f.stock_cd}${f.falta_en_cd ? ` · faltan ${f.falta_en_cd}` : ""}` }))} />
      )}
    </div>
    {datos.pedidos.length > 0 && (<>
      <h2 className="titulo-seccion espacio-arriba">Pedidos del período</h2>
      <Tabla>
        <thead><tr><th>Pedido</th><th>Fecha</th><th>Local</th><th className="num">Unidades</th><th>Estado</th>
          <th>Llegada estimada</th><th>Verificado</th><th className="num">Tardó</th></tr></thead>
        <tbody>
          {datos.pedidos.map((p) => (
            <tr key={p.pedido_id}><td>#{p.pedido_id}</td><td>{fecha(p.fecha)}</td><td>{p.sucursal}</td>
              <td className="num">{p.unidades}</td>
              <td><span className={`estado ${CLASE_ESTADO[p.estado]}`}>{p.estado}</span></td>
              <td>{p.llegada_estimada ? fecha(p.llegada_estimada) : "—"}</td>
              <td>{p.verificado && p.horas !== null ? fecha(p.verificado) : "—"}</td>
              <td className="num">{duracion(p.horas)}</td></tr>
          ))}
        </tbody>
      </Tabla>
      <p className="nota espacio-arriba">El tiempo de reposición va desde que el local hace el pedido hasta que termina de verificar los bultos: recién ahí la mercadería se puede vender.</p>
    </>)}
  </>);
}
