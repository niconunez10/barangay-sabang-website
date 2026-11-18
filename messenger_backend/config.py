from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    facebook_app_secret: str = ""
    facebook_verify_token: str = ""
    facebook_page_access_token: str = ""
    facebook_graph_version: str = "v22.0"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    tavily_api_key: str = ""
    announcements_feed_path: str = "messenger_backend/data/announcements.json"
    duty_desk_webhook_url: str = ""
    duty_desk_webhook_secret: str = ""
    ner_model: str = ""
    barangay_tanod_phone: str = ""
    bfp_hotline: str = "911"
    pnp_hotline: str = "911"
    current_event_max_age_days: int = 7
    trusted_search_domains: str = (
        "gov.ph,pagasa.dost.gov.ph,pna.gov.ph,gmanetwork.com,abs-cbn.com,"
        "inquirer.net,philstar.com,rappler.com"
    )

    @property
    def trusted_domains(self) -> tuple[str, ...]:
        return tuple(
            domain.strip().lower()
            for domain in self.trusted_search_domains.split(",")
            if domain.strip()
        )


settings = Settings()
