# Dados da demonstração

Todos os dados de `portfolio/` são sintéticos:

- empresa, sellers e produtos fictícios;
- pedidos e valores financeiros inventados;
- métricas de ML apenas demonstrativas;
- nenhuma cópia de dados pessoais ou de marketplace;
- timestamp fixo e dataset versionado para permitir reprodução.

`portfolio/tests/demo-data.test.mjs` garante que todas as áreas tenham conteúdo
e que pricing, forecast e predições referenciem produtos existentes.

O acesso demonstrativo e as mutações da War Room são gravados em
`sessionStorage`; fechar a aba encerra o estado. “Reiniciar cenário” limpa as
ações imediatamente.

A tela inicial simula um login usando somente credenciais fictícias
preenchidas e não envia qualquer valor. A demo não carrega analytics,
formulários de coleta ou API. Interações não são compartilhadas entre
visitantes.
