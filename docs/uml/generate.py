"""
Genera los diagramas UML de MindOS (docs/uml).

  python docs/uml/generate.py                 # reverse + render (lo normal)
  python docs/uml/generate.py render          # solo renderiza los .puml a SVG
  python docs/uml/generate.py reverse         # solo ingeniería inversa desde el código
  python docs/uml/generate.py check           # valida la sintaxis de todos los .puml (CI)
  python docs/uml/generate.py render --format svg --format png

Herramientas (se instalan solas en docs/uml/.tools/, ignorado por git):
  - PlantUML (jar fijado + SHA-256): renderiza src/ y generated/. Requiere Java 11+.
    En Windows el jar trae Graphviz embebido; en Linux/macOS usa `dot` si está instalado
    y, si no, el motor de layout interno (smetana).
  - pyreverse (pylint, en un venv propio): diagramas de clases/paquetes de los servicios Python.
  - tplant (npm): diagrama de interfaces/clases del Dashboard (TypeScript). Requiere Node.js.

Solo usa la librería estándar, para poder ejecutarse con cualquier Python >= 3.10.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path

UML_DIR = Path(__file__).resolve().parent
REPO_ROOT = UML_DIR.parents[1]
SRC_DIR = UML_DIR / "src"
GENERATED_DIR = UML_DIR / "generated"
OUT_DIR = UML_DIR / "out"
TOOLS_DIR = UML_DIR / ".tools"

PLANTUML_VERSION = "1.2026.8"
PLANTUML_SHA256 = "5e1ecfa8ecd32c90b03bbf3b1eb6f020943f98ab0fcf4032be31a0002ee2c462"
PLANTUML_URL = (
    f"https://github.com/plantuml/plantuml/releases/download/v{PLANTUML_VERSION}/"
    f"plantuml-{PLANTUML_VERSION}.jar"
)
PLANTUML_JAR = TOOLS_DIR / f"plantuml-{PLANTUML_VERSION}.jar"

TPLANT_VERSION = "3.1.3"

# Paquetes Python a los que se les aplica ingeniería inversa: nombre -> carpeta de código.
PYTHON_TARGETS = {
    "memory": "memory/src",
    "agents": "agents/src",
    "gateway": "gateway/src",
    "comms": "comms/src",
    "mcp_server": "mcp_server/mindos_mcp",
    "common": "common/mindos_common",
    "schemas": "schemas/mindos_schemas",
}

# El tema compartido, relativo a generated/<lenguaje>/*.puml.
THEME_INCLUDE = "!include ../../src/_tema.iuml"


def log(msg: str) -> None:
    print(f"[uml] {msg}", flush=True)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], check=True, **kwargs)


# ───────────────────────────── Herramientas ─────────────────────────────

def require_java() -> str:
    java = shutil.which("java")
    if not java:
        sys.exit("[uml] No se encontró `java` en el PATH. Instala Java 11+ (p. ej. Temurin).")
    return java


def ensure_plantuml() -> Path:
    if not PLANTUML_JAR.exists():
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        log(f"Descargando PlantUML {PLANTUML_VERSION}…")
        tmp = PLANTUML_JAR.with_suffix(".part")
        urllib.request.urlretrieve(PLANTUML_URL, tmp)
        tmp.replace(PLANTUML_JAR)

    digest = hashlib.sha256(PLANTUML_JAR.read_bytes()).hexdigest()
    if digest != PLANTUML_SHA256:
        PLANTUML_JAR.unlink()
        sys.exit(f"[uml] SHA-256 inesperado para {PLANTUML_JAR.name} ({digest}); se eliminó el archivo.")
    return PLANTUML_JAR


def ensure_pyreverse() -> Path:
    venv_dir = TOOLS_DIR / "venv"
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    pyreverse = bin_dir / ("pyreverse.exe" if os.name == "nt" else "pyreverse")
    if not pyreverse.exists():
        log("Creando venv con pylint (pyreverse)…")
        venv.create(venv_dir, with_pip=True)
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        run([python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
             "-r", UML_DIR / "requirements.txt"])
    return pyreverse


def ensure_tplant() -> tuple[str, Path]:
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        sys.exit("[uml] tplant necesita Node.js (`node` y `npm` en el PATH).")

    prefix = TOOLS_DIR / "node"
    package_json = prefix / "node_modules" / "tplant" / "package.json"
    if not package_json.exists():
        log(f"Instalando tplant@{TPLANT_VERSION}…")
        prefix.mkdir(parents=True, exist_ok=True)
        run([npm, "install", "--prefix", prefix, "--no-audit", "--no-fund", "--silent",
             f"tplant@{TPLANT_VERSION}"])

    bin_field = json.loads(package_json.read_text(encoding="utf-8"))["bin"]
    bin_rel = bin_field if isinstance(bin_field, str) else bin_field["tplant"]
    return node, package_json.parent / bin_rel


# ─────────────────────────── Ingeniería inversa ───────────────────────────

def add_theme_and_title(puml: Path, title: str, vertical: bool = False) -> None:
    """Inserta el tema compartido y un título tras `@startuml` en un .puml generado.
    `vertical` apila los niveles de izquierda a derecha: los diagramas anchos y poco
    profundos (paquetes, DTOs) quedan altos en vez de salirse de la pantalla."""
    lines = puml.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("@startuml"))
    header = [THEME_INCLUDE, f"title {title}"] + (["left to right direction"] if vertical else [])
    lines[start + 1:start + 1] = header
    puml.write_text("\n".join(lines) + "\n", encoding="utf-8")


def reverse_python() -> None:
    pyreverse = ensure_pyreverse()
    out = GENERATED_DIR / "python"
    out.mkdir(parents=True, exist_ok=True)

    for name, folder in PYTHON_TARGETS.items():
        # Se pasan archivos explícitos: los servicios usan paquetes de espacio de nombres
        # (sin __init__.py en todas las carpetas) y pyreverse no los recorre como directorio.
        files = sorted(
            p.relative_to(REPO_ROOT).as_posix()
            for p in (REPO_ROOT / folder).rglob("*.py")
            if "tests" not in p.parts and p.stat().st_size > 0
        )
        log(f"pyreverse · {name} ({len(files)} módulos)")
        run([pyreverse, "-o", "puml", "-d", out, "-p", name,
             "--source-roots", ".,schemas,common", *files],
            cwd=REPO_ROOT, stdout=subprocess.DEVNULL)

        add_theme_and_title(out / f"classes_{name}.puml", f"{name} — clases (generado con pyreverse)")
        packages = out / f"packages_{name}.puml"
        if packages.exists():
            add_theme_and_title(packages, f"{name} — paquetes (generado con pyreverse)", vertical=True)


def reverse_typescript() -> None:
    node, tplant = ensure_tplant()
    out = GENERATED_DIR / "typescript"
    out.mkdir(parents=True, exist_ok=True)
    target = out / "dashboard.puml"

    # Solo lib/: tipos del API, cliente HTTP, auth y cola offline. Las páginas y componentes
    # son funciones de React, que no aportan a un diagrama de clases.
    log("tplant · dashboard (dashboard/src/lib)")
    run([node, tplant, "--input", "dashboard/src/lib/**/*.{ts,tsx}", "--output", target,
         "--associations"], cwd=REPO_ROOT, stdout=subprocess.DEVNULL)
    drop_top_level_members(target)
    add_theme_and_title(target, "Dashboard — interfaces y clases TypeScript (generado con tplant)",
                        vertical=True)


def drop_top_level_members(puml: Path) -> None:
    """tplant escribe las funciones exportadas sueltas como `+f(): T` fuera de toda clase, lo
    que PlantUML rechaza. Se descartan esas líneas (solo las que están fuera de un bloque)."""
    kept, depth = [], 0
    for line in puml.read_text(encoding="utf-8").splitlines():
        if depth == 0 and line.lstrip().startswith(("+", "-", "#", "~")):
            continue
        depth += line.count("{") - line.count("}")
        kept.append(line)
    puml.write_text("\n".join(kept) + "\n", encoding="utf-8")


# ──────────────────────────────── Render ────────────────────────────────

def diagram_dirs() -> list[Path]:
    """Carpetas con .puml, en src/ y generated/ (el tema .iuml no es un diagrama)."""
    dirs = {p.parent for base in (SRC_DIR, GENERATED_DIR) if base.exists() for p in base.rglob("*.puml")}
    return sorted(dirs)


def plantuml_cmd(extra: list[str]) -> list[str]:
    cmd = [require_java(), "-Djava.awt.headless=true", "-DPLANTUML_LIMIT_SIZE=16384",
           "-jar", ensure_plantuml(), "--threads", "auto"]
    if os.name != "nt" and not shutil.which("dot"):
        log("Graphviz no encontrado: se usa el layout interno de PlantUML (smetana).")
        cmd += ["--pragma", "layout=smetana"]
    return cmd + extra


def out_dir_for(folder: Path) -> Path:
    if folder.is_relative_to(SRC_DIR):
        return OUT_DIR / folder.relative_to(SRC_DIR)
    return OUT_DIR / "generated" / folder.relative_to(GENERATED_DIR)


def render(formats: list[str]) -> None:
    for folder in diagram_dirs():
        sources = sorted(folder.glob("*.puml"))
        for fmt in formats:
            target = out_dir_for(folder)
            log(f"{fmt.upper()} · {folder.relative_to(UML_DIR).as_posix()} → "
                f"{target.relative_to(UML_DIR).as_posix()} ({len(sources)} diagramas)")
            run(plantuml_cmd([f"--{fmt}", "--output-dir", target, *sources]))


def check() -> None:
    sources = [p for folder in diagram_dirs() for p in sorted(folder.glob("*.puml"))]
    log(f"Validando sintaxis de {len(sources)} diagramas…")
    result = subprocess.run([str(c) for c in plantuml_cmd(["--check-syntax", *sources])])
    if result.returncode != 0:
        sys.exit("[uml] Hay diagramas con errores de sintaxis.")
    log("OK")


def main() -> None:
    # En Windows, con la salida redirigida, stdout cae a cp1252 y no puede imprimir "→" ni acentos.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Genera los diagramas UML de MindOS.")
    parser.add_argument("command", nargs="?", default="all", choices=["all", "render", "reverse", "check"])
    parser.add_argument("--format", action="append", choices=["svg", "png"],
                        help="Formato de salida (repetible). Por defecto: svg.")
    parser.add_argument("--skip-typescript", action="store_true",
                        help="Omite tplant (útil si no hay Node.js disponible).")
    args = parser.parse_args()
    formats = args.format or ["svg"]

    if args.command in ("all", "reverse"):
        reverse_python()
        if not args.skip_typescript:
            reverse_typescript()
    if args.command in ("all", "render"):
        render(formats)
    if args.command == "check":
        check()


if __name__ == "__main__":
    main()
