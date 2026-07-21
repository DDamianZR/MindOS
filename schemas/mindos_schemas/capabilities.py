from typing import Any

from pydantic import BaseModel, Field


class Capability(BaseModel):
    name: str = Field(
        ...,
        description="Nombre único identificador de la habilidad/herramienta (ej: search_knowledge)"
    )
    description: str = Field(
        ...,
        description="Descripción detallada y explicativa para el LLM sobre cuándo y cómo debe usar esta habilidad"
    )
    parameters_schema: dict[str, Any] = Field(
        ...,
        description="Esquema JSON (JSON Schema) que describe las propiedades y tipos de los parámetros que recibe la habilidad"
    )
    provider_service: str = Field(
        ...,
        description="Identificador del servicio que expone esta capacidad (ej: memory, whatsapp)"
    )
    endpoint_path: str = Field(
        ...,
        description="Ruta REST HTTP o nombre del canal del Event Bus donde se debe invocar esta capacidad"
    )
    requires_approval: bool = Field(
        default=False,
        description="Especifica si la ejecución de esta capacidad requiere el consentimiento del usuario (ej: borrar datos)"
    )


class RegisterCapabilitiesRequest(BaseModel):
    capabilities: list[Capability] = Field(..., description="Lista de habilidades a registrar en el ecosistema")


class RegisterCapabilitiesResponse(BaseModel):
    success: bool = Field(..., description="Indica si el registro de las capacidades fue exitoso")
    registered_names: list[str] = Field(..., description="Nombres de las capacidades registradas")
