// Pantalla de Inicio: un resumen de lo que está pasando (ventas de hoy, pedidos
// sin consolidar, envíos en camino, productos bajo mínimo). Cada indicador lleva
// a la pantalla donde se resuelve. Si la base está vacía, dice cómo empezar.
// Cada usuario ve solo lo que lleva a pantallas que puede usar, y los números
// ya vienen filtrados por el back (un local ve solo lo suyo).
import { useEffect, useState } from "react";

import { api } from "../api.js";
import Cabecera from "../componentes/Cabecera.jsx";
import { Cargando, Vacio } from "../componentes/Controles.jsx";
import { puede } from "../componentes/Permisos.js";
import { pesos } from "../formato.js";

// Fecha de hoy en hora local (AAAA-MM-DD), para filtrar las ventas del día
function hoy() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function Inicio({ irA, puedeIr, usuario }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [productos, pedidos, remitos, ventasHoy, existencias] = await Promise.all([
          api.listar("/productos"),
          api.listar("/pedidos?estado=PENDIENTE"),
          api.listar("/remitos"),
          api.obtener(`/reportes/ventas?desde=${hoy()}&hasta=${hoy()}&agrupar=total`),
          api.obtener("/reportes/existencias?solo_bajo_minimo=true"),
        ]);
        setDatos({
          hayProductos: productos.length > 0,
          pedidosPendientes: pedidos.length,
          armando: remitos.filter((r) => r.estado === "ABIERTO").length,
          enCamino: remitos.filter((r) => r.estado === "EN_TRANSITO").length,
          ventasHoy: ventasHoy.cantidad_ventas,
          ingresoHoy: ventasHoy.total_neto,
          bajoMinimo: existencias.filas.length,
        });
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  return (
    <section>
      <Cabecera icono="🏠" titulo={`Hola, ${usuario.nombre_completo.split(" ")[0]}`}
        subtitulo={usuario.ubicacion_nombre ? `Lo que está pasando hoy en ${usuario.ubicacion_nombre}` : "Lo que está pasando hoy en el comercio"} />

      {error && (
        <Vacio icono="🔌" titulo="No hay conexión con el sistema"
          texto="El backend no está corriendo. Levantalo con: .venv\Scripts\python -m uvicorn backend.main:app --reload" />
      )}
      {!error && datos === null && <Cargando />}

      {datos && !datos.hayProductos && (
        <Vacio icono="🌱" titulo="Todavía no hay datos cargados"
          texto="Empezá por los productos y los locales. Para probar con datos de ejemplo, corré: .venv\Scripts\python -m backend.datos.seed --reiniciar"
          accion={puedeIr("productos") ? "Cargar productos" : undefined} alAccionar={() => irA("productos")} />
      )}

      {datos?.hayProductos && (<>
        <div className="indicadores">
          <Indicador tema="tema-durazno" icono="🛒" valor={datos.ventasHoy} texto={`ventas hoy · ${pesos(datos.ingresoHoy)}`}
            pie={puedeIr("ventas") ? "Ir a vender →" : "Ver reportes →"} alTocar={() => irA(puedeIr("ventas") ? "ventas" : "reportes")} />
          {puedeIr("logistica") && (<>
            <Indicador tema="tema-cielo" icono="📝" valor={datos.pedidosPendientes}
              texto={puede(usuario, "puede_preparar_envios") ? "pedidos de locales sin preparar" : "pedidos tuyos esperando al CD"}
              pie="Ver envíos →" atencion={datos.pedidosPendientes > 0 && puede(usuario, "puede_preparar_envios")}
              alTocar={() => irA("logistica")} />
            <Indicador tema="tema-cielo" icono="🚚" valor={datos.enCamino} texto={`envíos en camino · ${datos.armando} armándose`}
              pie="Ver envíos →" atencion={datos.enCamino > 0 && puede(usuario, "puede_recibir")} alTocar={() => irA("logistica")} />
          </>)}
          <Indicador tema="tema-menta" icono="⚠️" valor={datos.bajoMinimo}
            texto={puede(usuario, "ve_toda_la_red") ? "faltantes para reponer, sumando todos los lugares" : "productos para reponer"}
            pie="Ver stock →" atencion={datos.bajoMinimo > 0} alTocar={() => irA("stock")} />
        </div>

        <h2 className="titulo-seccion">Accesos rápidos</h2>
        <div className="accesos">
          {puedeIr("ventas") && <Acceso tema="tema-durazno" icono="🛒" titulo="Nueva venta" texto="Cobrar en el local" alTocar={() => irA("ventas")} />}
          {puede(usuario, "puede_pedir_reposicion") && <Acceso tema="tema-cielo" icono="📝" titulo="Pedir mercadería" texto="Y recibir lo que llega" alTocar={() => irA("logistica")} />}
          {puede(usuario, "puede_preparar_envios") && <Acceso tema="tema-cielo" icono="🚚" titulo="Reponer los locales" texto="Pedidos, bultos y despacho" alTocar={() => irA("logistica")} />}
          {puede(usuario, "puede_comprar") && <Acceso tema="tema-menta" icono="📦" titulo="Registrar una compra" texto="Mercadería que entra al CD" alTocar={() => irA("stock")} />}
          {puedeIr("usuarios") && <Acceso tema="tema-manteca" icono="👤" titulo="Usuarios" texto="Quién entra y qué puede hacer" alTocar={() => irA("usuarios")} />}
          {puedeIr("productos") && <Acceso tema="tema-manteca" icono="🧃" titulo="Productos y precios" texto="Catálogo, costos y mínimos" alTocar={() => irA("productos")} />}
          <Acceso tema="tema-rosa" icono="📊" titulo="Ver reportes" texto="Ventas, márgenes y mermas" alTocar={() => irA("reportes")} />
        </div>
      </>)}
    </section>
  );
}

function Indicador({ tema, icono, valor, texto, pie, atencion, alTocar }) {
  return (
    <button className={`indicador ${tema} ${atencion ? "atencion" : ""}`} onClick={alTocar}>
      <span className="indicador-icono" aria-hidden="true">{icono}</span>
      <strong>{valor}</strong>
      <span>{texto}</span>
      <span className="indicador-pie">{pie}</span>
    </button>
  );
}

function Acceso({ tema, icono, titulo, texto, alTocar }) {
  return (
    <button className={`acceso ${tema}`} onClick={alTocar}>
      <span className="indicador-icono" aria-hidden="true">{icono}</span>
      <span>{titulo}<small>{texto}</small></span>
    </button>
  );
}
