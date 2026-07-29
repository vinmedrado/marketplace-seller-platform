from services.insight_service import _normalize_insight_payload
from services.saas_service import PLANS, ROLES


def test_insight_payload_contract_has_aliases():
    item = _normalize_insight_payload({"impact_estimated": 123.45, "action": "Revisar", "priority": "alta"})
    assert item["impact_estimated"] == 123.45
    assert item["impact_estimate"] == 123.45
    assert item["action"] == "Revisar"
    assert item["recommended_action"] == "Revisar"


def test_saas_plans_have_limits_and_features():
    assert {"starter", "growth", "professional"}.issubset(PLANS.keys())
    for plan in PLANS.values():
        assert plan["limits"]["products"] > 0
        assert plan["limits"]["jobs_per_month"] > 0
        assert plan["features"]


def test_roles_contract():
    assert {"owner", "admin", "operator", "viewer"}.issubset(ROLES)
