import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const data = JSON.parse(readFileSync(new URL('../src/demo-data.json', import.meta.url), 'utf8'));
const requiredCollections = ['kpis', 'revenueSeries', 'products', 'pricing', 'competitors', 'actions', 'forecast', 'transactions'];

for (const key of requiredCollections) {
  assert.ok(Array.isArray(data[key]) && data[key].length > 0, `${key} deve possuir dados sintéticos`);
}

const ids = new Set(data.products.map((product) => product.id));
for (const recommendation of data.pricing) assert.ok(ids.has(recommendation.productId));
for (const forecast of data.forecast) assert.ok(ids.has(forecast.productId));
for (const prediction of data.ml.predictions) assert.ok(ids.has(prediction.productId));
assert.match(data.metadata.notice, /sintétic/i);
console.log(`demo-data: ${data.products.length} produtos e todas as áreas preenchidas`);
