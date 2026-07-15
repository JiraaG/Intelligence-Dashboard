#!/usr/bin/env node
/**
 * Verify (and optionally fetch) countries.geo.json.
 * Pinned SHA-256 is read from src/assets/data/ASSET_LICENSE.md (single source of truth).
 *
 * Usage:
 *   node scripts/verify-geojson.mjs
 *   node scripts/verify-geojson.mjs --fetch
 */
import { createHash } from 'node:crypto';
import { createWriteStream, existsSync, readFileSync } from 'node:fs';
import { mkdir, rename } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { pipeline } from 'node:stream/promises';
import { Readable } from 'node:stream';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const ASSET_REL = join('src', 'assets', 'data', 'countries.geo.json');
const LICENSE_REL = join('src', 'assets', 'data', 'ASSET_LICENSE.md');
const ASSET_PATH = join(ROOT, ASSET_REL);
const LICENSE_PATH = join(ROOT, LICENSE_REL);

const FETCH = process.argv.includes('--fetch');

function fail(msg) {
  console.error(`[verify-geojson] FAIL: ${msg}`);
  process.exit(1);
}

function parseLicensePin(text) {
  const shaMatch = text.match(/\*\*SHA-256:\*\*\s*`([0-9A-Fa-f]{64})`/);
  const urlMatch = text.match(
    /## Canonical download URL \(deterministic\)\s*\n\s*\n\s*(https:\/\/\S+)/,
  );
  if (!shaMatch) fail(`could not parse SHA-256 from ${LICENSE_REL}`);
  if (!urlMatch) fail(`could not parse canonical URL from ${LICENSE_REL}`);
  return {
    sha256: shaMatch[1].toUpperCase(),
    url: urlMatch[1].trim(),
  };
}

async function fetchTo(url, dest) {
  await mkdir(dirname(dest), { recursive: true });
  const tmp = `${dest}.tmp`;
  const res = await fetch(url);
  if (!res.ok || !res.body) fail(`download HTTP ${res.status} for ${url}`);
  await pipeline(Readable.fromWeb(res.body), createWriteStream(tmp));
  await rename(tmp, dest);
  console.log(`[verify-geojson] downloaded → ${ASSET_REL}`);
}

function sha256File(path) {
  const hash = createHash('sha256');
  hash.update(readFileSync(path));
  return hash.digest('hex').toUpperCase();
}

function validateFeatureCollection(path) {
  let data;
  try {
    data = JSON.parse(readFileSync(path, 'utf8'));
  } catch (e) {
    fail(`invalid JSON: ${e.message}`);
  }
  if (data?.type !== 'FeatureCollection') fail('type must be FeatureCollection');
  if (!Array.isArray(data.features) || data.features.length === 0) {
    fail('features must be a non-empty array');
  }
  const sample = data.features[0]?.properties ?? {};
  if (!sample['ISO3166-1-Alpha-2'] && !sample['ISO_A2']) {
    fail('features missing ISO3166-1-Alpha-2 (or ISO_A2) property used by radar-map');
  }
  console.log(`[verify-geojson] FeatureCollection OK (${data.features.length} features)`);
}

async function main() {
  if (!existsSync(LICENSE_PATH)) fail(`missing ${LICENSE_REL}`);
  const { sha256: pinned, url } = parseLicensePin(readFileSync(LICENSE_PATH, 'utf8'));

  if (!existsSync(ASSET_PATH)) {
    if (!FETCH) {
      fail(
        `missing ${ASSET_REL}. Run: node scripts/verify-geojson.mjs --fetch\n` +
          `  or download:\n  ${url}`,
      );
    }
    console.log(`[verify-geojson] fetching pinned asset…`);
    await fetchTo(url, ASSET_PATH);
  } else if (FETCH) {
    console.log(`[verify-geojson] asset present; skip download (still verifying)`);
  }

  const actual = sha256File(ASSET_PATH);
  if (actual !== pinned) {
    fail(`SHA-256 mismatch\n  expected: ${pinned}\n  actual:   ${actual}`);
  }
  console.log(`[verify-geojson] SHA-256 OK (${actual})`);
  validateFeatureCollection(ASSET_PATH);
  console.log('[verify-geojson] PASS');
}

main().catch((e) => fail(e?.stack || String(e)));
