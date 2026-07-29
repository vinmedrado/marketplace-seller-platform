"""tests/integration/test_publish_pipeline.py — Testes integrados de publicação."""
import pytest
from services.publish_service import publish_product, publish_batch
from services.product_service import add_image


def test_publish_dry_run(db, cliente, produto):
    """Dry-run deve retornar ok sem chamar API real."""
    add_image(db, produto.id, "https://img.teste.com/foto.jpg", principal=True)
    result = publish_product(
        db, produto.id, cliente.id,
        marketplace="mercadolivre",
        dry_run=True,
    )
    assert result["dry_run"] == True
    assert result["status"] in ("ok", "dry_run")
    assert result["preco"] is not None
    assert result["preco"] > 0


def test_publish_valida_erros(db, cliente, produto):
    """Produto sem categoria deve falhar na validação."""
    produto.categoria_id = None
    db.commit()
    result = publish_product(db, produto.id, cliente.id, dry_run=True)
    assert "erro" in result["status"] or result.get("erros")


def test_publish_log_salvo(db, cliente, produto):
    """Log de publicação deve ser persistido."""
    from models.orm import PublishLog
    add_image(db, produto.id, "https://img.teste.com/foto.jpg", principal=True)
    publish_product(db, produto.id, cliente.id, dry_run=True)
    logs = db.query(PublishLog).filter_by(product_id=produto.id).all()
    assert len(logs) >= 1


def test_publish_batch(db, cliente):
    """Batch de publicação processa múltiplos produtos."""
    from services.product_service import create_product
    from models.schemas import ProductCreate
    ids = []
    for i in range(3):
        p = create_product(db, cliente.id, ProductCreate(
            sku=f"SKU-BATCH-{i:03d}", titulo=f"Produto Batch {i}",
            categoria_id="MLB1051", custo=50.0 + i,
        ))
        add_image(db, p.id, "https://img.teste.com/foto.jpg", principal=True)
        ids.append(p.id)
    results = publish_batch(db, ids, cliente.id, dry_run=True)
    assert len(results) == 3
    for r in results:
        assert "product_id" in r
        assert "status" in r


def test_publish_preco_integrado_pricing(db, cliente, produto_com_concorrencia):
    """Preço publicado deve refletir o motor de precificação."""
    add_image(db, produto_com_concorrencia.id, "https://img.teste.com/foto.jpg", principal=True)
    result = publish_product(
        db, produto_com_concorrencia.id, cliente.id,
        marketplace="mercadolivre", dry_run=True, pricing_modo="rule_based"
    )
    if result.get("preco"):
        assert result["preco"] > float(produto_com_concorrencia.custo)


def test_publish_listing_salvo(db, cliente, produto):
    """Listing deve ser criado no banco após publicação dry_run ok."""
    from models.orm import MarketplaceListing
    produto.categoria_id = "MLB1051"
    db.commit()
    add_image(db, produto.id, "https://img.teste.com/foto.jpg", principal=True)
    publish_product(db, produto.id, cliente.id, dry_run=True)
    listings = db.query(MarketplaceListing).filter_by(product_id=produto.id).all()
    assert len(listings) >= 1
