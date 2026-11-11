# Marketplace Seller Platform — Technical case study

*English / Español · Data engineering, automation, backend and product design*

## The problem

Marketplace sellers often operate across disconnected catalog exports, pricing spreadsheets and API integrations. That makes it difficult to understand margins, track changes and explain a price recommendation.

## System design

\`\`\`text
Static React portfolio (synthetic data; no credentials)
Authenticated React console → FastAPI → domain services → SQLAlchemy / PostgreSQL
                                     ↘ data pipelines / pricing / ML
\`\`\`

The **public portfolio** is deliberately isolated from the **authenticated operations console**. A seller's product operations are scoped by tenant, and updates accept only permitted commercial fields. Pricing combines costs, fees and margin constraints with competitive inputs, with rule-based fallback when an ML artifact is unavailable.

The repository separates \`frontend/\`, \`portfolio/\`, \`ui/\`, \`services/\`, \`pricing/\`, \`ml/\` and \`data_engineering/\`. Database schema changes use Alembic.

## What this demonstrates

- Practical data engineering across ingestion, transformation, analytics and operational APIs.
- Design boundaries: public demo vs authenticated tenant-specific operations.
- Explainable decisions instead of opaque price suggestions.
- Security-minded controls: OAuth callback validation, encrypted stored tokens and scoped product updates.

## Quality evidence

The [CI workflow](../.github/workflows/ci.yml) runs backend tests/migrations, privacy checks and dependency checks, plus frontend/demo tests and builds. Dependency-audit configuration has documented limitations; CI alone is not a penetration test.

**Architecture decision:** in-process job execution fits this project scope but needs a durable queue and distributed locking for horizontal production scale.

## Explore

- [Public demo](https://vinmedrado.github.io/marketplace-seller-platform/)
- [Architecture](ARCHITECTURE.md)
- [Security documentation](SECURITY.md)
- [Source code](https://github.com/vinmedrado/marketplace-seller-platform)

---

## Resumen en español

**Problema:** los vendedores gestionan catálogos, precios y datos comerciales en herramientas desconectadas.

**Solución:** plataforma con API FastAPI, PostgreSQL y React que integra flujos de datos, gestión de productos y recomendaciones de precios explicables. La demostración pública utiliza **datos sintéticos** y está separada de la consola autenticada.

**Competencias demostradas:** ingeniería de datos, automatización, APIs REST, aislamiento entre clientes, pruebas automatizadas y decisiones de arquitectura.

**Limitación explícita:** los controles automatizados no equivalen a una auditoría integral de seguridad; los procesos en memoria necesitarían una cola persistente para escalar.

[Ver demo](https://vinmedrado.github.io/marketplace-seller-platform/) · [Ver código](https://github.com/vinmedrado/marketplace-seller-platform)
