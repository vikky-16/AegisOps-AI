"""
AegisOps AI - OpenTelemetry Collector Configuration Schemas
Defines request and response contracts for tailored customer OTel Collector YAML generation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class GenerateOtelConfigRequest(BaseModel):
    protocols: List[str] = Field(default=["grpc", "http"], description="gRPC (4317) and/or HTTP (4318) ingress")
    telemetry_types: List[str] = Field(default=["logs", "metrics", "traces", "events"])
    deployment_target: str = Field(default="kubernetes", description="kubernetes | docker | linux | vm | sdk")
    tls_enabled: bool = Field(default=True, description="Enforce TLS/HTTPS on egress")
    compression: str = Field(default="gzip", description="gzip | none")
    api_key: Optional[str] = Field(default=None, description="Ingestion API key to embed in headers")
    custom_endpoint: Optional[str] = Field(default=None, description="Custom AegisOps ingestion endpoint override")
    integration_id: Optional[str] = Field(default=None, description="Integration ID tag for OTel resource attributes")


class GenerateOtelConfigResponse(BaseModel):
    tenant_id: str
    format: str = "yaml"
    collector_config_yaml: str
    docker_run_command: str
    kubernetes_manifest_yaml: str
    instructions: str
