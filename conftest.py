"""
Aislamiento de la suite respecto del `.env` local.

Los servicios leen el `.env` de la raíz al importarse. Si ahí hay una ANTHROPIC_API_KEY real,
el servicio de agentes resuelve el proveedor como `anthropic` y los tests llaman a la API de
pago (lentos, no deterministas y con costo). Las variables de entorno tienen precedencia sobre
el `.env` en pydantic-settings, así que basta con fijarlas vacías antes de que se importe nada.
Un test que necesite el proveedor real lo configura explícitamente con `monkeypatch`.
"""
import os

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
os.environ["LLM_PROVIDER"] = "auto"
