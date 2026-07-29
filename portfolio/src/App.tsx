import { useEffect, useMemo, useState } from 'react';
import rawData from './demo-data.json';

type Risk = 'healthy' | 'medium' | 'high' | 'critical' | 'slow';
type ActionStatus = 'pending' | 'applied' | 'ignored';
type Action = {
  id: string;
  priority: string;
  title: string;
  source: string;
  impact: number;
  confidence: number;
  status: ActionStatus;
};

const data = rawData;
const money = (value: number) => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const number = (value: number) => value.toLocaleString('pt-BR');
const riskLabel: Record<Risk, string> = {
  healthy: 'Saudável',
  medium: 'Atenção',
  high: 'Alto',
  critical: 'Crítico',
  slow: 'Baixo giro',
};

const nav = [
  ['/', 'Visão executiva', '⌁'],
  ['/catalogo', 'Catálogo', '▦'],
  ['/pricing', 'Pricing & mercado', '↗'],
  ['/war-room', 'War Room', '◎'],
  ['/forecast', 'Forecast', '◫'],
  ['/financeiro', 'Financeiro', '≋'],
  ['/ml', 'ML explicável', '✦'],
  ['/arquitetura', 'Como funciona', '◇'],
  ['/privacidade', 'Privacidade & LGPD', '◈'],
] as const;

function usePortfolioRouter() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);
  return { path };
}

function AppLink({ to, children, className, onClick: afterNavigate }: { to: string; children: React.ReactNode; className?: string; onClick?: () => void }) {
  const onClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.history.pushState({}, '', to);
    window.dispatchEvent(new PopStateEvent('popstate'));
    window.scrollTo({ top: 0, behavior: 'smooth' });
    afterNavigate?.();
  };
  return <a href={to} className={className} onClick={onClick}>{children}</a>;
}

function useDemoActions() {
  const [actions, setActions] = useState<Action[]>(() => {
    try {
      const stored = sessionStorage.getItem('selleros-portfolio-actions');
      return stored ? JSON.parse(stored) : data.actions;
    } catch {
      return data.actions as Action[];
    }
  });

  const update = (id: string, status: ActionStatus) => {
    setActions((current) => {
      const next = current.map((action) => action.id === id ? { ...action, status } : action);
      sessionStorage.setItem('selleros-portfolio-actions', JSON.stringify(next));
      return next;
    });
  };
  const reset = () => {
    sessionStorage.removeItem('selleros-portfolio-actions');
    setActions(data.actions as Action[]);
  };
  return { actions, update, reset };
}

