from fastapi.testclient import TestClient
from ui.api import app


def _auth(client):
    r = client.post('/auth/login', json={'email': 'demo@marketplace.local', 'senha': 'demo123456'})
    assert r.status_code == 200
    return {'Authorization': f"Bearer {r.json()['access_token']}"}


def test_action_intelligence_private_routes_require_auth():
    client = TestClient(app)
    for path in ['/action-center', '/market-war-room', '/executive-summary', '/alerts/lifecycle']:
        assert client.get(path).status_code == 401


def test_action_intelligence_routes_smoke():
    client = TestClient(app)
    headers = _auth(client)
    for path in ['/ai-copilot/context', '/action-center', '/market-war-room', '/executive-summary', '/operational-timeline/actions', '/alerts/lifecycle', '/operational-score/explainable', '/profit-simulations']:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, resp.text
