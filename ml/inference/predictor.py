"""ml/inference/predictor.py — Inferência com fallback automático."""
import json
import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from config.settings import ML_MODELS_DIR, ML_MIN_MARGIN
from ml.features.feature_engineering import build_features, validate_features

log = logging.getLogger("msp.ml.inference")

_MODEL_CACHE: dict = {}


def _load_model(marketplace: str) -> Optional[dict]:
    if marketplace in _MODEL_CACHE:
        return _MODEL_CACHE[marketplace]
    path = ML_MODELS_DIR / f"pricing_{marketplace}_latest.joblib"
    if not path.exists():
        log.warning(f"Modelo não encontrado: {path}. Usando fallback rule-based.")
        return None
    try:
        artifact = joblib.load(path)
        _MODEL_CACHE[marketplace] = artifact
        log.info(f"Modelo carregado: {path}")
        return artifact
    except Exception as e:
        log.error(f"Erro ao carregar modelo: {e}")
        return None


def predict_price(row: dict, marketplace: str = "mercadolivre") -> dict:
    """
    Prevê preço ideal usando ML se disponível, senão fallback rule-based.
    Nunca viola custo + margem mínima.
    """
    custo    = float(row.get("custo", 0) or 0)
    margem   = float(row.get("margem_minima", ML_MIN_MARGIN) or ML_MIN_MARGIN)
    comissao = float(row.get("comissao_pct", 0.14) or 0.14)
    imposto  = float(row.get("imposto_pct",  0.06) or 0.06)
    preco_minimo = custo / max(1 - comissao - imposto - margem, 0.01)

    artifact = _load_model(marketplace)

    if artifact is None:
        preco = _rule_based_price(row)
        return {
            "preco_previsto":         round(max(preco, preco_minimo), 2),
            "score_competitividade":  _competitividade(preco, row),
            "margem_prevista":        round((preco - custo) / preco, 4) if preco > 0 else 0,
            "confianca":              0.5,
            "ml_usado":               False,
            "motivo":                 "fallback_rule_based",
        }

    try:
        features = build_features(row)
        if not validate_features(features):
            raise ValueError("Features inválidas")

        pipeline      = artifact["pipeline"]
        feature_names = artifact.get("feature_names", [])

        # Se o modelo foi treinado com subconjunto de features, usa só as que ele conhece
        if feature_names and len(feature_names) != len(features):
            from ml.features.feature_engineering import FEATURE_NAMES
            row_dict = dict(zip(FEATURE_NAMES, features.tolist()))
            features = np.array([row_dict.get(f, 0.0) for f in feature_names], dtype=np.float64)

        preco_ml = float(pipeline.predict([features])[0])
        preco_ml = max(preco_ml, preco_minimo)

        # Explicabilidade via feature importance (se RF)
        importances = {}
        model = pipeline.named_steps.get("model")
        if hasattr(model, "feature_importances_") and feature_names:
            top = sorted(
                zip(feature_names, features, model.feature_importances_),
                key=lambda x: x[2], reverse=True
            )[:5]
            importances = {n: {"valor": round(float(v), 4), "importancia": round(float(i), 4)}
                           for n, v, i in top}

        return {
            "preco_previsto":         round(preco_ml, 2),
            "score_competitividade":  _competitividade(preco_ml, row),
            "margem_prevista":        round((preco_ml - custo) / preco_ml, 4) if preco_ml > 0 else 0,
            "confianca":              0.82,
            "ml_usado":               True,
            "motivo":                 "ml_prediction",
            "feature_importance_top": importances,
        }
    except Exception as e:
        log.error(f"Erro na inferência ML: {e}. Usando fallback.")
        preco = _rule_based_price(row)
        return {
            "preco_previsto":        round(max(preco, preco_minimo), 2),
            "score_competitividade": _competitividade(preco, row),
            "margem_prevista":       round((preco - custo) / preco, 4) if preco > 0 else 0,
            "confianca":             0.4,
            "ml_usado":              False,
            "motivo":                f"fallback_erro: {e}",
        }


def _rule_based_price(row: dict) -> float:
    custo    = float(row.get("custo", 0) or 0)
    margem   = float(row.get("margem_minima", 0.10) or 0.10)
    comissao = float(row.get("comissao_pct", 0.14) or 0.14)
    imposto  = float(row.get("imposto_pct",  0.06) or 0.06)
    markup   = margem + 0.10

    preco_base = custo / max(1 - comissao - imposto - markup, 0.01)

    conc_min = float(row.get("preco_concorrencia_min") or 0)
    conc_med = float(row.get("preco_concorrencia_med") or 0)
    if conc_min > 0 and conc_med > 0:
        preco_comp = conc_min * 0.40 + conc_med * 0.60
        preco_base = min(preco_base, preco_comp * 1.02)

    return round(preco_base, 2)


def _competitividade(preco: float, row: dict) -> float:
    conc_min = float(row.get("preco_concorrencia_min") or 0)
    conc_max = float(row.get("preco_concorrencia_max") or 0)
    if not conc_min or not conc_max or conc_max <= conc_min:
        return 0.5
    score = 1.0 - (preco - conc_min) / (conc_max - conc_min)
    return round(max(0.0, min(1.0, score)), 4)


def reload_model(marketplace: str = "mercadolivre"):
    """Força recarga do modelo do disco."""
    _MODEL_CACHE.pop(marketplace, None)
    return _load_model(marketplace) is not None
