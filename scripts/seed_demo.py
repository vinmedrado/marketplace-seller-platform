"""Popula o cenário local de demonstração com dados sintéticos determinísticos."""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import ENV
from db.base import SessionLocal
from models.orm import (
    AlertHistory,
    BackgroundJob,
    BuyBoxScoreSnapshot,
    CompetitorOffer,
    CompetitorSearch,
    DemandForecastSnapshot,
    MarketplaceListing,
    OnboardingState,
    PlanSubscription,
    PricingResult,
    Product,
    ProductImage,
    PublishLog,
)
from services.auth_service import ensure_demo_user
from services.saas_service import PLANS, seed_alerts

RNG = random.Random(42)
PRODUCTS = [
    ("SKU-DEMO-001", "Fone Bluetooth Pro ANC", "Eletrônicos", 89.90, 158.90, 42),
    ("SKU-DEMO-002", "Smartwatch Fitness AMOLED", "Eletrônicos", 129.90, 299.90, 18),
    ("SKU-DEMO-003", "Tênis Corrida Masculino Leve", "Calçados", 79.90, 179.90, 35),
    ("SKU-DEMO-004", "Mochila Executiva Antifurto USB", "Acessórios", 54.90, 139.90, 27),
    ("SKU-DEMO-005", "Cadeira Gamer Ergonômica", "Móveis", 399.90, 529.90, 8),
    ("SKU-DEMO-006", "Kit Panelas Antiaderente 5 Peças", "Casa", 119.90, 269.90, 14),
    ("SKU-DEMO-007", "Luminária LED Articulada", "Casa", 34.90, 89.90, 50),
    ("SKU-DEMO-008", "Mouse Gamer 12000 DPI", "Eletrônicos", 39.90, 99.90, 60),
    ("SKU-DEMO-009", "Câmera Wi-Fi Segurança Full HD", "Eletrônicos", 94.90, 219.90, 21),
    ("SKU-DEMO-010", "Organizador Modular Premium", "Casa", 24.90, 69.90, 44),
]


def seed_product(db, tenant_id: str, index: int, spec: tuple) -> Product:
    sku, title, category, cost, price, stock = spec
    product = db.query(Product).filter_by(cliente_id=tenant_id, sku=sku).first()
    if not product:
        product = Product(cliente_id=tenant_id, sku=sku, titulo=title)
        db.add(product)
        db.flush()

    sold = 20 + index * 11
    product.titulo = title
    product.title = title
    product.titulo_otimizado = f"{title} Original com Nota Fiscal"
    product.descricao = "Produto sintético para a demonstração local do MarketPlace Seller Platform."
    product.categoria_id = "MLB1051"
    product.category_id = product.categoria_id
    product.categoria_nome = category
    product.custo = cost
    product.preco_base = price
    product.price = price
    product.currency_id = "BRL"
    product.margem_minima = 0.18
    product.estoque = stock
    product.available_quantity = stock
    product.sold_quantity = sold
    product.estoque_minimo = 10
    product.marca = "Aurora Fictícia"
    product.ncm = "64041100"
    product.gtin = f"789490001{1500 + index:04}"
    product.atributos = {"synthetic": True}
    product.tags = ["demo", "synthetic"]
    product.external_product_id = f"MLB-DEMO-{index:04}"
    product.condition = "new"
    product.status = "active"
    product.health = 0.72 + ((index % 4) * 0.06)
    product.last_synced_at = datetime.utcnow() - timedelta(minutes=index * 7)

    if not product.images:
        db.add(ProductImage(product_id=product.id, url="https://placehold.co/800x800?text=MarketPlace+Seller+Platform", principal=True))
    return product


