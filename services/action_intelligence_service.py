"""Action Intelligence persistence and executable action layer.

This service intentionally keeps the heuristic intelligence from the previous
premium demo, but persists decisions, alerts, simulations and operational events
in real ORM tables. The JSON storage file is no longer the primary source of
truth; it is only tolerated by older deployments that have not migrated yet.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from models.orm import (
    ActionDecision,
    ActionRecommendation,
    BackgroundJob,
    CompetitorOffer,
    CompetitorSearch,
    OperationalEvent,
    Product,
    ProfitSimulation,
    SmartAlertLifecycle,
)
from services.copilot_service import (
    build_ai_copilot,
    build_market_radar,
    build_maturity_score,
    build_operational_timeline,
    build_recommended_actions,
    build_smart_alerts,
    simulate_advanced_profit,
)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _money(v: float) -> str:
    return (f"R$ {float(v or 0):,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")


def _dt(v: Any) -> str:
    if not v:
        return _now_iso()
    if isinstance(v, str):
        return v
    return v.replace(microsecond=0).isoformat() + "Z"


def _event(db: Session, tenant_id: str, event_type: str, category: str, severity: str,
           title: str, description: str = "", impact: float = 0,
           product_id: str | None = None, job_id: str | None = None,
           action_id: str | None = None) -> OperationalEvent:
    row = OperationalEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        category=category,
        severity=severity,
        title=title,
        description=description,
        impact_estimated=round(float(impact or 0), 2),
        related_product_id=product_id,
        related_job_id=job_id,
        related_action_id=action_id,
    )
    db.add(row)
    return row


def _action_to_dict(a: ActionRecommendation) -> dict[str, Any]:
    return {
        "id": a.id,
        "priority": a.priority,
        "category": a.category,
        "origin": a.origin,
        "title": a.title,
        "explanation": a.explanation,
        "recommended_action": a.recommended_action,
        "next_best_action": a.next_best_action,
        "expected_impact": float(a.expected_impact or 0),
        "impact_label": _money(float(a.expected_impact or 0)) + "/mês",
        "confidence": float(a.confidence or 0),
        "status": a.status,
        "created_at": _dt(a.created_at),
        "updated_at": _dt(a.updated_at),
        "resolved_at": _dt(a.resolved_at) if a.resolved_at else None,
        "product_id": a.product_id,
        "job_id": a.job_id,
    }


def _decision_to_dict(d: ActionDecision) -> dict[str, Any]:
    return {
        "id": d.id,
        "action_id": d.action_id,
        "status": d.status,
        "note": d.note,
        "impact": float(d.impact or 0),
        "source": d.source,
        "created_at": _dt(d.created_at),
    }


def _base_action_payloads(db: Session, tenant_id: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for idx, rec in enumerate(build_recommended_actions(db, tenant_id).get("items", [])):
        impact = float(rec.get("impact_estimated") or 0)
        stable_id = rec.get("id") or f"rec-{idx + 1}"
        actions.append({
            "id": stable_id,
            "tenant_id": tenant_id,
            "priority": rec.get("priority", "MEDIUM"),
            "category": rec.get("category", "operational"),
            "origin": "AI Operations Copilot",
            "title": rec.get("title", "Ação recomendada"),
            "explanation": rec.get("justification", "Ação criada a partir de sinais operacionais."),
            "recommended_action": rec.get("suggested_action") or rec.get("recommended_action") or "Revisar decisão operacional.",
            "next_best_action": rec.get("cta", "Simular impacto"),
            "expected_impact": impact,
            "confidence": rec.get("confidence", 0.82 if rec.get("priority") == "HIGH" else 0.72),
            "product_id": rec.get("product_id"),
            "job_id": None,
        })

    failed = db.query(BackgroundJob).filter_by(tenant_id=tenant_id, status="failed").order_by(BackgroundJob.created_at.desc()).limit(3).all()
    for job in failed:
        actions.append({
            "id": f"job-{job.id}",
            "tenant_id": tenant_id,
            "priority": "HIGH",
            "category": "jobs",
            "origin": "Smart Alerts Engine",
            "title": f"Reprocessar job {job.job_type}",
            "explanation": job.error_message or "Falha operacional pode deixar pricing, scraping ou publicação desatualizados.",
            "recommended_action": "Reexecutar job e validar logs do pipeline.",
            "next_best_action": "Reprocessar job",
            "expected_impact": 420.0,
            "confidence": 0.91,
            "product_id": None,
            "job_id": job.id,
        })

    low = db.query(Product).filter(Product.cliente_id == tenant_id, Product.ativo == True, Product.estoque <= Product.estoque_minimo).limit(4).all()
    for p in low:
        impact = float(p.preco_base or 0) * 2
        actions.append({
            "id": f"stock-{p.id}",
            "tenant_id": tenant_id,
            "priority": "MEDIUM",
            "category": "estoque",
            "origin": "Operational Score",
            "title": f"Repor estoque: {p.sku}",
            "explanation": "Produto com estoque abaixo do mínimo reduz capacidade de capturar oportunidade de margem.",
            "recommended_action": "Priorizar reposição antes de escalar campanhas ou publicação.",
            "next_best_action": "Abrir produto",
            "expected_impact": impact,
            "confidence": 0.77,
            "product_id": p.id,
            "job_id": None,
        })
    return actions[:20]


def ensure_recommendations(db: Session, tenant_id: str) -> list[ActionRecommendation]:
    existing = {r.id: r for r in db.query(ActionRecommendation).filter_by(tenant_id=tenant_id).all()}
    created = False
    for payload in _base_action_payloads(db, tenant_id):
        if payload["id"] in existing:
            continue
        row = ActionRecommendation(status="pending", created_at=datetime.utcnow() - timedelta(minutes=len(existing) * 4), **payload)
        db.add(row)
        existing[row.id] = row
        created = True
        _event(db, tenant_id, "recommendation_created", payload["category"], "warning" if payload["priority"] == "HIGH" else "info", payload["title"], payload["explanation"], payload["expected_impact"], payload.get("product_id"), payload.get("job_id"), payload["id"])
    if created:
        db.commit()
    return db.query(ActionRecommendation).filter_by(tenant_id=tenant_id).order_by(ActionRecommendation.created_at.desc()).all()


def build_action_center(db: Session, tenant_id: str) -> dict[str, Any]:
    rows = ensure_recommendations(db, tenant_id)
    items = [_action_to_dict(r) for r in rows]
    decisions = db.query(ActionDecision).filter_by(tenant_id=tenant_id).order_by(ActionDecision.created_at.desc()).limit(20).all()
    return {
        "summary": {
            "pending": sum(i["status"] == "pending" for i in items),
            "applied": sum(i["status"] == "applied" for i in items),
            "ignored": sum(i["status"] == "ignored" for i in items),
            "resolved": sum(i["status"] == "resolved" for i in items),
            "critical": sum(i["status"] == "pending" and i["priority"] == "HIGH" for i in items),
            "estimated_pending_impact": round(sum(float(i.get("expected_impact") or 0) for i in items if i["status"] == "pending"), 2),
        },
        "items": sorted(items, key=lambda x: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x.get("priority"), 9), x.get("status") != "pending")),
        "decision_history": [_decision_to_dict(d) for d in decisions],
    }


def _execute_operation(db: Session, tenant_id: str, action: ActionRecommendation) -> tuple[str, str]:
    category = (action.category or "operational").lower()
    if category in {"pricing", "margem", "concorrência", "concorrencia"} and action.product_id:
        try:
            from pricing.engine import calculate_price
            calculate_price(db, action.product_id, tenant_id, modo="rule_based")
            _event(db, tenant_id, "pricing_recalculated", "pricing", "healthy", "Pricing recalculado", f"Ação aplicada: {action.title}", action.expected_impact, action.product_id, None, action.id)
            return "pricing_recalculated", "Pricing recalculado e decisão registrada."
        except Exception as exc:
            _event(db, tenant_id, "pricing_recalculation_failed", "pricing", "critical", "Falha ao recalcular pricing", str(exc), action.expected_impact, action.product_id, None, action.id)
            return "pricing_recalculation_failed", f"Decisão registrada, mas o recálculo falhou: {exc}"
    if category in {"jobs", "job"}:
        job = BackgroundJob(tenant_id=tenant_id, cliente_id=tenant_id, job_type="retry_failed_job", status="queued", progress_label="Reprocessamento criado pelo Action Center", parameters_json={"source_action_id": action.id, "original_job_id": action.job_id})
        db.add(job)
        db.flush()
        _event(db, tenant_id, "job_created", "jobs", "warning", "Job de reprocessamento criado", f"Ação aplicada: {action.title}", action.expected_impact, None, job.id, action.id)
        return "job_requeued", "Job de reprocessamento criado e decisão registrada."
    if category in {"publicação", "publicacao", "publish"}:
        job = BackgroundJob(tenant_id=tenant_id, cliente_id=tenant_id, job_type="publish_dry_run", status="queued", progress_label="Dry-run de publicação criado pelo Action Center", parameters_json={"source_action_id": action.id, "product_id": action.product_id})
        db.add(job)
        db.flush()
        _event(db, tenant_id, "publish_dry_run_created", "publicacao", "info", "Dry-run de publicação criado", f"Ação aplicada: {action.title}", action.expected_impact, action.product_id, job.id, action.id)
        return "publish_dry_run_created", "Dry-run de publicação criado e decisão registrada."
    if category in {"monitoramento", "concorrência", "concorrencia"}:
        job = BackgroundJob(tenant_id=tenant_id, cliente_id=tenant_id, job_type="competitor_monitoring", status="queued", progress_label="Monitoramento competitivo criado", parameters_json={"source_action_id": action.id, "product_id": action.product_id})
        db.add(job)
        db.flush()
        _event(db, tenant_id, "scraping_job_created", "concorrencia", "warning", "Job de monitoramento competitivo criado", f"Ação aplicada: {action.title}", action.expected_impact, action.product_id, job.id, action.id)
        return "competitor_monitoring_created", "Job de monitoramento competitivo criado e decisão registrada."
    _event(db, tenant_id, "recommendation_applied", category, "healthy", "Recomendação aplicada", action.title, action.expected_impact, action.product_id, action.job_id, action.id)
    return "decision_recorded", "Decisão operacional registrada."


def update_action_status(db: Session, tenant_id: str, action_id: str, status: str, note: str | None = None) -> dict[str, Any]:
    if status not in {"applied", "ignored", "resolved", "pending"}:
        raise ValueError("Status inválido para ação.")
    ensure_recommendations(db, tenant_id)
    action = db.query(ActionRecommendation).filter_by(tenant_id=tenant_id, id=action_id).first()
    if not action:
        raise LookupError("Ação não encontrada.")
    action.status = status
    action.updated_at = datetime.utcnow()
    if status in {"applied", "resolved"}:
        action.resolved_at = datetime.utcnow()
    operation, message = ("decision_recorded", f"Ação marcada como {status}.")
    if status == "applied":
        operation, message = _execute_operation(db, tenant_id, action)
    elif status in {"ignored", "resolved"}:
        _event(db, tenant_id, f"recommendation_{status}", action.category, "info", f"Ação {status}", action.title, action.expected_impact, action.product_id, action.job_id, action.id)
    decision = ActionDecision(tenant_id=tenant_id, action_id=action.id, status=status, note=note or message, impact=action.expected_impact or 0, source="Action Center")
    db.add(decision)
    db.commit()
    return {"status": "ok", "action_id": action_id, "new_status": status, "executed_operation": operation, "message": message, "action_center": build_action_center(db, tenant_id)}


def enrich_copilot(db: Session, tenant_id: str) -> dict[str, Any]:
    p = build_ai_copilot(db, tenant_id)
    ac = build_action_center(db, tenant_id)
    p["recommendations"] = ac["items"]
    p["decision_history"] = ac["decision_history"]
    p["executive_context"] = {
        "current_situation": p.get("summary"),
        "memory_window": "últimas decisões e recomendações persistidas no banco",
        "pending_actions": ac["summary"]["pending"],
        "applied_actions": ac["summary"]["applied"],
        "estimated_open_impact": ac["summary"]["estimated_pending_impact"],
    }
    return p


def build_market_war_room(db: Session, tenant_id: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    from models.orm import PricingResult
    for p in db.query(Product).filter_by(cliente_id=tenant_id, ativo=True).all():
        latest = db.query(PricingResult).filter_by(cliente_id=tenant_id, product_id=p.id).order_by(PricingResult.criado_em.desc()).first()
        offers = db.query(CompetitorOffer).join(CompetitorSearch, CompetitorOffer.search_id == CompetitorSearch.id).filter(CompetitorSearch.product_id == p.id, CompetitorOffer.cliente_id == tenant_id).limit(80).all()
        prices = [float(o.preco or 0) for o in offers if o.preco]
        current = float((latest.preco_sugerido if latest else p.preco_base) or 0)
        minc = min(prices) if prices else current * .96
        avg = sum(prices) / len(prices) if prices else current
        margin = float((latest.margem_real_pct if latest else p.margem_minima) or 0)
        minm = float(p.margem_minima or 0)
        under = current > minc * 1.04 or margin < minm
        risk = min(100, max(8, (18 if under else 0) + len(prices) * 1.2 + max(0, (current - minc) / max(current, 1)) * 100 + (25 if margin < minm else 0)))
        if risk >= 20:
            items.append({"product_id": p.id, "sku": p.sku, "title": p.titulo, "category": p.categoria_nome or "Sem categoria", "current_price": round(current, 2), "lowest_competitor_price": round(minc, 2), "avg_competitor_price": round(avg, 2), "competitor_count": len(prices), "margin_pct": round(margin * 100, 2), "min_margin_pct": round(minm * 100, 2), "risk_score": round(risk, 1), "estimated_impact": round(max(120, risk * 18), 2), "status": "under_attack" if under else "watchlist", "recommendation": "Simular resposta parcial preservando margem mínima." if under else "Monitorar sellers agressivos antes de reagir."})
    items.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"headline": f"{len([i for i in items if i['status']=='under_attack'])} produtos sob ataque competitivo e {len(items)} em watchlist operacional.", "summary": {"under_attack": len([i for i in items if i["status"] == "under_attack"]), "watchlist": len(items), "estimated_impact": round(sum(i["estimated_impact"] for i in items), 2)}, "items": items[:12], "radar": build_market_radar(db, tenant_id), "what_to_do_now": ["Priorizar SKUs com risco acima de 70", "Simular resposta antes de alterar preço", "Recalcular pricing apenas onde margem mínima está protegida"]}


def war_room_simulate_response(db: Session, tenant_id: str, product_id: str) -> dict[str, Any]:
    product = db.query(Product).filter_by(id=product_id, cliente_id=tenant_id).first()
    if not product:
        raise LookupError("Produto não encontrado.")
    payload = {"name": f"Resposta competitiva {product.sku}", "preco": float(product.preco_base or 0), "custo": float(product.custo or 0), "comissao": 14, "imposto": 8, "frete": 18, "concorrencia": max(float(product.preco_base or 0) * .96, 1), "monthly_units": 60}
    result = simulate_advanced_profit(payload)
    _event(db, tenant_id, "simulation_generated", "pricing", "info", "Simulação de resposta competitiva gerada", f"War Room simulou resposta para {product.sku}", result.get("advanced", {}).get("monthly_impact", 0), product_id)
    db.commit()
    return {"status": "ok", "product_id": product_id, "payload": payload, "result": result, "message": "Simulação gerada com dados do produto."}


def war_room_recalculate_pricing(db: Session, tenant_id: str, product_id: str) -> dict[str, Any]:
    from pricing.engine import calculate_price
    result = calculate_price(db, product_id, tenant_id, modo="rule_based")
    _event(db, tenant_id, "pricing_recalculated", "pricing", "healthy", "Pricing recalculado pelo War Room", "Botão Recalcular Pricing executado no Market War Room.", result.get("lucro_estimado", 0), product_id)
    db.commit()
    return {"status": "ok", "product_id": product_id, "executed_operation": "pricing_recalculated", "message": "Pricing recalculado pelo Market War Room.", "result": result}


def war_room_create_action(db: Session, tenant_id: str, product_id: str) -> dict[str, Any]:
    product = db.query(Product).filter_by(id=product_id, cliente_id=tenant_id).first()
    if not product:
        raise LookupError("Produto não encontrado.")
    action = ActionRecommendation(id=f"war-{product_id}-{uuid4().hex[:6]}", tenant_id=tenant_id, product_id=product_id, category="concorrência", priority="HIGH", origin="Market War Room", title=f"Responder ataque competitivo: {product.sku}", explanation="Produto priorizado pelo War Room por risco competitivo ou margem pressionada.", recommended_action="Simular resposta e recalcular pricing preservando margem mínima.", next_best_action="Simular impacto", expected_impact=float(product.preco_base or 0) * 3, confidence=0.86, status="pending")
    db.add(action)
    _event(db, tenant_id, "recommendation_created", "concorrencia", "warning", action.title, action.explanation, action.expected_impact, product_id, None, action.id)
    db.commit()
    return {"status": "ok", "action_id": action.id, "message": "Ação criada no Action Center a partir do War Room."}


def build_action_timeline(db: Session, tenant_id: str) -> dict[str, Any]:
    persisted = db.query(OperationalEvent).filter_by(tenant_id=tenant_id).order_by(OperationalEvent.created_at.desc()).limit(40).all()
    rows = []
    for e in persisted:
        rows.append({"id": e.id, "time": e.created_at.strftime("%H:%M") if e.created_at else "--:--", "type": e.event_type, "category": e.category, "severity": e.severity, "title": e.title, "description": e.description, "impact_estimated": float(e.impact_estimated or 0), "related_product_id": e.related_product_id, "related_job_id": e.related_job_id, "related_action_id": e.related_action_id, "created_at": _dt(e.created_at)})
    for e in build_operational_timeline(db, tenant_id).get("items", [])[:10]:
        e.setdefault("category", e.get("type", "operational")); e.setdefault("impact_estimated", e.get("impact", 0)); rows.append(e)
    return {"items": rows[:35], "filters": ["pricing", "margem", "concorrência", "jobs", "decision", "simulation"], "updated_at": _now_iso(), "narrative": "Timeline combina eventos persistidos, decisões reais e sinais operacionais recentes."}


def build_alerts_lifecycle(db: Session, tenant_id: str) -> dict[str, Any]:
    base = build_smart_alerts(db, tenant_id).get("items", [])
    for idx, a in enumerate(base):
        aid = f"smart-{a.get('category')}-{idx}"
        row = db.query(SmartAlertLifecycle).filter_by(tenant_id=tenant_id, id=aid).first()
        if not row:
            row = SmartAlertLifecycle(id=aid, tenant_id=tenant_id, alert_key=aid, title=a.get("title") or "Alerta inteligente", category=a.get("category") or "operational", priority=a.get("priority") or "medium", status="unread", source="Smart Alerts Engine", impact_estimated=float(a.get("impact_estimated") or 0), recommended_action=a.get("recommended_action"))
            db.add(row)
    db.commit()
    items = []
    for r in db.query(SmartAlertLifecycle).filter_by(tenant_id=tenant_id).order_by(SmartAlertLifecycle.created_at.desc()).limit(60).all():
        items.append({"id": r.id, "alert_key": r.alert_key, "title": r.title, "category": r.category, "priority": r.priority, "status": r.status, "source": r.source, "impact_estimated": float(r.impact_estimated or 0), "recommended_action": r.recommended_action, "related_product_id": r.related_product_id, "related_job_id": r.related_job_id, "assigned_to": r.assigned_to, "created_at": _dt(r.created_at), "resolved_at": _dt(r.resolved_at) if r.resolved_at else None})
    return {"items": items, "summary": {"unread": sum(i["status"] == "unread" for i in items), "read": sum(i["status"] == "read" for i in items), "acknowledged": sum(i["status"] == "acknowledged" for i in items), "resolved": sum(i["status"] == "resolved" for i in items), "critical": sum(str(i.get("priority", "")).lower() in {"high", "alta"} for i in items)}}


def update_alert_status(db: Session, tenant_id: str, alert_id: str, status: str) -> dict[str, Any]:
    if status not in {"unread", "read", "acknowledged", "resolved"}:
        raise ValueError("Status inválido para alerta.")
    build_alerts_lifecycle(db, tenant_id)
    row = db.query(SmartAlertLifecycle).filter_by(tenant_id=tenant_id, id=alert_id).first()
    if not row:
        raise LookupError("Alerta não encontrado.")
    row.status = status
    if status == "resolved":
        row.resolved_at = datetime.utcnow()
    _event(db, tenant_id, f"alert_{status}", row.category, "healthy" if status == "resolved" else "info", f"Alerta {status}: {row.title}", row.recommended_action or "Ciclo de vida do alerta atualizado.", row.impact_estimated, row.related_product_id, row.related_job_id)
    db.commit()
    return {"status": "ok", "alert_id": alert_id, "new_status": status}


def build_explainable_score(db: Session, tenant_id: str) -> dict[str, Any]:
    m = build_maturity_score(db, tenant_id)
    comps = m.get("components", {})
    pos = [{"label": k, "delta": round(float(v or 0) / 10, 1), "reason": "Componente saudável contribuiu para a maturidade."} for k, v in comps.items() if float(v or 0) >= 75]
    neg = [{"label": k, "delta": round((70 - float(v or 0)) / 8, 1), "reason": "Componente abaixo do patamar premium derrubou o score."} for k, v in comps.items() if float(v or 0) < 70]
    lift = min(12, len(neg) * 4 + 3)
    return {**m, "what_increased": pos, "what_reduced": neg, "simulation": {"if_resolve_top_actions": min(100, m.get("score", 0) + lift), "estimated_lift": lift, "recommendation": "Resolver ações HIGH pendentes e alertas críticos aumenta o score rapidamente."}}


def build_executive_summary(db: Session, tenant_id: str) -> dict[str, Any]:
    ac = build_action_center(db, tenant_id); war = build_market_war_room(db, tenant_id); score = build_explainable_score(db, tenant_id); pending = ac["summary"]["estimated_pending_impact"]
    return {"situation": f"A operação está com score {score['score']}/100 ({score['category']}) e {ac['summary']['pending']} ações pendentes no cockpit.", "risks": [{"title": r["title"], "impact": r["estimated_impact"], "recommendation": r["recommendation"]} for r in war["items"][:3]], "opportunities": enrich_copilot(db, tenant_id).get("recommendations", [])[:3], "recommended_actions": [a for a in ac["items"] if a["status"] == "pending"][:3], "estimated_impact": {"monthly": round(pending, 2), "annual": round(pending * 12, 2), "label": f"{_money(pending)}/mês · {_money(pending * 12)}/ano"}, "operational_status": "Attention" if ac["summary"]["critical"] else "Good", "executive_text": f"Resumo executivo: {war['headline']} As ações pendentes somam potencial estimado de {_money(pending)}/mês. Próximo passo recomendado: priorizar ações HIGH no Action Center e simular resposta no War Room antes de alterar preços."}


def export_executive_summary(db: Session, tenant_id: str) -> dict[str, Any]:
    s = build_executive_summary(db, tenant_id)
    lines = ["# Executive Summary", "", f"Gerado em: {_now_iso()}", "", "## Situação atual", s["situation"], "", "## Impacto estimado", s["estimated_impact"]["label"], "", "## Top riscos"]
    for r in s["risks"]:
        lines.append(f"- {r['title']} — impacto {_money(r['impact'])}. Ação: {r['recommendation']}")
    lines += ["", "## Top ações recomendadas"]
    for a in s["recommended_actions"]:
        lines.append(f"- [{a['priority']}] {a['title']} — {a['recommended_action']}")
    markdown = "\n".join(lines)
    return {"generated_at": _now_iso(), "summary": s, "markdown": markdown}


def list_profit_simulations(db: Session, tenant_id: str) -> dict[str, Any]:
    rows = db.query(ProfitSimulation).filter_by(tenant_id=tenant_id).order_by(ProfitSimulation.created_at.desc()).limit(50).all()
    return {"items": [{"id": r.id, "name": r.name, "payload": r.payload_json, "result": r.result_json, "created_at": _dt(r.created_at), "created_by": r.created_by} for r in rows]}


def save_profit_simulation(db: Session, tenant_id: str, payload: dict[str, Any], created_by: str | None = None) -> dict[str, Any]:
    result = simulate_advanced_profit(payload)
    row = ProfitSimulation(tenant_id=tenant_id, name=payload.get("name") or f"Cenário {datetime.utcnow().strftime('%H:%M')}", payload_json=payload, result_json=result, created_by=created_by)
    db.add(row)
    db.flush()
    _event(db, tenant_id, "simulation_saved", "simulation", "info", f"Simulação salva: {row.name}", "Profit Simulator salvou um cenário comparável.", result.get("advanced", {}).get("monthly_impact", 0))
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "payload": row.payload_json, "result": row.result_json, "created_at": _dt(row.created_at)}


def create_action_from_simulation(db: Session, tenant_id: str, simulation_id: str) -> dict[str, Any]:
    sim = db.query(ProfitSimulation).filter_by(tenant_id=tenant_id, id=simulation_id).first()
    if not sim:
        raise LookupError("Simulação não encontrada.")
    impact = float((sim.result_json or {}).get("advanced", {}).get("monthly_impact", 0) or 0)
    action = ActionRecommendation(id=f"sim-{simulation_id}", tenant_id=tenant_id, category="simulação", priority="MEDIUM", origin="Profit Simulator", title=f"Aplicar cenário: {sim.name}", explanation="Recomendação criada a partir de simulação salva.", recommended_action="Revisar cenário e aplicar apenas se margem mínima estiver protegida.", next_best_action="Abrir Action Center", expected_impact=impact, confidence=0.78, status="pending")
    db.merge(action)
    _event(db, tenant_id, "recommendation_created", "simulation", "info", action.title, action.explanation, impact, action_id=action.id)
    db.commit()
    return {"status": "ok", "action_id": action.id, "message": "Recomendação persistida a partir da simulação."}


# ─────────────────────────────────────────────
# PATCH 4/10 — Marketplace Operational Intelligence REAL
# ─────────────────────────────────────────────
def _product_flags(product: Product) -> list[str]:
    flags = product.health_flags_json or []
    if not isinstance(flags, list):
        return []
    return [str(f) for f in flags]


def _product_title(product: Product) -> str:
    return product.title or product.titulo or product.external_product_id or str(product.id)


def generate_marketplace_intelligence(
    db: Session,
    tenant_id: str,
    *,
    severity: str | None = None,
    type: str | None = None,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Gera Action Intelligence real a partir dos produtos sincronizados do Mercado Livre.

    Não usa mock nem dados inventados: se não houver catálogo sincronizado, retorna
    lista vazia e uma mensagem operacional clara.
    """
    q = db.query(Product).filter(Product.cliente_id == tenant_id, Product.marketplace == "mercadolivre")
    if product_id:
        q = q.filter(Product.id == product_id)
    products = q.all()

    if not products:
        _event(db, tenant_id, "intelligence_generated", "marketplace_dashboard", "info", "Intelligence consultada sem catálogo", "Conta ainda sem produtos sincronizados.")
        db.commit()
        return {
            "message": "Nenhum produto sincronizado ainda. Sincronize o catálogo para gerar inteligência operacional real.",
            "critical": [],
            "warnings": [],
            "opportunities": [],
            "all": [],
            "summary": {"critical": 0, "warnings": 0, "opportunities": 0, "total": 0},
        }

    prices = [float(p.price or p.preco_base or 0) for p in products if float(p.price or p.preco_base or 0) > 0]
    avg_price = sum(prices) / len(prices) if prices else 0
    now = _now_iso()
    insights: list[dict[str, Any]] = []

    def add(kind: str, sev: str, title: str, description: str, product: Product, action: str) -> None:
        insights.append({
            "type": kind,
            "severity": sev,
            "title": title,
            "description": description,
            "product_id": str(product.id),
            "external_product_id": product.external_product_id,
            "product_title": _product_title(product),
            "recommended_action": action,
            "created_at": now,
        })

    for p in products:
        flags = _product_flags(p)
        qty = int(p.available_quantity if p.available_quantity is not None else (p.estoque or 0))
        sold = int(p.sold_quantity or 0)
        price = float(p.price or p.preco_base or 0)
        status = (p.status or "").lower()
        health = float(p.health) if p.health is not None else None

        if "OUT_OF_STOCK" in flags or qty <= 0:
            add("OUT_OF_STOCK", "critical", "Produto sem estoque", f"{_product_title(p)} está sem unidades disponíveis no Mercado Livre.", p, "Repor estoque ou pausar campanhas para evitar perda de conversão.")
        elif "LOW_STOCK" in flags or qty <= 3:
            add("LOW_STOCK", "warning", "Produto com estoque baixo", f"{_product_title(p)} possui apenas {qty} unidade(s) disponíveis.", p, "Priorizar reposição ou revisar previsão de demanda.")

        if "PAUSED" in flags or status == "paused":
            add("PAUSED", "warning", "Produto pausado", f"{_product_title(p)} está pausado e não está capturando demanda.", p, "Revisar motivo da pausa e reativar quando estoque, preço e descrição estiverem corretos.")

        if "POOR_HEALTH" in flags or (health is not None and health < 0.65):
            percent = f"{round((health or 0) * 100)}%" if health is not None else "abaixo do ideal"
            add("POOR_HEALTH", "warning", "Saúde do anúncio baixa", f"{_product_title(p)} está com health {percent}.", p, "Melhorar título, fotos, atributos, ficha técnica e política comercial do anúncio.")

        if status == "active" and sold == 0 and qty > 0:
            add("NO_SALES", "opportunity", "Produto ativo sem vendas", f"{_product_title(p)} está ativo, possui estoque, mas ainda não registra vendas.", p, "Revisar preço, título, thumbnail, frete e posicionamento competitivo.")

        if avg_price > 0 and price > 0 and (price > avg_price * 1.75 or price < avg_price * 0.35):
            add("PRICE_RISK", "warning", "Preço fora da média interna", f"Preço de {_money(price)} está distante da média interna de {_money(avg_price)}.", p, "Validar margem, categoria, variação do produto e concorrência antes de escalar campanhas.")

        if qty >= 20 and sold <= 1 and status == "active":
            add("HIGH_STOCK_LOW_SALES", "opportunity", "Estoque alto com baixa venda", f"{_product_title(p)} tem {qty} unidades e apenas {sold} venda(s).", p, "Testar ajuste comercial, melhorar oferta/frete ou criar ação promocional controlada.")

    if severity:
        insights = [i for i in insights if i["severity"] == severity]
    if type:
        insights = [i for i in insights if i["type"] == type]

    order = {"critical": 0, "warning": 1, "opportunity": 2, "info": 3}
    insights = sorted(insights, key=lambda i: (order.get(i["severity"], 9), i["type"], i["product_title"]))
    critical = [i for i in insights if i["severity"] == "critical"]
    warnings = [i for i in insights if i["severity"] == "warning"]
    opportunities = [i for i in insights if i["severity"] == "opportunity"]

    _event(db, tenant_id, "intelligence_generated", "marketplace_dashboard", "info", "Intelligence operacional gerada", f"{len(insights)} insight(s) gerados com base no catálogo real.")
    db.commit()
    return {
        "message": None if insights else "Catálogo analisado. Nenhum risco operacional relevante encontrado no momento.",
        "critical": critical,
        "warnings": warnings,
        "opportunities": opportunities,
        "all": insights,
        "summary": {"critical": len(critical), "warnings": len(warnings), "opportunities": len(opportunities), "total": len(insights)},
    }
