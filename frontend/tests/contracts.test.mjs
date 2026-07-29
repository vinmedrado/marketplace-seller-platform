import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
const api = readFileSync(new URL('../../ui/api.py', import.meta.url), 'utf8');
const frontendPackage = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const viteConfig = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf8');
const localRouter = readFileSync(new URL('../src/components/router/Router.tsx', import.meta.url), 'utf8');

const warRoomRoutes = [
  '/market-war-room/${productId}/simulate-response',
  '/market-war-room/${productId}/recalculate-pricing',
  '/market-war-room/${productId}/create-action',
];

for (const route of warRoomRoutes) {
  assert.ok(client.includes(route), `cliente deve declarar ${route}`);
  const backendRoute = route.replace('${productId}', '{product_id}');
  assert.ok(api.includes(backendRoute), `API deve declarar ${backendRoute}`);
}
assert.ok(client.includes("sessionStorage.getItem('access_token')"));
assert.ok(!client.includes("localStorage.getItem('access_token')"));
for (const route of ['/privacy', '/privacy/me/export', '/privacy/me/requests']) {
  assert.ok(client.includes(route), `cliente deve declarar ${route}`);
  assert.ok(api.includes(route), `API deve declarar ${route}`);
}
assert.equal(frontendPackage.dependencies['react-router-dom'], undefined);
assert.ok(viteConfig.includes("'react-router-dom': fileURLToPath"));
for (const primitive of ['BrowserRouter', 'Routes', 'Route', 'Navigate', 'Outlet', 'NavLink']) {
  assert.ok(localRouter.includes(`function ${primitive}`), `roteador local deve declarar ${primitive}`);
}
console.log('contracts: War Room, sessão, roteamento local e direitos LGPD verificados');
