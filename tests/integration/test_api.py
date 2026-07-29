"""Testes integrados da API com autenticação e rotas legacy protegidas."""
import pytest
from fastapi.testclient import TestClient

from ui.api import app
from db.base import get_db


@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    r = client.post('/auth/login', json={'email': 'demo@marketplace.local', 'senha': 'demo123456'})
    assert r.status_code == 200
    token = r.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_private_routes_require_token(client):
    for method, url in [
        ('get', '/clientes'),
        ('post', '/ml/train'),
        ('get', '/app/dashboard'),
        ('get', '/products'),
        ('get', '/jobs'),
    ]:
        if method == 'post':
            r = client.post(url, json={})
        else:
            r = client.get(url)
        assert r.status_code == 401


def test_post_clientes_is_admin_only(client, auth_headers):
    r = client.post('/clientes', json={'nome': 'Bloqueado', 'email': 'bloq@test.com', 'plano': 'free'}, headers=auth_headers)
    assert r.status_code == 403


def test_auth_me(client, auth_headers):
    r = client.get('/auth/me', headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data['email'] == 'demo@marketplace.local'
    assert data['tenant_id']


def test_privacy_notice_export_and_request_lifecycle(client, auth_headers):
    notice = client.get("/privacy")
    assert notice.status_code == 200
    assert "rights" in notice.json()

    export = client.get("/privacy/me/export", headers=auth_headers)
    assert export.status_code == 200
    payload = export.json()
    assert payload["subject"]["email"] == "demo@marketplace.local"
    assert "password hashes" in payload["excluded_security_material"]
    assert "hashed_password" not in export.text
    assert "token_hash" not in export.text

    created = client.post(
        "/privacy/me/requests",
        json={"request_type": "access", "description": "Solicito confirmação do tratamento."},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["protocol"]
    assert created.json()["status"] == "pending"

    listed = client.get("/privacy/me/requests", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["protocol"] == created.json()["protocol"] for item in listed.json()["items"])


def test_products_crud_authenticated(client, auth_headers):
    payload = {
        'sku': 'API-SKU-001',
        'title': 'Produto via API Test',
        'category': 'Eletrônicos',
        'cost_price': 75.0,
        'base_price': 149.9,
        'min_margin': 0.10,
        'stock_quantity': 12,
    }
    created = client.post('/products', json=payload, headers=auth_headers)
    assert created.status_code == 200
    product = created.json()
    assert product['sku'] == 'API-SKU-001'

    listed = client.get('/products', headers=auth_headers)
    assert listed.status_code == 200
    assert any(p['id'] == product['id'] for p in listed.json())

    updated = client.put(f"/products/{product['id']}", json={'base_price': 159.9}, headers=auth_headers)
    assert updated.status_code == 200
    assert float(updated.json()['preco_base']) == 159.9

    deleted = client.delete(f"/products/{product['id']}", headers=auth_headers)
    assert deleted.status_code == 200


def _create_product(client, headers):
    r = client.post('/products', json={
        'sku': 'FLOW-SKU-001',
        'title': 'Produto Fluxo Completo',
        'category': 'Demo',
        'cost_price': 80,
        'base_price': 190,
        'min_margin': 0.12,
        'stock_quantity': 20,
    }, headers=headers)
    assert r.status_code == 200
    return r.json()


def test_dashboard_pricing_publish_jobs_and_ml(client, auth_headers):
    product = _create_product(client, auth_headers)

    dash = client.get('/app/dashboard', headers=auth_headers)
    assert dash.status_code == 200
    assert 'total_produtos' in dash.json()

    pricing = client.post('/pricing/calculate', json={'product_id': product['id'], 'marketplace': 'mercadolivre', 'modo': 'rule_based'}, headers=auth_headers)
    assert pricing.status_code == 200
    assert pricing.json()['preco_sugerido'] > 0

    publish = client.post('/publish/dry-run', json={'product_id': product['id'], 'marketplace': 'mercadolivre', 'dry_run': True}, headers=auth_headers)
    assert publish.status_code == 200
    assert publish.json()['dry_run'] is True

    job = client.post('/jobs/pricing', json={}, headers=auth_headers)
    assert job.status_code == 200
    assert job.json()['tenant_id']

    ml = client.post('/ml/train/app', json={'marketplace': 'mercadolivre', 'force': True}, headers=auth_headers)
    assert ml.status_code == 200
    assert 'n_samples' in ml.json()


def test_legacy_routes_respect_authenticated_tenant(client, auth_headers):
    me = client.get('/auth/me', headers=auth_headers).json()
    ok = client.get(f"/dashboard/{me['tenant_id']}", headers=auth_headers)
    assert ok.status_code == 200

    forbidden = client.get('/dashboard/00000000-0000-0000-0000-000000000000', headers=auth_headers)
    assert forbidden.status_code in {403, 404}


def test_optimize_title_public_utility(client):
    r = client.post('/ai/optimize-title', params={'titulo': 'tenis corrida masculino', 'marketplace': 'mercadolivre'})
    assert r.status_code == 200
    assert 'otimizado' in r.json()


def test_market_war_room_actions_match_frontend_contract(client, auth_headers):
    product = _create_product(client, auth_headers)
    product_id = product["id"]
    for suffix in ("simulate-response", "recalculate-pricing", "create-action"):
        response = client.post(f"/market-war-room/{product_id}/{suffix}", headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ok"


def test_analytical_get_routes_are_idempotent(client, auth_headers, db):
    from models.orm import DemandForecastSnapshot, PortfolioAnalysisSnapshot

    _create_product(client, auth_headers)
    before = (
        db.query(DemandForecastSnapshot).count(),
        db.query(PortfolioAnalysisSnapshot).count(),
    )
    assert client.get("/forecast/overview", headers=auth_headers).status_code == 200
    assert client.get("/portfolio/analysis", headers=auth_headers).status_code == 200
    after = (
        db.query(DemandForecastSnapshot).count(),
        db.query(PortfolioAnalysisSnapshot).count(),
    )
    assert after == before
