import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');

assert.match(app, /ACESSO DEMONSTRATIVO/);
assert.match(app, /recrutador@demo\.local/);
assert.match(app, /portfolio2026/);
assert.ok(app.includes("'/visao-executiva'"));
assert.ok(app.includes("'marketplace-seller-platform-portfolio-access'"));
assert.doesNotMatch(app, /fetch\(|axios|XMLHttpRequest/);
assert.match(styles, /color-scheme:\s*light/);
assert.doesNotMatch(styles, /color-scheme:\s*dark/);
console.log('access: entrada demonstrativa local e tema claro verificados');
