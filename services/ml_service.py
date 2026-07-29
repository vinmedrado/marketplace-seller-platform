"""services/ml_service.py — Orquestração de treino e predição de ML."""
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from ml.datasets.dataset_builder import build_dataset_from_db, save_dataset
from ml.training.trainer import train
from ml.inference.predictor import predict_price, reload_model
from models.orm import MLTrainingRun, MLPrediction, Product
from pricing.engine import calculate_price

log = logging.getLogger("msp.service.ml")


def train_model(
    db: Session,
    marketplace: str = "mercadolivre",
    model_type: str = "random_forest",
    force: bool = False,
    tenant_id: str | None = None,
) -> dict:
    """Treina (ou retreina) modelo de precificação."""
    model_scope = f"{marketplace}__{tenant_id}" if tenant_id else marketplace
    run = MLTrainingRun(
        run_name        = f"pricing_{model_scope}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        model_type      = model_type,
        marketplace     = marketplace,
        status          = "running",
    )
    db.add(run); db.commit(); db.refresh(run)

    try:
        df, version = _get_or_build_dataset(db, marketplace, model_scope, force, tenant_id)
        meta = train(df, model_scope, model_type, dataset_version=version)

        run.status           = "completed"
        run.dataset_version  = version
        run.dataset_hash     = meta.get("dataset_version", "")
        run.n_samples        = meta["n_samples"]
        run.n_features       = meta["n_features"]
        run.mae              = meta["mae"]
        run.rmse             = meta["rmse"]
        run.r2               = meta["r2"]
        run.params           = meta
        run.feature_importance = meta.get("feature_importance", {})
        run.model_path       = meta["model_path"]
        run.finalizado_em    = datetime.utcnow()
        db.commit()

        reload_model(model_scope)
        log.info(f"Treino concluído: R²={meta['r2']:.4f} | MAE={meta['mae']:.2f}")
        return {
            "run_id":     run.id,
            "status":     "completed",
            "mae":        meta["mae"],
            "r2":         meta["r2"],
            "n_samples":  meta["n_samples"],
            "model_path": meta["model_path"],
        }

    except Exception as e:
        run.status = "failed"
        db.commit()
        log.error(f"Treino falhou: {e}")
        raise


def predict_for_product(
    db: Session,
    product_id: str,
    cliente_id: str,
    marketplace: str = "mercadolivre",
) -> dict:
    """Gera predição ML e salva na tabela ml_predictions."""
    product = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not product:
        raise ValueError(f"Produto {product_id} não encontrado")

    from scrapers.ml_scraper import get_competitor_stats
    from config.settings import MARKETPLACE_COMMISSIONS, TAX_RATE
    conc = get_competitor_stats(db, product_id, marketplace)

    row = {
        "custo":                         float(product.custo or 0),
        "margem_minima":                 float(product.margem_minima or 0.10),
        "comissao_pct":                  MARKETPLACE_COMMISSIONS.get(marketplace, 0.14),
        "imposto_pct":                   TAX_RATE,
        "preco_concorrencia_min":        conc.get("preco_min"),
        "preco_concorrencia_med":        conc.get("preco_medio"),
        "preco_concorrencia_max":        conc.get("preco_max"),
        "n_concorrentes":                conc.get("n_ofertas", 0),
        "pct_frete_gratis_concorrentes": 0.5,
        "vendas_media_concorrentes":     20,
    }

    model_scope = f"{marketplace}__{cliente_id}"
    result = predict_price(row, model_scope)

    pred = MLPrediction(
        product_id            = product_id,
        cliente_id            = cliente_id,
        marketplace           = marketplace,
        preco_previsto        = result["preco_previsto"],
        score_competitividade = result["score_competitividade"],
        margem_prevista       = result["margem_prevista"],
        confianca             = result["confianca"],
        features_usadas       = row,
    )
    db.add(pred); db.commit(); db.refresh(pred)
    result["prediction_id"] = pred.id
    return result


def _get_or_build_dataset(db, marketplace, model_scope, force, tenant_id=None):
    from ml.datasets.dataset_builder import load_latest_dataset, build_dataset_from_db, save_dataset
    if not force:
        df, version = load_latest_dataset(model_scope)
        if df is not None and len(df) >= 100:
            return df, version
    df = build_dataset_from_db(db, marketplace, tenant_id=tenant_id)
    path, version = save_dataset(df, model_scope)
    return df, version
