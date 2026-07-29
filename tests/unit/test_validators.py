"""tests/unit/test_validators.py — Testes de validação."""
import pytest
from validators.product_validator import validate_product, validate_payload, _validate_gtin


def test_validate_gtin_valido():
    ok, msg = _validate_gtin("7894900011517")  # EAN-13 válido (GS1 standard)
    assert ok == True


def test_validate_gtin_invalido():
    ok, msg = _validate_gtin("1234567890123")
    assert ok == False


def test_validate_gtin_formato_errado():
    ok, msg = _validate_gtin("123")
    assert ok == False
    assert "Formato inválido" in msg


def test_validate_product_ok(db, produto):
    result = validate_product(db, produto, "mercadolivre", check_duplicate=False)
    assert result["valido"] == True
    assert len(result["erros"]) == 0


def test_validate_product_sem_categoria(db, produto):
    produto.categoria_id = None
    result = validate_product(db, produto, check_duplicate=False)
    assert result["valido"] == False
    assert any("Categoria" in e for e in result["erros"])


def test_validate_product_titulo_longo(db, produto):
    produto.titulo = "A" * 70
    produto.titulo_otimizado = "A" * 70
    result = validate_product(db, produto, "mercadolivre", check_duplicate=False)
    assert result["valido"] == False
    assert any("Título excede" in e for e in result["erros"])


def test_validate_product_custo_zero(db, produto):
    produto.custo = 0
    result = validate_product(db, produto, check_duplicate=False)
    assert result["valido"] == False
    assert any("Custo" in e for e in result["erros"])


def test_validate_product_score_risco(db, produto):
    produto.categoria_id = None
    produto.custo = 0
    result = validate_product(db, produto, check_duplicate=False)
    assert result["score_risco"] >= 4  # pelo menos 2 erros * 2


def test_validate_payload_ok():
    payload = {
        "title": "Produto Teste",
        "category_id": "MLB1051",
        "price": 99.99,
        "currency_id": "BRL",
        "available_quantity": 10,
        "condition": "new",
    }
    result = validate_payload(payload)
    assert result["valido"] == True


def test_validate_payload_campo_faltando():
    payload = {"title": "Teste", "price": 99.99}
    result  = validate_payload(payload)
    assert result["valido"] == False
    assert len(result["erros"]) > 0


def test_validate_payload_preco_zero():
    payload = {
        "title": "X", "category_id": "MLB1", "price": 0,
        "currency_id": "BRL", "available_quantity": 1, "condition": "new"
    }
    result = validate_payload(payload)
    assert result["valido"] == False
