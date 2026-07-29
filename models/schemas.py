"""models/schemas.py — Pydantic schemas para validação e API."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator, model_validator
import uuid


# ─────────────────────────────────────────────
# CLIENTE
# ─────────────────────────────────────────────
class ClienteCreate(BaseModel):
    nome:  str
    email: str
    plano: str = "free"

class ClienteOut(BaseModel):
    id:    str
    nome:  str
    email: str
    plano: str
    ativo: bool
    criado_em: datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# PRODUTO
# ─────────────────────────────────────────────
class ProductCreate(BaseModel):
    sku:           str
    titulo:        str
    descricao:     Optional[str] = None
    categoria_id:  Optional[str] = None
    categoria_nome:Optional[str] = None
    custo:         float
    preco_base:    Optional[float] = None
    margem_minima: float = 0.10
    peso_kg:       Optional[float] = None
    altura_cm:     Optional[float] = None
    largura_cm:    Optional[float] = None
    comprimento_cm:Optional[float] = None
    estoque:       int = 0
    ncm:           Optional[str] = None
    gtin:          Optional[str] = None
    marca:         Optional[str] = None
    atributos:     Dict[str, Any] = {}
    tags:          List[str] = []

    @model_validator(mode="before")
    @classmethod
    def aceitar_campos_frontend(cls, data):
        if isinstance(data, dict):
            aliases = {
                "title": "titulo", "description": "descricao", "category": "categoria_nome",
                "brand": "marca", "cost_price": "custo", "base_price": "preco_base",
                "min_margin": "margem_minima", "stock_quantity": "estoque",
            }
            data = dict(data)
            for src, dst in aliases.items():
                if src in data and dst not in data:
                    data[dst] = data[src]
        return data

    @field_validator("custo")
    @classmethod
    def custo_positivo(cls, v):
        if v < 0:
            raise ValueError("Custo deve ser positivo")
        return v

class ProductOut(ProductCreate):
    id:              str
    cliente_id:      str
    titulo_otimizado: Optional[str] = None
    ativo:           bool
    criado_em:       datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# PRICING
# ─────────────────────────────────────────────
class PricingRequest(BaseModel):
    product_id:  str
    marketplace: str = "mercadolivre"
    modo:        str = "rule_based"   # rule_based | ml_assisted
    markup_pct:  Optional[float] = None

class PricingResponse(BaseModel):
    product_id:             str
    marketplace:            str
    modo:                   str
    custo:                  float
    preco_sugerido:         float
    preco_concorrencia_min: Optional[float]
    preco_concorrencia_med: Optional[float]
    lucro_estimado:         float
    margem_real_pct:        float
    score_competitividade:  float
    ml_usado:               bool
    ml_confianca:           Optional[float]
    breakdown:              Dict[str, Any]


# ─────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────
class ScrapingRequest(BaseModel):
    product_id:  str
    marketplace: str = "mercadolivre"
    query:       Optional[str] = None
    max_pages:   int = 3

class ScrapingResult(BaseModel):
    search_id:      str
    total_coletado: int
    total_novo:     int
    total_dup:      int
    preco_min:      Optional[float]
    preco_max:      Optional[float]
    preco_medio:    Optional[float]


# ─────────────────────────────────────────────
# PUBLICAÇÃO
# ─────────────────────────────────────────────
class PublishRequest(BaseModel):
    product_id:   str
    marketplace:  str = "mercadolivre"
    dry_run:      bool = False
    listing_type: str = "gold_special"

class PublishResponse(BaseModel):
    listing_id:     Optional[str] = None
    marketplace_id: Optional[str] = None
    status:         str
    preco:          Optional[float] = None
    url:            Optional[str] = None
    dry_run:        bool = False
    erro:           Optional[str] = None


# ─────────────────────────────────────────────
# ML
# ─────────────────────────────────────────────
class MLTrainRequest(BaseModel):
    marketplace: str = "mercadolivre"
    force:       bool = False

class MLTrainResponse(BaseModel):
    model_config = {"protected_namespaces": ()}  # evita warning com model_path
    run_id:      str
    status:      str
    mae:         Optional[float]
    r2:          Optional[float]
    n_samples:   int
    model_path:  str


# ─────────────────────────────────────────────
# GENERIC
# ─────────────────────────────────────────────
class StatusResponse(BaseModel):
    status:  str
    message: str
    data:    Optional[Dict[str, Any]] = None

# ─────────────────────────────────────────────
# AUTH / JOBS
# ─────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    senha: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class MeResponse(BaseModel):
    id: str
    nome: str
    email: str
    role: str
    tenant_id: str
    organization_id: str
    modo_demo: bool = True

class PrivacyRequestCreate(BaseModel):
    request_type: str
    description: Optional[str] = None

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, value: str) -> str:
        normalized = value.lower().strip()
        allowed = {"access", "correction", "deletion", "anonymization", "portability", "revocation", "review"}
        if normalized not in allowed:
            raise ValueError("Tipo de solicitação de privacidade inválido.")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        if len(clean) > 1000:
            raise ValueError("A descrição deve possuir no máximo 1000 caracteres.")
        return clean or None

class JobOut(BaseModel):
    id: str
    tenant_id: str
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    progress_label: str
    parameters_json: Dict[str, Any] | None = None
    result_json: Dict[str, Any] | None = None
    error_message: Optional[str] = None
    stdout_tail: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    model_config = {"from_attributes": True}
