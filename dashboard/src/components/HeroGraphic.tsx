"use client";

import { useId } from "react";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/**
 * Ilustración del hero. Único sitio de la portada con degradado: anillo, esfera y diamante
 * se superponen con transparencia. Decorativa: no aporta información que el texto no diga.
 */
export function HeroGraphic({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const sphere = `hero-sphere-${uid}`;

  return (
    <div aria-hidden="true" className={cx("mindos-hero", className)}>
      <style>{`
        @media (prefers-reduced-motion: no-preference) {
          @keyframes mindos-hero-in {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: none; }
          }
          .mindos-hero { animation: mindos-hero-in 700ms ease-out both; }
        }
      `}</style>
      <svg viewBox="0 0 600 460" className="h-full w-full text-obsidian" fill="none">
        <circle cx="188" cy="214" r="108" stroke="#5b8def" strokeWidth="40" opacity="0.38" />
        <circle cx="188" cy="214" r="86" stroke="#8ebaf2" strokeWidth="12" opacity="0.45" />

        <defs>
          <radialGradient id={sphere} cx="36%" cy="32%" r="68%">
            <stop offset="0%" stopColor="#f4efff" />
            <stop offset="38%" stopColor="#b09cf8" />
            <stop offset="100%" stopColor="#6d4ad4" />
          </radialGradient>
        </defs>
        <circle cx="318" cy="198" r="82" fill={`url(#${sphere})`} opacity="0.9" />
        <ellipse cx="288" cy="166" rx="28" ry="15" fill="#ffffff" opacity="0.3" />

        <g opacity="0.92">
          <polygon points="404,228 508,326 404,424 300,326" fill="#e8843c" />
          <polygon points="404,228 508,326 404,326" fill="#ffd0ae" />
          <polygon points="404,228 300,326 404,326" fill="#f3a15e" />
          <polygon points="300,326 404,424 404,326" fill="#d86a2c" />
          <polygon points="508,326 404,424 404,326" fill="#c2541c" />
        </g>

        <g stroke="currentColor" strokeWidth="1" opacity="0.7">
          <line x1="146" y1="70" x2="92" y2="142" />
          <line x1="408" y1="50" x2="332" y2="122" />
          <line x1="400" y1="444" x2="404" y2="424" />
        </g>
        <g fill="currentColor">
          <circle cx="92" cy="142" r="2.25" />
          <circle cx="332" cy="122" r="2.25" />
          <circle cx="404" cy="424" r="2.25" />
        </g>

        <g className="font-mono" fill="currentColor" fontSize="11" fontWeight="500">
          <text x="16" y="74">MEMORIA VERSIONADA</text>
          <text x="248" y="54">RAZONAMIENTO AUDITABLE</text>
          <text x="248" y="452">AGENTE CON APROBACIÓN</text>
        </g>
      </svg>
    </div>
  );
}
