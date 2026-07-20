#!/usr/bin/env node
/**
 * Smoke checks for MapLibre Phase I renderer wiring.
 *
 * Asserts:
 * - package.json depends on maplibre-gl
 * - facade radar-map.component.ts exists
 * - leaflet legacy host exists
 * - MAP_RENDERER factory default is maplibre (not leaflet)
 *
 * Usage: node scripts/verify-map-renderer.mjs
 */
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

function fail(msg) {
  console.error(`[verify-map-renderer] FAIL: ${msg}`);
  process.exit(1);
}

function ok(msg) {
  console.log(`[verify-map-renderer] OK: ${msg}`);
}

const pkgPath = join(ROOT, 'package.json');
if (!existsSync(pkgPath)) fail('missing package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
if (!pkg.dependencies?.['maplibre-gl']) {
  fail('package.json missing dependency maplibre-gl');
}
ok(`maplibre-gl = ${pkg.dependencies['maplibre-gl']}`);

const facade = join(ROOT, 'src/app/components/radar-map/radar-map.component.ts');
if (!existsSync(facade)) fail('missing facade radar-map.component.ts');
ok('facade radar-map.component.ts');

const leaflet = join(ROOT, 'src/app/components/radar-map/leaflet/radar-map-leaflet.component.ts');
if (!existsSync(leaflet)) fail('missing leaflet legacy radar-map-leaflet.component.ts');
ok('leaflet legacy host');

const maplibre = join(
  ROOT,
  'src/app/components/radar-map/maplibre/radar-map-maplibre.component.ts',
);
if (!existsSync(maplibre)) fail('missing maplibre host radar-map-maplibre.component.ts');
ok('maplibre host');

const tokenPath = join(ROOT, 'src/app/services/map-renderer.token.ts');
if (!existsSync(tokenPath)) fail('missing map-renderer.token.ts');
const tokenSrc = readFileSync(tokenPath, 'utf8');
const factoryBody = tokenSrc.match(/export function resolveMapRenderer\(\)[\s\S]*?\n\}/)?.[0] ?? '';
const defaultReturns = [...factoryBody.matchAll(/return\s+'(\w+)'\s*;/g)].map((m) => m[1]);
const lastReturn = defaultReturns[defaultReturns.length - 1];
if (lastReturn !== 'maplibre') {
  fail(`MAP_RENDERER factory last/default return is '${lastReturn}', expected 'maplibre'`);
}
ok('MAP_RENDERER default is maplibre');

console.log('[verify-map-renderer] all checks passed');
