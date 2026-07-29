"""PATCH 14/15 — Análise Estratégica de Portfólio.

Classifica produtos por giro e margem usando somente dados reais disponíveis no
banco. Quando margem/vendas/histórico estiverem ausentes, mantém valores nulos,
reduz confidence e adiciona warnings — sem inventar dados.
"""
from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from models.orm import (
    ActionRecommendation,
    BuyBoxScoreSnapshot,
    DemandForecastSnapshot,
    FinancialReconciliationSnapshot,
    InternalAlert,
    PortfolioAnalysisSnapshot,
    Product,
    TitleOptimizationHistory,
)

CLASS_LABELS = {
    "STAR": "Estrela",
    "CASH_COW": "Vaca leiteira",
    "PROBLEM": "Problema",
    "DOG": "Abacaxi",
}


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _latest(db: Session, model, tenant_id: str, product_id: str):
    return db.query(model).filter_by(tenant_id=tenant_id, product_id=product_id).order_by(model.generated_at.desc()).first()


def _title_score(db: Session, tenant_id: str, product_id: str) -> int | None:
    row = db.query(TitleOptimizationHistory).filter_by(tenant_id=tenant_id, product_id=product_id).order_by(TitleOptimizationHistory.generated_at.desc()).first()
    return int(row.score) if row and row.score is not None else None


def _estimated_margin(product: Product, finance: FinancialReconciliationSnapshot | None) -> float | None:
    price = _f(product.price) or _f(product.preco_base)
    cost = _f(product.custo)
    if price and cost and cost > 0:
        return round((price - cost) / price, 4)
    # Snapshot financeiro é agregado por tenant/período; usar apenas como proxy conservador, sem inventar por produto.
    if finance and _f(finance.gross_revenue) and _f(finance.net_revenue):
        gross = _f(finance.gross_revenue) or 0
        net = _f(finance.net_revenue) or 0
        if gross > 0:
            return round(net / gross, 4)
    return None


def _sales_velocity(product: Product, forecast: DemandForecastSnapshot | None) -> float:
    if forecast and forecast.avg_daily_sales is not None:
        return round(max(0.0, float(forecast.avg_daily_sales)), 4)
    sold = _f(product.sold_quantity) or 0
    return round(max(0.0, sold / 30.0), 4)


def _stock_days(product: Product, sales_velocity: float, forecast: DemandForecastSnapshot | None) -> float | None:
    if forecast and forecast.estimated_days_remaining is not None:
        return round(float(forecast.estimated_days_remaining), 2)
    stock = _f(product.available_quantity) if product.available_quantity is not None else _f(product.estoque)
    if stock is None or sales_velocity <= 0:
        return None
    return round(stock / sales_velocity, 2)


def _classify(sales_velocity: float, margin: float | None, median_velocity: float, median_margin: float | None) -> tuple[str, bool, bool]:
    high_turnover = sales_velocity >= median_velocity if median_velocity > 0 else sales_velocity > 0
    if margin is None:
        good_margin = False
    elif median_margin is not None:
        good_margin = margin > 0 and margin >= median_margin
    else:
        good_margin = margin > 0
    if high_turnover and good_margin:
        return "STAR", high_turnover, good_margin
    if high_turnover and not good_margin:
        return "CASH_COW", high_turnover, good_margin
    if not high_turnover and good_margin:
        return "PROBLEM", high_turnover, good_margin
    return "DOG", high_turnover, good_margin


def _recommendations(portfolio_class: str, *, stock_days: float | None, buybox: float | None, title_score: int | None, margin: float | None) -> list[str]:
    base = {
        "STAR": ["Manter estoque saudável.", "Proteger Buy Box.", "Monitorar concorrência.", "Avaliar impulsionamento com cautela."],
        "CASH_COW": ["Revisar preço e custos.", "Buscar melhoria de margem.", "Avaliar frete, taxas e comissões.", "Proteger giro antes de aumentar preço."],
        "PROBLEM": ["Melhorar título e anúncio.", "Comparar preço com mercado.", "Avaliar campanha ou exposição.", "Revisar fotos e atributos."],
        "DOG": ["Reduzir exposição.", "Liquidar estoque se fizer sentido.", "Revisar precificação.", "Considerar descontinuar após análise comercial."],
    }[portfolio_class][:]
    if stock_days is not None and stock_days < 10:
        base.insert(0, "Repor estoque com prioridade.")
    if buybox is not None and buybox < 45:
        base.append("Revisar fatores de Buy Box.")
    if title_score is not None and title_score < 70:
        base.append("Rodar Otimização de Título antes de ampliar tráfego.")
    if margin is not None and margin < 0:
        base.insert(0, "Revisar margem negativa imediatamente.")
    return base[:6]


