// Catálogo de diagramas de MindOS (Fase 8). Cada categoría vive en su propio archivo
// (`uml.ts`, `bases-de-datos.ts`, ...) y exporta un `DiagramCategory`.

export type DiagramStatus =
  /** Dibujado aquí como código Mermaid, leyendo el código real del repo. */
  | "generated"
  /** Ya existía como SVG renderizado (PlantUML en docs/uml o docs/modelo-dominio). */
  | "existing"
  /** El tipo de diagrama no describe nada que MindOS tenga hoy; `reason` explica por qué. */
  | "not_applicable";

export interface Diagram {
  /** Número del catálogo, tal como en la lista original: "1.1", "8.14". */
  id: string;
  /** Identificador estable para la URL: minúsculas y guiones, sin acentos. Ej: "casos-de-uso". */
  slug: string;
  title: string;
  status: DiagramStatus;
  /** Qué muestra, en 1-2 frases en español, para alguien que conoce el producto pero no el código. */
  description: string;
  /** Código Mermaid (v11). Obligatorio si status = "generated". */
  mermaid?: string;
  /** SVGs ya renderizados bajo /public. Obligatorio si status = "existing". */
  svgs?: Array<{ src: string; caption: string }>;
  /** Archivos del repo en los que se basa (rutas relativas a la raíz). Vacío si not_applicable. */
  basedOn: string[];
  /** Solo si status = "not_applicable": por qué no aplica hoy y qué tendría que existir para que aplique. */
  reason?: string;
}

export interface DiagramCategory {
  /** Número de la categoría: "1" ... "8". */
  id: string;
  slug: string;
  title: string;
  /** Una frase: para qué sirve esta familia de diagramas. */
  summary: string;
  diagrams: Diagram[];
}
