"""validators/product_validator.py — Validação de produtos antes da publicação."""
import hashlib
import logging
import re
from typing import Optional
from sqlalchemy.orm import Session
from models.orm import Product, MarketplaceListing

log = logging.getLogger("msp.validator")

MAX_TITLE_ML = 60
MIN_PRICE    = 0.01
MAX_PRICE    = 999_999.00


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_product(
    db: Session,
    product: Product,
    marketplace: str = "mercadolivre",
    check_duplicate: bool = True,
) -> dict:
    """
    Valida produto para publicação.
    Retorna dict com 'valido', 'erros', 'alertas'.
    """
    erros:   list[str] = []
    alertas: list[str] = []

    # ── Título ──
    titulo = (product.titulo_otimizado or product.titulo or "").strip()
    if not titulo:
        erros.append("Título obrigatório")
    elif len(titulo) > MAX_TITLE_ML and marketplace == "mercadolivre":
        erros.append(f"Título excede {MAX_TITLE_ML} caracteres ({len(titulo)})")
    elif len(titulo) < 10:
        alertas.append("Título muito curto — considere otimizar")

    # ── SKU ──
    if not product.sku:
        erros.append("SKU obrigatório")
    elif check_duplicate:
        dup = _check_sku_duplicate(db, product)
        if dup:
            erros.append(f"SKU duplicado: '{product.sku}'")

    # ── Categoria ──
    if not product.categoria_id:
        erros.append("Categoria obrigatória")

    # ── Preço / custo ──
    custo = float(product.custo or 0)
    if custo <= 0:
        erros.append("Custo deve ser maior que zero")
    preco = float(product.preco_base or 0)
    if preco > 0:
        if preco < MIN_PRICE:
            erros.append(f"Preço abaixo do mínimo ({MIN_PRICE})")
        if preco > MAX_PRICE:
            erros.append(f"Preço acima do máximo ({MAX_PRICE})")
        if custo > 0 and preco < custo * 1.05:
            erros.append("Preço menor que custo + 5% — verifique margens")

    # ── Imagens ──
    if not product.images:
        alertas.append("Nenhuma imagem cadastrada — pode prejudicar conversão")
    elif len(product.images) < 3:
        alertas.append(f"Apenas {len(product.images)} imagem(ns) — recomendamos mínimo 3")

    # ── Dimensões ──
    for campo in ("peso_kg", "altura_cm", "largura_cm", "comprimento_cm"):
        val = getattr(product, campo, None)
        if val is not None and float(val) <= 0:
            alertas.append(f"{campo} deve ser positivo")

    # ── NCM ──
    if product.ncm:
        if not re.match(r"^\d{8}$", product.ncm):
            erros.append(f"NCM inválido: '{product.ncm}' (deve ter 8 dígitos)")

    # ── GTIN ──
    if product.gtin:
        gtin_valid, gtin_msg = _validate_gtin(product.gtin)
        if not gtin_valid:
            alertas.append(f"GTIN: {gtin_msg}")

    # ── Anti-duplicate listing ──
    if check_duplicate and product.id:
        existing = db.query(MarketplaceListing).filter_by(
            product_id=product.id,
            marketplace=marketplace,
            status="ativo"
        ).first()
        if existing:
            alertas.append(f"Produto já possui anúncio ativo: {existing.marketplace_id}")

    # ── Score ──
    score_risco = len(erros) * 2 + len(alertas)

    return {
        "valido":      len(erros) == 0,
        "erros":       erros,
        "alertas":     alertas,
        "score_risco": score_risco,
    }


def validate_payload(payload: dict, marketplace: str = "mercadolivre") -> dict:
    """Valida payload antes de enviar à API."""
    erros: list[str] = []

    required = ["title", "category_id", "price", "currency_id",
                 "available_quantity", "condition"]
    for field in required:
        if not payload.get(field):
            erros.append(f"Campo obrigatório ausente no payload: {field}")

    price = payload.get("price", 0)
    if price is not None and float(price) <= 0:
        erros.append("Preço no payload deve ser positivo")

    return {"valido": len(erros) == 0, "erros": erros}


def _check_sku_duplicate(db: Session, product: Product) -> bool:
    q = db.query(Product).filter(
        Product.cliente_id == product.cliente_id,
        Product.sku == product.sku,
        Product.ativo == True,
    )
    if product.id:
        q = q.filter(Product.id != product.id)
    return q.first() is not None


def _validate_gtin(gtin: str) -> tuple[bool, str]:
    gtin = str(gtin).replace(".0", "").strip()
    if not gtin.isdigit() or len(gtin) not in (8, 12, 13, 14):
        return False, f"Formato inválido (recebido: '{gtin}')"
    nums = [int(d) for d in gtin[:-1]]
    # GS1 standard: posições ímpares (1-based da esquerda) × peso A, pares × peso B
    # EAN-13/GTIN-13: odd=1, even=3  |  EAN-8/GTIN-8/GTIN-12/GTIN-14: odd=3, even=1
    if len(gtin) == 13:
        soma = sum(n * (1 if (i + 1) % 2 != 0 else 3) for i, n in enumerate(nums))
    else:
        soma = sum(n * (3 if (i + 1) % 2 != 0 else 1) for i, n in enumerate(nums))
    check = (10 - soma % 10) % 10
    if int(gtin[-1]) != check:
        return False, "Dígito verificador inválido"
    return True, "OK"
