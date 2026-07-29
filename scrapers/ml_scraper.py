"""scrapers/ml_scraper.py — Scraping de concorrência no Mercado Livre."""
import hashlib
import logging
import random
import time
from datetime import date
from sqlalchemy.orm import Session
from integrations.mercadolivre.api import search_items
from models.orm import CompetitorSearch, CompetitorOffer
from config.settings import SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX, SCRAPING_MAX_PAGES

log = logging.getLogger("msp.scraper.ml")


def _dedup_hash(item: dict) -> str:
    key = f"{item.get('id','')}{item.get('price','')}{item.get('seller',{}).get('id','')}"
    return hashlib.md5(key.encode()).hexdigest()


def scrape_competitor_prices(
    db: Session,
    cliente_id: str,
    product_id: str,
    query: str,
    max_pages: int = None,
) -> dict:
    """
    Scraping de preços de concorrência.
    Retorna estatísticas e persiste no banco.
    """
    max_pages = max_pages or SCRAPING_MAX_PAGES
    t_start = time.time()

    # Cria registro de busca
    search = CompetitorSearch(
        cliente_id  = cliente_id,
        product_id  = product_id,
        marketplace = "mercadolivre",
        query       = query,
        status      = "running",
        dt_raw      = date.today(),
    )
    db.add(search); db.commit(); db.refresh(search)

    total_coletado = 0
    total_novo     = 0
    total_dup      = 0
    precos         = []

    try:
        for page in range(max_pages):
            offset = page * 50
            log.info(f"Scraping '{query}' — página {page+1}/{max_pages}")
            data = search_items(query, limit=50, offset=offset)
            results = data.get("results", [])
            if not results:
                break

            for item in results:
                total_coletado += 1
                h = _dedup_hash(item)

                # Verifica duplicata
                existe = db.query(CompetitorOffer).filter_by(
                    search_id=search.id, hash_dedup=h
                ).first()
                if existe:
                    total_dup += 1
                    continue

                preco = float(item.get("price") or 0)
                if preco > 0:
                    precos.append(preco)

                offer = CompetitorOffer(
                    search_id    = search.id,
                    cliente_id   = cliente_id,
                    marketplace  = "mercadolivre",
                    titulo       = item.get("title", ""),
                    preco        = preco,
                    preco_original = float(item.get("original_price") or preco),
                    vendedor     = item.get("seller", {}).get("nickname", ""),
                    reputacao    = str(item.get("seller", {}).get("power_seller_status", "")),
                    vendas       = int(item.get("sold_quantity") or 0),
                    frete_gratis = item.get("shipping", {}).get("free_shipping", False),
                    url          = item.get("permalink", ""),
                    thumbnail    = item.get("thumbnail", ""),
                    hash_dedup   = h,
                    dt_raw       = date.today(),
                )
                db.add(offer)
                total_novo += 1

            db.commit()

            # Respeita delay entre páginas
            if page < max_pages - 1:
                delay = random.uniform(SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX)
                time.sleep(delay)

            total_pages = data.get("paging", {}).get("total", 0) // 50 + 1
            if page + 1 >= min(max_pages, total_pages):
                break

        # Atualiza search
        search.status      = "completed"
        search.total_found = total_coletado
        db.commit()

        stats = {
            "search_id":      search.id,
            "total_coletado": total_coletado,
            "total_novo":     total_novo,
            "total_dup":      total_dup,
            "preco_min":      round(min(precos), 2) if precos else None,
            "preco_max":      round(max(precos), 2) if precos else None,
            "preco_medio":    round(sum(precos) / len(precos), 2) if precos else None,
            "duracao_s":      round(time.time() - t_start, 2),
        }
        log.info(f"Scraping concluído: {stats}")
        return stats

    except Exception as e:
        search.status = "failed"
        db.commit()
        log.error(f"Erro no scraping: {e}")
        raise


def get_competitor_stats(db, product_id, marketplace="mercadolivre"):
    """
    Retorna estatísticas de preço da concorrência.
    Cálculo Python puro: compatível com SQLite e PostgreSQL.
    """
    rows = (
        db.query(CompetitorOffer.preco, CompetitorOffer.vendas)
        .join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id)
        .filter(
            CompetitorSearch.product_id == product_id,
            CompetitorSearch.marketplace == marketplace,
            CompetitorOffer.preco.isnot(None),
            CompetitorOffer.preco > 0,
        )
        .all()
    )
    if not rows:
        return {}

    precos = sorted([float(r.preco) for r in rows])
    vendas = [int(r.vendas or 0) for r in rows]
    n = len(precos)

    def _pct(data, p):
        idx = (p / 100.0) * (len(data) - 1)
        lo, hi = int(idx), min(int(idx) + 1, len(data) - 1)
        return data[lo] + (data[hi] - data[lo]) * (idx - lo)

    return {
        "preco_min":    round(precos[0], 2),
        "preco_max":    round(precos[-1], 2),
        "preco_medio":  round(sum(precos) / n, 2),
        "p25":          round(_pct(precos, 25), 2),
        "p50":          round(_pct(precos, 50), 2),
        "p75":          round(_pct(precos, 75), 2),
        "n_ofertas":    n,
        "vendas_total": sum(vendas),
    }
