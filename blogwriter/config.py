"""Settings and workflow modes. All secrets come from the environment / .env, never from code."""
import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split(value: str) -> List[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@dataclass(frozen=True)
class Mode:
    name: str
    perspectives: int      # research angles investigated
    questions: int         # search questions per angle
    chapters: int          # chapters in the long report
    chapter_words: int     # target words per chapter of the documentary report
    blog_words: int        # target blog length
    article_words: int     # target article length
    fetch_pages: int       # pages read in full per research angle
    coverage_pages: int    # pages from OTHER outlets covering the same story, read in full
    facts_per_angle: int   # max verified facts kept per research angle
    gap_rounds: int        # extra rounds that search for what is still unanswered
    gap_queries: int       # searches per gap round
    background: bool = True  # also research Wikipedia background, archive (older) coverage and the other feed items


# chapters = the most documentary sections to write (the report follows a fixed story arc, empty ones are skipped)
MODES = {
    "fast": Mode("fast", 4, 1, 5, 350, 300, 700, 2, 3, 6, 0, 0, False),
    "standard": Mode("standard", 16, 2, 14, 700, 800, 1400, 3, 5, 8, 1, 5),
    "deep": Mode("deep", 19, 3, 16, 900, 1000, 1800, 4, 6, 10, 2, 6),
}


@dataclass(frozen=True)
class Settings:
    newsapi_key: str = ""
    gnews_key: str = ""
    groq_keys: List[str] = field(default_factory=list)
    nvidia_keys: List[str] = field(default_factory=list)
    # tried in order; the fast model first, the slow high-quality one as backup
    nvidia_models: List[str] = field(default_factory=lambda: [
        "nvidia/nemotron-3.5-lightning-30b-a3b", "mistralai/mistral-large-4-1t-a52b"])
    groq_model: str = "openai/gpt-oss-20b"
    ollama_model: str = "qwen3.5:latest"
    ollama_url: str = "http://localhost:11434"
    ollama_ctx: int = 8192
    max_tokens: int = 4000
    # Order in which LLM providers are tried.
    providers: List[str] = field(default_factory=lambda: ["groq", "nvidia", "ollama"])
    output_dir: str = "output"
    # step 5: results are emailed over SMTP (587 = STARTTLS, 465 = SSL)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""
    mail_to: List[str] = field(default_factory=list)
    # finished files are uploaded to S3-compatible object storage (Cloudflare R2, Backblaze B2, ...)
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "auto"
    s3_public_url: str = ""      # public base URL of the bucket (e.g. https://pub-xxxx.r2.dev); else signed links
    # each report is listed as a Gumroad product (a draft unless gumroad_publish is on)
    gumroad_token: str = ""
    gumroad_price_cents: int = 390          # US$3.90 per report
    gumroad_publish: bool = False
    # blog / article posting: each platform is used only when its credentials are set
    publish_live: bool = True            # False: save drafts instead of publishing (Telegram is then skipped)
    devto_api_key: str = ""
    hashnode_token: str = ""
    hashnode_publication_id: str = ""
    wordpress_url: str = ""              # https://yoursite.com (needs an Application Password)
    wordpress_user: str = ""
    wordpress_app_password: str = ""
    ghost_url: str = ""
    ghost_admin_key: str = ""            # "id:secret" from Ghost Admin -> Integrations
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.mail_to and (self.mail_from or self.smtp_user))

    @property
    def storage_configured(self) -> bool:
        return bool(self.s3_endpoint and self.s3_bucket and self.s3_access_key and self.s3_secret_key)

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            newsapi_key=e("NEWSAPI_KEY", ""),
            gnews_key=e("GNEWS_KEY", ""),
            groq_keys=_split(e("GROQ_API_KEYS", e("GROQ_API_KEY", ""))),
            nvidia_keys=_split(e("NVIDIA_API_KEYS", e("NVIDIA_API_KEY", ""))),
            nvidia_models=_split(e("NVIDIA_MODELS", "")) or [
                "nvidia/nemotron-3.5-lightning-30b-a3b", "mistralai/mistral-large-4-1t-a52b"],
            groq_model=e("GROQ_MODEL", "openai/gpt-oss-20b"),
            ollama_model=e("OLLAMA_MODEL", "qwen3.5:latest").removeprefix("ollama/"),
            ollama_url=e("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
            ollama_ctx=int(e("OLLAMA_NUM_CTX", "8192")),
            max_tokens=int(e("MAX_TOKENS", "4000")),
            providers=_split(e("LLM_PROVIDERS", "groq,nvidia,ollama")),
            output_dir=e("OUTPUT_DIR", "output"),
            smtp_host=e("SMTP_HOST", ""),
            smtp_port=int(e("SMTP_PORT", "587") or 587),
            smtp_user=e("SMTP_USER", ""),
            smtp_password=e("SMTP_PASSWORD", ""),
            mail_from=e("MAIL_FROM", "") or e("SMTP_USER", ""),
            mail_to=_split(e("MAIL_TO", "")),
            s3_endpoint=e("S3_ENDPOINT", "").rstrip("/"),
            s3_bucket=e("S3_BUCKET", ""),
            s3_access_key=e("S3_ACCESS_KEY_ID", ""),
            s3_secret_key=e("S3_SECRET_ACCESS_KEY", ""),
            s3_region=e("S3_REGION", "auto") or "auto",
            s3_public_url=e("S3_PUBLIC_URL", "").rstrip("/"),
            gumroad_token=e("GUMROAD_ACCESS_TOKEN", ""),
            gumroad_price_cents=int(e("GUMROAD_PRICE_CENTS", "390") or 390),
            gumroad_publish=e("GUMROAD_PUBLISH", "").strip().lower() in ("1", "true", "yes"),
            publish_live=e("PUBLISH_LIVE", "true").strip().lower() not in ("0", "false", "no"),
            devto_api_key=e("DEVTO_API_KEY", ""),
            hashnode_token=e("HASHNODE_TOKEN", ""),
            hashnode_publication_id=e("HASHNODE_PUBLICATION_ID", ""),
            wordpress_url=e("WORDPRESS_URL", "").rstrip("/"),
            wordpress_user=e("WORDPRESS_USER", ""),
            wordpress_app_password=e("WORDPRESS_APP_PASSWORD", ""),
            ghost_url=e("GHOST_URL", "").rstrip("/"),
            ghost_admin_key=e("GHOST_ADMIN_KEY", ""),
            telegram_bot_token=e("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=e("TELEGRAM_CHAT_ID", ""),
        )
