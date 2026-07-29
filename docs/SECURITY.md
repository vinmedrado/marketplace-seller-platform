# Segurança

## Controles existentes

- Segredos fracos, SQLite, conta demo e URLs HTTP são rejeitados em produção.
- Tokens de marketplace são persistidos somente criptografados.
- Colunas legadas de token em texto simples são removidas por migration.
- OAuth `state` possui assinatura HMAC, expiração, nonce e consumo único.
- Refresh tokens são armazenados por hash e rotacionados.
- Login e utilitários públicos possuem rate limiting de processo.
- OpenAPI e Redoc ficam desabilitados em produção.
- Netlify e Nginx enviam CSP e headers defensivos.
- A demo pública não possui backend nem segredos.
- Exportações LGPD excluem hashes de senha, tokens e nonces.
- Produção exige canal de privacidade configurado e possui retenção
  parametrizada para logs técnicos.

## Operação

Nunca publique `.env`. Gere `API_SECRET_KEY` com pelo menos 32 caracteres e uma
`FERNET_KEY` válida. Configure somente origens HTTPS no CORS de produção.

Quando billing estiver configurado, `PAGARME_WEBHOOK_SECRET` é obrigatório.
Convites expiram após sete dias e o token só é devolvido pela API em
desenvolvimento quando o envio de e-mail não está configurado.

## Limites

O rate limiter é local ao processo. Uma implantação distribuída deve aplicar
limites no gateway ou usar armazenamento compartilhado.

A rotina `scripts/privacy_cleanup.py` inicia em dry-run. Backups e dados
operacionais exigem política complementar da implantação; não são apagados
automaticamente.

O console usa `sessionStorage`, reduzindo persistência entre sessões, mas
cookies HttpOnly seriam a evolução recomendada para um produto público.

O console privado mantém React Router para navegação SPA. O `npm audit` atual
aponta advisories de RSC/Server Actions nessa dependência; esses recursos não
são usados pelo projeto cliente-only. A demo pública não usa React Router e
possui auditoria npm sem vulnerabilidades conhecidas. A dependência deve
continuar sendo atualizada quando houver correção upstream sem regressão.
