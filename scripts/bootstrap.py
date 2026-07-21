import os
import subprocess
import sys


def run_command(command, cwd=None):
    print(f"Ejecutando: {' '.join(command)} (Cwd: {cwd or '.'})")
    result = subprocess.run(command, cwd=cwd, shell=True)
    if result.returncode != 0:
        print(f"Error ejecutando el comando: {result.returncode}")
        sys.exit(result.returncode)

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("--- Inicializando el Kernel de MindOS ---")

    # 1. Instalar dependencias base necesarias para el Kernel
    print("\nInstalando dependencias base (ruff, structlog, pydantic)...")
    run_command([sys.executable, "-m", "pip", "install", "pydantic>=2.0.0", "structlog", "ruff"])

    # 2. Instalar mindos-schemas en modo editable
    schemas_path = os.path.join(root_dir, "schemas")
    print(f"\nInstalando mindos-schemas en modo editable desde: {schemas_path}")
    run_command([sys.executable, "-m", "pip", "install", "-e", "."], cwd=schemas_path)

    # 3. Instalar mindos-common en modo editable
    common_path = os.path.join(root_dir, "common")
    print(f"\nInstalando mindos-common en modo editable desde: {common_path}")
    run_command([sys.executable, "-m", "pip", "install", "-e", "."], cwd=common_path)

    print("\n--- Kernel de MindOS inicializado con éxito ---")
    print("Puedes usar 'import mindos_schemas' y 'import mindos_common' desde cualquier servicio.")

if __name__ == "__main__":
    main()
