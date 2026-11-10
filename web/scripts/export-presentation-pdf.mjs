import { chromium } from '@playwright/test';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../delivery/presentation.html');
const out = resolve(here, '../../delivery/presentation.pdf');

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL ?? 'chrome' });
const page = await browser.newPage();
await page.goto('file:///' + src.replace(/\\/g, '/'), { waitUntil: 'networkidle' });
await page.pdf({ path: out, width: '297mm', height: '167mm', printBackground: true, preferCSSPageSize: false });
await browser.close();
console.log('PDF saved:', out);
