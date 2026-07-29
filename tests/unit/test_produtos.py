"""tests/unit/test_produtos.py — Testes de produtos."""
import pytest
from services.product_service import (
    create_product, get_product, list_products,
    update_product, delete_product, add_image
)
from models.schemas import ProductCreate


def _make_product_data(**kwargs):
    base = dict(
        sku="SKU-UNIT-001", titulo="Produto Teste Unitário",
        categoria_id="MLB1051", custo=50.0, preco_base=120.0,
        margem_minima=0.10, estoque=10, marca="MarcaX"
    )
    base.update(kwargs)
    return ProductCreate(**base)


def test_create_product(db, cliente):
    p = create_product(db, cliente.id, _make_product_data())
    assert p.id
    assert p.sku == "SKU-UNIT-001"
    assert p.titulo_otimizado  # otimizador deve ter preenchido


def test_create_product_sku_duplicate(db, cliente):
    create_product(db, cliente.id, _make_product_data(sku="SKU-DUP"))
    with pytest.raises(Exception):
        create_product(db, cliente.id, _make_product_data(sku="SKU-DUP"))


def test_get_product(db, cliente, produto):
    p = get_product(db, produto.id, cliente.id)
    assert p is not None
    assert p.id == produto.id


def test_get_product_wrong_cliente(db, produto):
    p = get_product(db, produto.id, "wrong-cliente-id")
    assert p is None


def test_list_products(db, cliente, produto):
    result = list_products(db, cliente.id)
    assert len(result) >= 1
    assert any(p.id == produto.id for p in result)


def test_update_product(db, cliente, produto):
    updated = update_product(db, produto.id, cliente.id, {"custo": 99.99})
    assert float(updated.custo) == 99.99


def test_update_product_titulo_re_otimiza(db, cliente, produto):
    updated = update_product(db, produto.id, cliente.id,
                              {"titulo": "Fone Bluetooth Gamer Pro 2.4GHz"})
    assert updated.titulo_otimizado
    assert len(updated.titulo_otimizado) > 5


def test_delete_product(db, cliente):
    p = create_product(db, cliente.id, _make_product_data(sku="SKU-DEL-001"))
    assert delete_product(db, p.id, cliente.id) == True
    assert get_product(db, p.id, cliente.id) is None


def test_add_image(db, produto):
    img = add_image(db, produto.id, "https://img.teste.com/foto.jpg", principal=True)
    assert img.id
    assert img.principal == True
