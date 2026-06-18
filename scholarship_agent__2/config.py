from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic direct auth
    anthropic_api_key: str = ""

    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    claude_code_use_vertex: int = 0  # 1 = use Vertex AI, 0 = use Anthropic

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    @property
    def use_vertex(self) -> bool:
        return self.claude_code_use_vertex == 1

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)

    def vertex_env(self) -> dict[str, str]:
        """Build the env dict to pass to ClaudeAgentOptions for Vertex AI."""
        return {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "CLOUD_ML_REGION": self.google_cloud_location,
            "ANTHROPIC_VERTEX_PROJECT_ID": self.google_cloud_project,
        }

    def anthropic_env(self) -> dict[str, str]:
        """Build the env dict to pass to ClaudeAgentOptions for direct Anthropic API."""
        return {"ANTHROPIC_API_KEY": self.anthropic_api_key}


settings = Settings()

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

REPORTS_DIR.mkdir(exist_ok=True)
