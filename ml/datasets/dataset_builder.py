"""Dataset builder realista para o motor de pricing.

Compatível com uso em produção/demo/testes:
- lê produtos, concorrência e histórico de pricing do banco quando disponíveis;
- gera fallback sintético seguro quando a base ainda está vazia;
- normaliza/valida colunas antes do treino.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import MARKETPLACE_COMMISSIONS, TAX_RATE, ML_MIN_MARGIN
from models.orm import Product, PricingResult
from scrapers.ml_scraper import get_competitor_stats

DATASET_DIR = Path("storage/ml_datasets")
REQUIRED_COLUMNS = [
    "custo", "margem_minima", "comissao_pct", "imposto_pct", "markup_pct",
    "preco_concorrencia_min", "preco_concorrencia_med", "preco_concorrencia_max",
    "n_concorrentes", "pct_frete_gratis_concorrentes", "vendas_media_concorrentes",
    "estoque", "preco_base", "preco_ideal",
]


def _as_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _row_from_product(db: Session, product: Product, marketplace: str) -> dict:
    conc = get_competitor_stats(db, product.id, marketplace) or {}
    last = (
        db.query(PricingResult)
        .filter_by(product_id=product.id, cliente_id=product.cliente_id, marketplace=marketplace)
        .order_by(PricingResult.criado_em.desc())
        .first()
    )
    custo = _as_float(product.custo, 1.0)
    margem = _as_float(product.margem_minima, ML_MIN_MARGIN)
    comissao = MARKETPLACE_COMMISSIONS.get(marketplace, 0.14)
    imposto = TAX_RATE
    preco_base = _as_float(product.preco_base, custo * 2)
    conc_med = _as_float(conc.get("preco_medio"), preco_base)
    preco_ideal = _as_float(getattr(last, "preco_sugerido", None), max(preco_base, conc_med * 0.99))
    markup = max((preco_ideal - custo) / preco_ideal - comissao - imposto, margem) if preco_ideal > 0 else margem + 0.1
    return {
        "custo": custo,
        "margem_minima": margem,
        "comissao_pct": comissao,
        "imposto_pct": imposto,
        "markup_pct": markup,
        "preco_concorrencia_min": _as_float(conc.get("preco_min"), preco_base * 0.85),
        "preco_concorrencia_med": conc_med,
        "preco_concorrencia_max": _as_float(conc.get("preco_max"), preco_base * 1.18),
        "n_concorrentes": int(conc.get("n_ofertas") or 0),
        "pct_frete_gratis_concorrentes": 0.5,
        "vendas_media_concorrentes": max(1, int((conc.get("vendas_total") or 100) / max(int(conc.get("n_ofertas") or 1), 1))),
        "estoque": int(product.estoque or 0),
        "preco_base": preco_base,
        "preco_ideal": preco_ideal,
    }


def _generate_fake_dataset(n: int = 300, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    for _ in range(n):
        custo = round(rng.uniform(18, 620), 2)
        margem = round(rng.uniform(0.10, 0.32), 4)
        comissao = rng.choice([0.11, 0.12, 0.14, 0.16])
        imposto = rng.choice([0.04, 0.06, 0.08])
        markup = round(margem + rng.uniform(0.06, 0.22), 4)
        preco_minimo = custo / max(1 - comissao - imposto - margem, 0.01)
        preco_base = custo / max(1 - comissao - imposto - markup, 0.01)
        noise = rng.uniform(0.92, 1.14)
        conc_med = preco_base * rng.uniform(0.90, 1.18)
        conc_min = conc_med * rng.uniform(0.82, 0.95)
        conc_max = conc_med * rng.uniform(1.05, 1.32)
        ideal = max(preco_minimo, (preco_base * 0.65 + conc_med * 0.35) * noise)
        rows.append({
            "custo": round(custo, 2),
            "margem_minima": margem,
            "comissao_pct": comissao,
            "imposto_pct": imposto,
            "markup_pct": markup,
            "preco_concorrencia_min": round(conc_min, 2),
            "preco_concorrencia_med": round(conc_med, 2),
            "preco_concorrencia_max": round(conc_max, 2),
            "n_concorrentes": rng.randint(3, 40),
            "pct_frete_gratis_concorrentes": round(rng.random(), 3),
            "vendas_media_concorrentes": rng.randint(1, 260),
            "estoque": rng.randint(0, 250),
            "preco_base": round(preco_base, 2),
            "preco_ideal": round(ideal, 2),
        })
    return rows


def normalize_pricing_dataset(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        df = pd.DataFrame(_generate_fake_dataset(300))
    df = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    for col in REQUIRED_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([float("inf"), float("-inf")], pd.NA).dropna(subset=["custo", "preco_ideal"])
    defaults = {
        "margem_minima": ML_MIN_MARGIN, "comissao_pct": 0.14, "imposto_pct": TAX_RATE,
        "markup_pct": 0.25, "n_concorrentes": 0, "pct_frete_gratis_concorrentes": 0.0,
        "vendas_media_concorrentes": 0, "estoque": 0,
    }
    for col, default in defaults.items():
        df[col] = df[col].fillna(default)
    df["preco_base"] = df["preco_base"].fillna(df["custo"] * 2)
    df["preco_concorrencia_med"] = df["preco_concorrencia_med"].fillna(df["preco_base"])
    df["preco_concorrencia_min"] = df["preco_concorrencia_min"].fillna(df["preco_concorrencia_med"] * 0.9)
    df["preco_concorrencia_max"] = df["preco_concorrencia_max"].fillna(df["preco_concorrencia_med"] * 1.1)
    df = df[df["custo"] > 0]
    df = df[df["preco_ideal"] > df["custo"]]
    return df[REQUIRED_COLUMNS].reset_index(drop=True)


def validate_training_dataset(df: pd.DataFrame, min_rows: int = 50) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if df is None or df.empty:
        return False, ["dataset vazio"]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"colunas ausentes: {', '.join(missing)}")
    if len(df) < min_rows:
        errors.append(f"amostras insuficientes: {len(df)} < {min_rows}")
    if "preco_ideal" in df and (df["preco_ideal"] <= 0).any():
        errors.append("preco_ideal inválido")
    return not errors, errors


def build_training_dataset(
    db: Session | None = None,
    marketplace: str = "mercadolivre",
    min_rows: int = 200,
    tenant_id: str | None = None,
) -> pd.DataFrame:
    rows: list[dict] = []
    if db is not None:
        query = db.query(Product).filter_by(ativo=True)
        if tenant_id is not None:
            query = query.filter(Product.cliente_id == tenant_id)
        products = query.all()
        rows = [_row_from_product(db, p, marketplace) for p in products]
    if len(rows) < min_rows:
        rows.extend(_generate_fake_dataset(min_rows - len(rows)))
    df = normalize_pricing_dataset(pd.DataFrame(rows))
    ok, errors = validate_training_dataset(df, min_rows=min(50, min_rows))
    if not ok:
        raise ValueError("Dataset de treino inválido: " + "; ".join(errors))
    return df


def build_dataset_from_db(
    db: Session | None = None,
    marketplace: str = "mercadolivre",
    tenant_id: str | None = None,
) -> pd.DataFrame:
    return build_training_dataset(db, marketplace, tenant_id=tenant_id)


def _dataset_version(df: pd.DataFrame, marketplace: str) -> str:
    payload = json.dumps({"marketplace": marketplace, "rows": len(df), "sum": round(float(df["preco_ideal"].sum()), 2)}, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def save_dataset(df: pd.DataFrame, marketplace: str = "mercadolivre"):
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    version = f"{marketplace}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{_dataset_version(df, marketplace)}"
    path = DATASET_DIR / f"pricing_dataset_{version}.parquet"
    try:
        df.to_parquet(path, index=False)
    except Exception:
        path = path.with_suffix(".csv")
        df.to_csv(path, index=False)
    return str(path), version

# Compatibilidade com o serviço legado: procura o dataset mais recente salvo.
def load_latest_dataset(marketplace: str = "mercadolivre"):
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DATASET_DIR.glob(f"pricing_dataset_{marketplace}_*.parquet")) or sorted(DATASET_DIR.glob(f"pricing_dataset_{marketplace}_*.csv"))
    if not files:
        return None, None
    path = files[-1]
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    return normalize_pricing_dataset(df), path.stem.replace("pricing_dataset_", "")
