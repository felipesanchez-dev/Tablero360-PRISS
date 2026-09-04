/* Publica el tablero para toda la oficina, en un solo paso.
 *
 *   node herramientas/publicar.mjs ["ruta del Excel.xlsx"]
 *
 * Regenera datos.json desde el Excel y lo sube al repositorio. GitHub Pages se
 * actualiza solo en un par de minutos y todos ven los datos nuevos sin tener
 * que abrir el Excel.
 */
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DATOS = path.join(RAIZ, "datos.json");

function git(...args) {
  // maxBuffer generoso: "git show HEAD:datos.json" pasa del megabyte y el
  // límite por defecto de spawnSync lo cortaría a la mitad.
  const r = spawnSync("git", args, { cwd: RAIZ, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  if (r.error) throw r.error;
  return { code: r.status, out: (r.stdout || "").trim(), err: (r.stderr || "").trim() };
}

function fallar(msg, detalle) {
  console.error("\n✖ " + msg);
  if (detalle) console.error("  " + detalle.split("\n").join("\n  "));
  process.exit(1);
}

// 1. Que esto sea de verdad el repositorio, y no una copia suelta.
if (git("rev-parse", "--is-inside-work-tree").code !== 0)
  fallar(
    "Esta carpeta no es un repositorio de git.",
    "Clona el repositorio y trabaja dentro de esa carpeta:\n" +
      "git clone https://github.com/felipesanchez-dev/Tablero360-PRISS.git",
  );

// 2. Regenerar datos.json con el mismo parser del tablero.
console.log("→ Leyendo el Excel y regenerando datos.json…");
const gen = spawnSync(
  process.execPath,
  ["--max-old-space-size=8192", path.join(RAIZ, "herramientas/generar-datos.mjs"), ...process.argv.slice(2)],
  { cwd: RAIZ, stdio: "inherit" },
);
if (gen.status !== 0) fallar("No se pudo generar datos.json. No se subió nada.");
if (!fs.existsSync(DATOS)) fallar("datos.json no quedó escrito. No se subió nada.");

// 3. ¿Cambiaron los datos de verdad? El sello "generado" es distinto en cada
//    corrida, así que se compara el contenido sin él: si el Excel es el mismo,
//    no tiene sentido ensuciar el historial con un commit idéntico.
function huella(txt) {
  try {
    const j = JSON.parse(txt);
    return JSON.stringify({
      casos: j.casos,
      pruebasOk: j.pruebasOk,
      omitidas: j.omitidas,
      historia: (j.historia || []).length,
    });
  } catch (e) {
    return null;
  }
}
const publicado = git("show", "HEAD:datos.json");
if (publicado.code === 0) {
  const antes = huella(publicado.out);
  const ahora = huella(fs.readFileSync(DATOS, "utf8"));
  if (antes && ahora && antes === ahora) {
    git("checkout", "--", "datos.json"); // dejarlo igual a lo publicado
    console.log("\n✓ Los datos no cambiaron respecto a lo publicado. No hay nada que subir.");
    process.exit(0);
  }
}
git("add", "--", "datos.json");

// 4. Traer lo que haya en el remoto antes de subir, para no chocar.
console.log("→ Sincronizando con el repositorio…");
const rama = git("rev-parse", "--abbrev-ref", "HEAD").out || "main";
git("fetch", "origin", rama);
const detras = git("rev-list", "--count", `HEAD..origin/${rama}`).out;
if (detras && detras !== "0") {
  const pull = git("stash", "push", "--quiet", "--", "datos.json");
  const rebase = git("pull", "--rebase", "origin", rama);
  if (pull.code === 0) git("stash", "pop", "--quiet");
  if (rebase.code !== 0)
    fallar(
      "El repositorio remoto tiene cambios que no se pudieron integrar.",
      rebase.err || rebase.out,
    );
  git("add", "--", "datos.json");
}

// 5. Commit y push.
const j = JSON.parse(fs.readFileSync(DATOS, "utf8"));
const est = {};
for (const d of j.casos) est[d.e] = (est[d.e] || 0) + 1;
const cerr = est["RESUELTO"] || 0;
const ent = cerr + (est["POR VALIDAR"] || 0);
const pct = (n) => Math.round((n / j.casos.length) * 100);
const fecha = new Date().toISOString().slice(0, 10);
const mensaje =
  `Datos del ${fecha}: ${j.casos.length} casos · ` +
  `${pct(ent)}% entregado · ${pct(cerr)}% validado`;

const commit = git("commit", "-m", mensaje, "--", "datos.json");
if (commit.code !== 0) fallar("No se pudo hacer el commit.", commit.err || commit.out);

console.log("→ Subiendo…");
const push = git("push", "origin", rama);
if (push.code !== 0)
  fallar(
    "El commit quedó hecho pero el push falló.",
    (push.err || push.out) + "\nCorrige y reintenta con: git push origin " + rama,
  );

const origen = git("remote", "get-url", "origin").out.replace(/\.git$/, "");
const m = origen.match(/github\.com[/:]([^/]+)\/(.+)$/);
console.log(`\n✓ Publicado. ${mensaje}`);
if (m) console.log(`  El tablero se actualiza en un par de minutos: https://${m[1]}.github.io/${m[2]}/`);
