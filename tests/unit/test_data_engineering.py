"""tests/unit/test_data_engineering.py — Testes de data engineering."""
import pytest
from datetime import date
from data_engineering.pipelines.staging_pipeline import process_staging, _quartiles
from data_engineering.pipelines.mart_pipeline import build_pricing_mart, run_full_pipeline
from data_engineering.pipelines.raw_pipeline import ingest_raw_offers
from data_engineering.feature_store.store import (
    save_features, load_features, load_features_batch, list_versions
)


def test_quartiles_basico():
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    q1, q3 = _quartiles(data)
    assert q1 < q3
    assert q1 == 3
    assert q3 == 8


def test_quartiles_lista_vazia():
    q1, q3 = _quartiles([])
    assert q1 == 0.0
    assert q3 == 0.0


def test_raw_pipeline_sem_dados(db, cliente):
    count = ingest_raw_offers(db, cliente.id, "mercadolivre", date.today())
    assert count == 0


def test_staging_sem_dados(db, cliente):
    result = process_staging(db, cliente.id, "mercadolivre", date.today())
    assert result["total"] == 0
    assert result["validos"] == 0
    assert result["removidos"] == 0


def test_staging_com_dados(db, cliente, produto_com_concorrencia):
    """Dados de concorrência já foram marcados como staging no fixture."""
    result = process_staging(db, cliente.id, "mercadolivre", date.today())
    assert isinstance(result["total"], int)


def test_mart_pipeline(db, cliente, produto_com_concorrencia):
    result = build_pricing_mart(db, cliente.id, "mercadolivre", date.today())
    assert "rows" in result
    assert isinstance(result["rows"], list)


def test_full_pipeline(db, cliente, produto_com_concorrencia):
    result = run_full_pipeline(db, cliente.id, "mercadolivre", date.today())
    assert "raw"     in result
    assert "staging" in result
    assert "mart"    in result


def test_feature_store_save_load(tmp_path, monkeypatch):
    from data_engineering.feature_store import store as fs_module
    monkeypatch.setattr(fs_module, "FEATURE_STORE_DIR", tmp_path)

    features = {"custo": 100.0, "preco_min": 180.0, "n_concorrentes": 15}
    path = save_features("prod-test-001", "product", features, "v1", date.today())
    assert path

    loaded = load_features("prod-test-001", "product", date.today())
    assert loaded is not None
    assert loaded["custo"] == 100.0
    assert loaded["n_concorrentes"] == 15


def test_feature_store_load_batch(tmp_path, monkeypatch):
    from data_engineering.feature_store import store as fs_module
    monkeypatch.setattr(fs_module, "FEATURE_STORE_DIR", tmp_path)

    for i in range(5):
        save_features(f"prod-{i}", "product", {"custo": float(i * 10)}, "v1", date.today())

    df = load_features_batch("product", date.today())
    assert len(df) == 5
    assert "custo" in df.columns


def test_feature_store_inexistente():
    loaded = load_features("nao-existe-xxx", "product", date(2000, 1, 1))
    assert loaded is None
