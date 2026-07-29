"""data_engineering/pipelines/staging_pipeline.py — Camada STAGING: limpeza e qualidade."""
import logging
from datetime import date
from sqlalchemy.orm import Session
from models.orm import CompetitorOffer, CompetitorSearch

log = logging.getLogger("msp.de.staging")

PRECO_MIN = 0.01
PRECO_MAX = 999_999.0
OUTLIER_IQR_FACTOR = 2.5


def process_staging(db: Session, cliente_id: str, marketplace: str, dt: date = None) -> dict:
    """
    Camada staging:
    - Remove outliers de preço via IQR
    - Garante campos obrigatórios
    - Marca dt_staging
    Retorna estatísticas.
    """
    dt = dt or date.today()
    offers = (
        db.query(CompetitorOffer)
        .join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id)
        .filter(
            CompetitorSearch.cliente_id == cliente_id,
            CompetitorSearch.marketplace == marketplace,
            CompetitorOffer.dt_raw == dt,
            CompetitorOffer.dt_staging == None,
        )
        .all()
    )

    if not offers:
        log.info(f"STAGING [{marketplace}] {dt}: nada a processar")
        return {"total": 0, "validos": 0, "removidos": 0}

    precos = [float(o.preco) for o in offers if o.preco and float(o.preco) > 0]
    q1, q3 = _quartiles(precos)
    iqr    = q3 - q1
    lower  = q1 - OUTLIER_IQR_FACTOR * iqr
    upper  = q3 + OUTLIER_IQR_FACTOR * iqr

    validos = removidos = 0
    for offer in offers:
        preco = float(offer.preco or 0)
        if preco < PRECO_MIN or preco > PRECO_MAX or preco < lower or preco > upper:
            db.delete(offer)
            removidos += 1
        elif not offer.titulo or len(offer.titulo) < 3:
            db.delete(offer)
            removidos += 1
        else:
            offer.dt_staging = dt
            validos += 1

    db.commit()
    log.info(f"STAGING [{marketplace}] {dt}: validos={validos} removidos={removidos}")
    return {"total": len(offers), "validos": validos, "removidos": removidos}


def _quartiles(data: list[float]) -> tuple[float, float]:
    if not data:
        return 0.0, 0.0
    s = sorted(data)
    n = len(s)
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    return q1, q3
