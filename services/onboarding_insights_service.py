"""PATCH 15/15 — Onboarding guiado e insights iniciais.

Serviço consultivo que usa módulos reais já existentes do MarketPlace Seller Platform. Mantém dados
por tenant, não inventa métrica, não expõe tokens e não dispara alterações no ML.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.orm import (
    MarketplaceConnection, Product, BuyBoxScoreSnapshot, DemandForecastSnapshot,
    PortfolioAnalysisSnapshot, TitleOptimizationHistory, AccountHealthSnapshot,
    AlertSetting, InternalAlert,
)


def _f(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _latest(db: Session, model, tenant_id: str, product_id: str | None = None):
    q = db.query(model).filter_by(tenant_id=tenant_id)
    if product_id and hasattr(model, 'product_id'):
        q = q.filter_by(product_id=product_id)
    return q.order_by(desc(model.generated_at)).first()


def _product_card(product: Product | None, extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not product:
        return None
    payload = {
        'product_id': str(product.id),
        'external_product_id': product.external_product_id,
        'title': product.titulo or product.title or product.sku,
        'thumbnail': product.thumbnail,
        'price': _f(product.price) or _f(product.preco_base),
        'available_quantity': product.available_quantity if product.available_quantity is not None else product.estoque,
        'sold_quantity': product.sold_quantity,
    }
    if extra:
        payload.update(extra)
    return payload


def get_onboarding_insights(db: Session, tenant_id: str) -> dict[str, Any]:
    connected = db.query(MarketplaceConnection).filter_by(tenant_id=tenant_id, is_active=True).first() is not None
    products = db.query(Product).filter(Product.cliente_id == tenant_id, Product.ativo == True).all()
    synced = len(products) > 0

    # Produto com maior risco Buy Box: menor probabilidade recente.
    buybox_row = db.query(BuyBoxScoreSnapshot).filter_by(tenant_id=tenant_id).order_by(BuyBoxScoreSnapshot.current_probability.asc(), BuyBoxScoreSnapshot.generated_at.desc()).first()
    buybox_product = db.query(Product).filter_by(id=buybox_row.product_id, cliente_id=tenant_id).first() if buybox_row else None

    # Melhor margem vem do snapshot de portfólio quando disponível; sem snapshot, usa custo/preço real do produto.
    margin_row = db.query(PortfolioAnalysisSnapshot).filter_by(tenant_id=tenant_id).filter(PortfolioAnalysisSnapshot.estimated_margin != None).order_by(PortfolioAnalysisSnapshot.estimated_margin.desc(), PortfolioAnalysisSnapshot.generated_at.desc()).first()
    margin_product = db.query(Product).filter_by(id=margin_row.product_id, cliente_id=tenant_id).first() if margin_row else None
    if not margin_product:
        candidates = []
        for p in products:
            price = _f(p.price) or _f(p.preco_base)
            cost = _f(p.custo)
            if price and cost and price > 0:
                candidates.append(((price-cost)/price, p))
        if candidates:
            candidates.sort(reverse=True, key=lambda x: x[0])
            margin_row = {'estimated_margin': round(candidates[0][0], 4)}
            margin_product = candidates[0][1]

    # Estoque crítico: menor dias restantes ou menor estoque positivo.
    forecast_row = db.query(DemandForecastSnapshot).filter_by(tenant_id=tenant_id).order_by(DemandForecastSnapshot.estimated_days_remaining.asc().nullslast(), DemandForecastSnapshot.generated_at.desc()).first()
    stock_product = db.query(Product).filter_by(id=forecast_row.product_id, cliente_id=tenant_id).first() if forecast_row else None
    if not stock_product and products:
        stock_product = sorted(products, key=lambda p: (p.available_quantity if p.available_quantity is not None else p.estoque or 0))[0]

    # Título fraco: menor score real salvo pelo PATCH 13.
    title_row = db.query(TitleOptimizationHistory).filter_by(tenant_id=tenant_id).order_by(TitleOptimizationHistory.score.asc(), TitleOptimizationHistory.generated_at.desc()).first()
    title_product = db.query(Product).filter_by(id=title_row.product_id, cliente_id=tenant_id).first() if title_row and title_row.product_id else None

    # Oportunidade principal: maior opportunity_score do portfólio.
    opportunity_row = db.query(PortfolioAnalysisSnapshot).filter_by(tenant_id=tenant_id).order_by(PortfolioAnalysisSnapshot.opportunity_score.desc(), PortfolioAnalysisSnapshot.generated_at.desc()).first()
    opportunity_product = db.query(Product).filter_by(id=opportunity_row.product_id, cliente_id=tenant_id).first() if opportunity_row else None

    health = db.query(AccountHealthSnapshot).filter_by(tenant_id=tenant_id).order_by(AccountHealthSnapshot.generated_at.desc()).first()
    alert_settings = db.query(AlertSetting).filter_by(tenant_id=tenant_id).first()
    active_alerts = db.query(InternalAlert).filter_by(cliente_id=tenant_id, is_read=False).count()

    warnings: list[str] = []
    if not connected:
        warnings.append('Conecte a conta Mercado Livre para liberar sync e inteligência operacional.')
    if not synced:
        warnings.append('Sincronize o catálogo para gerar insights reais de produtos.')
    if not margin_row:
        warnings.append('Margem real indisponível. Informe custos para melhorar recomendações.')
    if not title_row:
        warnings.append('Nenhum score de título salvo ainda. Rode Otimização de Título nos produtos críticos.')

    completed_steps = [connected, synced, bool(buybox_row or opportunity_row or products), bool(alert_settings and (alert_settings.telegram_enabled or alert_settings.whatsapp_enabled)), connected and synced]
    next_step = 1 + next((i for i, done in enumerate(completed_steps) if not done), len(completed_steps)-1)

    return {
        'connected': connected,
        'catalog_synced': synced,
        'total_products': len(products),
        'next_step': min(next_step, 5),
        'steps': [
            {'key': 'connected', 'title': 'Conta conectada', 'done': connected},
            {'key': 'catalog', 'title': 'Catálogo sincronizado', 'done': synced},
            {'key': 'insights', 'title': 'Primeiros insights gerados', 'done': bool(buybox_row or opportunity_row or products)},
            {'key': 'alerts', 'title': 'Alertas configurados', 'done': bool(alert_settings and (alert_settings.telegram_enabled or alert_settings.whatsapp_enabled))},
            {'key': 'ready', 'title': 'MarketPlace Seller Platform pronto', 'done': connected and synced},
        ],
        'highlights': {
            'highest_buybox_risk': _product_card(buybox_product, {'buybox_probability': _f(getattr(buybox_row, 'current_probability', None)), 'reason': 'Menor probabilidade interna de Buy Box disponível.'}) if buybox_row else None,
            'best_margin': _product_card(margin_product, {'estimated_margin': _f(getattr(margin_row, 'estimated_margin', None)) if not isinstance(margin_row, dict) else margin_row.get('estimated_margin'), 'reason': 'Melhor margem estimada com dados disponíveis.'}) if margin_product else None,
            'critical_stock': _product_card(stock_product, {'stock_days_remaining': _f(getattr(forecast_row, 'estimated_days_remaining', None)), 'reason': 'Estoque ou dias restantes pedem atenção.'}) if stock_product else None,
            'weak_title': _product_card(title_product, {'title_score': getattr(title_row, 'score', None), 'reason': 'Menor score de título registrado.'}) if title_product else None,
            'main_opportunity': _product_card(opportunity_product, {'opportunity_score': getattr(opportunity_row, 'opportunity_score', None), 'reason': 'Maior score de oportunidade no portfólio.'}) if opportunity_product else None,
        },
        'summary': {
            'account_health_score': getattr(health, 'score', None),
            'account_health_status': getattr(health, 'status', None),
            'active_alerts': active_alerts,
            'telegram_configured': bool(alert_settings and alert_settings.telegram_enabled),
            'whatsapp_configured': bool(alert_settings and alert_settings.whatsapp_enabled),
        },
        'warnings': warnings,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'disclaimer': 'Insights iniciais usam apenas dados disponíveis no MarketPlace Seller Platform. Nenhuma alteração é enviada ao Mercado Livre automaticamente.',
    }
