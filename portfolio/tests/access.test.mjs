import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const logo = readFileSync(new URL('../public/logo-horizontal.svg', import.meta.url), 'utf8');
const socialCard = readFileSync(new URL('../public/linkedin-card.png', import.meta.url));

assert.match(app, /ACESSO DEMONSTRATIVO/);
assert.match(app, /recrutador@demo\.local/);
assert.match(app, /portfolio2026/);
assert.ok(app.includes("'/visao-executiva'"));
assert.ok(app.includes("'marketplace-seller-platform-portfolio-access'"));
assert.doesNotMatch(app, /fetch\(|axios|XMLHttpRequest/);
assert.match(styles, /color-scheme:\s*light/);
assert.doesNotMatch(styles, /color-scheme:\s*dark/);
assert.match(logo, /MarketPlace/);
assert.match(app, /logo-horizontal\.svg/);
assert.match(html, /https:\/\/marketplace-seller-platform\.netlify\.app\/linkedin-card\.png/);
assert.equal(socialCard.readUInt32BE(16), 1200);
assert.equal(socialCard.readUInt32BE(20), 627);
assert.ok(socialCard.byteLength < 5 * 1024 * 1024);
console.log('access: entrada, identidade vetorial, card social e tema claro verificados');
