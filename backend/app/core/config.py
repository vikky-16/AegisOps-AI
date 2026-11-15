"""
AegisOps AI Core Configuration Settings
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AegisOps AI"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"
    
    # Security & Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "aegisops-super-secret-enterprise-key-2026-sre-ai")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./aegisops.db")
    
    # Microservices URLs
    GATEWAY_URL: str = os.getenv("GATEWAY_URL", "http://127.0.0.1:8001")
    SERVICE_A_URL: str = os.getenv("SERVICE_A_URL", "http://127.0.0.1:8002")
    SERVICE_B_URL: str = os.getenv("SERVICE_B_URL", "http://127.0.0.1:8003")
    DATABASE_SERVICE_URL: str = os.getenv("DATABASE_SERVICE_URL", "http://127.0.0.1:8004")
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8005")
    PAYMENT_API_URL: str = os.getenv("PAYMENT_API_URL", "http://127.0.0.1:8003")
    
    # AIOps Configuration
    MONITORING_INTERVAL_SEC: float = 1.0
    ANOMALY_CONTAMINATION: float = 0.05
    CORRELATION_WINDOW_SEC: int = 20
    AUTO_HEALING_LOW_RISK: bool = True
    STORAGE_ALERT_THRESHOLD_PCT: float = 85.0
    
    # Apache Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_TELEMETRY_TOPIC: str = os.getenv("KAFKA_TELEMETRY_TOPIC", "telemetry.raw")
    KAFKA_CONSUMER_GROUP: str = os.getenv("KAFKA_CONSUMER_GROUP", "aegisops-telemetry-consumer")
    
    # OpenTelemetry & Streaming Pipeline Configuration
    OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "aegisops-ai")
    
    # Paths
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    LOGS_DIR: str = os.path.join(DATA_DIR, "logs")
    ARCHIVE_DIR: str = os.path.join(DATA_DIR, "archive")
    DEMO_DIR: str = os.path.join(DATA_DIR, "demo")
    TELEMETRY_DATA_DIR: str = os.path.join(DATA_DIR, "telemetry")

    class Config:
        case_sensitive = True


settings = Settings()

# Ensure directories exist
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)
os.makedirs(settings.DEMO_DIR, exist_ok=True)
os.makedirs(settings.TELEMETRY_DATA_DIR, exist_ok=True)
