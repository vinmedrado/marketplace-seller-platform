"""data_engineering/pipelines/raw_pipeline.py — Camada RAW: ingestão bruta."""
import logging
from datetime import date
from sqlalchemy.orm import Session
from models.orm import CompetitorOffer, CompetitorSearch

log = logging.getLogger("msp.de.raw")


def ingest_raw_offers(db: Session, cliente_id: str, marketplace: str, dt: date = None) -> int:
    """
    Coleta ofertas brutas do banco e aplica metadata de particionamento.
    Retorna total de registros na camada RAW.
    """
    dt = dt or date.today()
    total = (
        db.query(CompetitorOffer)
        .join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id)
        .filter(
            CompetitorSearch.cliente_id == cliente_id,
            CompetitorSearch.marketplace == marketplace,
            CompetitorOffer.dt_raw == dt,
        )
        .count()
    )
    log.info(f"RAW [{marketplace}] {dt}: {total} registros")
    return total
