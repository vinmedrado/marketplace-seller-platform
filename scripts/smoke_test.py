"""Smoke test seguro do console SellerOS.

Por padrão executa apenas leituras. Use ``--mutating`` para validar um fluxo
temporário de produto; o produto criado é removido ao final.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import requests


def expect_ok(response: requests.Response, label: str) -> Any:
    if response.status_code >= 400:
        raise RuntimeError(f"{label}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def get(base: str, path: str, headers: dict[str, str]) -> Any:
    return expect_ok(requests.get(f"{base}{path}", headers=headers, timeout=20), path)


def run_read_only(base: str, headers: dict[str, str]) -> None:
    routes = [
        "/app/dashboard",
        "/dashboard/market-ready",
        "/products",
        "/competition",
        "/pricing/history",
        "/publish/history",
        "/insights",
        "/intelligence-center",
        "/operational-score",
        "/health-monitoring",
        "/ai-copilot",
        "/action-center",
        "/market-war-room",
        "/executive-summary",
        "/operational-timeline/actions",
        "/alerts/lifecycle",
        "/operational-score/explainable",
        "/forecast/overview",
        "/portfolio/analysis",
        "/system/status",
    ]
    for index, route in enumerate(routes, start=1):
        print(f"[read {index:02}/{len(routes)}] {route}")
        get(base, route, headers)


def run_temporary_flow(base: str, headers: dict[str, str]) -> None:
    product_id: str | None = None
    try:
        payload = {
            "sku": f"SMOKE-{int(time.time())}",
            "title": "Produto temporário do smoke test",
            "description": "Removido automaticamente ao final.",
            "category": "QA",
            "cost_price": 55,
            "base_price": 129.9,
            "min_margin": 0.18,
            "stock_quantity": 12,
        }
        product = expect_ok(requests.post(f"{base}/products", json=payload, headers=headers, timeout=20), "create product")
        product_id = product["id"]
        operations = [
            ("pricing", f"/pricing/calculate", {"product_id": product_id, "marketplace": "mercadolivre", "modo": "rule_based"}),
            ("publish dry-run", f"/publish/dry-run", {"product_id": product_id, "marketplace": "mercadolivre", "dry_run": True}),
        ]
        for label, path, body in operations:
            print(f"[mutating] {label}")
            expect_ok(requests.post(f"{base}{path}", json=body, headers=headers, timeout=30), label)
        for suffix in ("simulate-response", "recalculate-pricing", "create-action"):
            print(f"[mutating] war-room/{suffix}")
            expect_ok(requests.post(f"{base}/market-war-room/{product_id}/{suffix}", headers=headers, timeout=30), suffix)
    finally:
        if product_id:
            response = requests.delete(f"{base}/products/{product_id}", headers=headers, timeout=20)
            expect_ok(response, "cleanup product")
            print("[cleanup] produto temporário removido")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default="demo@marketplace.local")
    parser.add_argument("--password", default="demo123456")
    parser.add_argument("--mutating", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print("[health]")
    expect_ok(requests.get(f"{base}/health", timeout=10), "health")
    print("[login]")
    tokens = expect_ok(
        requests.post(f"{base}/auth/login", json={"email": args.email, "senha": args.password}, timeout=10),
        "login",
    )
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    run_read_only(base, headers)
    if args.mutating:
        run_temporary_flow(base, headers)
    print("SMOKE OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
