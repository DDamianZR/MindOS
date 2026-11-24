// Iconos de trazo de MindOS: un solo grosor y una sola rejilla (20 px) para que se lean como
// familia. Decorativos por defecto (aria-hidden): el texto que los acompaña lleva el significado.
import type { SVGProps } from "react";

function Icon({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

type P = SVGProps<SVGSVGElement>;

/** Marca: tres nodos enlazados, el grafo en su forma mínima. */
export function BrandMark(props: P) {
  return (
    <Icon {...props}>
      <path d="M5.2 13.6 9 6.9M11 6.9l3.8 6.7M6.6 15h6.8" />
      <circle cx="10" cy="5" r="2.1" fill="currentColor" stroke="none" />
      <circle cx="4.4" cy="15" r="2.1" />
      <circle cx="15.6" cy="15" r="2.1" />
    </Icon>
  );
}

export function AssistantIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h9A1.5 1.5 0 0 1 16 5.5v6a1.5 1.5 0 0 1-1.5 1.5H9l-3.5 3v-3A1.5 1.5 0 0 1 4 11.5z" />
      <path d="M7.5 7.5h5M7.5 10h3" />
    </Icon>
  );
}

export function SearchIcon(props: P) {
  return (
    <Icon {...props}>
      <circle cx="9" cy="9" r="4.75" />
      <path d="m12.6 12.6 3.4 3.4" />
    </Icon>
  );
}

export function GraphIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M6.4 8.1 8.6 6.4M11.5 6.6l2.2 2.3M13.4 12.3l-2.3 1.6M7.8 13.6 6.3 11.2" />
      <circle cx="10" cy="5" r="1.75" />
      <circle cx="5.25" cy="9.75" r="1.75" />
      <circle cx="14.75" cy="10.5" r="1.75" />
      <circle cx="9.5" cy="15" r="1.75" />
    </Icon>
  );
}

export function TimelineIcon(props: P) {
  return (
    <Icon {...props}>
      <circle cx="10" cy="10" r="6.25" />
      <path d="M10 6.5V10l2.4 1.6" />
    </Icon>
  );
}

export function CaptureIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M10 4.5v11M4.5 10h11" />
    </Icon>
  );
}

export function ReasoningIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M5 4.5v4a3 3 0 0 0 3 3h7" />
      <path d="m12.5 9 2.5 2.5-2.5 2.5" />
      <circle cx="5" cy="15.25" r="0.9" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function QuestionsIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M7.4 7.6a2.7 2.7 0 1 1 3.9 2.4c-.8.5-1.3 1-1.3 2" />
      <circle cx="10" cy="14.6" r="0.9" fill="currentColor" stroke="none" />
      <circle cx="10" cy="10" r="6.75" />
    </Icon>
  );
}

export function ContradictionIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M4.5 7h8M10 4.5 12.5 7 10 9.5M15.5 13h-8M10 10.5 7.5 13l2.5 2.5" />
    </Icon>
  );
}

export function ApprovalIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M10 3.75 15.25 6v4c0 3-2.1 5.3-5.25 6.25C6.85 15.3 4.75 13 4.75 10V6z" />
      <path d="m7.75 10 1.6 1.6 2.9-3.1" />
    </Icon>
  );
}

export function SendIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M10 15.5v-11M5.5 9 10 4.5 14.5 9" />
    </Icon>
  );
}

export function StopIcon(props: P) {
  return (
    <Icon {...props}>
      <rect x="6" y="6" width="8" height="8" rx="1.25" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function MenuIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M4 6.5h12M4 10h12M4 13.5h12" />
    </Icon>
  );
}

export function CloseIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="m5.5 5.5 9 9M14.5 5.5l-9 9" />
    </Icon>
  );
}

export function NewConversationIcon(props: P) {
  return (
    <Icon {...props}>
      <path d="M10.5 4.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h8a1.5 1.5 0 0 0 1.5-1.5V9.5" />
      <path d="m9 11 .4-2.1 5.3-5.3a1.2 1.2 0 0 1 1.7 1.7l-5.3 5.3z" />
    </Icon>
  );
}
