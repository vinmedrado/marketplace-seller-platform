"""scripts/run_pipeline.py — Executa pipeline de dados manualmente."""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.logging_config import setup_logging

log = setup_logging("run_pipeline")


def run(cliente_id: str = None, marketplace: str = "mercadolivre", steps: list = None):
    steps = steps or ["scraping", "staging", "mart", "pricing"]

    try:
        from db.base import SessionLocal
        db = SessionLocal()
    except Exception as e:
        log.error(f"Banco indisponível: {e}")
        sys.exit(1)

    try:
        from models.orm import Cliente, Product

        if cliente_id:
            clientes = db.query(Cliente).filter_by(id=cliente_id, ativo=True).all()
        else:
            clientes = db.query(Cliente).filter_by(ativo=True).all()

        if not clientes:
            log.warning("Nenhum cliente ativo encontrado. Execute scripts/seed_demo.py primeiro.")
            return

        for cliente in clientes:
            log.info(f"Pipeline para {cliente.nome} [{cliente.id}]")
            products = db.query(Product).filter_by(cliente_id=cliente.id, ativo=True).all()
            log.info(f"  {len(products)} produto(s)")

            if "scraping" in steps:
                log.info("  [1/4] Scraping...")
                from services.scraping_service import run_scraping
                for p in products[:3]:  # limita para demo
                    try:
                        r = run_scraping(db, p.id, cliente.id, marketplace, max_pages=2)
                        log.info(f"    {p.sku}: {r.get('total_novo', 0)} novos")
                    except Exception as e:
                        log.error(f"    {p.sku}: {e}")

            if "staging" in steps:
                log.info("  [2/4] Staging...")
                from data_engineering.pipelines.staging_pipeline import process_staging
                r = process_staging(db, cliente.id, marketplace)
                log.info(f"    validos={r['validos']} removidos={r['removidos']}")

            if "mart" in steps:
                log.info("  [3/4] Mart...")
                from data_engineering.pipelines.mart_pipeline import build_pricing_mart
                r = build_pricing_mart(db, cliente.id, marketplace)
                log.info(f"    {len(r['rows'])} produtos agregados")

            if "pricing" in steps:
                log.info("  [4/4] Pricing...")
                from pricing.engine import batch_price
                results = batch_price(db, cliente.id, marketplace, "ml_assisted")
                ok  = sum(1 for r in results if "preco_sugerido" in r)
                err = len(results) - ok
                log.info(f"    ok={ok} erros={err}")

        log.info("✅ Pipeline concluído")

    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Executa pipeline de dados")
    p.add_argument("--cliente-id",   default=None)
    p.add_argument("--marketplace",  default="mercadolivre")
    p.add_argument("--steps",        nargs="+", default=["scraping", "staging", "mart", "pricing"])
    args = p.parse_args()
    run(args.cliente_id, args.marketplace, args.steps)
