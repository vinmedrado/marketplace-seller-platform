"""scripts/train_pricing_model.py — Treina modelo de precificação."""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.logging_config import setup_logging

log = setup_logging("train_pricing_model")


def run(marketplace: str = "mercadolivre", model_type: str = "random_forest", force: bool = True):
    log.info(f"Treinando modelo: marketplace={marketplace} model_type={model_type}")

    # Tenta com DB real primeiro, senão usa dados sintéticos
    try:
        from db.base import SessionLocal
        db = SessionLocal()
        try:
            from services.ml_service import train_model
            result = train_model(db, marketplace=marketplace, model_type=model_type, force=force)
        finally:
            db.close()
    except Exception as e:
        log.warning(f"Banco indisponível ({e}). Treinando com dados sintéticos.")
        result = _train_synthetic(marketplace, model_type)

    log.info("=" * 50)
    log.info(f"✅ Treino concluído:")
    log.info(f"   MAE  = {result.get('mae', 'N/A')}")
    log.info(f"   RMSE = {result.get('rmse', result.get('mae', 'N/A'))}")
    log.info(f"   R²   = {result.get('r2', 'N/A')}")
    log.info(f"   N    = {result.get('n_samples', 'N/A')} amostras")
    log.info(f"   Path = {result.get('model_path', 'N/A')}")
    log.info("=" * 50)
    return result


def _train_synthetic(marketplace: str, model_type: str) -> dict:
    from ml.datasets.dataset_builder import build_dataset_from_db, save_dataset
    from ml.training.trainer import train

    df, version = None, "synthetic"
    df = build_dataset_from_db(db=None, marketplace=marketplace)
    _, version  = save_dataset(df, marketplace)
    return train(df, marketplace, model_type, dataset_version=version)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Treina modelo de precificação")
    p.add_argument("--marketplace",  default="mercadolivre")
    p.add_argument("--model-type",   default="random_forest", choices=["random_forest", "gradient_boosting"])
    p.add_argument("--force",        action="store_true", default=True)
    args = p.parse_args()
    run(args.marketplace, args.model_type, args.force)
