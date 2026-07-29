# Aviso de Privacidade — SellerOS

Última atualização: 29 de julho de 2026.

## Escopo

O SellerOS é um estudo de caso de engenharia para uso pessoal. Ele não é uma
oferta comercial. Existem duas experiências separadas:

- a demonstração pública em `portfolio/`, publicada como site estático;
- o console pessoal em `frontend/`, conectado à API apenas quando operado pelo
  responsável pelo projeto.

Este aviso documenta decisões de privacidade e não representa certificação
automática de conformidade jurídica.

## Demonstração pública

A demonstração pública não possui login, formulário, analytics, cookies,
backend ou banco remoto. Ela usa somente dados sintéticos versionados.

As interações fictícias do War Room são guardadas em `sessionStorage` no
dispositivo do visitante e desaparecem ao final da sessão. O Netlify pode
manter registros técnicos de acesso conforme suas próprias configurações e
políticas.

## Console pessoal

Quando o console é executado, podem ser tratados:

- nome, e-mail, perfil de acesso e vínculo organizacional;
- hash de senha e tokens protegidos por criptografia ou hash;
- identificadores fornecidos por integrações iniciadas pelo usuário;
- registros técnicos mínimos para segurança, diagnóstico e auditoria;
- dados operacionais inseridos ou sincronizados pelo próprio responsável.

As finalidades são autenticação, entrega das funcionalidades solicitadas,
segurança, prevenção a fraude, diagnóstico e atendimento de direitos.

As bases legais devem ser definidas pelo controlador para cada implantação.
O projeto prevê execução de contrato ou procedimento solicitado, legítimo
interesse após avaliação, obrigação legal/regulatória e consentimento somente
para tratamentos opcionais claramente identificados.

## Compartilhamento condicional

Dados somente são enviados a terceiros quando a respectiva funcionalidade é
configurada e acionada:

- Mercado Livre, para OAuth e sincronização;
- Resend, para e-mails transacionais;
- Pagar.me, para billing histórico, caso habilitado;
- Netlify e GitHub, para hospedagem do código e da demo pública.

Antes de uma implantação real, o responsável deve avaliar contratos,
localização, retenção, transferências internacionais e medidas de cada
operador.

## Retenção e segurança

Logs técnicos possuem prazos configuráveis. Tokens e convites expirados são
elegíveis para descarte. Dados da conta permanecem somente enquanto necessários
à finalidade ou a obrigações aplicáveis.

O projeto emprega minimização, segregação por tenant, tokens criptografados ou
em hash, OAuth com estado assinado e de uso único, controle de acesso e headers
defensivos. Nenhum sistema é completamente imune a incidentes.

## Direitos do titular

O console autenticado permite:

- exportar os próprios dados;
- protocolar confirmação e acesso;
- solicitar correção, eliminação, anonimização ou bloqueio;
- solicitar portabilidade;
- revogar consentimento, quando essa for a base legal;
- solicitar revisão humana de decisão automatizada.

Eliminação não é absoluta e pode ser limitada por hipóteses legais de
conservação. Modelos do SellerOS apenas recomendam; nenhuma predição altera
preço ou publica anúncio sem confirmação humana.

O contato privado deve ser configurado em `PRIVACY_CONTACT_EMAIL` antes de
operar a API em produção. Para dúvidas gerais sobre este repositório, use o
perfil público [vinmedrado no GitHub](https://github.com/vinmedrado), sem
publicar dados pessoais em issues.

Mais detalhes operacionais estão em [Governança LGPD](docs/LGPD.md).
