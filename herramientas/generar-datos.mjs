/* Genera datos.json a partir del Excel, sin abrir el navegador.
 *
 *   node herramientas/generar-datos.mjs "Matriz de Casos de Prueba.xlsx"
 *
 * Es opcional: el botón «⬆ Publicar» del tablero hace exactamente lo mismo
 * desde el navegador. Sirve para regenerar el archivo desde la terminal o
 * desde una GitHub Action.
 *
 * No duplica la lógica: extrae el parser y la agregación del propio
 * index.html, así que nunca se puede desincronizar del tablero.
 */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SALIDA = process.argv[3] || path.join(RAIZ, "datos.json");

/* Si no se pasa la ruta, busca el Excel más reciente: primero en la carpeta del
   tablero y luego en Descargas, que es donde suele quedar al bajarlo. */
function buscarExcel() {
  const candidatos = [];
  const mirar = (dir, filtro) => {
    try {
      for (const f of fs.readdirSync(dir)) {
        if (!/\.xlsm?x?$/i.test(f) || f.startsWith("~$")) continue;
        if (filtro && !filtro.test(f)) continue;
        const completo = path.join(dir, f);
        candidatos.push({ completo, mtime: fs.statSync(completo).mtimeMs });
      }
    } catch (e) {}
  };
  mirar(RAIZ, null);
  const desc = path.join(process.env.USERPROFILE || process.env.HOME || "", "Downloads");
  mirar(desc, /matriz/i);
  candidatos.sort((a, b) => b.mtime - a.mtime);
  return candidatos.length ? candidatos[0].completo : null;
}

const XLSX_PATH = process.argv[2] || buscarExcel();

if (!XLSX_PATH || !fs.existsSync(XLSX_PATH)) {
  console.error(
    [
      "No encontré el Excel.",
      "  Déjalo en la carpeta del tablero, o en Descargas con 'matriz' en el nombre,",
      "  o pásame la ruta:  node herramientas/generar-datos.mjs \"ruta\\al\\archivo.xlsx\"",
    ].join("\n"),
  );
  process.exit(1);
}
if (!process.argv[2]) console.log(`  usando: ${XLSX_PATH}`);

const html = fs.readFileSync(path.join(RAIZ, "index.html"), "utf8");
const script = html.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/)[1];

function trozo(ini, fin) {
  const i = script.indexOf(ini);
  const j = script.indexOf(fin, i);
  if (i < 0 || j < 0) throw new Error("No encontré el bloque: " + ini.slice(0, 60));
  return script.slice(i, j);
}

const codigo =
  trozo(
    "      /* ---------- Parseo flexible del Excel ----------",
    "      /* ---------- Estado de la app ---------- */",
  ) +
  trozo(
    "      function computeDias(data) {",
    "      /* ---------- Selección múltiple (filtros avanzados) ---------- */",
  );

const ctx = { console, Date, Math, JSON, Set, Map, Object, Array, Number, String };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(RAIZ, "vendor/xlsx.full.min.js"), "utf8"), ctx);
vm.runInContext(codigo + "\n;this.API = { parseWorkbook, computeDias, contar };", ctx);
const { parseWorkbook, computeDias, contar } = ctx.API;

const t0 = Date.now();
const { casos, pruebasOk, omitidas } = parseWorkbook(
  new Uint8Array(fs.readFileSync(XLSX_PATH)),
);
if (!casos.length) {
  console.error("El Excel se leyó pero no se detectaron casos.");
  process.exit(1);
}
computeDias(casos);
const c = contar(casos);

// La historia previa se conserva y se le añade la foto de hoy.
let historia = [];
try {
  historia = JSON.parse(fs.readFileSync(SALIDA, "utf8")).historia || [];
} catch (e) {}
const ahora = new Date().toISOString().slice(0, 19);
const ult = historia[historia.length - 1];
const campos = ["tot", "res", "val", "pro", "info", "pen"];
if (!ult || !campos.every((k) => ult[k] === c[k])) {
  const s = { ts: ahora };
  for (const k of campos) s[k] = c[k];
  historia.push(s);
  historia = historia.slice(-400);
}

const limpio = casos.map((d) => {
  const o = {};
  for (const k in d)
    if (!["dias", "diasPriss", "diasValid", "espera", "fcierre"].includes(k))
      o[k] = d[k];
  return o;
});

fs.writeFileSync(
  SALIDA,
  JSON.stringify({
    generado: new Date().toISOString(),
    origen: path.basename(XLSX_PATH),
    casos: limpio,
    pruebasOk,
    omitidas: omitidas || [],
    historia,
  }),
);

const mb = (fs.statSync(SALIDA).size / 1024 / 1024).toFixed(2);
console.log(
  `${path.basename(SALIDA)} generado en ${((Date.now() - t0) / 1000).toFixed(1)} s — ` +
    `${casos.length} casos, ${pruebasOk} pruebas sin novedad, ${mb} MB`,
);
console.log(
  `  sin atender ${c.pen} · en desarrollo ${c.pro} · espera info ${c.info} · ` +
    `por validar ${c.val} · validados ${c.res} → ${c.pctEnt}% entregado, ${c.pctCerr}% validado`,
);
if (omitidas && omitidas.length)
  console.warn("  ⚠ hojas que no se pudieron leer:", omitidas.join(", "));
