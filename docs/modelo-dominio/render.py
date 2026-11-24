"""
Renderiza los diagramas UML del modelo de dominio (docs/modelo-dominio/src/**/*.puml) a SVG.

  python docs/modelo-dominio/render.py            # renderiza todo a out/
  python docs/modelo-dominio/render.py check      # solo valida la sintaxis (útil en CI)
  python docs/modelo-dominio/render.py --format png

Requiere Java 11+. El jar de PlantUML se descarga una vez a docs/modelo-dominio/.tools/
(ignorado por git) y se verifica con SHA-256. Solo usa la librería estándar.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "src"
OUT = BASE / "out"
TOOLS = BASE / ".tools"

VERSION = "1.2026.8"
SHA256 = "5e1ecfa8ecd32c90b03bbf3b1eb6f020943f98ab0fcf4032be31a0002ee2c462"
URL = f"https://github.com/plantuml/plantuml/releases/download/v{VERSION}/plantuml-{VERSION}.jar"
JAR = TOOLS / f"plantuml-{VERSION}.jar"


def ensure_jar() -> Path:
    if not shutil.which("java"):
        sys.exit("[render] No se encontró `java` en el PATH (se necesita Java 11+).")
    if not JAR.exists():
        TOOLS.mkdir(parents=True, exist_ok=True)
        print(f"[render] Descargando PlantUML {VERSION}…", flush=True)
        tmp = JAR.with_suffix(".part")
        urllib.request.urlretrieve(URL, tmp)
        tmp.replace(JAR)
    digest = hashlib.sha256(JAR.read_bytes()).hexdigest()
    if digest != SHA256:
        JAR.unlink()
        sys.exit(f"[render] SHA-256 inesperado ({digest}); se eliminó {JAR.name}.")
    return JAR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", nargs="?", default="render", choices=["render", "check"])
    parser.add_argument("--format", default="svg", choices=["svg", "png"])
    args = parser.parse_args()

    jar = ensure_jar()
    sources = sorted(p for p in SRC.rglob("*.puml"))
    if not sources:
        sys.exit("[render] No hay .puml en src/.")

    cmd = ["java", "-Djava.awt.headless=true", "-jar", str(jar), "-charset", "UTF-8"]
    if args.mode == "check":
        cmd += ["-checkonly"]
    else:
        # -nometadata: salida determinista (sin marcas de tiempo) → diffs limpios en git.
        cmd += [f"-t{args.format}", "-nometadata", "-o", str(OUT)]
    cmd += [str(p) for p in sources]

    print(f"[render] {args.mode}: {len(sources)} diagramas", flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"[render] PlantUML terminó con código {result.returncode} (revisa los errores de arriba).")
    print("[render] OK", flush=True)


if __name__ == "__main__":
    main()