def _scores(portfolio_class: str, *, stock_days: float | None, buybox: float | None, title_score: int | None, margin: float | None, velocity: float) -> tuple[int, int]:
    risk = 25
    opp = 35
    if portfolio_class == "STAR":
        opp += 35; risk -= 5
    elif portfolio_class == "CASH_COW":
        opp += 20; risk += 20
    elif portfolio_class == "PROBLEM":
        opp += 25; risk += 15
    else:
        risk += 35
    if stock_days is not None and stock_days < 10:
        risk += 25
    if buybox is not None:
        risk += max(0, int((50 - buybox) / 2))
        opp += max(0, int((buybox - 60) / 4))
    if title_score is not None and title_score < 70:
        opp += 15
    if margin is not None and margin < 0.08:
        risk += 18
    if velocity > 0:
        opp += 5
    return max(0, min(100, risk)), max(0, min(100, opp))


def _confidence(*, margin: float | None, forecast: Any, buybox: Any, title_score: int | None, finance: Any) -> float:
    c = 0.35
    if margin is not None: c += 0.20
    if forecast: c += 0.15
    if buybox: c += 0.12
    if title_score is not None: c += 0.08
    if finance: c += 0.05
    return round(min(0.95, c), 2)


def _make_action(db: Session, tenant_id: str, product_id: str, portfolio_class: str, title: str, risk: int, opportunity: int) -> None:
    mapping = {
        "STAR": ("PORTFOLIO_STAR", "Produto estrela detectado", "Manter estoque e proteger Buy Box para preservar oportunidade."),
        "CASH_COW": ("PORTFOLIO_CASH_COW", "Vaca leiteira com atenção de margem", "Produto gira bem, mas precisa revisão de preço, custos e taxas."),
        "PROBLEM": ("PORTFOLIO_PROBLEM", "Produto com margem, mas baixo giro", "Revisar anúncio, título, exposição e competitividade antes de escalar."),
        "DOG": ("PORTFOLIO_DOG", "Abacaxi no portfólio", "Produto combina baixo giro e margem fraca ou indisponível; avaliar liquidação ou descontinuação."),
    }
    code, action_title, explanation = mapping[portfolio_class]
    if risk < 60 and opportunity < 65 and portfolio_class not in {"STAR", "DOG"}:
        return
    action_id = f"portfolio-{code.lower()}-{product_id}-{datetime.utcnow().strftime('%Y%m%d')}"
    if db.query(ActionRecommendation).filter_by(id=action_id, tenant_id=tenant_id).first():
        return
    db.add(ActionRecommendation(
        id=action_id,
        tenant_id=tenant_id,
        product_id=product_id,
        category="portfolio",
        priority="HIGH" if risk >= 70 or portfolio_class == "DOG" else "MEDIUM",
        origin="Portfolio Analysis",
        title=action_title,
        explanation=f"{explanation} Produto: {title}",
        recommended_action="Abrir Análise de Portfólio e revisar recomendações antes de qualquer ação operacional.",
        next_best_action="Revisar produto no portfólio",
        expected_impact=max(risk, opportunity),
        confidence=0.78,
        status="pending",
    ))
    if portfolio_class in {"DOG", "CASH_COW", "STAR"}:
        rebalance_id = f"portfolio-rebalance-{product_id}-{datetime.utcnow().strftime('%Y%m%d')}"
        if not db.query(ActionRecommendation).filter_by(id=rebalance_id, tenant_id=tenant_id).first():
            db.add(ActionRecommendation(
                id=rebalance_id,
                tenant_id=tenant_id,
                product_id=product_id,
                category="portfolio",
                priority="MEDIUM",
                origin="Portfolio Analysis",
                title="PORTFOLIO_REBALANCE_RECOMMENDED",
                explanation="Rebalanceamento recomendado com base em giro, margem, risco e oportunidade. Não há promessa de ranking ou venda garantida.",
                recommended_action="Comparar classe do produto com estoque, preço, margem e plano comercial.",
                next_best_action="Rebalancear prioridade",
                expected_impact=opportunity,
                confidence=0.7,
                status="pending",
            ))


def _alert(db: Session, tenant_id: str, product_id: str, cls: str, title: str, stock_qty: float | None, stock_days: float | None, margin: float | None) -> None:
    alert_type = None; severity = "warning"; msg = None
    if cls == "DOG" and (stock_qty or 0) >= 20:
        alert_type = "PORTFOLIO_RISK"; severity = "critical"; msg = "Abacaxi com estoque alto: avaliar redução de exposição, liquidação ou revisão de preço."
    elif cls == "STAR" and stock_days is not None and stock_days < 10:
        alert_type = "PORTFOLIO_OPPORTUNITY"; msg = "Estrela com estoque baixo: risco de perder demanda por ruptura."
    elif cls == "CASH_COW" and margin is not None and margin < 0.05:
        alert_type = "PORTFOLIO_RISK"; severity = "critical"; msg = "Vaca leiteira com margem crítica: revisar custos, frete, taxas e preço."
    if not alert_type:
        return
    exists = db.query(InternalAlert).filter_by(cliente_id=tenant_id, type=alert_type, target_url=f"/app/produtos/{product_id}", is_read=False).first()
    if exists:
        return
    db.add(InternalAlert(cliente_id=tenant_id, type=alert_type, priority=severity, title=title[:120], description=msg, target_url=f"/app/produtos/{product_id}", metadata_json={"product_id": product_id, "portfolio_class": cls}))


