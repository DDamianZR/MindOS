import { arquitectura } from "./arquitectura";
import { basesDeDatos } from "./bases-de-datos";
import { infraestructura } from "./infraestructura";
import { inteligenciaArtificial } from "./inteligencia-artificial";
import { procesos } from "./procesos";
import { seguridad } from "./seguridad";
import type { DiagramCategory } from "./types";
import { uml } from "./uml";
import { uxUi } from "./ux-ui";

export type { Diagram, DiagramCategory, DiagramStatus } from "./types";

/** Las 8 familias del catálogo, en el orden de la lista original. */
export const DIAGRAM_CATEGORIES: DiagramCategory[] = [
  uml,
  basesDeDatos,
  arquitectura,
  procesos,
  uxUi,
  infraestructura,
  seguridad,
  inteligenciaArtificial,
];
