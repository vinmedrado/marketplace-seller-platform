from services.product_intelligence_service import simulate_impact


def test_impact_simulator_contract():
    data = simulate_impact({"cost": 100, "price": 200, "commission_pct": 10, "tax_pct": 5, "margin_pct": 25, "competitor_price": 190, "monthly_units": 50})
    assert data["result"]["unit_profit"] > 0
    assert data["result"]["monthly_profit"] > 0
    assert data["result"]["risk"] in {"healthy", "warning", "critical"}
    assert len(data["series"]) == 3
