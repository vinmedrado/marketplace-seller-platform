import React, { Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './styles/globals.css';
import { ToastProvider } from './components/ui/Toast';
import AppLayout from './components/layout/AppLayout';
import { Skeleton } from './components/ui/Card';
import { registerSellerOSPWA } from './pwa';

const Landing = lazy(() => import('./pages/Landing'));
const Login = lazy(() => import('./pages/Login'));
const AcceptInvite = lazy(() => import('./pages/AcceptInvite'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Products = lazy(() => import('./pages/Products'));
const ProductDetail = lazy(() => import('./pages/ProductDetail'));
const Competition = lazy(() => import('./pages/Competition'));
const Pricing = lazy(() => import('./pages/Pricing'));
const Publish = lazy(() => import('./pages/Publish'));
const Intelligence = lazy(() => import('./pages/Intelligence'));
const Jobs = lazy(() => import('./pages/Jobs'));
const IntelligenceCenter = lazy(() => import('./pages/IntelligenceCenter'));
const HealthMonitoring = lazy(() => import('./pages/HealthMonitoring'));
const ImpactSimulator = lazy(() => import('./pages/ImpactSimulator'));
const Settings = lazy(() => import('./pages/Settings'));
const Onboarding = lazy(() => import('./pages/Onboarding'));
const Plans = lazy(() => import('./pages/Plans'));
const Users = lazy(() => import('./pages/Users'));
const Marketplace = lazy(() => import('./pages/Marketplace'));
const AICopilot = lazy(() => import('./pages/AICopilot'));
const OperationalTimeline = lazy(() => import('./pages/OperationalTimeline'));
const ExecutiveMode = lazy(() => import('./pages/ExecutiveMode'));
const MarketRadar = lazy(() => import('./pages/MarketRadar'));
const ProfitSimulatorAdvanced = lazy(() => import('./pages/ProfitSimulatorAdvanced'));
const ActionCenter = lazy(() => import('./pages/ActionCenter'));
const MarketWarRoom = lazy(() => import('./pages/MarketWarRoom'));
const ExecutiveSummary = lazy(() => import('./pages/ExecutiveSummary'));
const PricingScanner = lazy(() => import('./pages/PricingScanner'));
const Questions = lazy(() => import('./pages/Questions'));
const AccountHealth = lazy(() => import('./pages/AccountHealth'));
const BuyBoxScore = lazy(() => import('./pages/BuyBoxScore'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Billing = lazy(() => import('./pages/Billing'));
const DemandForecast = lazy(() => import('./pages/DemandForecast'));
const FinancialReconciliation = lazy(() => import('./pages/FinancialReconciliation'));
const TitleOptimizer = lazy(() => import('./pages/TitleOptimizer'));
const PortfolioAnalysis = lazy(() => import('./pages/PortfolioAnalysis'));
const SystemStatus = lazy(() => import('./pages/SystemStatus'));
const Privacy = lazy(() => import('./pages/Privacy'));

const qc = new QueryClient();
const Guard = ({ children }: { children: React.ReactNode }) => sessionStorage.getItem('access_token') ? <>{children}</> : <Navigate to="/login" />;
const Loading = () => <div className="p-4"><Skeleton className="h-32" /><Skeleton className="h-80 mt-4" /></div>;

registerSellerOSPWA();

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <BrowserRouter>
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/aceitar-convite/:token" element={<AcceptInvite />} />
              <Route path="/pricing-scanner" element={<PricingScanner />} />
              <Route path="/app" element={<Guard><AppLayout /></Guard>}>
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="produtos" element={<Products />} />
                <Route path="produtos/:id" element={<ProductDetail />} />
                <Route path="concorrencia" element={<Competition />} />
                <Route path="precificacao" element={<Pricing />} />
                <Route path="publicacao" element={<Publish />} />
                <Route path="inteligencia" element={<Intelligence />} />
                <Route path="ai-copilot" element={<AICopilot />} />
                <Route path="action-center" element={<ActionCenter />} />
                <Route path="market-war-room" element={<MarketWarRoom />} />
                <Route path="executive-summary" element={<ExecutiveSummary />} />
                <Route path="intelligence-center" element={<IntelligenceCenter />} />
                <Route path="executive" element={<ExecutiveMode />} />
                <Route path="timeline" element={<OperationalTimeline />} />
                <Route path="market-radar" element={<MarketRadar />} />
                <Route path="health" element={<HealthMonitoring />} />
                <Route path="simulador" element={<ImpactSimulator />} />
                <Route path="profit-simulator" element={<ProfitSimulatorAdvanced />} />
                <Route path="jobs" element={<Jobs />} />
                <Route path="onboarding" element={<Onboarding />} />
                <Route path="plano" element={<Plans />} />
                <Route path="usuarios" element={<Users />} />
                <Route path="marketplace" element={<Marketplace />} />
                <Route path="pricing-scanner" element={<PricingScanner />} />
                <Route path="questions" element={<Questions />} />
                <Route path="account-health" element={<AccountHealth />} />
                <Route path="buybox" element={<BuyBoxScore />} />
                <Route path="alerts" element={<Alerts />} />
                <Route path="billing" element={<Billing />} />
                <Route path="forecast" element={<DemandForecast />} />
                <Route path="finance-reconciliation" element={<FinancialReconciliation />} />
                <Route path="title-optimizer" element={<TitleOptimizer />} />
                <Route path="portfolio" element={<PortfolioAnalysis />} />
                <Route path="system-status" element={<SystemStatus />} />
                <Route path="configuracoes" element={<Settings />} />
                <Route path="privacidade" element={<Privacy />} />
                <Route index element={<Navigate to="onboarding" />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
