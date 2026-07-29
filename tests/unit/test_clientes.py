"""tests/unit/test_clientes.py — Testes de clientes."""
import pytest
from services.cliente_service import create_cliente, get_cliente, list_clientes, delete_cliente
from models.schemas import ClienteCreate


def test_create_cliente(db):
    c = create_cliente(db, ClienteCreate(nome="Loja X", email="x@loja.com", plano="free"))
    assert c.id
    assert c.nome  == "Loja X"
    assert c.email == "x@loja.com"
    assert c.ativo == True


def test_create_cliente_email_duplicado(db, cliente):
    with pytest.raises(ValueError, match="já cadastrado"):
        create_cliente(db, ClienteCreate(nome="Outro", email=cliente.email, plano="free"))


def test_get_cliente(db, cliente):
    c = get_cliente(db, cliente.id)
    assert c is not None
    assert c.id == cliente.id


def test_get_cliente_inexistente(db):
    assert get_cliente(db, "00000000-0000-0000-0000-000000000000") is None


def test_list_clientes(db, cliente):
    result = list_clientes(db)
    assert len(result) >= 1
    ids = [c.id for c in result]
    assert cliente.id in ids


def test_delete_cliente(db):
    c = create_cliente(db, ClienteCreate(nome="Del", email="del@test.com", plano="free"))
    assert delete_cliente(db, c.id) == True
    assert get_cliente(db, c.id) is None
