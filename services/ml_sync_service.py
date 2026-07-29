"""Sync REAL de catálogo Mercado Livre.

PATCH 2/10 — usa OAuth/refresh do PATCH 1, persiste produtos reais e gera eventos
operacionais para alimentar os próximos módulos de Action Intelligence.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.settings import ML_BASE_URL
from models.orm import MarketplaceConnection, OperationalEvent, Product
from services.ml_token_service import get_valid_access_token, get_connection

log = logging.getLogger("msp.ml.sync")
MARKETPLACE = "mercadolivre"
ITEMS_SEARCH_LIMIT = 50
MAX_RETRIES = 3
REQUEST_TIMEOUT = 20
RATE_LIMIT_SLEEP_SECONDS = 0.35


class MLSyncServiceError(Exception):
    pass


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _request_json(method: str, url: str, *, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, headers=_headers(token), params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < MAX_RETRIES:
                sleep_for = min(2 ** attempt, 8)
                log.warning("Erro API ML", extra={"event": "Erro API ML", "status_code": response.status_code, "attempt": attempt, "url": url})
                time.sleep(sleep_for)
                continue
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 8))
                continue
            break
    raise MLSyncServiceError(f"Erro ao consultar Mercado Livre: {last_error}")


def _health_flags(item: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    qty = int(item.get("available_quantity") or 0)
    status = (item.get("status") or "").lower()
    health = item.get("health")
    price = float(item.get("price") or 0)

    if qty <= 0:
        flags.append("OUT_OF_STOCK")
    elif qty <= 3:
        flags.append("LOW_STOCK")
    if status == "paused":
        flags.append("PAUSED")
    if health is not None:
        try:
            if float(health) < 0.65:
                flags.append("POOR_HEALTH")
        except (TypeError, ValueError):
            pass
    if price <= 0:
        flags.append("PRICE_RISK")
    return flags


def _event(db: Session, tenant_id: str, event_type: str, title: str, description: str = "", *, severity: str = "info", product_id: str | None = None) -> None:
    db.add(OperationalEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        category="marketplace_sync",
        severity=severity,
        title=title,
        description=description,
        related_product_id=product_id,
    ))


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def _upsert_product(db: Session, tenant_id: str, conn: MarketplaceConnection, item: dict[str, Any], synced_at: datetime) -> tuple[Product, bool]:
    external_id = str(item.get("id") or "").strip()
    if not external_id:
        raise MLSyncServiceError("Item Mercado Livre sem id.")

    product = db.query(Product).filter_by(cliente_id=tenant_id, external_product_id=external_id).first()
    is_new = product is None
    if product is None:
        product = Product(
            cliente_id=tenant_id,
            marketplace_connection_id=conn.id,
            marketplace=MARKETPLACE,
            external_product_id=external_id,
            sku=external_id,
            titulo=item.get("title") or external_id,
        )
        db.add(product)

    shipping = item.get("shipping") or {}
    flags = _health_flags(item)
    tags = item.get("tags") or []
    attributes = {a.get("id"): a.get("value_name") or a.get("value_id") for a in (item.get("attributes") or []) if isinstance(a, dict) and a.get("id")}

    product.marketplace_connection_id = conn.id
    product.marketplace = MARKETPLACE
    product.title = item.get("title")
    product.titulo = item.get("title") or product.titulo or external_id
    product.category_id = item.get("category_id")
    product.categoria_id = item.get("category_id")
    product.price = _decimal_or_none(item.get("price"))
    product.preco_base = _decimal_or_none(item.get("price"))
    product.currency_id = item.get("currency_id")
    product.available_quantity = int(item.get("available_quantity") or 0)
    product.estoque = int(item.get("available_quantity") or 0)
    product.sold_quantity = int(item.get("sold_quantity") or 0)
    product.condition = item.get("condition")
    product.status = item.get("status")
    product.permalink = item.get("permalink")
    product.thumbnail = item.get("thumbnail")
    product.listing_type_id = item.get("listing_type_id")
    product.health = _decimal_or_none(item.get("health"))
    product.catalog_listing = bool(item.get("catalog_listing"))
    product.shipping_mode = shipping.get("mode")
    product.free_shipping = bool(shipping.get("free_shipping"))
    product.tags_json = tags
    product.tags = tags
    product.atributos = {**(product.atributos or {}), "ml_attributes": attributes, "shipping": shipping, "health_flags": flags}
    product.raw_payload_json = item
    product.health_flags_json = flags
    product.last_synced_at = synced_at
    product.updated_at = synced_at
    product.atualizado_em = synced_at
    product.ativo = (item.get("status") != "closed")
    return product, is_new


def sync_catalog(db: Session, tenant_id: str, *, limit: int = ITEMS_SEARCH_LIMIT, max_items: int | None = None) -> dict[str, Any]:
    """Sincroniza o catálogo real do seller conectado via Mercado Livre."""
    synced_at = datetime.utcnow()
    log.info("Sync iniciado", extra={"event": "Sync iniciado", "tenant_id": str(tenant_id), "marketplace": MARKETPLACE})

    token = get_valid_access_token(db, tenant_id)
    conn = get_connection(db, tenant_id)
    if not conn or not conn.seller_id:
        raise MLSyncServiceError("Conexão Mercado Livre sem seller_id válido.")

    total_synced = 0
    new_products = 0
    updated_products = 0
    errors: list[dict[str, str]] = []
    offset = 0
    limit = max(1, min(int(limit or ITEMS_SEARCH_LIMIT), 50))

    while True:
        search_url = f"{ML_BASE_URL}/users/{conn.seller_id}/items/search"
        search_data = _request_json("GET", search_url, token=token, params={"offset": offset, "limit": limit})
        item_ids = search_data.get("results") or []
        paging = search_data.get("paging") or {}
        if not item_ids:
            break

        for item_id in item_ids:
            if max_items and total_synced >= max_items:
                break
            try:
                detail_url = f"{ML_BASE_URL}/items/{item_id}"
                item = _request_json("GET", detail_url, token=token)
                product, is_new = _upsert_product(db, tenant_id, conn, item, synced_at)
                db.flush()
                flags = product.health_flags_json or []
                if is_new:
                    new_products += 1
                    _event(db, tenant_id, "product_created", "Produto novo encontrado", product.titulo, product_id=product.id)
                    log.info("Produto criado", extra={"event": "Produto criado", "tenant_id": str(tenant_id), "external_product_id": item_id})
                else:
                    updated_products += 1
                    log.info("Produto atualizado", extra={"event": "Produto atualizado", "tenant_id": str(tenant_id), "external_product_id": item_id})
                if "PAUSED" in flags:
                    _event(db, tenant_id, "product_paused", "Produto pausado", product.titulo, severity="warning", product_id=product.id)
                if "LOW_STOCK" in flags:
                    try:
                        from services.alerts_service import create_alert
                        create_alert(db, tenant_id, alert_type="LOW_STOCK", severity="warning", title="Estoque baixo", message=f"Produto {product.titulo} está com estoque baixo ({product.available_quantity or 0} unidade(s)).", dedupe_key=f"product:{product.id}:LOW_STOCK")
                    except Exception:
                        log.warning("alert_low_stock_failed_soft", extra={"event": "alert_low_stock_failed_soft", "tenant_id": str(tenant_id)})
                if "OUT_OF_STOCK" in flags:
                    _event(db, tenant_id, "product_out_of_stock", "Produto sem estoque", product.titulo, severity="warning", product_id=product.id)
                    try:
                        from services.alerts_service import create_alert
                        create_alert(db, tenant_id, alert_type="OUT_OF_STOCK", severity="critical", title="Produto sem estoque", message=f"Produto {product.titulo} está ativo/sincronizado com estoque zerado. Ação sugerida: reabastecer ou pausar temporariamente.", dedupe_key=f"product:{product.id}:OUT_OF_STOCK")
                    except Exception:
                        log.warning("alert_out_of_stock_failed_soft", extra={"event": "alert_out_of_stock_failed_soft", "tenant_id": str(tenant_id)})
                total_synced += 1
                time.sleep(RATE_LIMIT_SLEEP_SECONDS)
            except Exception as exc:  # noqa: BLE001
                errors.append({"item_id": str(item_id), "error": str(exc)})
                _event(db, tenant_id, "sync_error", "Erro sync", f"Item {item_id}: {exc}", severity="error")
                try:
                    from services.alerts_service import create_alert
                    create_alert(db, tenant_id, alert_type="SYNC_ERROR", severity="warning", title="Erro na sincronização Mercado Livre", message=f"Falha ao sincronizar o item {item_id}. O fluxo continua e poderá ser reprocessado.", dedupe_key=f"sync:{item_id}:SYNC_ERROR")
                except Exception:
                    pass
                log.exception("Erro API ML", extra={"event": "Erro API ML", "tenant_id": str(tenant_id), "item_id": str(item_id)})

        db.commit()
        log.info("Página sincronizada", extra={"event": "Página sincronizada", "tenant_id": str(tenant_id), "offset": offset, "page_count": len(item_ids)})
        if max_items and total_synced >= max_items:
            break
        total_available = int(paging.get("total") or 0)
        offset += limit
        if offset >= total_available:
            break

    _event(db, tenant_id, "catalog_synced", "Catálogo sincronizado", f"{total_synced} produtos sincronizados; {len(errors)} erros.")
    db.commit()
    result = {"total_synced": total_synced, "new_products": new_products, "updated_products": updated_products, "errors": errors, "synced_at": synced_at.isoformat()}
    log.info("Sync concluído", extra={"event": "Sync concluído", "tenant_id": str(tenant_id), **result})
    return result


def list_marketplace_products(db: Session, tenant_id: str, *, page: int = 1, page_size: int = 50, status: str | None = None, search: str | None = None) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 100))
    query = db.query(Product).filter_by(cliente_id=tenant_id, marketplace=MARKETPLACE)
    if status:
        query = query.filter(Product.status == status)
    if search:
        query = query.filter(Product.titulo.ilike(f"%{search}%"))
    total = query.count()
    rows = query.order_by(Product.last_synced_at.desc().nullslast(), Product.atualizado_em.desc()).offset((page - 1) * page_size).limit(page_size).all()
    active = db.query(Product).filter_by(cliente_id=tenant_id, marketplace=MARKETPLACE, status="active").count()
    paused = db.query(Product).filter_by(cliente_id=tenant_id, marketplace=MARKETPLACE, status="paused").count()
    out_of_stock = db.query(Product).filter(Product.cliente_id == tenant_id, Product.marketplace == MARKETPLACE, Product.available_quantity <= 0).count()
    last_sync = db.query(Product.last_synced_at).filter_by(cliente_id=tenant_id, marketplace=MARKETPLACE).order_by(Product.last_synced_at.desc().nullslast()).first()
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "summary": {"total_products": total, "active_products": active, "paused_products": paused, "out_of_stock": out_of_stock, "last_sync": last_sync[0].isoformat() if last_sync and last_sync[0] else None},
        "items": [{
            "id": p.id,
            "external_product_id": p.external_product_id,
            "title": p.title or p.titulo,
            "price": float(p.price or p.preco_base or 0),
            "currency_id": p.currency_id,
            "available_quantity": p.available_quantity if p.available_quantity is not None else p.estoque,
            "sold_quantity": p.sold_quantity or 0,
            "condition": p.condition,
            "status": p.status,
            "permalink": p.permalink,
            "thumbnail": p.thumbnail,
            "category_id": p.category_id or p.categoria_id,
            "listing_type_id": p.listing_type_id,
            "health": float(p.health) if p.health is not None else None,
            "health_flags": p.health_flags_json or [],
            "shipping_mode": p.shipping_mode,
            "free_shipping": bool(p.free_shipping),
            "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
        } for p in rows],
    }
