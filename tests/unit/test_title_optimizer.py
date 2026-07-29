"""tests/unit/test_title_optimizer.py — Testes do otimizador de títulos."""
import pytest
from ai.title_optimizer import optimize_title, _clean, _capitalize, _truncate, _score


def test_optimize_title_basic():
    result = optimize_title("tenis esportivo masculino")
    assert result["otimizado"]
    assert len(result["otimizado"]) <= result["max_chars"]
    assert result["score"] > 0


def test_optimize_title_truncate():
    titulo_longo = "A" * 200
    result = optimize_title(titulo_longo, "mercadolivre")
    assert len(result["otimizado"]) <= 60


def test_optimize_title_adiciona_marca():
    result = optimize_title("Fone Bluetooth", marca="Sony")
    assert "Sony" in result["otimizado"]


def test_optimize_title_shopee_limite():
    result = optimize_title("Produto Teste", marketplace="shopee")
    assert result["max_chars"] == 100
    assert len(result["otimizado"]) <= 100


def test_optimize_title_score_range():
    result = optimize_title("Tênis Nike Air Max 42 Corrida Masculino Original")
    assert 0 <= result["score"] <= 1.0


def test_optimize_title_suggestions():
    result = optimize_title("x")  # título muito curto
    assert len(result["sugestoes"]) > 0


def test_capitalize():
    assert _capitalize("tenis esportivo de corrida") == "Tenis Esportivo de Corrida"


def test_clean_remove_chars():
    titulo = "Tênis!!! c/ Garantia@"
    cleaned = _clean(titulo)
    assert "!" not in cleaned
    assert "@" not in cleaned
    assert "com" in cleaned.lower()  # c/ expandido


def test_truncate_word_boundary():
    s = "palavra um dois tres quatro cinco seis"
    result = _truncate(s, 20)
    assert len(result) <= 20
    assert not result.endswith(" ")


def test_score_titulo_otimo():
    titulo = "Tênis Esportivo Corrida Masculino Nike 42 Original Garantia"
    score  = _score(titulo, 60, ["Original", "Garantia"])
    assert score > 0.5
