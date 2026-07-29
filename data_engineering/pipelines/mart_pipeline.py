"""data_engineering/pipelines/mart_pipeline.py — Camada MART: agregações analíticas."""
import logging
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.orm import CompetitorOffer, CompetitorSearch, PricingResult

log = logging.getLogger("msp.de.mart")


def build_pricing_mart(db: Session, cliente_id: str, marketplace: str, dt: date = None) -> dict:
    """
    Agrega dados da concorrência + resultados de pricing em visão analítica.
    """
    dt = dt or date.today()
    result = (
        db.query(
            CompetitorSearch.product_id,
            func.min(CompetitorOffer.preco).label("preco_min"),
            func.max(CompetitorOffer.preco).label("preco_max"),
            func.avg(CompetitorOffer.preco).label("preco_medio"),
            func.count(CompetitorOffer.id).label("n_ofertas"),
            func.sum(CompetitorOffer.vendas).label("vendas_total"),
        )
        .join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id)
        .filter(
            CompetitorSearch.cliente_id == cliente_id,
            CompetitorSearch.marketplace == marketplace,
            CompetitorOffer.dt_staging == dt,
        )
        .group_by(CompetitorSearch.product_id)
        .all()
    )

    mart_rows = []
    for r in result:
        mart_rows.append({
            "product_id":  str(r.product_id),
            "dt":          str(dt),
            "marketplace": marketplace,
            "preco_min":   float(r.preco_min or 0),
            "preco_max":   float(r.preco_max or 0),
            "preco_medio": float(r.preco_medio or 0),
            "n_ofertas":   r.n_ofertas,
            "vendas_total": r.vendas_total or 0,
        })

    log.info(f"MART [{marketplace}] {dt}: {len(mart_rows)} produtos")
    return {"dt": str(dt), "marketplace": marketplace, "rows": mart_rows}


def run_full_pipeline(db: Session, cliente_id: str, marketplace: str, dt: date = None) -> dict:
    """Executa RAW → STAGING → MART em sequência."""
    from data_engineering.pipelines.raw_pipeline     import ingest_raw_offers
    from data_engineering.pipelines.staging_pipeline import process_staging
    dt = dt or date.today()
    raw     = ingest_raw_offers(db, cliente_id, marketplace, dt)
    staging = process_staging(db, cliente_id, marketplace, dt)
    mart    = build_pricing_mart(db, cliente_id, marketplace, dt)
    return {"raw": raw, "staging": staging, "mart": mart}
