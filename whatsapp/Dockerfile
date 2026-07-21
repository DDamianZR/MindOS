# Imagen del adaptador de WhatsApp (F3-T4). Contexto de build = whatsapp/ (no necesita el resto
# del monorepo: es Node, no Python).
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev

COPY src/ ./src/

# Sesión de Baileys (QR/credenciales) — SIEMPRE en un volumen, nunca en la imagen ni en el repo.
RUN mkdir -p /app/auth_state
VOLUME ["/app/auth_state"]

EXPOSE 8004

HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=5 \
    CMD node -e "fetch('http://localhost:8004/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "src/index.js"]
