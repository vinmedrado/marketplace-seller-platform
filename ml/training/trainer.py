"""ml/training/trainer.py — Treinamento do modelo de precificação."""
import json
import logging
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from config.settings import ML_MODELS_DIR
from ml.features.feature_engineering import FEATURE_NAMES

log = logging.getLogger("msp.ml.trainer")

TARGET_COL  = "preco_ideal"
MODEL_TYPES = {"random_forest": RandomForestRegressor, "gradient_boosting": GradientBoostingRegressor}


def train(
    df: pd.DataFrame,
    marketplace: str = "mercadolivre",
    model_type: str = "random_forest",
    dataset_version: str = "unknown",
) -> dict:
    """
    Treina modelo de precificação.
    Retorna métricas e salva artefatos.
    """
    log.info(f"Iniciando treino: {model_type} | {len(df)} amostras")

    # ── Features / Target ──
    feature_cols = [c for c in FEATURE_NAMES if c in df.columns]
    X = df[feature_cols].values
    y = df[TARGET_COL].values

    # Valida que preços não violam custo
    custo_col = df["custo"].values if "custo" in df.columns else np.zeros(len(y))
    mask = y > custo_col * 1.05
    X, y = X[mask], y[mask]
    log.info(f"Após filtro margem mínima: {len(y)} amostras")

    # ── Split ──
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # ── Pipeline ──
    params = _get_params(model_type)
    model_cls = MODEL_TYPES.get(model_type, RandomForestRegressor)
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  model_cls(**params, random_state=42)),
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    # ── Métricas ──
    mae  = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    r2   = r2_score(y_test, y_pred)
    cv_r2 = cross_val_score(pipeline, X, y, cv=5, scoring="r2").mean()

    log.info(f"MAE={mae:.2f}  RMSE={rmse:.2f}  R²={r2:.4f}  CV-R²={cv_r2:.4f}")

    # ── Feature importance ──
    model = pipeline.named_steps["model"]
    importance = {}
    if hasattr(model, "feature_importances_"):
        importance = dict(zip(feature_cols, model.feature_importances_.tolist()))
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    # ── Salvar artefatos ──
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    model_filename = f"pricing_{marketplace}_{model_type}_{timestamp}.joblib"
    model_path     = ML_MODELS_DIR / model_filename

    joblib.dump({
        "pipeline":        pipeline,
        "feature_names":   feature_cols,
        "marketplace":     marketplace,
        "model_type":      model_type,
        "dataset_version": dataset_version,
        "metrics":         {"mae": mae, "rmse": rmse, "r2": r2, "cv_r2": cv_r2},
        "trained_at":      timestamp,
    }, model_path)

    # Salva como "latest"
    latest_path = ML_MODELS_DIR / f"pricing_{marketplace}_latest.joblib"
    joblib.dump({"pipeline": pipeline, "feature_names": feature_cols}, latest_path)

    # Salva metadata JSON
    meta = {
        "model_path":        str(model_path),
        "marketplace":       marketplace,
        "model_type":        model_type,
        "dataset_version":   dataset_version,
        "n_samples":         len(y),
        "n_features":        len(feature_cols),
        "mae":               round(mae, 4),
        "rmse":              round(rmse, 4),
        "r2":                round(r2, 6),
        "cv_r2":             round(cv_r2, 6),
        "feature_importance": importance,
        "trained_at":        timestamp,
    }
    meta_path = ML_MODELS_DIR / f"pricing_{marketplace}_latest_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    log.info(f"Modelo salvo: {model_path}")
    return meta


def _get_params(model_type: str) -> dict:
    if model_type == "random_forest":
        return {"n_estimators": 200, "max_depth": 12, "min_samples_leaf": 5, "n_jobs": -1}
    if model_type == "gradient_boosting":
        return {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.05, "subsample": 0.8}
    return {}
