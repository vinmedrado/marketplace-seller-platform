"""models/orm.py — Modelos SQLAlchemy ORM (compatível com PostgreSQL e SQLite)."""
import os
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric, Text,
    DateTime, Date, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from db.base import Base

# UUID: nativo no PostgreSQL, String(36) no SQLite
_USE_PG = os.getenv("DATABASE_URL", "sqlite://").startswith("postgresql")
if _USE_PG:
    from sqlalchemy.dialects.postgresql import UUID as _PG_UUID, JSONB as _PG_JSONB
    _UUID = lambda: _PG_UUID(as_uuid=False)
    _JSON = lambda: _PG_JSONB
else:
    _UUID = lambda: String(36)
    _JSON = lambda: JSON


def _uuid():
    return str(uuid.uuid4())


class Cliente(Base):
    __tablename__ = "clientes"
    id            = Column(_UUID(), primary_key=True, default=_uuid)
    nome          = Column(String, nullable=False)
    email         = Column(String, unique=True, nullable=False)
    plano         = Column(String, default="free")
    ativo         = Column(Boolean, default=True)
    config        = Column(_JSON(), default=dict)
    criado_em     = Column(DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    marketplace_accounts = relationship("MarketplaceAccount", back_populates="cliente", cascade="all, delete")
    marketplace_connections = relationship("MarketplaceConnection", back_populates="cliente", cascade="all, delete")
    products             = relationship("Product", back_populates="cliente", cascade="all, delete")


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    nome = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    plano = Column(String, default="demo")
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    settings = Column(_JSON(), default=dict)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    organization_id = Column(_UUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="owner")
    ativo = Column(Boolean, default=True)
    ultimo_login_em = Column(DateTime(timezone=True))
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)



class PlanSubscription(Base):
    __tablename__ = "plan_subscriptions"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan_key = Column(String, default="starter")
    status = Column(String, default="active")
    limits_json = Column(_JSON(), default=dict)
    features_json = Column(_JSON(), default=dict)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class OnboardingState(Base):
    __tablename__ = "onboarding_states"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, unique=True)
    completed = Column(Boolean, default=False)
    current_step = Column(Integer, default=1)
    data_json = Column(_JSON(), default=dict)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class InternalAlert(Base):
    __tablename__ = "internal_alerts"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    priority = Column(String, default="medium")
    title = Column(String, nullable=False)
    description = Column(Text)
    target_url = Column(String)
    is_read = Column(Boolean, default=False)
    metadata_json = Column(_JSON(), default=dict)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    lido_em = Column(DateTime(timezone=True))


class UserInvite(Base):
    __tablename__ = "user_invites"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, default="viewer")
    status = Column(String, default="pending")
    token = Column(String, default=_uuid)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))
    accepted_at = Column(DateTime(timezone=True))


class PrivacyRequest(Base):
    """Protocolo de exercício de direitos do titular."""
    __tablename__ = "privacy_requests"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(_UUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    request_type = Column(String(32), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="pending", index=True)
    description = Column(Text)
    response_note = Column(Text)
    requested_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    legal_deadline_at = Column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    user_id = Column(_UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, nullable=False, index=True)
    revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)


