# MindOS — Diagramas C4 (LikeC4)

**🔗 Publicado en GitHub Pages:** https://ddamianzr.github.io/MindOS/

Modelo [C4](https://c4model.com/) de MindOS escrito en [LikeC4](https://likec4.dev/).
Genera un sitio **estático e interactivo** (pan/zoom, navegación entre niveles, tema
claro/oscuro, export a PNG/Mermaid/PlantUML/D2) que se publica en **GitHub Pages**.

> Diagramas UML detallados (clases, secuencia, estados, despliegue, ER, C4 nivel 3):
> [`docs/uml`](../uml).

## Qué hay aquí

| Archivo | Contenido |
|---|---|
| [`mindos.c4`](mindos.c4) | `specification` (tipos de elemento) + `model` (personas, sistema, contenedores y relaciones). |
| [`views.c4`](views.c4) | Vistas: **`index`** (Contexto · C4 Nivel 1) y **`containers`** (Contenedores · C4 Nivel 2). |

- **Nivel 1 — Contexto:** MindOS como caja negra, su dueño (mono-usuario) y los sistemas
  externos (WhatsApp, asistentes de IA vía MCP, Ollama).
- **Nivel 2 — Contenedores:** se abre MindOS en sus servicios (Gateway, Memory, Agents,
  Comms, WhatsApp Bridge, MCP Server, Dashboard+PWA) y su infraestructura (Traefik,
  Redis/Event Bus, PostgreSQL+pgvector, MinIO).

> Fuente de arquitectura (autoritativa): [`plan/README.md`](../../plan/README.md) §3 y §1,
> [`plan/diagnostico-inicial.md`](../../plan/diagnostico-inicial.md) y los servicios reales del monorepo.
> Al cambiar la arquitectura, actualiza estos `.c4` en el mismo PR.

## Ver en local

```bash
# Servidor de desarrollo con recarga en caliente
npx likec4@latest start docs/c4
# -> http://localhost:5173
```

```bash
# Build de producción (igual que el de CI); relocatable con --base "./"
npx likec4@latest build --base "./" --output dist docs/c4
```

```bash
# Exportar imágenes estáticas (usa un navegador headless)
npx likec4@latest export png -o docs/c4/out docs/c4
```

## Publicar en GitHub Pages

El deploy es automático vía [`.github/workflows/c4-pages.yml`](../../.github/workflows/c4-pages.yml)
(build con LikeC4 + `actions/deploy-pages`). Se dispara al hacer push a `docs/c4-context`,
`main` o `master` cuando cambian estos archivos, o manualmente (**Run workflow**).

Pasos para activarlo (una sola vez, requieren tu cuenta de GitHub — este repo aún **no
tiene remoto**):

1. **Crear el repo en GitHub y conectar el remoto** (si no existe):
   ```bash
   git remote add origin https://github.com/<usuario>/<repo>.git
   git push -u origin docs/c4-context
   ```
2. **GitHub → Settings → Pages → Build and deployment → Source: `GitHub Actions`.**
3. Ejecutar el workflow: push a una rama válida o **Actions → C4 Pages → Run workflow**.
4. La URL final será `https://<usuario>.github.io/<repo>/` (queda enlazada en el job *deploy*).

> **Rama que no es la por defecto:** GitHub restringe el entorno `github-pages` a la rama
> por defecto. Para publicar directamente desde `docs/c4-context` sin fusionar, permite la
> rama en **Settings → Environments → github-pages → Deployment branches**. Lo más simple:
> fusionar `docs/c4-context` a la rama por defecto y dejar que el workflow publique.

### Alternativa: rama clásica `gh-pages`

Si prefieres el modelo "servir desde una rama" en vez de Actions:

```bash
npx likec4@latest build --base "./" --output dist docs/c4
git switch -c gh-pages
# publica el contenido de dist/ en la raíz de la rama gh-pages y haz push
```

Luego: **Settings → Pages → Source: `Deploy from a branch` → `gh-pages` / `/ (root)`**.
