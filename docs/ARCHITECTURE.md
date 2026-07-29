# Arquitetura

## Contextos de execução

### Portfólio público

`portfolio/` é uma aplicação React estática. Os dados vêm de
`src/demo-data.json`, passam por um teste de integridade e não fazem chamadas de
rede. Interações são isoladas por aba do navegador.

### Console pessoal

`frontend/` consome a API FastAPI. A API autentica o usuário, obtém o tenant do
token e repassa o caso de uso à camada de serviços. SQLAlchemy persiste
entidades no PostgreSQL; Alembic controla a evolução do schema.

## Fluxos importantes

### Pricing

1. O produto é buscado dentro do tenant autenticado.
2. Custos, comissão, imposto e margem mínima formam um piso.
3. Estatísticas competitivas ajustam a recomendação.
4. ML é usado quando existe um artefato válido do tenant.
5. Feature inválida ou artefato ausente aciona fallback rule-based.
6. Alterações operacionais permanecem explícitas.

### Mercado Livre

1. O backend cria um `state` aleatório, assinado, expirável e de uso único.
2. O callback valida assinatura, prazo e nonce armazenado.
3. Tokens são criptografados antes da persistência.
4. Sincronização do catálogo acontece por comando autenticado.

### Inteligência

Forecast e análise de portfólio são leituras idempotentes. Snapshots históricos,
ações e eventos são gerados apenas por endpoints `POST` de atualização.

## Trade-offs

O executor de jobs em processo é adequado ao uso pessoal, mas perderia
durabilidade numa implantação horizontal. Uma evolução comercial exigiria fila
externa, locking distribuído, retries e observabilidade de worker.

O caminho executável e suportado para evolução do schema é exclusivamente
`db/alembic/`; novas mudanças devem ser geradas e revisadas por Alembic.