function Shell({ children, reset, path }: { children: React.ReactNode; reset: () => void; path: string }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className="app-shell">
      <aside className={mobileOpen ? 'sidebar open' : 'sidebar'}>
        <div className="brand">
          <span className="brand-mark">S</span>
          <span><strong>SellerOS</strong><small>engineering portfolio</small></span>
        </div>
        <nav aria-label="Navegação principal">
          {nav.map(([routePath, label, icon]) => (
            <AppLink
              key={routePath}
              to={routePath}
              onClick={() => setMobileOpen(false)}
              className={path === routePath ? 'nav-link active' : 'nav-link'}
            >
              <span aria-hidden="true">{icon}</span>{label}
            </AppLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="pulse" /> Ambiente demonstrativo
          <small>Sem API ou credenciais reais</small>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen((value) => !value)} aria-label="Abrir menu">☰</button>
          <div className="demo-notice">
            <span>DEMO</span>
            <p><strong>{data.metadata.scenario}</strong><small>Dados 100% sintéticos e determinísticos</small></p>
          </div>
          <button className="button ghost" onClick={reset}>↻ Reiniciar cenário</button>
        </header>
        <main>{children}</main>
        <footer>
          SellerOS é um estudo de caso de engenharia. Nenhuma venda, empresa ou integração exibida é real.{' '}
          <AppLink to="/privacidade">Privacidade e LGPD</AppLink>
        </footer>
      </div>
      {mobileOpen && <button className="backdrop" aria-label="Fechar menu" onClick={() => setMobileOpen(false)} />}
    </div>
  );
}

function PageHeader({ eyebrow, title, text, children }: { eyebrow: string; title: string; text: string; children?: React.ReactNode }) {
  return (
    <div className="page-header">
      <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{text}</p></div>
      {children}
    </div>
  );
}

function Badge({ value }: { value: string }) {
  const normalized = value.toLowerCase() as Risk;
  return <span className={`badge ${normalized}`}>{riskLabel[normalized] ?? value}</span>;
}

function Overview({ actions }: { actions: Action[] }) {
  const maxRevenue = Math.max(...data.revenueSeries.map((point) => point.value));
  return (
    <>
      <PageHeader eyebrow="OPERAÇÃO EM UM RELANCE" title="Decisões antes de dashboards" text="Uma visão executiva que conecta receita, margem, competitividade e risco operacional." />
      <section className="kpi-grid">
        {data.kpis.map((kpi) => (
          <article className="card kpi" key={kpi.label}>
            <span>{kpi.label}</span>
            <strong>{kpi.kind === 'currency' ? money(kpi.value) : `${number(kpi.value)}${kpi.kind === 'percent' ? '%' : '/100'}`}</strong>
            <small className="positive">↗ {kpi.delta}% no cenário</small>
          </article>
        ))}
      </section>
      <section className="split">
        <article className="card">
          <div className="card-title"><div><span className="eyebrow">GMV SINTÉTICO</span><h2>Evolução mensal</h2></div><strong>{money(286450)}</strong></div>
          <div className="bar-chart" aria-label="Gráfico de evolução mensal de GMV">
            {data.revenueSeries.map((point) => (
              <div key={point.label} className="bar-item"><div style={{ height: `${(point.value / maxRevenue) * 100}%` }} /><span>{point.label}</span></div>
            ))}
          </div>
        </article>
        <article className="card">
          <div className="card-title"><div><span className="eyebrow">PRÓXIMA MELHOR AÇÃO</span><h2>Fila priorizada</h2></div><AppLink to="/war-room">Abrir War Room →</AppLink></div>
          <div className="action-list compact">
            {actions.filter((action) => action.status === 'pending').slice(0, 4).map((action) => (
              <div className="action-row" key={action.id}><i className={action.priority} /><div><strong>{action.title}</strong><small>{action.source} · {action.confidence}% confiança</small></div><span>{money(action.impact)}</span></div>
            ))}
          </div>
        </article>
      </section>
      <section className="card">
        <div className="card-title"><div><span className="eyebrow">PORTFÓLIO</span><h2>Produtos que exigem atenção</h2></div><AppLink to="/catalogo">Ver catálogo →</AppLink></div>
        <ProductTable products={data.products.filter((product) => product.risk !== 'healthy').slice(0, 4)} />
      </section>
    </>
  );
}

function ProductTable({ products }: { products: typeof data.products }) {
  return (
    <div className="table-scroll"><table>
      <thead><tr><th>Produto</th><th>Preço</th><th>Margem</th><th>Estoque</th><th>Vendas 30d</th><th>Buy Box</th><th>Saúde</th></tr></thead>
      <tbody>{products.map((product) => <tr key={product.id}>
        <td><strong>{product.title}</strong><small>{product.sku} · {product.category}</small></td>
        <td>{money(product.price)}</td><td>{product.margin}%</td><td>{product.stock}</td><td>{product.sold30d}</td><td>{product.buyBox}%</td><td><Badge value={product.risk} /></td>
      </tr>)}</tbody>
    </table></div>
  );
}

function Catalog() {
  const [query, setQuery] = useState('');
  const products = data.products.filter((product) => `${product.title} ${product.sku} ${product.category}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <>
      <PageHeader eyebrow="CATÁLOGO UNIFICADO" title="Saúde do portfólio" text="Campos operacionais, financeiros e competitivos reunidos por SKU.">
        <label className="search">⌕<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar SKU ou produto" /></label>
      </PageHeader>
      <div className="summary-strip"><span><strong>{data.products.length}</strong> produtos</span><span><strong>3</strong> categorias críticas</span><span><strong>23,7%</strong> margem média</span><span><strong>R$ 76 mil</strong> estoque a custo</span></div>
      <section className="card"><ProductTable products={products} /></section>
    </>
  );
}

function Pricing() {
  const [message, setMessage] = useState('');
  return (
    <>
      <PageHeader eyebrow="PRICING ENGINE" title="Preço com contexto de mercado" text="Recomendações explicáveis respeitando custo, comissão, imposto e margem mínima." />
      {message && <div className="toast" role="status">✓ {message}</div>}
      <section className="recommendation-grid">
        {data.pricing.map((item) => {
          const product = data.products.find((entry) => entry.id === item.productId)!;
          return <article className="card recommendation" key={item.productId}>
            <div className="confidence">{item.confidence}%<small>confiança</small></div>
            <span className="eyebrow">{product.sku}</span><h2>{product.title}</h2><p>{item.reason}</p>
            <div className="price-compare"><span>Atual<strong>{money(item.current)}</strong></span><b>→</b><span>Sugerido<strong>{money(item.suggested)}</strong></span><span>Mercado<strong>{money(item.market)}</strong></span></div>
            <div className="recommendation-foot"><span>Impacto estimado <strong>+{money(item.impact)}/mês</strong></span><button className="button" onClick={() => setMessage(`Simulação de ${product.sku} aplicada somente nesta sessão.`)}>Simular ajuste</button></div>
          </article>;
        })}
      </section>
      <section className="card">
        <div className="card-title"><div><span className="eyebrow">SINAIS COMPETITIVOS</span><h2>Mercado monitorado</h2></div><span className="live"><i /> atualização sintética</span></div>
        <div className="table-scroll"><table><thead><tr><th>Seller fictício</th><th>Produto</th><th>Preço</th><th>Reputação</th><th>Entrega</th><th>Sinal</th></tr></thead>
          <tbody>{data.competitors.map((competitor) => <tr key={competitor.seller}><td><strong>{competitor.seller}</strong></td><td>{competitor.productId}</td><td>{money(competitor.price)}</td><td>{competitor.reputation}%</td><td>{competitor.shipping}</td><td><span className="badge medium">{competitor.signal.replace('_', ' ')}</span></td></tr>)}</tbody>
        </table></div>
      </section>
    </>
  );
}

function WarRoom({ actions, update }: { actions: Action[]; update: (id: string, status: ActionStatus) => void }) {
  const [simulation, setSimulation] = useState(false);
  const pendingImpact = actions.filter((action) => action.status === 'pending').reduce((sum, action) => sum + action.impact, 0);
  return (
    <>
      <PageHeader eyebrow="DECISION INTELLIGENCE" title="Market War Room" text="Riscos e oportunidades traduzidos em ações rastreáveis — sem automação silenciosa.">
        <button className="button" onClick={() => setSimulation(true)}>▶ Simular resposta competitiva</button>
      </PageHeader>
      {simulation && <div className="simulation"><div><span className="eyebrow">SIMULAÇÃO LOCAL</span><strong>Preço R$ 474,90 · margem 17,4% · +R$ 1.320/mês</strong><small>Nenhum dado foi enviado ou persistido.</small></div><button onClick={() => setSimulation(false)}>×</button></div>}
      <section className="war-summary">
        <article><span>Impacto pendente</span><strong>{money(pendingImpact)}</strong></article><article><span>Ações críticas</span><strong>{actions.filter((a) => a.priority === 'critical' && a.status === 'pending').length}</strong></article><article><span>Já tratadas</span><strong>{actions.filter((a) => a.status !== 'pending').length}</strong></article>
      </section>
      <section className="card action-list">
        {actions.map((action) => <div className={`action-row full ${action.status}`} key={action.id}>
          <i className={action.priority} /><div><span className="eyebrow">{action.source}</span><strong>{action.title}</strong><small>{action.confidence}% confiança · impacto {money(action.impact)}/mês</small></div>
          <span className={`status ${action.status}`}>{action.status === 'pending' ? 'Pendente' : action.status === 'applied' ? 'Aplicada' : 'Ignorada'}</span>
          <div className="row-buttons"><button onClick={() => update(action.id, 'ignored')} disabled={action.status !== 'pending'}>Ignorar</button><button className="button" onClick={() => update(action.id, 'applied')} disabled={action.status !== 'pending'}>Aplicar na demo</button></div>
        </div>)}
      </section>
    </>
  );
}

function Forecast() {
  return (
    <>
      <PageHeader eyebrow="DEMAND FORECAST" title="Estoque antes da ruptura" text="Estimativa heurística baseada em giro sintético, cobertura e lead time — nunca uma promessa de vendas." />
      <section className="forecast-grid">{data.forecast.map((item) => {
        const product = data.products.find((entry) => entry.id === item.productId)!;
        const coverage = Math.min(100, (item.daysRemaining / 60) * 100);
        return <article className="card forecast-card" key={item.productId}>
          <div><Badge value={item.risk} /><span>{item.confidence}% confiança</span></div><h2>{product.title}</h2><small>{product.sku}</small>
          <strong className="days">{item.daysRemaining}<small> dias de cobertura</small></strong>
          <div className="meter"><i style={{ width: `${coverage}%` }} /></div>
          <dl><div><dt>Venda diária</dt><dd>{item.dailySales}</dd></div><div><dt>Ponto de reposição</dt><dd>{item.reorderPoint} un.</dd></div><div><dt>Tendência</dt><dd>{item.trend}</dd></div></dl>
        </article>;
      })}</section>
    </>
  );
}

function Finance() {
  const totals = useMemo(() => data.transactions.reduce((acc, item) => ({ gross: acc.gross + item.gross, expected: acc.expected + item.netExpected, received: acc.received + item.netReceived }), { gross: 0, expected: 0, received: 0 }), []);
  return (
    <>
      <PageHeader eyebrow="FINANCIAL RECONCILIATION" title="Do pedido ao recebimento" text="Separação explícita entre venda bruta, taxas, frete, líquido previsto e valor recebido." />
      <section className="kpi-grid three"><article className="card kpi"><span>Bruto conciliado</span><strong>{money(totals.gross)}</strong><small>5 pedidos sintéticos</small></article><article className="card kpi"><span>Líquido previsto</span><strong>{money(totals.expected)}</strong><small>Após taxas e frete</small></article><article className="card kpi"><span>Divergência</span><strong className="negative">{money(totals.expected - totals.received)}</strong><small>1 pedido para investigar</small></article></section>
      <section className="card"><div className="table-scroll"><table><thead><tr><th>Pedido</th><th>Data</th><th>Bruto</th><th>Taxas</th><th>Frete</th><th>Previsto</th><th>Recebido</th><th>Status</th></tr></thead>
        <tbody>{data.transactions.map((item) => <tr key={item.id}><td><strong>{item.id}</strong></td><td>{item.date}</td><td>{money(item.gross)}</td><td>{money(item.fees)}</td><td>{money(item.shipping)}</td><td>{money(item.netExpected)}</td><td>{money(item.netReceived)}</td><td><span className={`badge ${item.status === 'matched' ? 'healthy' : 'critical'}`}>{item.status === 'matched' ? 'Conciliado' : 'Divergente'}</span></td></tr>)}</tbody>
      </table></div></section>
    </>
  );
}

function MachineLearning() {
  return (
    <>
      <PageHeader eyebrow="ASSISTED ML" title="Modelo útil, fallback seguro" text="Random Forest para recomendação de preço, com guardrails de margem e fallback rule-based." />
      <section className="kpi-grid"><article className="card kpi"><span>MAE</span><strong>{money(data.ml.metrics.mae)}</strong><small>Erro absoluto médio</small></article><article className="card kpi"><span>R²</span><strong>{data.ml.metrics.r2}</strong><small>Holdout sintético</small></article><article className="card kpi"><span>Amostras</span><strong>{number(data.ml.metrics.samples)}</strong><small>Treino demonstrativo</small></article><article className="card kpi"><span>Versão</span><strong className="version">{data.ml.metrics.version}</strong><small>Artefato rastreável</small></article></section>
      <section className="split">
        <article className="card"><div className="card-title"><div><span className="eyebrow">EXPLICABILIDADE</span><h2>Importância das features</h2></div></div><div className="features">{data.ml.features.map((feature) => <div key={feature.name}><span>{feature.name}<strong>{feature.importance}%</strong></span><i><b style={{ width: `${feature.importance * 2.8}%` }} /></i></div>)}</div></article>
        <article className="card"><div className="card-title"><div><span className="eyebrow">GUARDRAILS</span><h2>Antes da inferência</h2></div></div><ol className="guardrails"><li>Custo, comissão, imposto e margem definem o piso.</li><li>Features inválidas acionam fallback determinístico.</li><li>Modelo e dataset são isolados por tenant.</li><li>Predição nunca publica ou altera preço sozinha.</li></ol></article>
      </section>
      <section className="card"><div className="card-title"><div><span className="eyebrow">AMOSTRA DE INFERÊNCIA</span><h2>Previsto versus atual</h2></div></div><div className="prediction-grid">{data.ml.predictions.map((prediction) => <div key={prediction.productId}><strong>{prediction.productId}</strong><span>Atual {money(prediction.actual)}</span><span>Previsto {money(prediction.predicted)}</span><small>{prediction.confidence}% confiança</small></div>)}</div></section>
    </>
  );
}

function Architecture() {
  return (
    <>
      <PageHeader eyebrow="BEHIND THE PRODUCT" title="Como o sistema funciona" text="A demo pública é isolada; o console pessoal continua conectado à arquitetura full-stack real." />
      <div className="truth-banner"><strong>Transparência por design</strong><span>Esta aplicação Netlify importa um JSON versionado. Ela não possui endpoint, usuário, token ou banco remoto.</span></div>
      <section className="card architecture">
        <span className="eyebrow">ARQUITETURA DO CONSOLE PESSOAL</span><h2>Fluxo de uma decisão operacional</h2>
        <div className="architecture-flow">
          <div><b>01</b><strong>React Console</strong><small>Auth e experiência operacional</small></div><i>→</i>
          <div><b>02</b><strong>FastAPI</strong><small>Contratos e isolamento tenant</small></div><i>→</i>
          <div><b>03</b><strong>Service Layer</strong><small>Pricing, forecast e ações</small></div><i>→</i>
          <div><b>04</b><strong>PostgreSQL</strong><small>40 entidades e auditoria</small></div>
        </div>
        <div className="architecture-branches"><article><span>↗</span><strong>Mercado Livre OAuth</strong><small>Tokens criptografados, state assinado e sync explícito</small></article><article><span>✦</span><strong>Pipeline de ML</strong><small>Dataset e modelos isolados por organização</small></article><article><span>≋</span><strong>Data Engineering</strong><small>Raw → staging → marts → sinais operacionais</small></article></div>
      </section>
      <section className="split decisions">
        <article className="card"><span className="eyebrow">DECISÕES</span><h2>Trade-offs assumidos</h2><ul><li>Demo estática para eliminar exposição e estado compartilhado.</li><li>Console e portfólio separados, compartilhando apenas conceitos.</li><li>Jobs em processo são suficientes no console pessoal, mas não são uma fila distribuída.</li><li>Forecast é heurístico e comunica sua confiança.</li></ul></article>
        <article className="card"><span className="eyebrow">QUALIDADE</span><h2>Como é verificado</h2><ul><li>Testes unitários e integrados do backend.</li><li>TypeScript strict e build Vite.</li><li>Teste de integridade de todos os dados demonstrativos.</li><li>Alembic como trilha executável de schema.</li></ul></article>
      </section>
      <section className="stack"><span>React</span><span>TypeScript</span><span>FastAPI</span><span>SQLAlchemy</span><span>PostgreSQL</span><span>Pandas</span><span>scikit-learn</span><span>Docker</span><span>Netlify</span></section>
    </>
  );
}

function Privacy() {
  return (
    <>
      <PageHeader eyebrow="PRIVACY BY DESIGN" title="LGPD como requisito de arquitetura" text="A demonstração pública elimina coleta; o console pessoal oferece transparência, retenção e exercício de direitos." />
      <div className="truth-banner"><strong>Esta demo não coleta dados pessoais</strong><span>Não há login, cookies, analytics, formulários, API ou banco remoto. Apenas o estado das ações fictícias é guardado no `sessionStorage` do próprio navegador.</span></div>
      <section className="privacy-grid">
        <article className="card"><span className="eyebrow">MINIMIZAÇÃO</span><h2>Menos dados por padrão</h2><p>O frontend público usa somente JSON sintético versionado. Nomes de sellers, pedidos, produtos e métricas não correspondem a pessoas ou empresas reais.</p></article>
        <article className="card"><span className="eyebrow">DIREITOS DO TITULAR</span><h2>Fluxo rastreável</h2><p>O console autenticado permite exportar os próprios dados e protocolar acesso, correção, eliminação, anonimização, portabilidade, revogação ou revisão humana.</p></article>
        <article className="card"><span className="eyebrow">RETENÇÃO</span><h2>Descarte configurável</h2><p>Logs técnicos têm prazo definido por ambiente. Tokens e convites expirados são elegíveis para remoção por rotina dedicada, inicialmente em modo de simulação.</p></article>
        <article className="card"><span className="eyebrow">DECISÕES ASSISTIDAS</span><h2>Humano no controle</h2><p>Modelos de ML apenas recomendam. Nenhuma predição altera preço, publica anúncio ou executa ação sem confirmação explícita do usuário.</p></article>
      </section>
      <section className="card decisions">
        <span className="eyebrow">GOVERNANÇA</span><h2>O que existe no repositório</h2>
        <ul><li>Aviso público de privacidade e inventário de tratamentos.</li><li>Protocolos autenticados para exercício de direitos.</li><li>Exportação sem hashes de senha, tokens ou nonces.</li><li>Política de retenção e rotina de descarte em dry-run.</li><li>Runbook de incidentes conforme regulamentação da ANPD.</li></ul>
        <p>Controles técnicos apoiam conformidade, mas não substituem avaliação jurídica, definição formal do controlador/encarregado e processos operacionais.</p>
      </section>
    </>
  );
}

export default function App() {
  const demo = useDemoActions();
  const { path } = usePortfolioRouter();
  const pages: Record<string, React.ReactNode> = {
    '/': <Overview actions={demo.actions} />,
    '/catalogo': <Catalog />,
    '/pricing': <Pricing />,
    '/war-room': <WarRoom actions={demo.actions} update={demo.update} />,
    '/forecast': <Forecast />,
    '/financeiro': <Finance />,
    '/ml': <MachineLearning />,
    '/arquitetura': <Architecture />,
    '/privacidade': <Privacy />,
  };
  return (
    <Shell reset={demo.reset} path={path}>
      {pages[path] ?? pages['/']}
    </Shell>
  );
}
