import os
import subprocess
import sys


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("--- Ejecutando Linter (Ruff) en MindOS ---")

    # Ejecutamos ruff check en la raíz del proyecto usando el módulo de Python
    result = subprocess.run([sys.executable, "-m", "ruff", "check", "."], cwd=root_dir, shell=True)

    if result.returncode == 0:
        print("\n[OK] El código cumple con las reglas de estilo y calidad de la arquitectura.")
        sys.exit(0)
    else:
        print("\n[FALLO] Se detectaron errores de estilo o calidad. Por favor corregirlos antes de subir cambios.")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
