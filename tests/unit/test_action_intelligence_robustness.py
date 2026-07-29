from models.orm import ActionRecommendation, ActionDecision, SmartAlertLifecycle, ProfitSimulation, OperationalEvent


def test_action_intelligence_models_registered():
    assert ActionRecommendation.__tablename__ == "action_recommendations"
    assert ActionDecision.__tablename__ == "action_decisions"
    assert SmartAlertLifecycle.__tablename__ == "smart_alert_lifecycle"
    assert ProfitSimulation.__tablename__ == "profit_simulations"
    assert OperationalEvent.__tablename__ == "operational_events"
