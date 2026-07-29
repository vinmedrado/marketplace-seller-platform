import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
const api = readFileSync(new URL('../../ui/api.py', import.meta.url), 'utf8');

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
console.log('contracts: War Room, sessão e direitos LGPD verificados');
