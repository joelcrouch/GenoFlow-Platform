# from pydantic import BaseSettings, Field
# from pydantic_settings import BaseSettings, SettingsConfigDict
# from pydantic import Field # Field still comes from pydantic
# from typing import List, Optional
# import os

# class Settings(BaseSettings):
#     model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
#     app_name: str = "GenoFlow API Gateway"
#     version: str = "1.0.0"
#     debug: bool = False
#     host: str = "0.0.0.0"
#     port: int = 8000

#     # CORS
#     allowed_origins: List[str] = ["http://localhost:3000", "https://genoflow.com"] # Default for now


#     # Redis configuration 
#     # redis_url: str = Field("redis://localhost:6379", env="REDIS_URL")
#     redis_url: str = "redis://localhost:6379"
#     redis_db: int = 0
#     redis_max_connections: int = 20
    
#     class Config:
#         env_file = ".env"
#         case_sensitive = False

# _settings: Optional[Settings] = None

# def get_settings() -> Settings:
#     global _settings
#     if _settings is None:
#         _settings = Settings()
#     return _settings
from pydantic_settings import BaseSettings, SettingsConfigDict # IMPORT SettingsConfigDict
from pydantic import Field
from typing import List, Optional
import os

class Settings(BaseSettings):
    # ADD THIS ConfigDict line
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = "GenoFlow API Gateway"
    version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    allowed_origins: List[str] = ["http://localhost:3000", "https://genoflow.com"]

    # Redis configuration
    # Remove 'env="REDIS_URL"' from Field, as SettingsConfigDict handles env var mapping
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_max_connections: int = 20

    # The 'env' argument on Field was for Pydantic v1's BaseSettings.
    # In Pydantic v2 with pydantic-settings, it automatically maps
    # environment variables to fields.
    # If your environment variable is REDIS_URL, and your field is `redis_url`,
    # it will automatically pick it up.

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings