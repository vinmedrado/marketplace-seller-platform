import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

assert.ok(app.includes("'/privacidade'"), 'demo deve publicar a rota de privacidade');
assert.match(app, /não coleta dados pessoais/i);
assert.match(app, /sessionStorage/);
assert.doesNotMatch(html, /google-analytics|googletagmanager|segment|mixpanel/i);
console.log('privacy: aviso público presente e sem scripts conhecidos de analytics');