class MarketplaceAccount(Base):
    """Registro legado sem credenciais, preservado para compatibilidade histórica."""
    __tablename__ = "marketplace_accounts"
    __table_args__ = (UniqueConstraint("cliente_id", "marketplace"),)
    id            = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id    = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"))
    marketplace   = Column(String, nullable=False)
    user_id       = Column(String)
    seller_id     = Column(String)
    expires_at    = Column(DateTime(timezone=True))
    ativo         = Column(Boolean, default=True)
    metadata_     = Column("metadata", JSON, default=dict)
    criado_em     = Column(DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = relationship("Cliente", back_populates="marketplace_accounts")


class MarketplaceConnection(Base):
    """Conexão real OAuth de marketplace por tenant.

    Mantém tokens SEMPRE criptografados. A tabela antiga marketplace_accounts fica
    preservada para compatibilidade de módulos existentes.
    """
    __tablename__ = "marketplace_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "marketplace"),)

    id                      = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id               = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    marketplace             = Column(String, nullable=False, default="mercadolivre")
    seller_id               = Column(String, index=True)
    nickname                = Column(String)
    country_id              = Column(String)
    access_token_encrypted  = Column(Text)
    refresh_token_encrypted = Column(Text)
    token_expires_at        = Column(DateTime(timezone=True))
    connected_at            = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at              = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active               = Column(Boolean, default=True, nullable=False)
    account_metadata        = Column(_JSON(), default=dict)

    cliente = relationship("Cliente", back_populates="marketplace_connections")


class OAuthState(Base):
    """Nonce OAuth de uso único; armazena somente o hash do state enviado."""
    __tablename__ = "oauth_states"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    state_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class QuestionsCache(Base):
    """Cache/auditoria de perguntas Mercado Livre por tenant.

    Guarda somente dados operacionais e sugestão revisável; tokens nunca são
    persistidos aqui.
    """
    __tablename__ = "questions_cache"
    __table_args__ = (UniqueConstraint("tenant_id", "question_id"),)

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    marketplace_connection_id = Column(_UUID(), ForeignKey("marketplace_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    question_id = Column(String, nullable=False, index=True)
    item_id = Column(String, index=True)
    question_text = Column(Text, nullable=False)
    status = Column(String, default="UNANSWERED", index=True)
    suggested_answer = Column(Text)
    ai_provider = Column(String)
    confidence = Column(Numeric(5, 4), default=0)
    needs_review = Column(Boolean, default=True)
    answered_at = Column(DateTime(timezone=True))
    raw_payload_json = Column(_JSON(), default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AccountHealthSnapshot(Base):
    """Histórico de saúde operacional da conta Mercado Livre por tenant.

    O score é interno SellerOS e não representa score oficial do Mercado Livre.
    Métricas indisponíveis pela API permanecem nulas para evitar inferências falsas.
    """
    __tablename__ = "account_health_snapshots"

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    marketplace_connection_id = Column(_UUID(), ForeignKey("marketplace_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    score = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    reputation_level = Column(String)
    cancellations_rate = Column(Numeric(8, 6))
    claims_rate = Column(Numeric(8, 6))
    delayed_rate = Column(Numeric(8, 6))
    active_products = Column(Integer, default=0)
    paused_products = Column(Integer, default=0)
    poor_health_products = Column(Integer, default=0)
    raw_payload_json = Column(_JSON(), default=dict)
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class BuyBoxScoreSnapshot(Base):
    """Histórico do score interno SellerOS de probabilidade de Buy Box.

    Não representa métrica oficial Mercado Livre. Guarda fatores e simulações
    para auditoria operacional e evolução futura do modelo.
    """
    __tablename__ = "buybox_score_snapshots"

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(_UUID(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    external_product_id = Column(String, index=True)
    current_price = Column(Numeric(12, 2))
    current_probability = Column(Numeric(5, 2), nullable=False)
    confidence = Column(Numeric(5, 2), nullable=False)
    recommendation = Column(Text)
    factors_json = Column(_JSON(), default=list)
    simulations_json = Column(_JSON(), default=list)
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AlertSetting(Base):
    """Preferências de alertas por tenant.

    Tokens de provider ficam no ambiente. Aqui persistimos apenas destinos e
    preferências operacionais do seller, sempre isoladas por tenant.
    """
    __tablename__ = "alert_settings"
    __table_args__ = (UniqueConstraint("tenant_id"),)

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    telegram_enabled = Column(Boolean, default=False, nullable=False)
    telegram_chat_id = Column(String)
    whatsapp_enabled = Column(Boolean, default=False, nullable=False)
    whatsapp_phone = Column(String)
    enabled_alert_types_json = Column(_JSON(), default=list)
    min_severity = Column(String, default="warning", nullable=False)
    quiet_hours_start = Column(String)
    quiet_hours_end = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertHistory(Base):
    """Histórico de disparos de alertas por provider.

    Mantém auditoria e deduplicação sem armazenar segredos. Erros externos são
    sanitizados antes de persistir.
    """
    __tablename__ = "alert_history"

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String, nullable=False, index=True)
    severity = Column(String, default="warning", nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text)
    provider = Column(String, nullable=False, index=True)
    status = Column(String, default="pending", nullable=False, index=True)
    dedupe_key = Column(String, index=True)
    sent_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)



class BillingSubscription(Base):
    """Assinatura SaaS do tenant via Pagar.me.

    Não armazena cartão nem dados sensíveis de pagamento; apenas IDs do provider,
    status e metadados operacionais necessários para billing e limites.
    """
    __tablename__ = "billing_subscriptions"

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    pagarme_customer_id = Column(String, index=True)
    pagarme_subscription_id = Column(String, index=True)
    plan_code = Column(String, default="STARTER", nullable=False, index=True)
    status = Column(String, default="trial", nullable=False, index=True)
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    last_payment_status = Column(String)
    last_payment_at = Column(DateTime(timezone=True))
    trial_ends_at = Column(DateTime(timezone=True))
    metadata_json = Column(_JSON(), default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class BillingEvent(Base):
    """Eventos de billing/webhook para auditoria e idempotência básica."""
    __tablename__ = "billing_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    provider = Column(String, default="pagarme", nullable=False, index=True)
    provider_event_id = Column(String, nullable=False, index=True)
    payload_json = Column(_JSON(), default=dict)
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)



class DemandForecastSnapshot(Base):
    """Histórico de previsão de demanda e ponto de recompra por produto.

    Heurística estatística interna SellerOS. Não inventa vendas e não representa
    modelo preditivo oficial do Mercado Livre.
    """
    __tablename__ = "demand_forecast_snapshots"

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(_UUID(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    avg_daily_sales = Column(Numeric(12, 4), default=0)
    estimated_days_remaining = Column(Numeric(12, 2))
    reorder_point = Column(Integer, default=0)
    demand_trend = Column(String, default="insufficient_history", index=True)
    stock_risk = Column(String, default="low", index=True)
    confidence = Column(Numeric(5, 2), default=0.35)
    raw_metrics_json = Column(_JSON(), default=dict)
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class FinancialReconciliationSnapshot(Base):
    """Snapshot financeiro por período para reconciliação Mercado Livre.

    MVP sem integração bancária automática: bank_received_amount é manual/opcional.
    Valores ausentes da API ficam nulos ou marcados em data_quality para evitar
    inventar resultado financeiro.
    """
    __tablename__ = "financial_reconciliation_snapshots"

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    marketplace_connection_id = Column(_UUID(), ForeignKey("marketplace_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    gross_revenue = Column(Numeric(14, 2))
    ml_fees = Column(Numeric(14, 2))
    shipping_costs = Column(Numeric(14, 2))
    refunds_amount = Column(Numeric(14, 2))
    chargebacks_amount = Column(Numeric(14, 2))
    net_revenue = Column(Numeric(14, 2))
    bank_received_amount = Column(Numeric(14, 2))
    reconciliation_difference = Column(Numeric(14, 2))
    orders_count = Column(Integer, default=0)
    refunded_orders_count = Column(Integer, default=0)
    disputed_orders_count = Column(Integer, default=0)
    data_quality_status = Column(String, default="insufficient", index=True)
    raw_payload_json = Column(_JSON(), default=dict)
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("cliente_id", "sku"),
        UniqueConstraint("cliente_id", "external_product_id"),
    )
    id               = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id       = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    marketplace_connection_id = Column(_UUID(), ForeignKey("marketplace_connections.id", ondelete="SET NULL"), nullable=True)
    marketplace      = Column(String, default="mercadolivre", index=True)
    external_product_id = Column(String, index=True)
    sku              = Column(String, nullable=False)
    titulo           = Column(String, nullable=False)
    title            = Column(String)
    titulo_otimizado = Column(String)
    descricao        = Column(Text)
    categoria_id     = Column(String)
    category_id      = Column(String)
    categoria_nome   = Column(String)
    custo            = Column(Numeric(12, 2), default=0)
    preco_base       = Column(Numeric(12, 2))
    price            = Column(Numeric(12, 2))
    currency_id      = Column(String)
    margem_minima    = Column(Numeric(5, 4), default=0.10)
    peso_kg          = Column(Numeric(8, 3))
    altura_cm        = Column(Numeric(8, 2))
    largura_cm       = Column(Numeric(8, 2))
    comprimento_cm   = Column(Numeric(8, 2))
    estoque          = Column(Integer, default=0)
    available_quantity = Column(Integer, default=0)
    sold_quantity    = Column(Integer, default=0)
    estoque_minimo   = Column(Integer, default=5)
    ncm              = Column(String)
    gtin             = Column(String)
    marca            = Column(String)
    atributos        = Column(_JSON(), default=dict)
    tags             = Column(_JSON())
    condition        = Column(String)
    status           = Column(String)
    permalink        = Column(Text)
    thumbnail        = Column(Text)
    listing_type_id  = Column(String)
    health           = Column(Numeric(5, 4))
    catalog_listing  = Column(Boolean, default=False)
    shipping_mode    = Column(String)
    free_shipping    = Column(Boolean, default=False)
    tags_json        = Column(_JSON(), default=list)
    raw_payload_json = Column(_JSON(), default=dict)
    health_flags_json = Column(_JSON(), default=list)
    last_synced_at   = Column(DateTime(timezone=True))
    created_at       = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at       = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    ativo            = Column(Boolean, default=True)
    criado_em        = Column(DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em    = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente  = relationship("Cliente", back_populates="products")
    images   = relationship("ProductImage", back_populates="product", cascade="all, delete")
    listings = relationship("MarketplaceListing", back_populates="product")


class ProductImage(Base):
    __tablename__ = "product_images"
    id         = Column(_UUID(), primary_key=True, default=_uuid)
    product_id = Column(_UUID(), ForeignKey("products.id", ondelete="CASCADE"))
    url        = Column(Text, nullable=False)
    ordem      = Column(Integer, default=0)
    principal  = Column(Boolean, default=False)
    criado_em  = Column(DateTime(timezone=True), default=datetime.utcnow)

    product = relationship("Product", back_populates="images")


class MarketplaceListing(Base):
    __tablename__  = "marketplace_listings"
    __table_args__ = (UniqueConstraint("cliente_id", "marketplace", "marketplace_id"),)
    id               = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id       = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"))
    product_id       = Column(_UUID(), ForeignKey("products.id"))
    marketplace      = Column(String, nullable=False)
    marketplace_id   = Column(String)
    titulo_publicado = Column(String)
    preco_publicado  = Column(Numeric(12, 2))
    status           = Column(String, default="rascunho")
    listing_type     = Column(String, default="gold_special")
    url              = Column(Text)
    payload          = Column(_JSON())
    resposta_api     = Column(_JSON())
    dt_publicado     = Column(DateTime(timezone=True))
    dt_atualizado    = Column(DateTime(timezone=True), default=datetime.utcnow)
    criado_em        = Column(DateTime(timezone=True), default=datetime.utcnow)

    product = relationship("Product", back_populates="listings")


class CompetitorSearch(Base):
    __tablename__ = "competitor_searches"
    id          = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id  = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"))
    product_id  = Column(_UUID(), ForeignKey("products.id"))
    marketplace = Column(String, nullable=False)
    query       = Column(String, nullable=False)
    status      = Column(String, default="pending")
    total_found = Column(Integer, default=0)
    dt_raw      = Column(Date)
    criado_em   = Column(DateTime(timezone=True), default=datetime.utcnow)

    offers = relationship("CompetitorOffer", back_populates="search", cascade="all, delete")


class CompetitorOffer(Base):
    __tablename__  = "competitor_offers"
    __table_args__ = (UniqueConstraint("search_id", "hash_dedup"),)
    id             = Column(_UUID(), primary_key=True, default=_uuid)
    search_id      = Column(_UUID(), ForeignKey("competitor_searches.id", ondelete="CASCADE"))
    cliente_id     = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"))
    marketplace    = Column(String)
    titulo         = Column(String)
    preco          = Column(Numeric(12, 2))
    preco_original = Column(Numeric(12, 2))
    vendedor       = Column(String)
    reputacao      = Column(String)
    vendas         = Column(Integer, default=0)
    frete_gratis   = Column(Boolean, default=False)
    url            = Column(Text)
    thumbnail      = Column(Text)
    hash_dedup     = Column(String)
    dt_raw         = Column(Date)
    dt_staging     = Column(Date)
    criado_em      = Column(DateTime(timezone=True), default=datetime.utcnow)

    search = relationship("CompetitorSearch", back_populates="offers")


class PricingResult(Base):
    __tablename__ = "pricing_results"
    id                     = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id             = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"))
    product_id             = Column(_UUID(), ForeignKey("products.id"))
    marketplace            = Column(String)
    modo                   = Column(String, default="rule_based")
    custo                  = Column(Numeric(12, 2))
    comissao_pct           = Column(Numeric(5, 4))
    imposto_pct            = Column(Numeric(5, 4))
    markup_pct             = Column(Numeric(5, 4))
    preco_sugerido         = Column(Numeric(12, 2))
    preco_concorrencia_min = Column(Numeric(12, 2))
    preco_concorrencia_med = Column(Numeric(12, 2))
    lucro_estimado         = Column(Numeric(12, 2))
    margem_real_pct        = Column(Numeric(5, 4))
    score_competitividade  = Column(Numeric(5, 4))
    ml_usado               = Column(Boolean, default=False)
    ml_confianca           = Column(Numeric(5, 4))
    features_json          = Column(_JSON())
    criado_em              = Column(DateTime(timezone=True), default=datetime.utcnow)


class PublishLog(Base):
    __tablename__ = "publish_logs"
    id         = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"))
    product_id = Column(_UUID(), ForeignKey("products.id"))
    listing_id = Column(_UUID(), ForeignKey("marketplace_listings.id"))
    marketplace= Column(String)
    acao       = Column(String)
    status     = Column(String)
    payload    = Column(_JSON())
    resposta   = Column(_JSON())
    erro       = Column(Text)
    duracao_ms = Column(Integer)
    criado_em  = Column(DateTime(timezone=True), default=datetime.utcnow)


class MLTrainingRun(Base):
    __tablename__ = "ml_training_runs"
    id                 = Column(_UUID(), primary_key=True, default=_uuid)
    run_name           = Column(String)
    model_type         = Column(String)
    marketplace        = Column(String)
    dataset_version    = Column(String)
    dataset_hash       = Column(String)
    n_samples          = Column(Integer)
    n_features         = Column(Integer)
    mae                = Column(Numeric(10, 4))
    rmse               = Column(Numeric(10, 4))
    r2                 = Column(Numeric(8, 6))
    params             = Column(_JSON())
    feature_importance = Column(_JSON())
    model_path         = Column(String)
    status             = Column(String, default="running")
    criado_em          = Column(DateTime(timezone=True), default=datetime.utcnow)
    finalizado_em      = Column(DateTime(timezone=True))


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    id                    = Column(_UUID(), primary_key=True, default=_uuid)
    product_id            = Column(_UUID(), ForeignKey("products.id"))
    cliente_id            = Column(_UUID(), ForeignKey("clientes.id"))
    marketplace           = Column(String)
    run_id                = Column(_UUID(), ForeignKey("ml_training_runs.id"))
    preco_previsto        = Column(Numeric(12, 2))
    score_competitividade = Column(Numeric(5, 4))
    margem_prevista       = Column(Numeric(5, 4))
    confianca             = Column(Numeric(5, 4))
    features_usadas       = Column(_JSON())
    criado_em             = Column(DateTime(timezone=True), default=datetime.utcnow)


class ScrapingLog(Base):
    __tablename__ = "scraping_logs"
    id             = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id     = Column(_UUID())
    marketplace    = Column(String)
    query          = Column(String)
    status         = Column(String)
    total_coletado = Column(Integer, default=0)
    total_novo     = Column(Integer, default=0)
    total_dup      = Column(Integer, default=0)
    erro           = Column(Text)
    duracao_ms     = Column(Integer)
    criado_em      = Column(DateTime(timezone=True), default=datetime.utcnow)


class ApiLog(Base):
    __tablename__ = "api_logs"
    id          = Column(_UUID(), primary_key=True, default=_uuid)
    cliente_id  = Column(_UUID())
    marketplace = Column(String)
    endpoint    = Column(String)
    metodo      = Column(String)
    status_code = Column(Integer)
    duracao_ms  = Column(Integer)
    erro        = Column(Text)
    criado_em   = Column(DateTime(timezone=True), default=datetime.utcnow)


class FeatureStore(Base):
    __tablename__  = "feature_store"
    __table_args__ = (UniqueConstraint("entity_id", "entity_type", "feature_name", "dt_feature"),)
    id              = Column(_UUID(), primary_key=True, default=_uuid)
    entity_id       = Column(String, nullable=False)
    entity_type     = Column(String, nullable=False)
    feature_name    = Column(String, nullable=False)
    feature_value   = Column(Numeric)
    feature_json    = Column(_JSON())
    dataset_version = Column(String)
    dt_feature      = Column(Date)
    criado_em       = Column(DateTime(timezone=True), default=datetime.utcnow)


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    cliente_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(String, nullable=False)
    status = Column(String, default="queued")
    progress_current = Column(Integer, default=0)
    progress_total = Column(Integer, default=100)
    progress_label = Column(String, default="Aguardando")
    parameters_json = Column(_JSON(), default=dict)
    result_json = Column(_JSON(), default=dict)
    error_message = Column(Text)
    stdout_tail = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Numeric(10, 2))


class TitleOptimizationHistory(Base):
    """Histórico multi-tenant de sugestões de título do PATCH 13/15.

    Apenas persiste recomendações consultivas; não representa alteração aplicada
    ao anúncio do Mercado Livre.
    """
    __tablename__ = "title_optimization_history"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(_UUID(), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    original_title = Column(Text, nullable=False)
    optimized_titles_json = Column(_JSON(), default=list)
    score = Column(Integer, default=0, index=True)
    competitor_terms_json = Column(_JSON(), default=list)
    ai_provider = Column(String)
    warnings_json = Column(_JSON(), default=list)
    raw_payload_json = Column(_JSON(), default=dict)
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class PortfolioAnalysisSnapshot(Base):
    """Snapshot multi-tenant da análise estratégica de portfólio do PATCH 14/15.

    Classificação consultiva baseada somente em dados disponíveis; margens/vendas
    ausentes permanecem nulas e reduzem confidence.
    """
    __tablename__ = "portfolio_analysis_snapshots"

    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(_UUID(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_class = Column(String, nullable=False, index=True)
    sales_velocity = Column(Numeric(12, 4))
    estimated_margin = Column(Numeric(12, 4))
    buybox_probability = Column(Numeric(5, 2))
    title_score = Column(Integer)
    risk_score = Column(Integer)
    opportunity_score = Column(Integer)
    confidence = Column(Numeric(5, 2), default=0.35)
    recommendations_json = Column(_JSON(), default=list)
    warnings_json = Column(_JSON(), default=list)
    raw_metrics_json = Column(_JSON(), default=dict)
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# ─────────────────────────────────────────────
# Action Intelligence persistence layer
# ─────────────────────────────────────────────
class ActionRecommendation(Base):
    __tablename__ = "action_recommendations"
    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(_UUID(), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(_UUID(), ForeignKey("background_jobs.id", ondelete="SET NULL"), nullable=True)
    category = Column(String, nullable=False, default="operational")
    priority = Column(String, nullable=False, default="MEDIUM")
    origin = Column(String, default="AI Operations Copilot")
    title = Column(String, nullable=False)
    explanation = Column(Text)
    recommended_action = Column(Text)
    next_best_action = Column(Text)
    expected_impact = Column(Numeric(12, 2), default=0)
    confidence = Column(Numeric(5, 4), default=0.75)
    status = Column(String, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True))


class ActionDecision(Base):
    __tablename__ = "action_decisions"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    action_id = Column(String, ForeignKey("action_recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False)
    note = Column(Text)
    impact = Column(Numeric(12, 2), default=0)
    source = Column(String, default="Action Center")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class SmartAlertLifecycle(Base):
    __tablename__ = "smart_alert_lifecycle"
    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_key = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String, default="operational")
    priority = Column(String, default="medium")
    status = Column(String, default="unread", index=True)
    source = Column(String, default="Smart Alerts Engine")
    impact_estimated = Column(Numeric(12, 2), default=0)
    recommended_action = Column(Text)
    related_product_id = Column(_UUID(), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    related_job_id = Column(_UUID(), ForeignKey("background_jobs.id", ondelete="SET NULL"), nullable=True)
    assigned_to = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True))


class ProfitSimulation(Base):
    __tablename__ = "profit_simulations"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    payload_json = Column(_JSON(), default=dict)
    result_json = Column(_JSON(), default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(String)


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    id = Column(_UUID(), primary_key=True, default=_uuid)
    tenant_id = Column(_UUID(), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    category = Column(String, default="operational")
    severity = Column(String, default="info")
    title = Column(String, nullable=False)
    description = Column(Text)
    impact_estimated = Column(Numeric(12, 2), default=0)
    related_product_id = Column(_UUID(), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    related_job_id = Column(_UUID(), ForeignKey("background_jobs.id", ondelete="SET NULL"), nullable=True)
    related_action_id = Column(String, ForeignKey("action_recommendations.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
