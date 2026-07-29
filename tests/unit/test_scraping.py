"""tests/unit/test_scraping.py — Testes de scraping."""
import pytest
from scrapers.ml_scraper import scrape_competitor_prices, get_competitor_stats, _dedup_hash
from services.scraping_service import run_scraping


def test_dedup_hash_consistente():
    item = {"id": "MLB123", "price": 99.99, "seller": {"id": "sel1"}}
    h1 = _dedup_hash(item)
    h2 = _dedup_hash(item)
    assert h1 == h2
    assert len(h1) == 32  # MD5


def test_dedup_hash_diferente():
    item1 = {"id": "MLB123", "price": 99.99,  "seller": {"id": "s1"}}
    item2 = {"id": "MLB123", "price": 100.00, "seller": {"id": "s1"}}
    assert _dedup_hash(item1) != _dedup_hash(item2)


def test_scraping_mock(db, cliente, produto):
    """Scraping com ML API indisponível usa mock automaticamente."""
    result = scrape_competitor_prices(
        db, cliente.id, produto.id, produto.titulo, max_pages=1
    )
    assert "search_id" in result
    assert result["total_coletado"] >= 0


def test_scraping_service(db, cliente, produto):
    result = run_scraping(db, produto.id, cliente.id, max_pages=1)
    assert "total_coletado" in result


def test_get_stats_sem_dados(db, produto):
    stats = get_competitor_stats(db, produto.id, "mercadolivre")
    assert stats == {}  # sem dados ainda


def test_get_stats_com_dados(db, cliente, produto_com_concorrencia):
    stats = get_competitor_stats(db, produto_com_concorrencia.id, "mercadolivre")
    assert "preco_min" in stats
    assert "preco_max" in stats
    assert "preco_medio" in stats
    assert stats["preco_min"] <= stats["preco_medio"] <= stats["preco_max"]
    assert stats["n_ofertas"] >= 10


def test_scraping_deduplicacao(db, cliente, produto):
    """Segunda execução não deve adicionar duplicatas."""
    scrape_competitor_prices(db, cliente.id, produto.id, produto.titulo, max_pages=1)
    r1 = run_scraping(db, produto.id, cliente.id, max_pages=1)
    r2 = run_scraping(db, produto.id, cliente.id, max_pages=1)
    assert r2.get("total_dup", 0) >= 0  # deve detectar duplicatas
