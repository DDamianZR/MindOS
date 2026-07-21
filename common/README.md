# mindos-common

Librería de utilidades comunes para los microservicios de **MindOS**.

## Componentes
*   `mindos_common/logging.py`: Configuración de logging estructurado con soporte de trazabilidad distribuida (`correlation_id`).
*   `mindos_common/context.py`: Contenedores asíncronos (`contextvars`) para almacenar metadatos de request/sesión.

## Instalación
```bash
pip install -e ../common
```
o mediante Poetry:
```toml
mindos-common = { path = "../common", develop = true }
```
