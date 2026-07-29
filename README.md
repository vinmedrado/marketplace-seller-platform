# MarketPlace Seller Platform

Estudo de caso full-stack para operação e inteligência de sellers em
marketplaces. O projeto combina React, FastAPI, PostgreSQL, pipelines de dados,
pricing assistido, ML explicável e privacidade por design.

O MarketPlace Seller Platform não é comercializado. O repositório mantém duas experiências
deliberadamente separadas:

- `frontend/`: console pessoal conectado à API e às integrações reais.
- `portfolio/`: demonstração pública para recrutadores, sem backend, usuários,
  tokens ou dados reais.

[![CI](https://github.com/vinmedrado/marketplace-seller-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/vinmedrado/marketplace-seller-platform/actions/workflows/ci.yml)

**[Abrir demonstração pública](https://marketplace-seller-platform.netlify.app/)**

## O que a demonstração apresenta

A aplicação pública oferece nove áreas preenchidas por um cenário sintético e
determinístico: visão executiva, catálogo, pricing e concorrência, War Room,
forecast, reconciliação financeira, ML explicável, arquitetura e LGPD.

As ações da demo são armazenadas apenas em `sessionStorage`. O botão
“Reiniciar cenário” restaura a experiência original, e nenhum visitante altera
o cenário visto por outra pessoa.

```text
portfolio/ ── JSON sintético versionado ── Netlify

frontend/ ── FastAPI ── service layer ── PostgreSQL
                              ├── Mercado Livre OAuth
                              ├── pricing/forecast
                              └── datasets e modelos ML por tenant
```

## Executar a demo pública

Requer Node.js 22.12 ou superior.

```bash
cd portfolio
npm ci
npm test
npm run check
npm run build
npm run dev
```

O arquivo `netlify.toml` já define base, build, publicação, rewrite SPA,
headers de segurança e cache de assets. Ao conectar este repositório no
Netlify, a aplicação publicada será exclusivamente `portfolio/`.

## Executar o console pessoal

Copie `.env.example` para `.env`, ajuste segredos e execute:

```bash
docker compose up --build
```

- Console: `http://localhost:5173`
- API: `http://localhost:8000`
- OpenAPI, somente fora de produção: `http://localhost:8000/docs`

O container executa `alembic upgrade head` antes de iniciar a API. A conta demo
é habilitada por padrão somente em desenvolvimento/teste e deve permanecer
desabilitada em produção.

Para preparar o cenário sintético local sem Docker:

```bash
alembic upgrade head
python scripts/seed_demo.py
```

O reset é bloqueado em produção e exige confirmação explícita:

```bash
python scripts/reset_demo.py --yes
```

## Qualidade

Backend:

```bash
python -m compileall -q .
pytest -q
python -m pip_audit -r requirements.txt
```

Console:

```bash
cd frontend
npm ci
npm run check
npm run lint
npm test
npm run build
```

Demo pública:

```bash
cd portfolio
npm ci
npm run check
npm test
npm run build
npm audit
```

## Privacidade e LGPD

A demo pública possui uma tela de acesso inteiramente local, com credenciais
fictícias já preenchidas. Não há autenticação remota, analytics, formulários
de coleta, API ou banco remoto.
O console pessoal oferece aviso de transparência, exportação autenticada e
protocolos de direitos do titular. Logs, tokens, nonces e convites possuem
política explícita de retenção e descarte.

```bash
# apenas informa registros elegíveis
python scripts/privacy_cleanup.py

# aplica a política configurada
python scripts/privacy_cleanup.py --apply
```

Produção exige um canal privado em `PRIVACY_CONTACT_EMAIL`. Consulte o
[Aviso de Privacidade](PRIVACY.md) e a
[Governança LGPD](docs/LGPD.md). Esses controles apoiam conformidade, mas não
substituem decisões do controlador, contratos e avaliação jurídica.

## Organização

| Diretório | Responsabilidade |
|---|---|
| `ui/` | Contratos HTTP FastAPI |
| `services/` | Casos de uso e inteligência operacional |
| `models/` | ORM e schemas Pydantic |
| `db/alembic/` | Evolução executável do schema |
| `pricing/` | Regras, guardrails e cálculo de preço |
| `ml/` | Features, treinamento, inferência e fallback |
| `data_engineering/` | Raw, staging, marts e feature store |
| `integrations/` | OAuth e API Mercado Livre |
| `frontend/` | Console pessoal |
| `portfolio/` | Experiência pública Netlify |
| `tests/` | Testes unitários e integrados do backend |

Mais detalhes em [Arquitetura](docs/ARCHITECTURE.md),
[Segurança](docs/SECURITY.md), [Governança LGPD](docs/LGPD.md) e
[Política de dados da demo](docs/DEMO_DATA.md).

## Limites assumidos

- Jobs do console pessoal executam em processo; não representam uma fila
  distribuída.
- Forecast é heurístico e sempre comunica confiança e limitações.
- Billing e planos foram mantidos como exercício arquitetural histórico, não
  como oferta comercial.
- Amazon e Shopee não são anunciados como integrações implementadas.

## Licença

MIT.
