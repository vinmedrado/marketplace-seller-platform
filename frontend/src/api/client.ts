import axios from 'axios';

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000' });

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original?._retry && sessionStorage.getItem('refresh_token')) {
      original._retry = true;
      try {
        const { data } = await axios.post(`${api.defaults.baseURL}/auth/refresh`, { refresh_token: sessionStorage.getItem('refresh_token') });
        sessionStorage.setItem('access_token', data.access_token);
        sessionStorage.setItem('refresh_token', data.refresh_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch {
        sessionStorage.removeItem('access_token');
        sessionStorage.removeItem('refresh_token');
      }
    }
    if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('api-error',{detail:error.response?.data?.detail?.message||error.message||'Erro de API'}));
    return Promise.reject(error);
  }
);

export const money = (v?: number | string | null) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
export async function login(email: string, senha: string) { const { data } = await api.post('/auth/login', { email, senha }); sessionStorage.setItem('access_token', data.access_token); sessionStorage.setItem('refresh_token', data.refresh_token); return data; }
export async function me() { return (await api.get('/auth/me')).data; }
export async function privacyNotice() { return (await api.get('/privacy')).data; }
export async function privacyExport() { return (await api.get('/privacy/me/export')).data; }
export async function privacyRequests() { return (await api.get('/privacy/me/requests')).data; }
export async function createPrivacyRequest(payload: { request_type: string; description?: string }) { return (await api.post('/privacy/me/requests', payload)).data; }
export async function inviteDetails(token: string) { return (await api.get(`/invites/${token}`)).data; }
export async function acceptInvite(token: string, payload: { name: string; password: string }) { return (await api.post(`/invites/${token}/accept`, payload)).data; }
export async function dashboard() { return (await api.get('/app/dashboard')).data; }
export async function products() { return (await api.get('/products')).data; }
export async function productDetail(id: string) { return (await api.get(`/products/${id}/detail`)).data; }
export async function createProduct(payload: any) { return (await api.post('/products', payload)).data; }
export async function updateProduct(id: string, payload: any) { return (await api.put(`/products/${id}`, payload)).data; }
export async function deleteProduct(id: string) { return (await api.delete(`/products/${id}`)).data; }
export async function competition(product_id?: string) { return (await api.get('/competition', { params: { product_id } })).data; }
export async function runCompetition(product_id: string) { return (await api.post('/competition/run', { product_id, marketplace: 'mercadolivre', max_pages: 1 })).data; }
export async function calculatePricing(product_id: string, modo = 'rule_based') { return (await api.post('/pricing/calculate', { product_id, marketplace: 'mercadolivre', modo })).data; }
export async function pricingHistory(product_id?: string) { return (await api.get('/pricing/history', { params: { product_id } })).data; }
export async function publishDryRun(product_id: string) { return (await api.post('/publish/dry-run', { product_id, marketplace: 'mercadolivre', dry_run: true })).data; }
export async function publishHistory() { return (await api.get('/publish/history')).data; }
export async function trainML() { return (await api.post('/ml/train/app', { marketplace: 'mercadolivre', force: true })).data; }
export async function jobs() { return (await api.get('/jobs')).data; }
export async function createJob(jobType: string, parameters: any = {}) { return (await api.post(`/jobs/${jobType}`, parameters)).data; }
export async function insights() { return (await api.get('/insights')).data; }
export async function marketDashboard() { return (await api.get('/dashboard/market-ready')).data; }
export async function pricingScenarios(product_id: string) { return (await api.get(`/pricing/scenarios/${product_id}`)).data; }
export async function competitionAnalytics(product_id?: string) { return (await api.get('/competition/analytics', { params: { product_id } })).data; }
export async function publishPreview(product_id: string) { return (await api.get(`/publish/preview/${product_id}`)).data; }
export async function getSettings() { return (await api.get('/settings')).data; }
export async function saveSettings(payload: any) { return (await api.put('/settings', payload)).data; }

export async function getOnboarding() { return (await api.get('/onboarding')).data; }
export async function saveOnboarding(payload: any) { return (await api.put('/onboarding', payload)).data; }
export async function getPlans() { return (await api.get('/plans')).data; }
export async function updatePlan(plan_key: string) { return (await api.put('/plans/current', { plan_key })).data; }
export async function getUsers() { return (await api.get('/users')).data; }
export async function inviteUser(payload: any) { return (await api.post('/users/invite', payload)).data; }
export async function updateUserRole(id: string, role: string) { return (await api.put(`/users/${id}/role`, { role })).data; }
export async function removeUser(id: string) { return (await api.delete(`/users/${id}`)).data; }
export async function getAlerts() { return (await api.get('/alerts')).data; }
export async function markAlertRead(id: string) { return (await api.post(`/alerts/${id}/read`)).data; }
export async function marketplaceStatus() { return (await api.get('/marketplace/status')).data; }
export async function getMarketplaceConnectUrl() { return (await api.get('/marketplace/connect-url')).data; }

export async function intelligenceCenter() { return (await api.get('/intelligence-center')).data; }
export async function operationalScore() { return (await api.get('/operational-score')).data; }
export async function healthMonitoring() { return (await api.get('/health-monitoring')).data; }
export async function impactSimulator(payload: any) { return (await api.post('/impact-simulator', payload)).data; }


