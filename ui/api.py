"""ui/api.py — FastAPI: todos os endpoints da plataforma."""
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from config.settings import (
    APP_NAME,
    APP_VERSION,
    CORS_ORIGINS,
    ENABLE_DEMO_USER,
    FRONTEND_URL,
    ENV,
    ML_CLIENT_ID,
    ML_CLIENT_SECRET,
    ML_REDIRECT_URI,
)
from db.base import get_db
from config.database import check_database_connection, database_kind, validate_runtime_environment
from models.schemas import (
    ClienteCreate, ClienteOut, ProductCreate, ProductOut,
    PricingRequest, PricingResponse, ScrapingRequest, ScrapingResult,
    PublishRequest, PublishResponse, MLTrainRequest, MLTrainResponse,
    StatusResponse, LoginRequest, RefreshRequest, TokenResponse, MeResponse, JobOut,
    PrivacyRequestCreate,
)

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Seller Automation Platform for Marketplaces",
    docs_url=None if ENV == "production" else "/docs",
    redoc_url=None if ENV == "production" else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ─────────────────────────────────────────────
# STARTUP / HEALTH
# ─────────────────────────────────────────────
@app.on_event("startup")
def startup_checks():
    """Valida ambiente e banco antes de aceitar tráfego.

    Falhas aqui devem derrubar o startup em produção para evitar rodar com
    segredo fraco, SQLite indevido ou banco indisponível.
    """
    validate_runtime_environment()
    check_database_connection()


@app.get("/health", tags=["system"])
def health():
    database_ok = True
    try:
        check_database_connection()
    except Exception:
        database_ok = False
    marketplace_configured = bool(ML_CLIENT_ID and ML_CLIENT_SECRET and ML_REDIRECT_URI)
    return {
        "status": "ok" if database_ok else "degraded",
        "api": "ok",
        "database": "ok" if database_ok else "error",
        "environment": ENV,
        "marketplace_api": "ok" if marketplace_configured else "not_configured",
        "database_engine": database_kind(),
        "version": APP_VERSION,
        "app": APP_NAME,
    }




# ─────────────────────────────────────────────
# AUTH APP
# ─────────────────────────────────────────────
def current_user(request: Request, db: Session = Depends(get_db)):
    from services.auth_service import decode_access_token
    from models.orm import User
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"message": "Faça login para acessar este recurso."})
    try:
        payload = decode_access_token(auth.split(" ", 1)[1])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"message": str(exc)})
    user = db.query(User).filter_by(id=payload.get("sub"), ativo=True).first()
    if not user:
        raise HTTPException(status_code=401, detail={"message": "Usuário não encontrado ou inativo."})
    return user



def optional_current_user(request: Request, db: Session = Depends(get_db)):
    """Retorna usuário autenticado quando houver token válido, sem bloquear rotas públicas."""
    from services.auth_service import decode_access_token
    from models.orm import User
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        payload = decode_access_token(auth.split(" ", 1)[1])
        return db.query(User).filter_by(id=payload.get("sub"), ativo=True).first()
    except Exception:
        return None


def enforce_public_rate_limit(request: Request) -> None:
    from services.rate_limit_service import public_utility_limiter
    client_host = request.client.host if request.client else "unknown"
    if ENV != "test" and not public_utility_limiter.allow(client_host):
        raise HTTPException(status_code=429, detail={"message": "Limite temporário de consultas atingido."})

@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def auth_login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    from services.auth_service import authenticate, ensure_demo_user, issue_tokens
    from services.rate_limit_service import login_limiter
    client_host = request.client.host if request.client else "unknown"
    limiter_key = f"{client_host}:{req.email.lower().strip()}"
    if ENV != "test" and not login_limiter.allow(limiter_key):
        raise HTTPException(status_code=429, detail={"message": "Muitas tentativas. Aguarde alguns minutos."})
    if ENABLE_DEMO_USER:
        ensure_demo_user(db)
    user = authenticate(db, req.email, req.senha)
    if not user:
        raise HTTPException(status_code=401, detail={"message": "E-mail ou senha inválidos."})
    return issue_tokens(db, user)

@app.post("/auth/refresh", response_model=TokenResponse, tags=["auth"])
def auth_refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    from services.auth_service import refresh_tokens
    try:
        return refresh_tokens(db, req.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"message": str(exc)})

@app.post("/auth/logout", tags=["auth"])
def auth_logout(req: RefreshRequest, db: Session = Depends(get_db)):
    from services.auth_service import revoke_refresh_token
    revoke_refresh_token(db, req.refresh_token)
    return {"status": "ok", "message": "Sessão encerrada."}

@app.get("/auth/me", response_model=MeResponse, tags=["auth"])
def auth_me(user = Depends(current_user), db: Session = Depends(get_db)):
    from models.orm import Cliente
    tenant = db.query(Cliente).filter_by(id=user.cliente_id).first()
    tenant_config = tenant.config if tenant and isinstance(tenant.config, dict) else {}
    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.cliente_id,
        "organization_id": user.organization_id,
        "modo_demo": bool(tenant_config.get("modo_demo")),
    }


@app.get("/privacy", tags=["privacy"])
def privacy_notice():
    from services.privacy_service import privacy_summary
    return privacy_summary()


