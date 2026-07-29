"""tests/conftest.py — Fixtures compartilhadas para todos os testes."""
import sys
import os
import pytest
from pathlib import Path

# Garante que o root do projeto está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Usa SQLite em memória para testes
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_db.sqlite")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("ML_CLIENT_ID", "")


from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from db.base import Base
import models.orm  # noqa: registra todos os modelos


TEST_DATABASE_URL = "sqlite:///./test_db.sqlite"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Habilita FKs no SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Cria tabelas no banco de testes."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Fecha todas as conexões antes de tentar deletar (necessário no Windows)
    engine.dispose()
    import time, os
    for _ in range(3):
        try:
            Path("test_db.sqlite").unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(0.5)


@pytest.fixture
def db():
    """Session de banco limpa para cada teste."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def cliente(db):
    """Cliente de teste."""
    from services.cliente_service import create_cliente
    from models.schemas import ClienteCreate
    return create_cliente(db, ClienteCreate(
        nome="Cliente Teste", email="teste@teste.com", plano="pro"
    ))


@pytest.fixture
def produto(db, cliente):
    """Produto de teste vinculado ao cliente."""
    from services.product_service import create_product
    from models.schemas import ProductCreate
    return create_product(db, cliente.id, ProductCreate(
        sku           = "SKU-TEST-001",
        titulo        = "Tênis Esportivo Corrida 42",
        descricao     = "Tênis de alta qualidade para corrida",
        categoria_id  = "MLB1051",
        categoria_nome= "Calçados",
        custo         = 89.90,
        preco_base    = 199.99,
        margem_minima = 0.10,
        peso_kg       = 0.8,
        estoque       = 50,
        marca         = "SportRun",
        ncm           = "64041100",
    ))


@pytest.fixture
def produto_com_concorrencia(db, cliente, produto):
    """Produto com dados de concorrência no banco."""
    from models.orm import CompetitorSearch, CompetitorOffer
    from datetime import date
    import hashlib

    search = CompetitorSearch(
        cliente_id=cliente.id, product_id=produto.id,
        marketplace="mercadolivre", query=produto.titulo,
        status="completed", total_found=10, dt_raw=date.today()
    )
    db.add(search); db.flush()

    prices = [149.99, 159.99, 169.99, 179.99, 189.99,
              199.99, 209.99, 219.99, 229.99, 239.99]
    for i, price in enumerate(prices):
        h = hashlib.md5(f"{search.id}{i}".encode()).hexdigest()
        offer = CompetitorOffer(
            search_id=search.id, cliente_id=cliente.id,
            marketplace="mercadolivre",
            titulo=f"Tênis Teste Concorrente {i+1}",
            preco=price, vendedor=f"vendedor_{i}",
            vendas=i * 10, frete_gratis=(i % 2 == 0),
            hash_dedup=h, dt_raw=date.today(), dt_staging=date.today()
        )
        db.add(offer)
    db.commit()
    return produto
