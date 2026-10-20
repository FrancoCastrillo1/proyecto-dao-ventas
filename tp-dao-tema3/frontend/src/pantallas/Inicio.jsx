// Pantalla de Inicio: explica qué hace el sistema a alguien que nunca lo usó y
// muestra los primeros pasos en orden. Cada paso se tilda solo consultando la
// api (¿hay productos?, ¿hay stock en el CD?, ...) y tiene un botón que lleva
// a la pantalla donde se hace.
import { useEffect, useState } from "react";

import { api } from "../api.js";

const AREAS = [
  { clave: "stock", icono: "📦", titulo: "Stock", tema: "tema-menta",
    texto: "Cuánto hay de cada producto en el CD y en cada local. Acá se cargan las compras al CD." },
  { clave: "logistica", icono: "🚚", titulo: "Logística", tema: "tema-cielo",
    texto: "Llevar mercadería del CD a los locales en bultos precintados, y controlarlos cuando llegan." },
  { clave: "ventas", icono: "🛒", titulo: "Ventas", tema: "tema-durazno",
    texto: "Vender en un local, cobrar con distintos medios de pago y registrar devoluciones." },
  { clave: "reportes", icono: "📊", titulo: "Reportes", tema: "tema-rosa",
    texto: "Ventas por período, productos más vendidos, faltantes, mermas y tiempos de entrega." },
];

export default function Inicio({ irA }) {
  const [estado, setEstado] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const productos = await api.listar("/productos");
        const ubicaciones = await api.listar("/ubicaciones");
        const cd = ubicaciones.find((u) => u.puede_despachar);
        const stockCd = cd ? await api.listar(`/stock/${cd.id}`) : [];
        const remitos = await api.listar("/remitos");
        const ventas = await api.listar("/ventas");
        setEstado({
          maestros: productos.length > 0,
          ubicaciones: Boolean(cd) && ubicaciones.some((u) => u.puede_vender),
          compras: stockCd.some((s) => s.cantidad > 0),
          reposicion: remitos.some((r) => r.estado.startsWith("VERIFICADO")),
          ventas: ventas.length > 0,
        });
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const pasos = [
    { hecho: estado?.maestros, ir: "productos", titulo: "Cargá categorías y productos",
      texto: "Primero las categorías (ej: Bebidas) y después los productos, con su precio, costo y stock mínimo." },
    { hecho: estado?.ubicaciones, ir: "ubicaciones", titulo: "Creá el Centro de Distribución y las sucursales",
      texto: "Hay un solo CD (de donde sale la mercadería) y uno o más locales que venden." },
    { hecho: estado?.compras, ir: "stock", titulo: "Comprá mercadería para el CD",
      texto: "En Stock, elegí el CD y registrá una compra. Es la única forma de que entre mercadería al sistema." },
    { hecho: estado?.reposicion, ir: "logistica", titulo: "Llevá mercadería a un local",
      texto: "En Logística: el local pide, el CD arma bultos precintados, los despacha y el local los verifica al recibirlos." },
    { hecho: estado?.ventas, ir: "ventas", titulo: "Vendé en un local",
      texto: "Solo se puede vender lo que llegó en bultos verificados. Probá distintos medios de pago." },
    { hecho: false, ir: "reportes", titulo: "Mirá los reportes",
      texto: "Con ventas y entregas hechas, los reportes muestran ingresos, márgenes, faltantes y mermas." },
  ];

  return (
    <section className="tema-lavanda">
      <div className="encabezado-pantalla">
        <div className="titulo">
          <span className="icono" aria-hidden="true">🏠</span>
          <h2>Bienvenido</h2>
        </div>
        <p className="descripcion">
          Este sistema maneja un comercio con varios <strong>locales</strong> que reciben mercadería de un{" "}
          <strong>Centro de Distribución (CD)</strong>. La mercadería viaja en bultos cerrados con un precinto de
          seguridad: solo se puede vender cuando el local revisa el precinto y confirma que llegó bien.
        </p>
      </div>

      <div className="areas">
        {AREAS.map((a) => (
          <div key={a.clave} className={`area ${a.tema}`}>
            <h3><span aria-hidden="true">{a.icono}</span> {a.titulo}</h3>
            <p>{a.texto}</p>
            <button className="secundario" onClick={() => irA(a.clave)}>Ir a {a.titulo}</button>
          </div>
        ))}
      </div>

      <h3>Primeros pasos</h3>
      {error && (
        <div className="aviso aviso-error" role="alert">
          <strong>No hay conexión con el backend.</strong>
          <span>Levantalo con <code>.venv\Scripts\python -m uvicorn backend.main:app --reload</code> y recargá la página.</span>
        </div>
      )}
      <ol className="checklist">
        {pasos.map((p, i) => (
          <li key={p.titulo} className={p.hecho ? "hecho" : ""}>
            <span className="marca" aria-label={p.hecho ? "Hecho" : `Paso ${i + 1}`}>{p.hecho ? "✓" : i + 1}</span>
            <span className="texto"><strong>{p.titulo}</strong>{p.texto}</span>
            <button className={p.hecho ? "secundario" : ""} onClick={() => irA(p.ir)}>{p.hecho ? "Ver" : "Empezar"}</button>
          </li>
        ))}
      </ol>

      <div className="aviso aviso-advertencia consejo">
        <strong>¿Querés probar con datos de ejemplo?</strong>
        <span>Corré <code>.venv\Scripts\python -m backend.datos.seed --reiniciar</code> (borra la base local y carga
          productos, locales, entregas y ventas de prueba) y recargá la página.</span>
      </div>
    </section>
  );
}
