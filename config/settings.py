"""Configurações centralizadas via .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).parent.parent.resolve()
APP_NAME = "marketplace_seller_platform"
APP_VERSION = "1.2.0-postgres-hardening"
ENV = os.getenv("ENV", "development").lower()
DEBUG = ENV in {"development", "test"}
ENABLE_DEMO_USER = os.getenv(
    "ENABLE_DEMO_USER",
    "true" if ENV in {"development", "test"} else "false",
).lower() == "true"
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-change-in-prod")
if ENV == "production" and API_SECRET_KEY in {"", "dev-secret-change-in-prod", "troque-em-producao", "change-me", "changeme"}:
    raise RuntimeError("API_SECRET_KEY seguro é obrigatório em produção.")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
DATABASE_URL = os.getenv("DATABASE_URL") or ("sqlite:///./data/marketplace_seller_platform.sqlite" if ENV != "production" else "")
if ENV == "production" and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL PostgreSQL é obrigatória em produção.")
if ENV == "production" and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("SQLite não é permitido em produção; configure DATABASE_URL PostgreSQL.")
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")
ML_REDIRECT_URI = os.getenv("ML_REDIRECT_URI", "http://localhost:8000/auth/ml/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# E-mail transacional (Resend)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@selleros.com.br")
RESEND_FROM_NAME = os.getenv("RESEND_FROM_NAME", "SellerOS")
PRIVACY_CONTACT_EMAIL = os.getenv("PRIVACY_CONTACT_EMAIL", "")
API_LOG_RETENTION_DAYS = int(os.getenv("API_LOG_RETENTION_DAYS", "90"))
SCRAPING_LOG_RETENTION_DAYS = int(os.getenv("SCRAPING_LOG_RETENTION_DAYS", "90"))
PRIVACY_REQUEST_RETENTION_DAYS = int(os.getenv("PRIVACY_REQUEST_RETENTION_DAYS", "1825"))
if ENV == "production" and not PRIVACY_CONTACT_EMAIL:
    raise RuntimeError("PRIVACY_CONTACT_EMAIL é obrigatório em produção.")
FERNET_KEY = os.getenv("FERNET_KEY", "")
if ENV == "production" and not FERNET_KEY:
    raise RuntimeError("FERNET_KEY é obrigatória em produção para criptografar tokens.")
ML_BASE_URL = "https://api.mercadolibre.com"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
MARKETPLACE_COMMISSIONS = {"mercadolivre": 0.14, "shopee": 0.12, "amazon": 0.15}
TAX_RATE = float(os.getenv("TAX_RATE", "0.06"))
ML_MODELS_DIR = BASE_DIR / "ml" / "models"
ML_DATASETS_DIR = BASE_DIR / "ml" / "datasets"
ML_MIN_MARGIN = float(os.getenv("ML_MIN_MARGIN", "0.10"))
ML_RETRAIN_DAYS = int(os.getenv("ML_RETRAIN_DAYS", "7"))
SCRAPING_DELAY_MIN = float(os.getenv("SCRAPING_DELAY_MIN", "1.0"))
SCRAPING_DELAY_MAX = float(os.getenv("SCRAPING_DELAY_MAX", "3.0"))
SCRAPING_MAX_PAGES = int(os.getenv("SCRAPING_MAX_PAGES", "5"))
SCRAPING_TIMEOUT = int(os.getenv("SCRAPING_TIMEOUT", "15"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
FEATURE_STORE_DIR = BASE_DIR / "data_engineering" / "feature_store" / "store"
for d in (LOG_DIR, DATA_DIR, STORAGE_DIR, FEATURE_STORE_DIR, ML_MODELS_DIR, ML_DATASETS_DIR):
    d.mkdir(parents=True, exist_ok=True)
AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", str(BASE_DIR / "data_engineering"))
USE_AIRFLOW = os.getenv("USE_AIRFLOW", "false").lower() == "true"

CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]


# PATCH 9/10 — Alertas Telegram/WhatsApp (opcionais)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")
ALERT_DEDUPE_WINDOW_MINUTES = int(os.getenv("ALERT_DEDUPE_WINDOW_MINUTES", "120"))


# PATCH 10/10 — Billing Pagar.me + SaaS Monetization Layer
PAGARME_API_KEY = os.getenv("PAGARME_API_KEY", "")
PAGARME_BASE_URL = os.getenv("PAGARME_BASE_URL", "https://api.pagar.me/core/v5")
PAGARME_WEBHOOK_SECRET = os.getenv("PAGARME_WEBHOOK_SECRET", "")
BILLING_PROVIDER = os.getenv("BILLING_PROVIDER", "pagarme")
BILLING_TRIAL_DAYS = int(os.getenv("BILLING_TRIAL_DAYS", "7"))
if ENV == "production" and PAGARME_API_KEY and not PAGARME_WEBHOOK_SECRET:
    raise RuntimeError("PAGARME_WEBHOOK_SECRET é obrigatório quando billing está habilitado em produção.")
