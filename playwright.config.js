const { defineConfig } = require('@playwright/test');
const { chromium } = require('playwright');
const path = require('path');

require(path.resolve(__dirname, 'backend/scripts/browser-source-loader.js'));

// On this Windows host the full Chromium binary fails Node's process spawn
// before it reaches Playwright. The bundled headless shell launches normally.
// Set STUDYBUDDY_PLAYWRIGHT_FULL_CHROMIUM=1 only when diagnosing that host issue.
module.exports = defineConfig({
  testDir: path.resolve(__dirname, 'backend/tests'),
  workers: 1,
  use: {
    headless: true,
    launchOptions: process.env.STUDYBUDDY_PLAYWRIGHT_FULL_CHROMIUM === '1'
      ? { executablePath: chromium.executablePath() } : {},
  },
  reporter: process.env.PLAYWRIGHT_REPORTER || 'line',
});
