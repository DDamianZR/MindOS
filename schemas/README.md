# mindos-schemas

Este paquete contiene los contratos de datos versionados, DTOs de las APIs de los microservicios, esquemas de eventos y definiciones de habilidades (`Capability`) del ecosistema de **MindOS**.

## Estructura
*   `mindos_schemas/capabilities.py`: Definiciones de capacidades y contratos del Capability Registry.
*   `mindos_schemas/events/`: Modelos de CloudEvents y eventos asíncronos del sistema.
*   `mindos_schemas/api/`: DTOs (Data Transfer Objects) para las APIs síncronas REST.

## Instalación en Desarrollo Local
Para instalar en modo editable desde cualquier otro microservicio:
```bash
pip install -e ../schemas
```
o mediante Poetry:
```toml
mindos-schemas = { path = "../schemas", develop = true }
```