@app.get("/privacy/me/export", tags=["privacy"])
def privacy_export(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.privacy_service import export_user_data
    return export_user_data(db, user)


@app.get("/privacy/me/requests", tags=["privacy"])
def privacy_requests(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.privacy_service import list_privacy_requests
    return list_privacy_requests(db, user)


@app.post("/privacy/me/requests", status_code=201, tags=["privacy"])
def privacy_create_request(
    payload: PrivacyRequestCreate,
    user = Depends(current_user),
    db: Session = Depends(get_db),
):
    from services.privacy_service import create_privacy_request
    return create_privacy_request(db, user, payload.request_type, payload.description)


@app.get("/app/dashboard", tags=["app"])
def app_dashboard(user = Depends(current_user), db: Session = Depends(get_db)):
    return build_dashboard_response(db, user.cliente_id)

@app.get("/app/products", response_model=List[ProductOut], tags=["app"])
def app_products(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import list_products
    return list_products(db, user.cliente_id)

@app.post("/jobs/{job_type}", response_model=JobOut, tags=["jobs"])
def create_job(job_type: str, parameters: dict | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    if job_type not in {"scraping", "pricing", "publish", "ml-train"}:
        raise HTTPException(400, detail={"message": "Tipo de job inválido."})
    from services.job_service import create_job
    return create_job(db, user.cliente_id, job_type, parameters)

@app.post("/jobs/scraping", response_model=JobOut, tags=["jobs"])
def create_scraping_job(parameters: dict | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.job_service import create_job
    return create_job(db, user.cliente_id, "scraping", parameters)

@app.post("/jobs/pricing", response_model=JobOut, tags=["jobs"])
def create_pricing_job(parameters: dict | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.job_service import create_job
    return create_job(db, user.cliente_id, "pricing", parameters)

@app.post("/jobs/publish", response_model=JobOut, tags=["jobs"])
def create_publish_job(parameters: dict | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.job_service import create_job
    return create_job(db, user.cliente_id, "publish", parameters)

@app.post("/jobs/ml-train", response_model=JobOut, tags=["jobs"])
def create_ml_job(parameters: dict | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.job_service import create_job
    return create_job(db, user.cliente_id, "ml-train", parameters)

@app.get("/jobs", response_model=List[JobOut], tags=["jobs"])
def get_jobs(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.job_service import list_jobs
    return list_jobs(db, user.cliente_id)


@app.post("/jobs/{job_id}/rerun", response_model=JobOut, tags=["jobs"])
def rerun_job(job_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.job_service import rerun_job
    job = rerun_job(db, user.cliente_id, job_id)
    if not job:
        raise HTTPException(404, detail={"message": "Job não encontrado."})
    return job

@app.get("/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
def get_job(job_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from models.orm import BackgroundJob
    job = db.query(BackgroundJob).filter_by(id=job_id, tenant_id=user.cliente_id).first()
    if not job:
        raise HTTPException(404, detail={"message": "Job não encontrado."})
    return job

# ─────────────────────────────────────────────
# TENANT SECURITY HELPERS
# ─────────────────────────────────────────────
def require_same_tenant(cliente_id: str, user, db: Session) -> None:
    _check_cliente(db, cliente_id)
    if str(user.cliente_id) != str(cliente_id):
        raise HTTPException(status_code=403, detail={"message": "Acesso negado para este tenant."})


# ─────────────────────────────────────────────
# PATCH 14/15 — PORTFOLIO ANALYSIS
# ─────────────────────────────────────────────
@app.get("/portfolio/analysis", tags=["portfolio-analysis"])
def portfolio_analysis(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.portfolio_analysis_service import analyze_portfolio
    try:
        return analyze_portfolio(db, user.cliente_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"message": "Não foi possível gerar a análise de portfólio agora."}) from exc


@app.post("/portfolio/refresh-analysis", tags=["portfolio-analysis"])
def portfolio_refresh_analysis(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.portfolio_analysis_service import analyze_portfolio
    return analyze_portfolio(db, user.cliente_id, persist=True)


@app.get("/portfolio/products/{product_id}", tags=["portfolio-analysis"])
def portfolio_product(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.portfolio_analysis_service import analyze_product
    try:
        return analyze_product(db, user.cliente_id, product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"message": "Não foi possível analisar este produto agora."}) from exc




# ─────────────────────────────────────────────
# PATCH 15/15 — PWA / ONBOARDING FINAL / SYSTEM STATUS
# ─────────────────────────────────────────────
@app.get("/onboarding/insights", tags=["final-onboarding"])
def onboarding_insights(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.onboarding_insights_service import get_onboarding_insights
    try:
        return get_onboarding_insights(db, user.cliente_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"message": "Não foi possível gerar os insights iniciais agora."}) from exc


@app.get("/system/status", tags=["system"])
def system_status(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.onboarding_insights_service import get_onboarding_insights
    from models.orm import BackgroundJob, InternalAlert, MarketplaceConnection, Product
    database_ok = True
    try:
        check_database_connection()
    except Exception:
        database_ok = False
    last_sync = db.query(BackgroundJob).filter_by(tenant_id=user.cliente_id).order_by(BackgroundJob.created_at.desc()).first()
    connected = db.query(MarketplaceConnection).filter_by(tenant_id=user.cliente_id, is_active=True).first() is not None
    active_alerts = db.query(InternalAlert).filter_by(cliente_id=user.cliente_id, is_read=False).count()
    modules = {
        "OAuth Mercado Livre": connected,
        "Catálogo": db.query(Product).filter_by(cliente_id=user.cliente_id).count() > 0,
        "Pricing Scanner": True,
        "Questions AI": True,
        "Account Health": True,
        "Buy Box Score": True,
        "Alertas": True,
        "Billing SaaS": True,
        "Forecast": True,
        "Reconciliação Financeira": True,
        "Otimização de Título": True,
        "Análise de Portfólio": True,
        "PWA": True,
    }
    return {
        "api": "online",
        "database": "online" if database_ok else "offline",
        "environment": ENV,
        "last_sync": {"type": getattr(last_sync, "tipo", None), "status": getattr(last_sync, "status", None), "created_at": getattr(last_sync, "created_at", None)} if last_sync else None,
        "active_alerts": active_alerts,
        "modules": modules,
        "onboarding": get_onboarding_insights(db, user.cliente_id),
        "generated_at": datetime.utcnow().isoformat()+"Z",
    }


# ─────────────────────────────────────────────
# CLIENTES
# ─────────────────────────────────────────────
@app.post("/clientes", response_model=ClienteOut, tags=["clientes"])
def create_cliente(data: ClienteCreate, user = Depends(current_user), db: Session = Depends(get_db)):
    """Rota legacy protegida: criação de cliente/tenant é operação administrativa.

    O usuário demo/owner comum não pode criar novos tenants por esta rota para evitar
    bypass de isolamento multi-tenant. Em produção, onboarding deve passar por fluxo
    administrativo/billing dedicado.
    """
    if getattr(user, "role", "") not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail={"message": "Rota legacy restrita a administradores."})
    from services.cliente_service import create_cliente
    try:
        return create_cliente(db, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/clientes", response_model=List[ClienteOut], tags=["clientes"])
def list_clientes(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.cliente_service import list_clientes
    return [db.query(__import__("models.orm", fromlist=["Cliente"]).Cliente).filter_by(id=user.cliente_id).first()]


@app.get("/clientes/{cliente_id}", response_model=ClienteOut, tags=["clientes"])
def get_cliente(cliente_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    from services.cliente_service import get_cliente
    c = get_cliente(db, cliente_id)
    if not c: raise HTTPException(404, "Cliente não encontrado")
    return c


# ─────────────────────────────────────────────
# PRODUTOS
# ─────────────────────────────────────────────
@app.post("/clientes/{cliente_id}/produtos", response_model=ProductOut, tags=["produtos"])
def create_product(cliente_id: str, data: ProductCreate, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import create_product
    require_same_tenant(cliente_id, user, db)
    return create_product(db, cliente_id, data)


@app.get("/clientes/{cliente_id}/produtos", response_model=List[ProductOut], tags=["produtos"])
def list_products(cliente_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import list_products
    require_same_tenant(cliente_id, user, db)
    return list_products(db, cliente_id)


@app.get("/clientes/{cliente_id}/produtos/{product_id}", response_model=ProductOut, tags=["produtos"])
def get_product(cliente_id: str, product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    from services.product_service import get_product
    p = get_product(db, product_id, cliente_id)
    if not p: raise HTTPException(404, "Produto não encontrado")
    return p


@app.patch("/clientes/{cliente_id}/produtos/{product_id}", tags=["produtos"])
def update_product(cliente_id: str, product_id: str, data: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    from services.product_service import update_product
    p = update_product(db, product_id, cliente_id, data)
    if not p: raise HTTPException(404, "Produto não encontrado")
    return p


@app.delete("/clientes/{cliente_id}/produtos/{product_id}", tags=["produtos"])
def delete_product(cliente_id: str, product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    from services.product_service import delete_product
    ok = delete_product(db, product_id, cliente_id)
    if not ok: raise HTTPException(404, "Produto não encontrado")
    return {"status": "deleted"}


# ─────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────
@app.post("/clientes/{cliente_id}/scraping", response_model=ScrapingResult, tags=["scraping"])
def run_scraping(
    cliente_id: str, req: ScrapingRequest,
    background_tasks: BackgroundTasks,
    user = Depends(current_user),
    db: Session = Depends(get_db),
):
    from services.scraping_service import run_scraping
    require_same_tenant(cliente_id, user, db)
    result = run_scraping(db, req.product_id, cliente_id,
                          req.marketplace, req.query, req.max_pages)
    return ScrapingResult(**result)


@app.get("/clientes/{cliente_id}/scraping/{product_id}/stats", tags=["scraping"])
def competitor_stats(cliente_id: str, product_id: str,
                     marketplace: str = "mercadolivre",
                     user = Depends(current_user),
                     db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    from scrapers.ml_scraper import get_competitor_stats
    return get_competitor_stats(db, product_id, marketplace)


# ─────────────────────────────────────────────
# PRICING
# ─────────────────────────────────────────────
@app.post("/clientes/{cliente_id}/pricing", tags=["pricing"])
def calculate_price(cliente_id: str, req: PricingRequest, user = Depends(current_user), db: Session = Depends(get_db)):
    from pricing.engine import calculate_price
    require_same_tenant(cliente_id, user, db)
    try:
        result = calculate_price(db, req.product_id, cliente_id,
                                  req.marketplace, req.modo, req.markup_pct)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/clientes/{cliente_id}/pricing/batch", tags=["pricing"])
def batch_price(cliente_id: str, marketplace: str = "mercadolivre",
                modo: str = "rule_based", user = Depends(current_user), db: Session = Depends(get_db)):
    from pricing.engine import batch_price
    require_same_tenant(cliente_id, user, db)
    return batch_price(db, cliente_id, marketplace, modo)


# ─────────────────────────────────────────────
# PUBLICAÇÃO
# ─────────────────────────────────────────────
@app.post("/clientes/{cliente_id}/publish", response_model=PublishResponse, tags=["publish"])
def publish_product(cliente_id: str, req: PublishRequest, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.publish_service import publish_product
    require_same_tenant(cliente_id, user, db)
    result = publish_product(db, req.product_id, cliente_id,
                              req.marketplace, req.dry_run, req.listing_type)
    return PublishResponse(**{
        "listing_id":     result.get("listing_id"),
        "marketplace_id": result.get("marketplace_id"),
        "status":         result.get("status", ""),
        "preco":          result.get("preco"),
        "url":            result.get("url"),
        "dry_run":        req.dry_run,
        "erro":           result.get("erro"),
    })



# ─────────────────────────────────────────────
# PATCH 13/15 — OTIMIZAÇÃO DE TÍTULO COM IA
# ─────────────────────────────────────────────
@app.get("/title-optimizer/products/{product_id}", tags=["title-optimizer"])
def title_optimizer_product(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.title_optimization_service import TitleOptimizationError, optimize_product_title
    try:
        return optimize_product_title(db, user.cliente_id, product_id)
    except TitleOptimizationError as exc:
        raise HTTPException(status_code=404 if "não encontrado" in str(exc).lower() else 400, detail={"message": str(exc)})


@app.get("/title-optimizer/analyze", tags=["title-optimizer"])
def title_optimizer_analyze(q: str = Query(..., min_length=3), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.title_optimization_service import TitleOptimizationError, analyze_manual_query
    try:
        return analyze_manual_query(db, user.cliente_id, q)
    except TitleOptimizationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})


# ─────────────────────────────────────────────
# TÍTULO / IA
# ─────────────────────────────────────────────
@app.post("/ai/optimize-title", tags=["ai"])
def optimize_title(request: Request, titulo: str, marketplace: str = "mercadolivre",
                   categoria: str = "default", marca: str = ""):
    enforce_public_rate_limit(request)
    from ai.title_optimizer import optimize_title
    return optimize_title(titulo, marketplace, categoria, marca)


# ─────────────────────────────────────────────
# ML
# ─────────────────────────────────────────────
@app.post("/ml/train", response_model=MLTrainResponse, tags=["ml"])
def train_model(req: MLTrainRequest, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.ml_service import train_model
    try:
        result = train_model(db, req.marketplace, force=req.force, tenant_id=user.cliente_id)
        return MLTrainResponse(
            run_id=result["run_id"], status=result["status"],
            mae=result.get("mae"), r2=result.get("r2"),
            n_samples=result["n_samples"], model_path=result["model_path"],
        )
    except Exception as exc:
        raise HTTPException(500, detail={"message": "Não foi possível treinar o modelo agora."}) from exc


@app.get("/ml/predict/{product_id}", tags=["ml"])
def predict(product_id: str, cliente_id: str,
            marketplace: str = "mercadolivre", user = Depends(current_user), db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    from services.ml_service import predict_for_product
    try:
        return predict_for_product(db, product_id, cliente_id, marketplace)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@app.get("/dashboard/market-ready", tags=["dashboard"])
def dashboard_market_ready_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import dashboard_market_ready
    return dashboard_market_ready(db, user.cliente_id)


@app.get("/app/dashboard/market-ready", tags=["dashboard"])
def dashboard_market_ready_safe(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import dashboard_market_ready
    return dashboard_market_ready(db, user.cliente_id)

@app.get("/dashboard/{cliente_id}", tags=["dashboard"])
def dashboard(cliente_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    return build_dashboard_response(db, cliente_id)

def build_dashboard_response(db: Session, cliente_id: str):
    from models.orm import Product, MarketplaceListing, PricingResult, BackgroundJob, PublishLog
    from sqlalchemy import func
    total_prods = db.query(Product).filter_by(cliente_id=cliente_id, ativo=True).count()
    total_active = db.query(MarketplaceListing).filter_by(cliente_id=cliente_id, status="ativo").count()
    avg_margem = db.query(func.avg(PricingResult.margem_real_pct)).filter_by(cliente_id=cliente_id).scalar()
    baixo_estoque = db.query(Product).filter(Product.cliente_id == cliente_id, Product.ativo == True, Product.estoque <= Product.estoque_minimo).count()
    latest_pricing = db.query(PricingResult).filter_by(cliente_id=cliente_id).order_by(PricingResult.criado_em.desc()).limit(8).all()
    products = db.query(Product).filter_by(cliente_id=cliente_id, ativo=True).order_by(Product.atualizado_em.desc()).limit(8).all()
    jobs = db.query(BackgroundJob).filter_by(tenant_id=cliente_id).order_by(BackgroundJob.created_at.desc()).limit(6).all()
    publishes = db.query(PublishLog).filter_by(cliente_id=cliente_id).order_by(PublishLog.criado_em.desc()).limit(6).all()
    series = []
    for row in reversed(latest_pricing):
        series.append({
            "label": row.criado_em.strftime("%d/%m"),
            "margem": round(float(row.margem_real_pct or 0) * 100, 2),
            "preco": float(row.preco_sugerido or 0),
        })
    return {
        "total_produtos": total_prods,
        "anuncios_ativos": total_active,
        "margem_media_pct": round(float(avg_margem or 0) * 100, 2),
        "oportunidades_repricing": len(latest_pricing),
        "baixo_estoque": baixo_estoque,
        "series_margem": series,
        "produtos_prioritarios": [{"id": p.id, "sku": p.sku, "titulo": p.titulo, "estoque": p.estoque, "preco_base": float(p.preco_base or 0), "custo": float(p.custo or 0)} for p in products],
        "jobs_recentes": [{"id": j.id, "tipo": j.job_type, "status": j.status, "label": j.progress_label, "progress": j.progress_current, "created_at": j.created_at} for j in jobs],
        "publicacoes_recentes": [{"id": p.id, "product_id": p.product_id, "status": p.status, "marketplace": p.marketplace, "criado_em": p.criado_em} for p in publishes],
        "empty": total_prods == 0,
    }


# ─────────────────────────────────────────────
# AUTH ML — callback estático antes da rota dinâmica
# ─────────────────────────────────────────────
@app.get("/auth/ml/callback", tags=["auth"])
def ml_callback(code: str, state: str, db: Session = Depends(get_db)):
    from integrations.mercadolivre.auth import exchange_code, validate_oauth_state
    try:
        tenant_id = validate_oauth_state(state, db)
        exchange_code(db, tenant_id, code)
        return RedirectResponse(url=f"{FRONTEND_URL.rstrip('/')}/app/marketplace?ml_connected=1")
    except Exception as exc:
        raise HTTPException(400, detail={"message": "Não foi possível concluir a conexão com o marketplace."}) from exc


@app.get("/auth/ml/{cliente_id}", tags=["auth"])
def ml_auth_link(cliente_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    require_same_tenant(cliente_id, user, db)
    from integrations.mercadolivre.auth import generate_auth_link
    return {"link": generate_auth_link(cliente_id, db)}


@app.get("/marketplace/connect-url", tags=["saas-marketplace"])
def marketplace_connect_url(user = Depends(current_user), db: Session = Depends(get_db)):
    from integrations.mercadolivre.auth import generate_auth_link
    return {"link": generate_auth_link(user.cliente_id, db)}



# ─────────────────────────────────────────────
# APP ROUTES PROTEGIDAS / FRONTEND REAL
# ─────────────────────────────────────────────
@app.get("/products", response_model=List[ProductOut], tags=["app-products"])
def products_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import list_products
    return list_products(db, user.cliente_id)

@app.post("/products", response_model=ProductOut, tags=["app-products"])
def products_create_private(data: ProductCreate, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import create_product
    return create_product(db, user.cliente_id, data)

@app.get("/products/{product_id}", response_model=ProductOut, tags=["app-products"])
def products_get_private(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import get_product
    p = get_product(db, product_id, user.cliente_id)
    if not p:
        raise HTTPException(404, detail={"message": "Produto não encontrado."})
    return p

@app.put("/products/{product_id}", response_model=ProductOut, tags=["app-products"])
def products_update_private(product_id: str, data: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import update_product
    field_map = {"title":"titulo", "description":"descricao", "category":"categoria_nome", "brand":"marca", "cost_price":"custo", "base_price":"preco_base", "min_margin":"margem_minima", "stock_quantity":"estoque"}
    payload = {field_map.get(k, k): v for k, v in data.items()}
    p = update_product(db, product_id, user.cliente_id, payload)
    if not p:
        raise HTTPException(404, detail={"message": "Produto não encontrado."})
    return p

@app.delete("/products/{product_id}", tags=["app-products"])
def products_delete_private(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import delete_product
    if not delete_product(db, product_id, user.cliente_id):
        raise HTTPException(404, detail={"message": "Produto não encontrado."})
    return {"status": "deleted"}

@app.get("/products/{product_id}/detail", tags=["app-products"])
def product_detail_private(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_service import get_product
    from scrapers.ml_scraper import get_competitor_stats
    from models.orm import PricingResult, CompetitorOffer, CompetitorSearch, PublishLog
    p = get_product(db, product_id, user.cliente_id)
    if not p:
        raise HTTPException(404, detail={"message": "Produto não encontrado."})
    pricing = db.query(PricingResult).filter_by(product_id=product_id, cliente_id=user.cliente_id).order_by(PricingResult.criado_em.desc()).first()
    offers = db.query(CompetitorOffer).join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id).filter(CompetitorSearch.product_id == product_id, CompetitorOffer.cliente_id == user.cliente_id).order_by(CompetitorOffer.criado_em.desc()).limit(20).all()
    publishes = db.query(PublishLog).filter_by(product_id=product_id, cliente_id=user.cliente_id).order_by(PublishLog.criado_em.desc()).limit(10).all()
    return {
        "product": ProductOut.model_validate(p).model_dump(mode="json"),
        "pricing_current": None if not pricing else {"preco_sugerido": float(pricing.preco_sugerido or 0), "lucro_estimado": float(pricing.lucro_estimado or 0), "margem_real_pct": float(pricing.margem_real_pct or 0), "score_competitividade": float(pricing.score_competitividade or 0), "criado_em": pricing.criado_em},
        "competitor_stats": get_competitor_stats(db, product_id),
        "competitors": [{"id": o.id, "titulo": o.titulo, "preco": float(o.preco or 0), "vendedor": o.vendedor, "reputacao": o.reputacao, "frete_gratis": o.frete_gratis, "vendas": o.vendas, "criado_em": o.criado_em} for o in offers],
        "publish_history": [{"id": x.id, "status": x.status, "erro": x.erro, "criado_em": x.criado_em} for x in publishes],
    }

@app.post("/competition/run", response_model=ScrapingResult, tags=["competition"])
def competition_run(req: ScrapingRequest, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.scraping_service import run_scraping
    return ScrapingResult(**run_scraping(db, req.product_id, user.cliente_id, req.marketplace, req.query, req.max_pages))

@app.get("/competition", tags=["competition"])
def competition_list(product_id: Optional[str] = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from models.orm import CompetitorOffer, CompetitorSearch
    q = db.query(CompetitorOffer).join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id).filter(CompetitorOffer.cliente_id == user.cliente_id)
    if product_id:
        q = q.filter(CompetitorSearch.product_id == product_id)
    offers = q.order_by(CompetitorOffer.criado_em.desc()).limit(100).all()
    prices = [float(o.preco or 0) for o in offers if o.preco]
    return {"summary": {"count": len(offers), "preco_min": min(prices) if prices else None, "preco_medio": round(sum(prices)/len(prices),2) if prices else None, "preco_max": max(prices) if prices else None}, "items": [{"id": o.id, "titulo": o.titulo, "preco": float(o.preco or 0), "vendedor": o.vendedor, "reputacao": o.reputacao, "frete_gratis": o.frete_gratis, "vendas": o.vendas, "criado_em": o.criado_em} for o in offers]}



@app.get("/pricing/market-scan", tags=["pricing-public"])
def pricing_market_scan(
    request: Request,
    q: str = Query(..., min_length=3, max_length=120),
    cost: float | None = Query(None, ge=0),
    user = Depends(optional_current_user),
    db: Session = Depends(get_db),
):
    """Scanner público/freemium de precificação Mercado Livre.

Sem login obrigatório. Quando o request estiver autenticado, registra evento
operacional leve para rastrear uso de aquisição/monitoramento.
    """
    from services.pricing_intelligence_service import PricingScanError, market_scan
    enforce_public_rate_limit(request)
    try:
        result = market_scan(q, cost)
        if user is not None:
            try:
                from models.orm import OperationalEvent
                db.add(OperationalEvent(
                    tenant_id=user.cliente_id,
                    event_type="pricing_market_scan",
                    category="pricing_scanner",
                    severity="info",
                    title="Pricing Scanner executado",
                    description=f"Consulta pública analisada: {result.get('query')} · {result.get('analyzed_count')} anúncios.",
                ))
                db.commit()
            except Exception:
                db.rollback()
        return result
    except PricingScanError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})
    except Exception:
        raise HTTPException(status_code=502, detail={"message": "Não foi possível consultar o Mercado Livre agora."})


@app.post("/pricing/calculate", tags=["pricing-app"])
def pricing_calculate_private(req: PricingRequest, user = Depends(current_user), db: Session = Depends(get_db)):
    from pricing.engine import calculate_price
    return calculate_price(db, req.product_id, user.cliente_id, req.marketplace, req.modo, req.markup_pct)

@app.get("/pricing/history", tags=["pricing-app"])
def pricing_history_private(product_id: Optional[str] = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from models.orm import PricingResult
    q = db.query(PricingResult).filter_by(cliente_id=user.cliente_id)
    if product_id:
        q = q.filter_by(product_id=product_id)
    rows = q.order_by(PricingResult.criado_em.desc()).limit(100).all()
    return [{"id": r.id, "product_id": r.product_id, "preco_sugerido": float(r.preco_sugerido or 0), "lucro_estimado": float(r.lucro_estimado or 0), "margem_real_pct": float(r.margem_real_pct or 0), "score_competitividade": float(r.score_competitividade or 0), "criado_em": r.criado_em} for r in rows]

@app.post("/publish/dry-run", response_model=PublishResponse, tags=["publish-app"])
def publish_dry_run_private(req: PublishRequest, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.publish_service import publish_product
    return PublishResponse(**publish_product(db, req.product_id, user.cliente_id, req.marketplace, True, req.listing_type))

@app.get("/publish/history", tags=["publish-app"])
def publish_history_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from models.orm import PublishLog
    rows = db.query(PublishLog).filter_by(cliente_id=user.cliente_id).order_by(PublishLog.criado_em.desc()).limit(100).all()
    return [{"id": r.id, "product_id": r.product_id, "marketplace": r.marketplace, "status": r.status, "payload": r.payload, "resposta": r.resposta, "erro": r.erro, "duracao_ms": r.duracao_ms, "criado_em": r.criado_em} for r in rows]

@app.post("/ml/train/app", response_model=MLTrainResponse, tags=["ml-app"])
def train_model_private(req: MLTrainRequest, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.ml_service import train_model
    result = train_model(db, req.marketplace, force=req.force, tenant_id=user.cliente_id)
    return MLTrainResponse(run_id=result["run_id"], status=result["status"], mae=result.get("mae"), r2=result.get("r2"), n_samples=result["n_samples"], model_path=result["model_path"])

# ─────────────────────────────────────────────
# MARKET READY — INSIGHTS, CENÁRIOS, PREVIEW E SETTINGS
# ─────────────────────────────────────────────
@app.get("/insights", tags=["insights"])
def insights_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import generate_insights
    return {"items": generate_insights(db, user.cliente_id)}

@app.get("/pricing/scenarios/{product_id}", tags=["pricing-app"])
def pricing_scenarios_private(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import pricing_scenarios
    try:
        return pricing_scenarios(db, user.cliente_id, product_id)
    except ValueError as exc:
        raise HTTPException(404, detail={"message": str(exc)})

@app.get("/competition/analytics", tags=["competition"])
def competition_analytics_private(product_id: Optional[str] = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import competitor_analytics
    return competitor_analytics(db, user.cliente_id, product_id)

@app.get("/publish/preview/{product_id}", tags=["publish-app"])
def publish_preview_private(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import publish_preview
    try:
        return publish_preview(db, user.cliente_id, product_id)
    except ValueError as exc:
        raise HTTPException(404, detail={"message": str(exc)})


@app.get("/intelligence-center", tags=["premium-intelligence"])
def intelligence_center_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_intelligence_service import build_intelligence_center
    return build_intelligence_center(db, user.cliente_id)

@app.get("/operational-score", tags=["premium-intelligence"])
def operational_score_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_intelligence_service import build_operational_score
    return build_operational_score(db, user.cliente_id)

@app.get("/health-monitoring", tags=["premium-intelligence"])
def health_monitoring_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_intelligence_service import build_health_monitoring
    return build_health_monitoring(db, user.cliente_id)

@app.post("/impact-simulator", tags=["premium-intelligence"])
def impact_simulator_private(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.product_intelligence_service import simulate_impact
    return simulate_impact(payload)



@app.get("/ai-copilot", tags=["operational-intelligence"])
def ai_copilot_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import build_ai_copilot
    return build_ai_copilot(db, user.cliente_id)

@app.get("/operational-timeline", tags=["operational-intelligence"])
def operational_timeline_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import build_operational_timeline
    return build_operational_timeline(db, user.cliente_id)

@app.get("/smart-alerts", tags=["operational-intelligence"])
def smart_alerts_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import build_smart_alerts
    return build_smart_alerts(db, user.cliente_id)

@app.get("/recommended-actions", tags=["operational-intelligence"])
def recommended_actions_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import build_recommended_actions
    return build_recommended_actions(db, user.cliente_id)

@app.get("/operational-maturity-score", tags=["operational-intelligence"])
def operational_maturity_score_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import build_maturity_score
    return build_maturity_score(db, user.cliente_id)

@app.get("/executive-mode", tags=["operational-intelligence"])
def executive_mode_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import build_executive_mode
    return build_executive_mode(db, user.cliente_id)

@app.get("/market-radar", tags=["operational-intelligence"])
def market_radar_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import build_market_radar
    return build_market_radar(db, user.cliente_id)

@app.post("/profit-simulator/advanced", tags=["operational-intelligence"])
def profit_simulator_advanced_private(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.copilot_service import simulate_advanced_profit
    return simulate_advanced_profit(payload)

@app.get("/settings", tags=["settings"])
def settings_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import get_settings
    return get_settings(db, user)

@app.put("/settings", tags=["settings"])
def settings_save_private(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.insight_service import save_settings
    try:
        return save_settings(db, user, payload)
    except ValueError as exc:
        raise HTTPException(404, detail={"message": str(exc)})



# ─────────────────────────────────────────────
# SAAS COMMERCIAL PATCH
# ─────────────────────────────────────────────
@app.get("/onboarding", tags=["saas-onboarding"])
def onboarding_get(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import get_onboarding
    return get_onboarding(db, user)

@app.put("/onboarding", tags=["saas-onboarding"])
def onboarding_save(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import save_onboarding
    return save_onboarding(db, user, payload)

@app.get("/plans", tags=["saas-plans"])
def plans_get(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import list_plans
    return list_plans(db, user)

@app.put("/plans/current", tags=["saas-plans"])
def plans_update(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import update_plan
    try:
        return update_plan(db, user, payload.get("plan_key", "starter"))
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400 if isinstance(exc, ValueError) else 403, detail={"message": str(exc)})

@app.get("/users", tags=["saas-users"])
def users_get(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import list_users
    return list_users(db, user)


@app.get("/invites/{token}", tags=["auth"])
def invite_details(token: str, db: Session = Depends(get_db)):
    from services.saas_service import get_invite
    try:
        return get_invite(db, token)
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)}) from exc


@app.post("/invites/{token}/accept", tags=["auth"])
def invite_accept(token: str, payload: dict, db: Session = Depends(get_db)):
    from services.saas_service import accept_invite
    try:
        return accept_invite(db, token, payload or {})
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"message": str(exc)}) from exc

@app.post("/users/invite", tags=["saas-users"])
def users_invite(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import invite_user
    try:
        return invite_user(db, user, payload)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400 if isinstance(exc, ValueError) else 403, detail={"message": str(exc)})

@app.put("/users/{target_id}/role", tags=["saas-users"])
def users_role(target_id: str, payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import update_user_role
    try:
        return update_user_role(db, user, target_id, payload.get("role", "viewer"))
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)})
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400 if isinstance(exc, ValueError) else 403, detail={"message": str(exc)})

@app.delete("/users/{target_id}", tags=["saas-users"])
def users_delete(target_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import remove_user
    try:
        return remove_user(db, user, target_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)})
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400 if isinstance(exc, ValueError) else 403, detail={"message": str(exc)})

@app.get("/alerts", tags=["saas-alerts"])
def alerts_get(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import list_alerts
    return list_alerts(db, user)

@app.post("/alerts/{alert_id}/read", tags=["saas-alerts"])
def alerts_read(alert_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import mark_alert_read
    try:
        return mark_alert_read(db, user, alert_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)})

@app.get("/marketplace/status", tags=["saas-marketplace"])
def marketplace_status_get(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.saas_service import marketplace_status
    return marketplace_status(db, user)


@app.post("/marketplace/sync", tags=["saas-marketplace"])
def marketplace_sync(limit: int = Query(50, ge=1, le=50), max_items: int | None = Query(None, ge=1), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.ml_sync_service import MLSyncServiceError, sync_catalog
    from services.billing_service import get_billing_status
    from services.plan_limits_service import check_limits
    billing = get_billing_status(db, user.cliente_id)
    limit_check = check_limits(db, user.cliente_id, billing.get("plan", {}).get("code"), action="catalog_sync")
    if not limit_check.allowed:
        raise HTTPException(status_code=402, detail={"message": limit_check.reason or "Limite do plano atingido.", "billing": billing})
    try:
        result = sync_catalog(db, user.cliente_id, limit=limit, max_items=max_items)
        if limit_check.warning and isinstance(result, dict):
            result["billing_warning"] = limit_check.reason
        return result
    except MLSyncServiceError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})




@app.get("/marketplace/summary", tags=["saas-marketplace"])
def marketplace_summary(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.marketplace_dashboard_service import build_marketplace_summary
    return build_marketplace_summary(db, user.cliente_id)


@app.get("/marketplace/intelligence", tags=["saas-marketplace"])
def marketplace_intelligence(severity: str | None = None, type: str | None = None, product_id: str | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import generate_marketplace_intelligence
    return generate_marketplace_intelligence(db, user.cliente_id, severity=severity, type=type, product_id=product_id)

@app.get("/marketplace/products", tags=["saas-marketplace"])
def marketplace_products(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), status: str | None = None, search: str | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.ml_sync_service import list_marketplace_products
    return list_marketplace_products(db, user.cliente_id, page=page, page_size=page_size, status=status, search=search)

@app.post("/marketplace/connect-demo", tags=["saas-marketplace"])
def marketplace_connect_demo(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    raise HTTPException(status_code=410, detail={"message": "Conexão demo removida neste patch. Use o OAuth real do Mercado Livre."})






# ─────────────────────────────────────────────
# ALERTAS TELEGRAM/WHATSAPP — PATCH 9/10
# ─────────────────────────────────────────────
@app.get("/alerts/settings", tags=["alerts-operational"])
def alerts_settings_get(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.alerts_service import get_alert_settings
    return get_alert_settings(db, user.cliente_id)


@app.post("/alerts/settings", tags=["alerts-operational"])
def alerts_settings_post(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.alerts_service import update_alert_settings
    return update_alert_settings(db, user.cliente_id, payload or {})


@app.get("/alerts/history", tags=["alerts-operational"])
def alerts_history_get(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.alerts_service import list_alert_history
    return list_alert_history(db, user.cliente_id, page=page, page_size=page_size)


@app.post("/alerts/test", tags=["alerts-operational"])
def alerts_test_post(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.alerts_service import send_test_alert
    return send_test_alert(db, user.cliente_id)


# ─────────────────────────────────────────────
# ACCOUNT HEALTH — Saúde da Conta ML em Tempo Real
# ─────────────────────────────────────────────
@app.get("/account/health", tags=["account-health"])
def account_health(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.account_health_service import AccountHealthServiceError, get_account_health
    try:
        return get_account_health(db, user.cliente_id)
    except AccountHealthServiceError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})


# ─────────────────────────────────────────────
# BUY BOX PROBABILITY SCORE — Score interno SellerOS
# ─────────────────────────────────────────────
@app.get("/products/{product_id}/buybox-score", tags=["buybox-score"])
def product_buybox_score(product_id: str, refresh_market: bool = Query(True), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.buybox_service import BuyBoxServiceError, get_product_buybox_score
    try:
        return get_product_buybox_score(db, user.cliente_id, product_id, refresh_market=refresh_market)
    except BuyBoxServiceError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)})


@app.get("/buybox/overview", tags=["buybox-score"])
def buybox_overview_get(limit: int = Query(30, ge=1, le=50), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.buybox_service import buybox_overview
    return buybox_overview(db, user.cliente_id, limit=limit)

# ─────────────────────────────────────────────
# QUESTIONS AI ASSISTANT — Mercado Livre perguntas abertas
# ─────────────────────────────────────────────
@app.get("/questions/pending", tags=["questions-ai"])
def questions_pending(limit: int = Query(30, ge=1, le=50), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.questions_service import QuestionsServiceError, fetch_pending_questions
    try:
        return fetch_pending_questions(db, user.cliente_id, limit=limit)
    except QuestionsServiceError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})


@app.post("/questions/{question_id}/suggest", tags=["questions-ai"])
def questions_suggest(question_id: str, payload: dict | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.questions_service import QuestionsServiceError, suggest_answer
    try:
        return suggest_answer(db, user.cliente_id, question_id, custom_context=(payload or {}).get("custom_context"))
    except QuestionsServiceError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})


@app.post("/questions/{question_id}/answer", tags=["questions-ai"])
def questions_answer(question_id: str, payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.questions_service import QuestionsServiceError, send_approved_answer
    try:
        return send_approved_answer(db, user.cliente_id, question_id, text=(payload or {}).get("text", ""))
    except QuestionsServiceError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})



# ─────────────────────────────────────────────
# ACTION INTELLIGENCE PREMIUM PATCH
# ─────────────────────────────────────────────
@app.get("/ai-copilot/context", tags=["action-intelligence"])
def ai_copilot_context_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import enrich_copilot
    return enrich_copilot(db, user.cliente_id)

@app.get("/action-center", tags=["action-intelligence"])
def action_center_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import build_action_center
    return build_action_center(db, user.cliente_id)

@app.post("/action-center/{action_id}/apply", tags=["action-intelligence"])
def action_center_apply(action_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import update_action_status
    return update_action_status(db, user.cliente_id, action_id, "applied")

@app.post("/action-center/{action_id}/ignore", tags=["action-intelligence"])
def action_center_ignore(action_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import update_action_status
    return update_action_status(db, user.cliente_id, action_id, "ignored")

@app.post("/action-center/{action_id}/resolve", tags=["action-intelligence"])
def action_center_resolve(action_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import update_action_status
    return update_action_status(db, user.cliente_id, action_id, "resolved")

@app.get("/market-war-room", tags=["action-intelligence"])
def market_war_room_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import build_market_war_room
    return build_market_war_room(db, user.cliente_id)


@app.post("/market-war-room/{product_id}/simulate-response", tags=["action-intelligence"])
def market_war_room_simulate_response(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import war_room_simulate_response
    try:
        return war_room_simulate_response(db, user.cliente_id, product_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)}) from exc


@app.post("/market-war-room/{product_id}/recalculate-pricing", tags=["action-intelligence"])
def market_war_room_recalculate_pricing(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import war_room_recalculate_pricing
    try:
        return war_room_recalculate_pricing(db, user.cliente_id, product_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(400, detail={"message": str(exc)}) from exc


@app.post("/market-war-room/{product_id}/create-action", tags=["action-intelligence"])
def market_war_room_create_action(product_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import war_room_create_action
    try:
        return war_room_create_action(db, user.cliente_id, product_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)}) from exc

@app.get("/operational-timeline/actions", tags=["action-intelligence"])
def operational_timeline_actions_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import build_action_timeline
    return build_action_timeline(db, user.cliente_id)

@app.get("/alerts/lifecycle", tags=["action-intelligence"])
def alerts_lifecycle_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import build_alerts_lifecycle
    return build_alerts_lifecycle(db, user.cliente_id)

@app.post("/alerts/{alert_id}/status", tags=["action-intelligence"])
def alerts_status_update(alert_id: str, payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import update_alert_status
    try:
        return update_alert_status(db, user.cliente_id, alert_id, payload.get("status", "read"))
    except ValueError as exc:
        raise HTTPException(400, detail={"message": str(exc)})

@app.get("/operational-score/explainable", tags=["action-intelligence"])
def operational_score_explainable_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import build_explainable_score
    return build_explainable_score(db, user.cliente_id)

@app.get("/executive-summary", tags=["action-intelligence"])
def executive_summary_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import build_executive_summary
    return build_executive_summary(db, user.cliente_id)


@app.get("/executive-summary/export", tags=["action-intelligence"])
def executive_summary_export_private(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import export_executive_summary
    return export_executive_summary(db, user.cliente_id)

@app.get("/profit-simulations", tags=["action-intelligence"])
def profit_simulations_get(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import list_profit_simulations
    return list_profit_simulations(db, user.cliente_id)

@app.post("/profit-simulations", tags=["action-intelligence"])
def profit_simulations_post(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import save_profit_simulation
    return save_profit_simulation(db, user.cliente_id, payload, getattr(user, "email", None))

@app.post("/profit-simulations/{simulation_id}/create-action", tags=["action-intelligence"])
def profit_simulation_create_action(simulation_id: str, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.action_intelligence_service import create_action_from_simulation
    try:
        return create_action_from_simulation(db, user.cliente_id, simulation_id)
    except LookupError as exc:
        raise HTTPException(404, detail={"message": str(exc)})


# ─────────────────────────────────────────────
# BILLING / SAAS MONETIZATION — PATCH 10/10
# ─────────────────────────────────────────────
@app.get("/billing/plans", tags=["billing"])
def billing_plans():
    from services.billing_service import get_plans
    return get_plans()


@app.get("/billing/status", tags=["billing"])
def billing_status(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.billing_service import get_billing_status
    return get_billing_status(db, user.cliente_id)


@app.post("/billing/subscribe", tags=["billing"])
def billing_subscribe(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.billing_service import subscribe
    try:
        return subscribe(db, user.cliente_id, payload.get("plan"), payload.get("customer") or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)})


@app.post("/billing/cancel", tags=["billing"])
def billing_cancel(user = Depends(current_user), db: Session = Depends(get_db)):
    from services.billing_service import cancel_subscription
    try:
        return cancel_subscription(db, user.cliente_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)})
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)})


@app.post("/billing/webhook", tags=["billing"])
async def billing_webhook(request: Request, db: Session = Depends(get_db)):
    from services.billing_service import process_webhook
    raw = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Payload JSON inválido."})
    signature = request.headers.get("x-hub-signature-256") or request.headers.get("x-pagarme-signature") or request.headers.get("signature")
    try:
        return process_webhook(db, payload, raw_body=raw, signature=signature)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail={"message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})


# ─────────────────────────────────────────────
# DEMAND FORECAST — PATCH 11/15
# ─────────────────────────────────────────────
@app.get("/forecast/overview", tags=["demand-forecast"])
def demand_forecast_overview(limit: int = Query(80, ge=1, le=150), lead_time_days: int = Query(7, ge=1, le=90), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.demand_forecast_service import forecast_overview
    return forecast_overview(db, user.cliente_id, limit=limit, lead_time_days=lead_time_days)


@app.post("/forecast/refresh", tags=["demand-forecast"])
def demand_forecast_refresh(limit: int = Query(80, ge=1, le=150), lead_time_days: int = Query(7, ge=1, le=90), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.demand_forecast_service import refresh_forecast_snapshots
    return refresh_forecast_snapshots(db, user.cliente_id, limit=limit, lead_time_days=lead_time_days)


@app.get("/forecast/products/{product_id}", tags=["demand-forecast"])
def demand_forecast_product(product_id: str, lead_time_days: int = Query(7, ge=1, le=90), user = Depends(current_user), db: Session = Depends(get_db)):
    from services.demand_forecast_service import DemandForecastError, get_product_forecast
    try:
        return get_product_forecast(db, user.cliente_id, product_id, lead_time_days=lead_time_days)
    except DemandForecastError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)})

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _check_cliente(db: Session, cliente_id: str):
    from services.cliente_service import get_cliente
    if not get_cliente(db, cliente_id):
        raise HTTPException(404, f"Cliente {cliente_id} não encontrado")

# ─────────────────────────────────────────────
# FINANCIAL RECONCILIATION — PATCH 12/15
# ─────────────────────────────────────────────
@app.get("/finance/reconciliation", tags=["financial-reconciliation"])
def financial_reconciliation_get(start_date: str | None = None, end_date: str | None = None, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.financial_reconciliation_service import FinancialReconciliationError, build_reconciliation
    try:
        return build_reconciliation(db, user.cliente_id, start_date, end_date, persist=True)
    except FinancialReconciliationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})


@app.post("/finance/reconciliation/manual-bank-received", tags=["financial-reconciliation"])
def financial_reconciliation_manual_bank(payload: dict, user = Depends(current_user), db: Session = Depends(get_db)):
    from services.financial_reconciliation_service import FinancialReconciliationError, save_manual_bank_received
    try:
        return save_manual_bank_received(db, user.cliente_id, payload or {})
    except FinancialReconciliationError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)})
