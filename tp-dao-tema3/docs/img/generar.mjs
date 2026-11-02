// Genera un PNG por cada diagrama Mermaid de docs/diagramas.md, para usarlos
// en la presentación. Abre Chrome sin ventana, dibuja cada diagrama con la
// librería de Mermaid y le saca una captura. Si un diagrama tiene un error de
// sintaxis, lo dice y termina con error.
// Un diagrama puede pedir el motor ELK (`"layout": "elk"` en su init), que traza
// las líneas en ángulo recto esquivando las cajas, y con la línea `%% pdf A3`
// también se guarda en PDF (vectorial, en una hoja A3) para entregarlo.
//
// Uso (desde tp-dao-tema3, con Chrome instalado y conexión a internet):
//   node docs/img/generar.mjs
// Otra ruta de Chrome: CHROME="C:/ruta/chrome.exe" node docs/img/generar.mjs
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const CARPETA = dirname(fileURLToPath(import.meta.url));
const CHROME = process.env.CHROME ?? "C:/Program Files/Google/Chrome/Application/chrome.exe";
const MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";
const ELK = "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.1.7/dist/mermaid-layout-elk.esm.min.mjs";
const A3 = { ancho: 11.69, alto: 16.54, margen: 0.4 }; // pulgadas
const PUERTO = 9351;
const ESCALA_SIMPLE_DESDE = 8_000_000; // píxeles (ancho × alto) a partir de los que no se duplica

// Cada bloque ```mermaid, con el título "## N. ..." que lo precede como nombre
const markdown = readFileSync(join(CARPETA, "..", "diagramas.md"), "utf-8");
const diagramas = [];
let titulo = "diagrama";
for (const bloque of markdown.split(/^```/m)) {
  const encabezado = [...bloque.matchAll(/^## (\d+)\. (.+)$/gm)].at(-1);
  if (encabezado) titulo = `${encabezado[1].padStart(2, "0")}-${encabezado[2]}`;
  if (bloque.startsWith("mermaid\n")) diagramas.push({ titulo, codigo: bloque.slice("mermaid\n".length) });
}
const nombreArchivo = (t) => t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + ".png";

const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PUERTO}`,
  `--user-data-dir=${mkdtempSync(join(tmpdir(), "mermaid-"))}`, "--no-first-run", "about:blank"]);
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
let destinos;
for (let i = 0; i < 40 && !destinos; i++) {
  try { destinos = await (await fetch(`http://127.0.0.1:${PUERTO}/json/list`)).json(); } catch { await esperar(250); }
}
const ws = new WebSocket(destinos.find((d) => d.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const pendientes = new Map();
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pendientes.has(m.id)) { pendientes.get(m.id)(m.result ?? m); pendientes.delete(m.id); }
});
const cdp = (method, params = {}) => new Promise((r) => { const n = ++id; pendientes.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
const js = async (e) => (await cdp("Runtime.evaluate", { expression: e, awaitPromise: true, returnByValue: true })).result?.value;

await cdp("Page.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 3000, height: 2000, deviceScaleFactor: 2, mobile: false });
const pagina = `<html><body style="margin:0;background:white;font-family:Segoe UI,sans-serif"><div id="lienzo" style="display:inline-block;padding:24px"></div>
<script type="module">import mermaid from "${MERMAID}"; import elk from "${ELK}"; mermaid.registerLayoutLoaders(elk);
mermaid.initialize({ startOnLoad: false, theme: "default", fontFamily: "Segoe UI, sans-serif" }); window.mermaid = mermaid;</script></body></html>`;
await cdp("Page.navigate", { url: `data:text/html;charset=utf-8,${encodeURIComponent(pagina)}` });
for (let i = 0; i < 40 && !(await js("typeof mermaid !== 'undefined'")); i++) await esperar(250);

let fallas = 0;
for (const [i, d] of diagramas.entries()) {
  const resultado = await js(`(async () => {
    try {
      const { svg } = await mermaid.render("d${i}", ${JSON.stringify(d.codigo)});
      const lienzo = document.getElementById("lienzo");
      lienzo.innerHTML = svg;
      // Mermaid lo achica al ancho del contenedor: se le da su tamaño natural
      const dibujo = lienzo.querySelector("svg");
      const [, , ancho, alto] = dibujo.getAttribute("viewBox").split(/[ ,]+/).map(Number);
      dibujo.style.maxWidth = "none";
      dibujo.setAttribute("width", ancho);
      dibujo.setAttribute("height", alto);
      const caja = lienzo.getBoundingClientRect();
      return { ancho: Math.ceil(caja.width), alto: Math.ceil(caja.height), svg: dibujo.outerHTML };
    } catch (error) { return { error: String(error.message ?? error) }; }
  })()`);
  if (resultado.error) {
    console.error(`✗ ${d.titulo}: ${resultado.error}`);
    fallas++;
    continue;
  }
  // Al doble de resolución, salvo los muy grandes (el diagrama completo):
  // Chrome corta la captura si pasa de cierta cantidad de píxeles
  const escala = resultado.ancho * resultado.alto > ESCALA_SIMPLE_DESDE ? 1 : 2;
  await cdp("Emulation.setDeviceMetricsOverride", { width: Math.max(resultado.ancho, 400), height: resultado.alto, deviceScaleFactor: escala, mobile: false });
  await esperar(300);
  const { data } = await cdp("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: resultado.ancho, height: resultado.alto, scale: 1 } });
  writeFileSync(join(CARPETA, nombreArchivo(d.titulo)), Buffer.from(data, "base64"));
  // También en SVG: se amplía sin perder nitidez (se abre con el navegador)
  writeFileSync(join(CARPETA, nombreArchivo(d.titulo).replace(/\.png$/, ".svg")), resultado.svg);
  console.log(`✓ ${nombreArchivo(d.titulo)} (${resultado.ancho}×${resultado.alto}, escala ${escala})`);
  if (/^%% pdf A3$/m.test(d.codigo)) {
    // La hoja se acuesta si el diagrama es más ancho que alto; se achica para que entre entero
    const apaisada = resultado.ancho > resultado.alto;
    const [anchoHoja, altoHoja] = apaisada ? [A3.alto, A3.ancho] : [A3.ancho, A3.alto];
    const achique = Math.min(((anchoHoja - 2 * A3.margen) * 96) / resultado.ancho, ((altoHoja - 2 * A3.margen) * 96) / resultado.alto);
    const { data: pdf } = await cdp("Page.printToPDF", {
      paperWidth: anchoHoja, paperHeight: altoHoja, marginTop: A3.margen, marginBottom: A3.margen,
      marginLeft: A3.margen, marginRight: A3.margen, scale: achique, printBackground: true, pageRanges: "1",
    });
    writeFileSync(join(CARPETA, nombreArchivo(d.titulo).replace(/\.png$/, ".pdf")), Buffer.from(pdf, "base64"));
    console.log(`  y en PDF A3 ${apaisada ? "apaisado" : "vertical"}`);
  }
}
ws.close();
chrome.kill();
process.exit(fallas ? 1 : 0);
