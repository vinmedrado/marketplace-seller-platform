"""ml/features/feature_engineering.py — Feature engineering para o modelo de precificação."""
import logging
import numpy as np
import pandas as pd
from typing import Optional

log = logging.getLogger("msp.ml.features")


FEATURE_NAMES = [
    "custo",
    "margem_minima",
    "comissao_pct",
    "imposto_pct",
    "preco_concorrencia_min",
    "preco_concorrencia_med",
    "preco_concorrencia_max",
    "spread_concorrencia",
    "n_concorrentes",
    "pct_frete_gratis_concorrentes",
    "vendas_media_concorrentes",
    "custo_x_conc_min_ratio",
    "custo_x_conc_med_ratio",
    "margem_sobre_min",
    "log_custo",
    "log_conc_min",
    "log_conc_med",
]


def build_features(row: dict) -> np.ndarray:
    """
    Constrói vetor de features a partir de um dicionário de dados do produto.
    Retorna array numpy compatível com o modelo treinado.
    """
    custo     = float(row.get("custo", 0) or 0)
    margem    = float(row.get("margem_minima", 0.10) or 0.10)
    comissao  = float(row.get("comissao_pct", 0.14) or 0.14)
    imposto   = float(row.get("imposto_pct",  0.06) or 0.06)

    conc_min  = float(row.get("preco_concorrencia_min", custo * 2) or custo * 2)
    conc_med  = float(row.get("preco_concorrencia_med", custo * 2.2) or custo * 2.2)
    conc_max  = float(row.get("preco_concorrencia_max", custo * 3) or custo * 3)
    n_conc    = float(row.get("n_concorrentes", 5) or 5)
    frete_pct = float(row.get("pct_frete_gratis_concorrentes", 0.5) or 0.5)
    vendas_m  = float(row.get("vendas_media_concorrentes", 10) or 10)

    spread    = conc_max - conc_min if conc_max > conc_min else 1.0
    r_min     = custo / conc_min if conc_min > 0 else 1.0
    r_med     = custo / conc_med if conc_med > 0 else 1.0
    m_sobre   = (conc_min * (1 + margem) - conc_min) / conc_min if conc_min > 0 else 0.0

    features = [
        custo,
        margem,
        comissao,
        imposto,
        conc_min,
        conc_med,
        conc_max,
        spread,
        n_conc,
        frete_pct,
        vendas_m,
        r_min,
        r_med,
        m_sobre,
        np.log1p(custo),
        np.log1p(conc_min),
        np.log1p(conc_med),
    ]
    return np.array(features, dtype=np.float64)


def build_features_df(rows: list[dict]) -> pd.DataFrame:
    """Constrói DataFrame de features a partir de lista de dicts."""
    arrays = [build_features(r) for r in rows]
    return pd.DataFrame(arrays, columns=FEATURE_NAMES)


def validate_features(features: np.ndarray) -> bool:
    """Verifica se features estão válidas (sem NaN/Inf)."""
    if np.any(np.isnan(features)):
        log.warning("Features contêm NaN")
        return False
    if np.any(np.isinf(features)):
        log.warning("Features contêm Inf")
        return False
    return True