def analyze_portfolio(db: Session, tenant_id: str, persist: bool = False) -> dict[str, Any]:
    products = db.query(Product).filter(Product.cliente_id == tenant_id, Product.ativo == True).order_by(Product.updated_at.desc()).all()
    latest_finance = db.query(FinancialReconciliationSnapshot).filter_by(tenant_id=tenant_id).order_by(FinancialReconciliationSnapshot.generated_at.desc()).first()
    base = []
    for p in products:
        forecast = _latest(db, DemandForecastSnapshot, tenant_id, p.id)
        velocity = _sales_velocity(p, forecast)
        margin = _estimated_margin(p, latest_finance)
        base.append((p, forecast, velocity, margin))
    velocities = [x[2] for x in base]
    margins = [x[3] for x in base if x[3] is not None]
    med_velocity = median(velocities) if velocities else 0
    med_margin = median(margins) if margins else None

    rows = []
    counts = {"STAR":0,"CASH_COW":0,"PROBLEM":0,"DOG":0}
    for p, forecast, velocity, margin in base:
        buy = _latest(db, BuyBoxScoreSnapshot, tenant_id, p.id)
        buy_prob = _f(getattr(buy, "current_probability", None))
        ts = _title_score(db, tenant_id, p.id)
        stock_days = _stock_days(p, velocity, forecast)
        cls, high_turnover, good_margin = _classify(velocity, margin, med_velocity, med_margin)
        risk, opp = _scores(cls, stock_days=stock_days, buybox=buy_prob, title_score=ts, margin=margin, velocity=velocity)
        conf = _confidence(margin=margin, forecast=forecast, buybox=buy, title_score=ts, finance=latest_finance)
        warnings = []
        if margin is None:
            warnings.append("Margem real não disponível. Informe custos para melhorar análise.")
        if not forecast:
            warnings.append("Histórico de demanda indisponível; giro usa sold_quantity como proxy conservador.")
        if buy_prob is None:
            warnings.append("Buy Box indisponível para este produto.")
        if ts is None:
            warnings.append("Score de título indisponível; rode Otimização de Título para aumentar precisão.")
        recs = _recommendations(cls, stock_days=stock_days, buybox=buy_prob, title_score=ts, margin=margin)
        stock_qty = _f(p.available_quantity) if p.available_quantity is not None else _f(p.estoque)
        raw = {"median_sales_velocity": med_velocity, "median_margin": med_margin, "high_turnover": high_turnover, "good_margin": good_margin, "stock_days_remaining": stock_days, "stock_qty": stock_qty}
        if persist:
            db.add(PortfolioAnalysisSnapshot(tenant_id=tenant_id, product_id=p.id, portfolio_class=cls, sales_velocity=velocity, estimated_margin=margin, buybox_probability=buy_prob, title_score=ts, risk_score=risk, opportunity_score=opp, confidence=conf, recommendations_json=recs, warnings_json=warnings, raw_metrics_json=raw, generated_at=datetime.utcnow()))
            _make_action(db, tenant_id, p.id, cls, p.titulo or p.title or p.sku, risk, opp)
            _alert(db, tenant_id, p.id, cls, p.titulo or p.title or p.sku, stock_qty, stock_days, margin)
        counts[cls] += 1
        rows.append({
            "product_id": p.id, "external_product_id": p.external_product_id, "title": p.titulo or p.title or p.sku, "thumbnail": p.thumbnail, "price": _f(p.price) or _f(p.preco_base),
            "sales_velocity": velocity, "stock_days_remaining": stock_days, "estimated_margin": margin, "buybox_probability": buy_prob, "title_score": ts,
            "risk_score": risk, "opportunity_score": opp, "portfolio_class": cls, "portfolio_class_label": CLASS_LABELS[cls], "confidence": conf,
            "recommendations": recs, "warnings": warnings,
        })
    total = len(rows) or 1
    avg_margin = round(sum(m for m in margins)/len(margins), 4) if margins else None
    avg_velocity = round(sum(velocities)/len(velocities), 4) if velocities else 0
    health = int(max(0, min(100, (counts["STAR"]*100 + counts["CASH_COW"]*68 + counts["PROBLEM"]*55 + counts["DOG"]*25) / total)))
    if persist:
        db.commit()
    return {"summary": {"total_products": len(rows), "stars": counts["STAR"], "cows": counts["CASH_COW"], "problems": counts["PROBLEM"], "dogs": counts["DOG"], "avg_margin": avg_margin, "avg_sales_velocity": avg_velocity, "portfolio_health_score": health}, "products": rows, "generated_at": datetime.utcnow().isoformat()+"Z", "disclaimer": "Classificação interna SellerOS baseada nos dados disponíveis. Quanto mais dados financeiros e históricos, maior a precisão."}


def analyze_product(db: Session, tenant_id: str, product_id: str) -> dict[str, Any]:
    result = analyze_portfolio(db, tenant_id)
    for item in result["products"]:
        if str(item["product_id"]) == str(product_id):
            return {"product": item, "generated_at": result["generated_at"], "disclaimer": result["disclaimer"]}
    raise ValueError("Produto não encontrado para este tenant.")
