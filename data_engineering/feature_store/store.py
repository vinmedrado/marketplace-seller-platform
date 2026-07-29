"""data_engineering/feature_store/store.py — Feature Store com persistência e versionamento."""
import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd

from config.settings import FEATURE_STORE_DIR

log = logging.getLogger("msp.de.feature_store")

FEATURE_STORE_DIR = Path(FEATURE_STORE_DIR)
FEATURE_STORE_DIR.mkdir(parents=True, exist_ok=True)


def save_features(
    entity_id: str,
    entity_type: str,
    features: dict,
    dataset_version: str = "v1",
    dt: date = None,
) -> str:
    """Persiste features no feature store local (parquet por partição de data)."""
    dt     = dt or date.today()
    folder = FEATURE_STORE_DIR / entity_type / str(dt)
    folder.mkdir(parents=True, exist_ok=True)
    path   = folder / f"{entity_id}.json"
    record = {
        "entity_id":      entity_id,
        "entity_type":    entity_type,
        "dataset_version":dataset_version,
        "dt_feature":     str(dt),
        "features":       features,
    }
    path.write_text(json.dumps(record, indent=2))
    log.debug(f"Features salvas: {path}")
    return str(path)


def load_features(
    entity_id: str,
    entity_type: str,
    dt: date = None,
) -> Optional[dict]:
    """Carrega features de uma entidade para uma data."""
    dt     = dt or date.today()
    path   = FEATURE_STORE_DIR / entity_type / str(dt) / f"{entity_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("features")


def load_features_batch(entity_type: str, dt: date = None) -> pd.DataFrame:
    """Carrega todas as features de um tipo para uma data."""
    dt     = dt or date.today()
    folder = FEATURE_STORE_DIR / entity_type / str(dt)
    if not folder.exists():
        return pd.DataFrame()
    rows = []
    for f in folder.glob("*.json"):
        rec = json.loads(f.read_text())
        row = {"entity_id": rec["entity_id"], **rec.get("features", {})}
        rows.append(row)
    return pd.DataFrame(rows)


def list_versions(entity_type: str) -> list[str]:
    base = FEATURE_STORE_DIR / entity_type
    if not base.exists():
        return []
    return sorted([d.name for d in base.iterdir() if d.is_dir()], reverse=True)


def build_product_features(db, product_id: str, marketplace: str = "mercadolivre") -> dict:
    """Constrói e persiste features de um produto a partir dos dados do banco."""
    from models.orm import Product
    from scrapers.ml_scraper import get_competitor_stats
    from config.settings import MARKETPLACE_COMMISSIONS, TAX_RATE

    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        return {}

    conc = get_competitor_stats(db, product_id, marketplace)
    features = {
        "custo":                         float(product.custo or 0),
        "margem_minima":                 float(product.margem_minima or 0.10),
        "comissao_pct":                  MARKETPLACE_COMMISSIONS.get(marketplace, 0.14),
        "imposto_pct":                   TAX_RATE,
        "preco_concorrencia_min":        conc.get("preco_min", 0),
        "preco_concorrencia_med":        conc.get("preco_medio", 0),
        "preco_concorrencia_max":        conc.get("preco_max", 0),
        "n_concorrentes":                conc.get("n_ofertas", 0),
        "pct_frete_gratis_concorrentes": 0.5,
        "vendas_media_concorrentes":     conc.get("vendas_total", 0),
    }
    save_features(product_id, "product", features, marketplace)
    return features
