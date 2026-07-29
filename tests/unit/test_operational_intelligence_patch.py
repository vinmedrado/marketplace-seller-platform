from services.copilot_service import simulate_advanced_profit


def test_advanced_profit_simulator_contract():
    result = simulate_advanced_profit({"cost": 100, "price": 190, "commission_pct": 14, "tax_pct": 6, "margin_pct": 25, "competitor_price": 180, "freight": 10, "monthly_units": 50})
    assert "advanced" in result
    assert result["advanced"]["annual_impact"] == result["advanced"]["monthly_impact"] * 12
    assert result["advanced"]["operational_impact_score"] >= 0
    assert any(row["label"] == "Com frete" for row in result["series"])


def test_operational_intelligence_endpoints_registered():
    from ui.api import app
    routes = {getattr(route, "path", "") for route in app.routes}
    required = {"/ai-copilot", "/operational-timeline", "/smart-alerts", "/recommended-actions", "/operational-maturity-score", "/executive-mode", "/market-radar", "/profit-simulator/advanced"}
    assert required.issubset(routes)
