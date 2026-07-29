"""tests/unit/test_pricing.py — Testes do motor de precificação."""
import pytest
from pricing.engine import (
    calculate_price, _rule_based, _round_price, _score_competitividade
)


def test_rule_based_sem_concorrencia():
    preco = _rule_based(custo=100, comissao=0.14, imposto=0.06, markup=0.20)
    assert preco > 100
    # Deve cobrir custo + comissao + imposto + markup
    assert preco >= 100 / (1 - 0.14 - 0.06 - 0.20)


def test_rule_based_com_concorrencia():
    preco = _rule_based(100, 0.14, 0.06, 0.20, conc_min=180, conc_med=220)
    assert preco > 100
    # Não deve ser mais caro que a concorrência
    assert preco <= 220 * 1.1


def test_preco_minimo_respeitado(db, cliente, produto):
    """Preço nunca pode ser menor que custo + margem mínima."""
    from pricing.engine import calculate_price
    result = calculate_price(db, produto.id, cliente.id, "mercadolivre", "rule_based")
    custo      = float(produto.custo)
    margem_min = float(produto.margem_minima)
    comissao   = 0.14
    imposto    = 0.06
    preco_min  = custo / max(1 - comissao - imposto - margem_min, 0.01)
    assert result["preco_sugerido"] >= preco_min * 0.99  # tolerância de 1%


def test_pricing_com_concorrencia(db, cliente, produto_com_concorrencia):
    result = calculate_price(db, produto_com_concorrencia.id, cliente.id, "mercadolivre")
    assert result["preco_sugerido"] > 0
    assert result["lucro_estimado"] > 0
    assert result["preco_concorrencia_min"] is not None


def test_pricing_ml_assisted_fallback(db, cliente, produto):
    """ML sem modelo treinado deve usar fallback sem quebrar."""
    result = calculate_price(db, produto.id, cliente.id, "mercadolivre", "ml_assisted")
    assert result["preco_sugerido"] > 0
    # ml_usado pode ser False se não há modelo, isso é esperado


def test_round_price():
    assert _round_price(49.50) == 49.99
    assert _round_price(99.01) == 99.99
    assert _round_price(100.00) == 99.99


def test_score_competitividade():
    conc = {"preco_min": 100, "preco_max": 200}
    assert _score_competitividade(100, conc) == 1.0
    assert _score_competitividade(200, conc) == 0.0
    assert 0 < _score_competitividade(150, conc) < 1


def test_breakdown_completo(db, cliente, produto):
    result = calculate_price(db, produto.id, cliente.id)
    bd = result["breakdown"]
    assert "custo" in bd
    assert "comissao" in bd
    assert "imposto" in bd
    assert "lucro_estimado" in bd
    assert "margem_real_pct" in bd
