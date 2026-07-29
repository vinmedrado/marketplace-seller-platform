"""integrations/mercadolivre/api.py — Wrapper da API ML com retry e mock fallback."""
import time
import logging
import requests
from functools import wraps
from sqlalchemy.orm import Session
from config.settings import ML_BASE_URL, DEBUG
from integrations.mercadolivre.auth import get_valid_token, refresh_token, MLAuthError

log = logging.getLogger("msp.ml.api")

# ── Dados mock para dev sem credenciais ───────
_MOCK_ITEMS = {
    "results": ["MLB001", "MLB002", "MLB003"],
    "paging":  {"total": 3, "offset": 0, "limit": 50},
}
_MOCK_CATEGORY = {
    "id": "MLB1051", "name": "Eletrônicos",
    "attributes": [
        {"id": "BRAND", "name": "Marca", "tags": {"required": True}, "values": [{"name": "Samsung"}, {"name": "LG"}]},
        {"id": "MODEL", "name": "Modelo", "tags": {"required": False}, "values": []},
    ]
}


def _retry(max_attempts: int = 3, delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    if e.response.status_code in (429, 500, 502, 503):
                        wait = delay * (2 ** attempt)
                        log.warning(f"Retry {attempt+1}/{max_attempts} em {wait:.1f}s ({e})")
                        time.sleep(wait)
                        last_exc = e
                    else:
                        raise
                except requests.RequestException as e:
                    time.sleep(delay)
                    last_exc = e
            raise last_exc
        return wrapper
    return decorator


def _headers(db: Session, cliente_id: str) -> dict:
    tok = get_valid_token(db, cliente_id)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@_retry()
def get_user_info(db: Session, cliente_id: str) -> dict:
    if not _has_credentials():
        return {"id": "mock_user", "nickname": "MOCK_SELLER", "email": "mock@test.com"}
    r = requests.get(f"{ML_BASE_URL}/users/me", headers=_headers(db, cliente_id), timeout=10)
    if r.status_code == 401:
        refresh_token(db, cliente_id)
        r = requests.get(f"{ML_BASE_URL}/users/me", headers=_headers(db, cliente_id), timeout=10)
    r.raise_for_status()
    return r.json()


@_retry()
def get_items(db: Session, cliente_id: str) -> dict:
    if not _has_credentials():
        log.info("ML API mock — retornando itens fake")
        return _MOCK_ITEMS
    headers = _headers(db, cliente_id)
    user_info = get_user_info(db, cliente_id)
    user_id   = user_info.get("id")
    r = requests.get(f"{ML_BASE_URL}/users/{user_id}/items/search",
                     headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


@_retry()
def get_category_attributes(db: Session, cliente_id: str, category_id: str) -> dict:
    if not _has_credentials():
        return _MOCK_CATEGORY
    r = requests.get(f"{ML_BASE_URL}/categories/{category_id}/attributes",
                     headers=_headers(db, cliente_id), timeout=10)
    r.raise_for_status()
    result = {}
    for att in r.json():
        if att.get("tags", {}).get("required"):
            result[att["id"]] = [v["name"] for v in att.get("values", [])]
    return result


@_retry()
def publish_item(db: Session, cliente_id: str, payload: dict, dry_run: bool = False) -> tuple[int, dict]:
    if not _has_credentials():
        mock_id = f"MLB{hash(str(payload)) % 9999999:07d}"
        return 201, {"id": mock_id, "status": "active", "permalink": f"https://www.mercadolivre.com.br/p/{mock_id}"}
    params = {"dry_run": True} if dry_run else {}
    r = requests.post(f"{ML_BASE_URL}/items",
                      headers=_headers(db, cliente_id),
                      json=payload, params=params, timeout=15)
    return r.status_code, r.json()


@_retry()
def update_item(db: Session, cliente_id: str, item_id: str, payload: dict) -> tuple[int, dict]:
    if not _has_credentials():
        return 200, {"id": item_id, "status": "active"}
    r = requests.put(f"{ML_BASE_URL}/items/{item_id}",
                     headers=_headers(db, cliente_id),
                     json=payload, timeout=15)
    return r.status_code, r.json()


@_retry()
def search_items(query: str, limit: int = 50, offset: int = 0) -> dict:
    """Busca pública — sem auth."""
    if not _has_credentials():
        return _mock_search(query, limit)
    r = requests.get(
        f"{ML_BASE_URL}/sites/MLB/search",
        params={"q": query, "limit": limit, "offset": offset},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _mock_search(query: str, limit: int) -> dict:
    import random
    base = random.uniform(50, 500)
    results = []
    for i in range(min(limit, 10)):
        price = round(base * random.uniform(0.85, 1.25), 2)
        results.append({
            "id":    f"MLB{random.randint(1000000, 9999999)}",
            "title": f"{query} - Opção {i+1}",
            "price": price,
            "sold_quantity": random.randint(0, 200),
            "condition": "new",
            "shipping": {"free_shipping": random.choice([True, False])},
            "seller": {"id": f"seller_{i}", "nickname": f"VENDEDOR_{i}"},
            "thumbnail": "https://via.placeholder.com/150",
            "permalink": f"https://www.mercadolivre.com.br/p/MLB{i}",
        })
    return {"results": results, "paging": {"total": len(results), "offset": 0, "limit": limit}}


def _has_credentials() -> bool:
    from config.settings import ML_CLIENT_ID
    return bool(ML_CLIENT_ID)
