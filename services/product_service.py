"""services/product_service.py — CRUD de produtos."""
import logging
from sqlalchemy.orm import Session
from models.orm import Product, ProductImage
from models.schemas import ProductCreate
from ai.title_optimizer import optimize_title

log = logging.getLogger("msp.service.product")


def create_product(db: Session, cliente_id: str, data: ProductCreate) -> Product:
    # Otimiza título automaticamente
    opt = optimize_title(
        data.titulo,
        marketplace="mercadolivre",
        categoria=data.categoria_nome or "default",
        marca=data.marca or "",
    )
    product = Product(
        cliente_id       = cliente_id,
        sku              = data.sku,
        titulo           = data.titulo,
        titulo_otimizado = opt["otimizado"],
        descricao        = data.descricao,
        categoria_id     = data.categoria_id,
        categoria_nome   = data.categoria_nome,
        custo            = data.custo,
        preco_base       = data.preco_base,
        margem_minima    = data.margem_minima,
        peso_kg          = data.peso_kg,
        altura_cm        = data.altura_cm,
        largura_cm       = data.largura_cm,
        comprimento_cm   = data.comprimento_cm,
        estoque          = data.estoque,
        ncm              = data.ncm,
        gtin             = data.gtin,
        marca            = data.marca,
        atributos        = data.atributos,
        tags             = data.tags,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    log.info(f"Produto criado: {product.id} | SKU={product.sku}")
    return product


def get_product(db: Session, product_id: str, cliente_id: str) -> Product | None:
    return db.query(Product).filter_by(id=product_id, cliente_id=cliente_id, ativo=True).first()


def list_products(db: Session, cliente_id: str, ativo: bool = True) -> list[Product]:
    return db.query(Product).filter_by(cliente_id=cliente_id, ativo=ativo).all()


def update_product(db: Session, product_id: str, cliente_id: str, data: dict) -> Product | None:
    p = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not p:
        return None
    for k, v in data.items():
        if hasattr(p, k):
            setattr(p, k, v)
    if "titulo" in data:
        opt = optimize_title(data["titulo"])
        p.titulo_otimizado = opt["otimizado"]
    db.commit()
    db.refresh(p)
    return p


def delete_product(db: Session, product_id: str, cliente_id: str) -> bool:
    p = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not p:
        return False
    p.ativo = False
    db.commit()
    return True


def add_image(db: Session, product_id: str, url: str, principal: bool = False) -> ProductImage:
    img = ProductImage(product_id=product_id, url=url, principal=principal)
    db.add(img)
    db.commit()
    db.refresh(img)
    return img