export async function aiCopilot() { return (await api.get('/ai-copilot')).data; }
export async function operationalTimeline() { return (await api.get('/operational-timeline')).data; }
export async function smartAlerts() { return (await api.get('/smart-alerts')).data; }
export async function recommendedActions() { return (await api.get('/recommended-actions')).data; }
export async function operationalMaturityScore() { return (await api.get('/operational-maturity-score')).data; }
export async function executiveMode() { return (await api.get('/executive-mode')).data; }
export async function marketRadar() { return (await api.get('/market-radar')).data; }
export async function advancedProfitSimulator(payload: any) { return (await api.post('/profit-simulator/advanced', payload)).data; }

export async function aiCopilotContext() { return (await api.get('/ai-copilot/context')).data; }
export async function actionCenter() { return (await api.get('/action-center')).data; }
export async function applyAction(id: string) { return (await api.post(`/action-center/${id}/apply`)).data; }
export async function ignoreAction(id: string) { return (await api.post(`/action-center/${id}/ignore`)).data; }
export async function resolveAction(id: string) { return (await api.post(`/action-center/${id}/resolve`)).data; }
export async function marketWarRoom() { return (await api.get('/market-war-room')).data; }
export async function operationalTimelineActions() { return (await api.get('/operational-timeline/actions')).data; }
export async function alertsLifecycle() { return (await api.get('/alerts/lifecycle')).data; }
export async function updateAlertLifecycle(id: string, status: string) { return (await api.post(`/alerts/${id}/status`, { status })).data; }
export async function operationalScoreExplainable() { return (await api.get('/operational-score/explainable')).data; }
export async function executiveSummary() { return (await api.get('/executive-summary')).data; }
export async function profitSimulations() { return (await api.get('/profit-simulations')).data; }
export async function saveProfitSimulation(payload: any) { return (await api.post('/profit-simulations', payload)).data; }
export async function createActionFromSimulation(id: string) { return (await api.post(`/profit-simulations/${id}/create-action`)).data; }

export async function warRoomSimulateResponse(productId: string) { return (await api.post(`/market-war-room/${productId}/simulate-response`)).data; }
export async function warRoomRecalculatePricing(productId: string) { return (await api.post(`/market-war-room/${productId}/recalculate-pricing`)).data; }
export async function warRoomCreateAction(productId: string) { return (await api.post(`/market-war-room/${productId}/create-action`)).data; }
export async function executiveSummaryExport() { return (await api.get('/executive-summary/export')).data; }
export async function updateAlertLifecycleStatus(id: string, status: string) { return (await api.post(`/alerts/${id}/status`, { status })).data; }
export async function syncMarketplaceCatalog(params: any = {}) { return (await api.post('/marketplace/sync', null, { params })).data; }
export async function marketplaceProducts(params: any = {}) { return (await api.get('/marketplace/products', { params })).data; }
export async function healthcheck() { return (await api.get('/health')).data; }

export async function marketplaceSummary() { return (await api.get('/marketplace/summary')).data; }
export async function marketplaceIntelligence(params: any = {}) { return (await api.get('/marketplace/intelligence', { params })).data; }

export async function marketPriceScan(q: string, cost?: number) { return (await api.get('/pricing/market-scan', { params: { q, cost } })).data; }

export async function pendingQuestions(limit = 30) { return (await api.get('/questions/pending', { params: { limit } })).data; }
export async function suggestQuestionAnswer(id: string, custom_context?: string) { return (await api.post(`/questions/${id}/suggest`, { custom_context })).data; }
export async function answerQuestion(id: string, text: string) { return (await api.post(`/questions/${id}/answer`, { text })).data; }

export async function accountHealth() { return (await api.get('/account/health')).data; }

export async function buyboxOverview(limit = 30) { return (await api.get('/buybox/overview', { params: { limit } })).data; }
export async function productBuyboxScore(productId: string, refresh_market = true) { return (await api.get(`/products/${productId}/buybox-score`, { params: { refresh_market } })).data; }


export async function alertsSettings() { return (await api.get('/alerts/settings')).data; }
export async function saveAlertsSettings(payload: any) { return (await api.post('/alerts/settings', payload)).data; }
export async function alertsHistory(page = 1, page_size = 50) { return (await api.get('/alerts/history', { params: { page, page_size } })).data; }
export async function alertsTest() { return (await api.post('/alerts/test')).data; }


export async function billingPlans() { return (await api.get('/billing/plans')).data; }
export async function billingStatus() { return (await api.get('/billing/status')).data; }
export async function billingSubscribe(plan: string, customer: any) { return (await api.post('/billing/subscribe', { plan, customer })).data; }
export async function billingCancel() { return (await api.post('/billing/cancel')).data; }

export async function demandForecastOverview(limit = 80, lead_time_days = 7) { return (await api.get('/forecast/overview', { params: { limit, lead_time_days } })).data; }
export async function productDemandForecast(productId: string, lead_time_days = 7) { return (await api.get(`/forecast/products/${productId}`, { params: { lead_time_days } })).data; }
export async function financialReconciliation(start_date: string, end_date: string) { return (await api.get('/finance/reconciliation', { params: { start_date, end_date } })).data; }
export async function saveManualBankReceived(payload: any) { return (await api.post('/finance/reconciliation/manual-bank-received', payload)).data; }

export async function titleOptimizerProduct(productId: string) { return (await api.get(`/title-optimizer/products/${productId}`)).data; }
export async function titleOptimizerAnalyze(q: string) { return (await api.get('/title-optimizer/analyze', { params: { q } })).data; }

export async function portfolioAnalysis() { return (await api.get('/portfolio/analysis')).data; }
export async function portfolioProductAnalysis(productId: string) { return (await api.get(`/portfolio/products/${productId}`)).data; }

export async function onboardingInsights() { return (await api.get('/onboarding/insights')).data; }
export async function systemStatus() { return (await api.get('/system/status')).data; }
