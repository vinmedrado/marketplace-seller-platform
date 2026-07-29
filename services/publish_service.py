"""services/publish_service.py — Pipeline completo de publicação."""
import logging
import time
from datetime import datetime
from sqlalchemy.orm import Session

from models.orm import Product, MarketplaceListing, PublishLog
from validators.product_validator import validate_product, validate_payload
from pricing.engine import calculate_price
from integrations.mercadolivre.api import publish_item
from ai.title_optimizer import optimize_title

log = logging.getLogger("msp.service.publish")


def publish_product(
    db: Session,
    product_id: str,
    cliente_id: str,
    marketplace: str = "mercadolivre",
    dry_run: bool = False,
    listing_type: str = "gold_special",
    pricing_modo: str = "rule_based",
) -> dict:
    """
    Pipeline completo:
    1. Valida produto
    2. Calcula preço ideal
    3. Monta payload
    4. Envia à API (ou simula)
    5. Salva listing + log
    """
    t0 = time.time()
    product = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not product:
        raise ValueError(f"Produto {product_id} não encontrado")

    # ── 1. Validação ──
    val = validate_product(db, product, marketplace)
    if not val["valido"]:
        _save_log(db, cliente_id, product_id, None, marketplace,
                  "publish", "erro_validacao", None,
                  None, str(val["erros"]), int((time.time()-t0)*1000))
        return {
            "listing_id": None,
            "marketplace_id": None,
            "status": "erro_validacao",
            "preco": None,
            "url": None,
            "dry_run": dry_run,
            "erro": "; ".join(str(error) for error in val["erros"]),
            "erros": val["erros"],
            "alertas": val["alertas"],
        }

    # ── 2. Preço ──
    try:
        pricing = calculate_price(db, product_id, cliente_id, marketplace, pricing_modo)
        preco = pricing["preco_sugerido"]
    except Exception as e:
        log.warning(f"Erro no pricing, usando preco_base: {e}")
        preco = float(product.preco_base or product.custo * 2.0)

    # ── 3. Payload ──
    titulo = product.titulo_otimizado or product.titulo
    if not titulo:
        opt   = optimize_title(product.titulo, marketplace)
        titulo = opt["otimizado"]

    imagens = [{"source": img.url} for img in product.images[:12]]

    atributos = []
    for k, v in (product.atributos or {}).items():
        atributos.append({"id": k, "value_name": str(v)})

    payload = {
        "title":              titulo,
        "category_id":        product.categoria_id,
        "price":              preco,
        "currency_id":        "BRL",
        "available_quantity": product.estoque if product.estoque > 0 else 100,
        "listing_type_id":    listing_type,
        "condition":          "new",
        "description":        {"plain_text": product.descricao or ""},
        "seller_custom_field": product.sku,
        "pictures":           imagens,
        "attributes":         atributos,
        "shipping": {"mode": "me2", "free_shipping": False},
    }

    # Adiciona dimensões se disponíveis
    if product.peso_kg:
        payload["shipping"]["dimensions"] = {
            "weight":  {"value": float(product.peso_kg),  "unit": "kg"},
            "height":  {"value": float(product.altura_cm  or 10), "unit": "cm"},
            "width":   {"value": float(product.largura_cm  or 10), "unit": "cm"},
            "length":  {"value": float(product.comprimento_cm or 10), "unit": "cm"},
        }

    # Valida payload
    val_payload = validate_payload(payload, marketplace)
    if not val_payload["valido"]:
        _save_log(db, cliente_id, product_id, None, marketplace,
                  "publish", "erro_payload", payload,
                  None, str(val_payload["erros"]), int((time.time()-t0)*1000))
        return {
            "listing_id": None,
            "marketplace_id": None,
            "status": "erro_payload",
            "preco": preco,
            "url": None,
            "dry_run": dry_run,
            "erro": "; ".join(str(error) for error in val_payload["erros"]),
            "erros": val_payload["erros"],
        }

    # ── 4. Envia ──
    status_code, resposta = publish_item(db, cliente_id, payload, dry_run=dry_run)
    sucesso = status_code in (200, 201)

    # ── 5. Salva listing ──
    listing = None
    if sucesso:
        mkt_id = resposta.get("id")
        listing = _upsert_listing(db, cliente_id, product_id, marketplace,
                                  mkt_id, titulo, preco, listing_type,
                                  resposta.get("permalink"), payload, resposta,
                                  "ativo" if not dry_run else "dry_run")

    duracao_ms = int((time.time() - t0) * 1000)
    status_str = "ok" if sucesso else f"erro_{status_code}"
    _save_log(db, cliente_id, product_id,
              listing.id if listing else None,
              marketplace, "publish", status_str,
              payload, resposta,
              None if sucesso else str(resposta),
              duracao_ms)

    log.info(f"Publicação {status_str}: produto={product_id} marketplace={marketplace} dry={dry_run}")

    return {
        "listing_id":     listing.id if listing else None,
        "marketplace_id": resposta.get("id"),
        "status":         status_str,
        "preco":          preco,
        "url":            resposta.get("permalink"),
        "dry_run":        dry_run,
        "erro":           None if sucesso else str(resposta),
        "duracao_ms":     duracao_ms,
        "alertas":        val["alertas"],
    }


def publish_batch(
    db: Session,
    product_ids: list[str],
    cliente_id: str,
    marketplace: str = "mercadolivre",
    dry_run: bool = False,
) -> list[dict]:
    results = []
    for pid in product_ids:
        try:
            r = publish_product(db, pid, cliente_id, marketplace, dry_run)
            r["product_id"] = pid
            results.append(r)
        except Exception as e:
            log.error(f"Erro ao publicar {pid}: {e}")
            results.append({"product_id": pid, "status": "erro", "erro": str(e)})
    return results


def _upsert_listing(db, cliente_id, product_id, marketplace, mkt_id,
                    titulo, preco, listing_type, url, payload, resposta, status) -> MarketplaceListing:
    listing = db.query(MarketplaceListing).filter_by(
        cliente_id=cliente_id, marketplace=marketplace, marketplace_id=mkt_id
    ).first() if mkt_id else None

    if not listing:
        listing = MarketplaceListing(
            cliente_id=cliente_id, product_id=product_id,
            marketplace=marketplace, marketplace_id=mkt_id,
        )
        db.add(listing)

    listing.titulo_publicado = titulo
    listing.preco_publicado  = preco
    listing.status           = status
    listing.listing_type     = listing_type
    listing.url              = url
    listing.payload          = payload
    listing.resposta_api     = resposta
    listing.dt_publicado     = datetime.utcnow()
    db.commit()
    db.refresh(listing)
    return listing


def _save_log(db, cliente_id, product_id, listing_id, marketplace,
              acao, status, payload, resposta, erro, duracao_ms):
    log_entry = PublishLog(
        cliente_id=cliente_id, product_id=product_id,
        listing_id=listing_id, marketplace=marketplace,
        acao=acao, status=status, payload=payload,
        resposta=resposta, erro=erro, duracao_ms=duracao_ms,
    )
    db.add(log_entry)
    db.commit()