def seed_market_context(db, tenant_id: str, product: Product, index: int) -> None:
    search = db.query(CompetitorSearch).filter_by(
        cliente_id=tenant_id,
        product_id=product.id,
        marketplace="mercadolivre",
    ).first()
    if not search:
        search = CompetitorSearch(
            cliente_id=tenant_id,
            product_id=product.id,
            marketplace="mercadolivre",
            query=product.titulo,
            status="completed",
            total_found=8,
            dt_raw=date.today(),
        )
        db.add(search)
        db.flush()
    if not search.offers:
        for offer_index in range(8):
            offer_price = round(float(product.preco_base) * RNG.uniform(0.82, 1.18), 2)
            db.add(CompetitorOffer(
                search_id=search.id,
                cliente_id=tenant_id,
                marketplace="mercadolivre",
                titulo=f"{product.titulo} — oferta sintética {offer_index + 1}",
                preco=offer_price,
                vendedor=f"Seller fictício {offer_index + 1}",
                reputacao=RNG.choice(["verde", "amarela", "premium"]),
                vendas=RNG.randint(10, 300),
                frete_gratis=offer_index % 2 == 0,
                url="https://example.invalid/oferta-demo",
                hash_dedup=f"{product.sku}-{offer_index}",
                dt_raw=date.today(),
                dt_staging=date.today(),
            ))

    if db.query(PricingResult).filter_by(cliente_id=tenant_id, product_id=product.id).count() == 0:
        price = float(product.preco_base)
        db.add(PricingResult(
            cliente_id=tenant_id,
            product_id=product.id,
            marketplace="mercadolivre",
            modo="demo",
            custo=product.custo,
            comissao_pct=0.14,
            imposto_pct=0.06,
            markup_pct=0.30,
            preco_sugerido=round(price * 1.03, 2),
            preco_concorrencia_min=round(price * 0.86, 2),
            preco_concorrencia_med=round(price * 1.01, 2),
            lucro_estimado=round(price * 0.22, 2),
            margem_real_pct=0.24,
            score_competitividade=0.82,
            ml_usado=True,
            ml_confianca=0.78,
            features_json={"synthetic": True},
        ))

    listing = db.query(MarketplaceListing).filter_by(
        cliente_id=tenant_id,
        product_id=product.id,
        marketplace="mercadolivre",
    ).first()
    if not listing:
        listing = MarketplaceListing(
            cliente_id=tenant_id,
            product_id=product.id,
            marketplace="mercadolivre",
            marketplace_id=f"DRY-{product.sku}",
            titulo_publicado=product.titulo,
            preco_publicado=product.preco_base,
            status="dry_run",
            payload={"dry_run": True, "synthetic": True},
            resposta_api={"synthetic": True},
            url="https://example.invalid/anuncio-demo",
        )
        db.add(listing)
        db.flush()
    if db.query(PublishLog).filter_by(cliente_id=tenant_id, product_id=product.id).count() == 0:
        db.add(PublishLog(
            cliente_id=tenant_id,
            product_id=product.id,
            listing_id=listing.id,
            marketplace="mercadolivre",
            acao="publish",
            status="dry_run",
            payload={"synthetic": True},
            resposta={"id": listing.marketplace_id},
            duracao_ms=RNG.randint(80, 420),
        ))

    daily_sales = round(float(product.sold_quantity or 0) / 30, 4)
    days_remaining = round(float(product.estoque or 0) / daily_sales, 2) if daily_sales else None
    if db.query(DemandForecastSnapshot).filter_by(tenant_id=tenant_id, product_id=product.id).count() == 0:
        db.add(DemandForecastSnapshot(
            tenant_id=tenant_id,
            product_id=product.id,
            avg_daily_sales=daily_sales,
            estimated_days_remaining=days_remaining,
            reorder_point=max(5, int(daily_sales * 14)),
            demand_trend=RNG.choice(["stable", "increasing", "decreasing"]),
            stock_risk="critical" if days_remaining and days_remaining < 8 else "high" if days_remaining and days_remaining < 15 else "low",
            confidence=0.82,
            raw_metrics_json={"synthetic": True},
        ))
    if db.query(BuyBoxScoreSnapshot).filter_by(tenant_id=tenant_id, product_id=product.id).count() == 0:
        db.add(BuyBoxScoreSnapshot(
            tenant_id=tenant_id,
            product_id=product.id,
            external_product_id=product.external_product_id,
            current_price=product.preco_base,
            current_probability=62 + index * 3,
            confidence=0.84,
            recommendation="Recomendação sintética para demonstração local.",
            factors_json=[{"factor": "price", "synthetic": True}],
            simulations_json=[],
        ))


def seed_tenant_context(db, tenant_id: str) -> None:
    if db.query(PlanSubscription).filter_by(cliente_id=tenant_id).count() == 0:
        plan = PLANS["growth"]
        db.add(PlanSubscription(
            cliente_id=tenant_id,
            plan_key="growth",
            limits_json=plan["limits"],
            features_json={"enabled": plan["features"]},
        ))
    if db.query(OnboardingState).filter_by(cliente_id=tenant_id).count() == 0:
        db.add(OnboardingState(
            cliente_id=tenant_id,
            completed=True,
            current_step=8,
            data_json={"company_name": "Seller Demo Premium", "synthetic": True},
        ))
    if db.query(BackgroundJob).filter_by(tenant_id=tenant_id).count() == 0:
        for job_type in ("scraping", "pricing", "publish", "ml-train"):
            db.add(BackgroundJob(
                tenant_id=tenant_id,
                cliente_id=tenant_id,
                job_type=job_type,
                status="success",
                progress_current=100,
                progress_total=100,
                progress_label="Concluído",
                parameters_json={"synthetic": True},
                result_json={"ok": True},
                stdout_tail="Job sintético seedado.",
                started_at=datetime.utcnow() - timedelta(hours=1),
                finished_at=datetime.utcnow(),
                duration_seconds=RNG.randint(4, 20),
            ))
    if db.query(AlertHistory).filter_by(tenant_id=tenant_id).count() == 0:
        db.add(AlertHistory(
            tenant_id=tenant_id,
            alert_type="STOCKOUT_RISK",
            severity="warning",
            title="Reposição recomendada",
            message="Evento sintético gerado pelo seed local.",
            provider="internal",
            status="sent",
            dedupe_key="seed:stockout",
            sent_at=datetime.utcnow() - timedelta(hours=2),
        ))


def main() -> None:
    if ENV == "production":
        raise SystemExit("Seed demo bloqueado em produção.")
    db = SessionLocal()
    try:
        user = ensure_demo_user(db)
        tenant_id = user.cliente_id
        for index, spec in enumerate(PRODUCTS, start=1):
            product = seed_product(db, tenant_id, index, spec)
            seed_market_context(db, tenant_id, product, index)
        seed_tenant_context(db, tenant_id)
        db.commit()
        seed_alerts(db, tenant_id)
        print("Seed sintético criado. Login local: demo@marketplace.local")
    finally:
        db.close()


if __name__ == "__main__":
    main()
