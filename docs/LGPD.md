# Governança de Privacidade e LGPD

## Objetivo

Este documento transforma a LGPD em requisitos verificáveis de engenharia e
operação. Código, políticas e configurações apoiam a conformidade, mas a
responsabilidade final depende de contexto, decisões do controlador,
contratos, treinamento e avaliação jurídica.

## Papéis

| Papel | Responsabilidade |
|---|---|
| Controlador | Define finalidades, bases legais, retenção e respostas aos titulares |
| Operador | Trata dados conforme instruções documentadas do controlador |
| Encarregado/canal | Recebe titulares e ANPD; `PRIVACY_CONTACT_EMAIL` é obrigatório em produção |
| Administrador técnico | Aplica acesso mínimo, atualizações, backups, descarte e resposta a incidentes |

No uso pessoal, uma mesma pessoa pode acumular papéis, mas deve registrar as
decisões.

## Inventário de tratamento

| Categoria | Exemplos | Finalidade | Proteção | Retenção padrão |
|---|---|---|---|---|
| Identificação | nome, e-mail | conta, acesso e comunicação | segregação por tenant e RBAC | vida da conta e obrigações aplicáveis |
| Autenticação | hash de senha, refresh token | segurança da sessão | hash, rotação, revogação e expiração | até expiração ou revogação |
| Integração | seller ID, nickname, tokens OAuth | funcionalidade solicitada | tokens criptografados; state em hash | enquanto integração ativa ou necessário |
| Logs técnicos | endpoint, status, erro sanitizado | segurança e diagnóstico | sem payload ou segredo | 90 dias, configurável |
| Protocolo LGPD | tipo, status e resposta | exercício de direitos e accountability | acesso autenticado e tenant | 1.825 dias, configurável |
| Operação do seller | catálogo, preço, estoque e pedidos | funcionalidades pessoais | tenant, RBAC e minimização | definida pelo responsável |
| Billing opcional | cliente e assinatura | cobrança, se habilitada | webhook assinado e acesso restrito | conforme obrigação contratual/fiscal |

O cenário público é sintético. Dados reais nunca devem ser copiados para
`portfolio/src/demo-data.json`, seeds, screenshots, fixtures ou documentação.

## Princípios incorporados

- **Finalidade e adequação:** cada categoria está vinculada a propósito
  documentado.
- **Necessidade:** a demo elimina backend; logs não armazenam corpo de
  requisição; exportação exclui credenciais.
- **Livre acesso e transparência:** `GET /privacy` e `PRIVACY.md`.
- **Qualidade:** solicitação de correção protocolada.
- **Segurança e prevenção:** criptografia, hash, expiração, RBAC, CSP e
  validações fail-fast.
- **Não discriminação:** ML usa sinais operacionais, não atributos pessoais
  sensíveis.
- **Responsabilização:** migration, protocolos, política de retenção e trilha
  de testes.

## Direitos do titular

Rotas autenticadas:

- `GET /privacy/me/export`: cópia estruturada dos dados pessoais do usuário;
- `GET /privacy/me/requests`: protocolos do titular autenticado;
- `POST /privacy/me/requests`: acesso, correção, eliminação, anonimização,
  portabilidade, revogação ou revisão.

Fluxo operacional:

1. autenticar o titular ou validar sua identidade por canal privado;
2. acusar recebimento e fornecer protocolo;
3. atender confirmação/acesso simplificado imediatamente quando possível;
4. responder declaração completa, incluindo origem, critérios e finalidade,
   em até 15 dias;
5. registrar decisão, execução, limitações legais e comunicação a operadores;
6. nunca enviar hash de senha, token, nonce ou segredo em uma exportação.

Pedidos de eliminação devem preservar dados quando houver obrigação legal,
exercício regular de direitos ou outra hipótese válida de conservação. O
controlador deve explicar eventual negativa.

## Retenção e descarte

Variáveis:

```text
API_LOG_RETENTION_DAYS=90
SCRAPING_LOG_RETENTION_DAYS=90
PRIVACY_REQUEST_RETENTION_DAYS=1825
```

Simulação:

```bash
python scripts/privacy_cleanup.py
```

Aplicação:

```bash
python scripts/privacy_cleanup.py --apply
```

A rotina remove somente logs técnicos antigos, estados OAuth, refresh tokens,
convites expirados e protocolos concluídos fora do prazo. Exclusão de conta ou
dados operacionais exige decisão humana para evitar perda indevida e respeitar
hipóteses de conservação.

Backups devem ter prazo próprio, criptografia, restauração testada e expiração
compatível. Descarte do banco primário deve propagar-se aos backups no ciclo
documentado.

## Decisões automatizadas

Random Forest e heurísticas apenas produzem recomendações com confiança,
fatores e guardrails. Publicação, repricing e ações do War Room dependem de
confirmação humana. O titular pode protocolar revisão em
`POST /privacy/me/requests` com `request_type=review`.

## Incidentes

Ao tomar conhecimento de incidente com risco ou dano relevante:

1. conter, preservar evidências e registrar data/hora;
2. identificar dados, titulares, sistemas, operadores, riscos e medidas;
3. acionar o responsável por privacidade;
4. comunicar ANPD e titulares em até três dias úteis, quando aplicável;
5. complementar informações e mitigar impactos;
6. manter o registro do incidente por pelo menos cinco anos;
7. revisar causa raiz, acessos, chaves, backups e controles.

Comunicados aos titulares devem usar linguagem simples e informar natureza dos
dados, controles, riscos, impactos, medidas, data de conhecimento e contato.
Não se deve expor segredo técnico que amplie o incidente.

## Operadores e transferências

Antes de habilitar GitHub, Netlify, Mercado Livre, Resend, Pagar.me ou qualquer
novo fornecedor:

- revisar termos, DPA, suboperadores e região de armazenamento;
- documentar finalidade, dados enviados e retenção;
- verificar transferências internacionais e mecanismo aplicável;
- conceder somente escopos necessários;
- definir procedimento de exclusão e resposta a incidente.

## Checklist de produção

- [ ] Definir formalmente controlador e canal privado do titular.
- [ ] Preencher `PRIVACY_CONTACT_EMAIL`.
- [ ] Confirmar bases legais por tratamento e teste de balanceamento para
      legítimo interesse.
- [ ] Revisar contratos e transferências dos operadores.
- [ ] Definir retenção de dados operacionais e backups.
- [ ] Testar exportação, protocolo e descarte em homologação.
- [ ] Documentar RBAC e revisar acessos periodicamente.
- [ ] Criar registro privado de incidentes e contatos de emergência.
- [ ] Elaborar RIPD quando o risco, escala ou natureza do tratamento exigir.
- [ ] Revisar este inventário a cada mudança de finalidade ou fornecedor.

## Referências oficiais

- [Lei nº 13.709/2018 — LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Direitos dos titulares — ANPD](https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares)
- [Comunicação de incidente — ANPD](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis)
- [Regulamentações da ANPD](https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd)
