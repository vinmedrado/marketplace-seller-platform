"""tests/unit/test_ml.py — Testes do pipeline de ML."""
import pytest
import numpy as np
import pandas as pd
from ml.features.feature_engineering import build_features, build_features_df, validate_features, FEATURE_NAMES
from ml.datasets.dataset_builder import build_dataset_from_db, _generate_fake_dataset
from ml.inference.predictor import predict_price, _rule_based_price


def test_build_features_shape():
    row = {"custo": 100, "margem_minima": 0.10, "comissao_pct": 0.14, "imposto_pct": 0.06}
    features = build_features(row)
    assert len(features) == len(FEATURE_NAMES)
    assert features.dtype == np.float64


def test_build_features_no_nan():
    row = {"custo": 100}  # valores mínimos
    features = build_features(row)
    assert not np.any(np.isnan(features))
    assert not np.any(np.isinf(features))


def test_validate_features_ok():
    row = {"custo": 100, "comissao_pct": 0.14, "imposto_pct": 0.06}
    f   = build_features(row)
    assert validate_features(f) == True


def test_validate_features_nan():
    f = np.array([np.nan] * len(FEATURE_NAMES))
    assert validate_features(f) == False


def test_build_features_df():
    rows = [{"custo": 50 + i} for i in range(10)]
    df   = build_features_df(rows)
    assert len(df) == 10
    assert list(df.columns) == FEATURE_NAMES


def test_fake_dataset_generation():
    rows = _generate_fake_dataset(100)
    assert len(rows) == 100
    for r in rows:
        assert r["custo"] > 0
        assert r["preco_ideal"] > r["custo"]


def test_build_dataset_without_db():
    df = build_dataset_from_db(db=None, marketplace="mercadolivre")
    assert len(df) >= 200
    assert "preco_ideal" in df.columns
    assert "custo" in df.columns


def test_predict_price_fallback():
    """Sem modelo treinado, deve usar fallback sem quebrar."""
    row    = {"custo": 100, "margem_minima": 0.10, "comissao_pct": 0.14, "imposto_pct": 0.06}
    result = predict_price(row, "mercadolivre")
    assert result["preco_previsto"] > 0
    assert result["preco_previsto"] >= 100  # nunca abaixo do custo
    assert 0 <= result["confianca"] <= 1
    assert "motivo" in result


def test_predict_price_respects_min_margin():
    row = {
        "custo": 100,
        "margem_minima": 0.30,
        "comissao_pct":  0.14,
        "imposto_pct":   0.06,
        "preco_concorrencia_min": 110,  # concorrência muito baixa
        "preco_concorrencia_med": 120,
    }
    result = predict_price(row, "mercadolivre")
    preco_min = 100 / (1 - 0.14 - 0.06 - 0.30)
    assert result["preco_previsto"] >= preco_min * 0.99


def test_train_and_predict(tmp_path, monkeypatch):
    """Treina modelo com dados sintéticos e faz predição."""
    monkeypatch.setattr("config.settings.ML_MODELS_DIR", tmp_path)

    from ml.training.trainer import train
    from ml.inference.predictor import _MODEL_CACHE

    df = pd.DataFrame(_generate_fake_dataset(300))
    meta = train(df, "test_marketplace", "random_forest", "test_v1")

    assert meta["r2"] > 0.5
    assert meta["mae"] > 0
    assert "model_path" in meta

    # Limpa cache para recarregar
    _MODEL_CACHE.clear()
