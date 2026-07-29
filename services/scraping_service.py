"""services/scraping_service.py — Orquestração do scraping de concorrência."""
import logging
import time
from sqlalchemy.orm import Session
from models.orm import Product, ScrapingLog
from scrapers.ml_scraper import scrape_competitor_prices

log = logging.getLogger("msp.service.scraping")


def run_scraping(
    db: Session,
    product_id: str,
    cliente_id: str,
    marketplace: str = "mercadolivre",
    query: str = None,
    max_pages: int = 3,
) -> dict:
    product = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not product:
        raise ValueError(f"Produto {product_id} não encontrado")

    query = query or product.titulo_otimizado or product.titulo
    t0    = time.time()
    try:
        stats  = scrape_competitor_prices(db, cliente_id, product_id, query, max_pages)
        status = "completed"
        erro   = None
    except Exception as e:
        stats  = {"total_coletado": 0, "total_novo": 0, "total_dup": 0}
        status = "failed"
        erro   = str(e)
        log.error(f"Scraping falhou: {e}")

    entry = ScrapingLog(
        cliente_id     = cliente_id,
        marketplace    = marketplace,
        query          = query,
        status         = status,
        total_coletado = stats.get("total_coletado", 0),
        total_novo     = stats.get("total_novo", 0),
        total_dup      = stats.get("total_dup", 0),
        erro           = erro,
        duracao_ms     = int((time.time() - t0) * 1000),
    )
    db.add(entry)
    db.commit()
    return stats
