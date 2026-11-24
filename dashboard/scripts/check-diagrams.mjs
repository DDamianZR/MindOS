// Valida el catálogo de diagramas (Fase 8) sin navegador:
//   node scripts/check-diagrams.mjs                 -> las 8 categorías
//   node scripts/check-diagrams.mjs uml procesos    -> solo esas
//
// Comprueba la forma de cada entrada (ids, slugs, estado coherente con sus campos, SVG que
// existen en public/) y que cada código Mermaid PARSEA con la misma versión de Mermaid que usa
// la app. El parseo no garantiza que el dibujo se vea bien: eso se revisa en /diagrams.
//
// Node 24 ejecuta los .ts de src/content/diagrams directamente (quita los tipos al cargar).
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// Mermaid usa DOMPurify, que sin `window` no expone sus métodos. Para PARSEAR no hace falta
// sanear nada, así que se neutraliza antes de cargar Mermaid (mismo módulo, misma instancia).
const { default: DOMPurify } = await import("dompurify");
DOMPurify.addHook = () => {};
DOMPurify.removeHook = () => {};
DOMPurify.removeHooks = () => {};
DOMPurify.sanitize = (s) => s;
const { default: mermaid } = await import("mermaid");

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const CATEGORIES = {
  uml: "uml",
  "bases-de-datos": "basesDeDatos",
  arquitectura: "arquitectura",
  procesos: "procesos",
  "ux-ui": "uxUi",
  infraestructura: "infraestructura",
  seguridad: "seguridad",
  "inteligencia-artificial": "inteligenciaArtificial",
};
// Número de diagramas por categoría en la lista original.
const EXPECTED = { "1": 14, "2": 6, "3": 13, "4": 6, "5": 8, "6": 9, "7": 8, "8": 14 };

const wanted = process.argv.slice(2);
const files = wanted.length ? wanted : Object.keys(CATEGORIES);
let problems = 0;
const tally = { generated: 0, existing: 0, not_applicable: 0 };

function fail(where, message) {
  problems += 1;
  console.log(`  ✗ ${where}: ${message}`);
}

for (const file of files) {
  const exportName = CATEGORIES[file];
  if (!exportName) {
    fail(file, `categoría desconocida (válidas: ${Object.keys(CATEGORIES).join(", ")})`);
    continue;
  }
  const mod = await import(pathToFileURL(join(ROOT, "src/content/diagrams", `${file}.ts`)).href);
  const category = mod[exportName];
  console.log(`\n${file}.ts`);
  if (!category) {
    fail(file, `no exporta \`${exportName}\``);
    continue;
  }
  if (!category.summary) fail(file, "falta `summary`");
  const expected = EXPECTED[category.id];
  if (category.diagrams.length !== expected) {
    fail(file, `tiene ${category.diagrams.length} diagramas y la lista original tiene ${expected}`);
  }

  const seenIds = new Set();
  const seenSlugs = new Set();
  for (const d of category.diagrams) {
    const where = `${d.id ?? "?"} ${d.title ?? ""}`;
    if (!d.id?.startsWith(`${category.id}.`)) fail(where, `el id debe empezar por "${category.id}."`);
    if (seenIds.has(d.id)) fail(where, "id repetido");
    seenIds.add(d.id);
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(d.slug ?? "")) fail(where, `slug inválido: "${d.slug}"`);
    if (seenSlugs.has(d.slug)) fail(where, "slug repetido");
    seenSlugs.add(d.slug);
    if (!d.title || !d.description) fail(where, "faltan title o description");
    if (!Array.isArray(d.basedOn)) fail(where, "basedOn debe ser una lista");
    tally[d.status] = (tally[d.status] ?? 0) + 1;

    if (d.status === "generated") {
      if (!d.mermaid?.trim()) {
        fail(where, "status generated sin código mermaid");
        continue;
      }
      if (/%%\{\s*init/.test(d.mermaid)) fail(where, "no uses directivas %%{init}%%: el tema lo pone la app");
      if (!d.basedOn?.length) fail(where, "un diagrama generado debe listar en basedOn los archivos que leíste");
      for (const path of d.basedOn ?? []) {
        if (!existsSync(join(ROOT, "..", path))) fail(where, `basedOn apunta a un archivo que no existe: ${path}`);
      }
      try {
        await mermaid.parse(d.mermaid);
      } catch (e) {
        fail(where, `Mermaid no lo puede leer -> ${String(e.message ?? e).split("\n").slice(0, 3).join(" | ")}`);
      }
    } else if (d.status === "existing") {
      if (!d.svgs?.length) fail(where, "status existing sin svgs");
      for (const svg of d.svgs ?? []) {
        if (!existsSync(join(ROOT, "public", svg.src))) fail(where, `no existe public${svg.src}`);
      }
    } else if (d.status === "not_applicable") {
      if (!d.reason) fail(where, "status not_applicable sin reason");
    } else {
      fail(where, `status desconocido: ${d.status}`);
    }
  }
  console.log(`  ${category.diagrams.length} diagramas revisados`);
}

console.log(
  `\nTotal: ${tally.generated} generados, ${tally.existing} existentes, ${tally.not_applicable} no aplican.`,
);
console.log(problems ? `${problems} problema(s).` : "Sin problemas.");
process.exit(problems ? 1 : 0);
