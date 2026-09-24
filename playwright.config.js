const { defineConfig } = require('@playwright/test');
const { chromium } = require('playwright');
const path = require('path');

require(path.resolve(__dirname, 'backend/scripts/browser-source-loader.js'));

// The bundled headless shell crashes on this Windows host. Run the full
// Playwright-managed Chromium binary instead, retaining headless test behavior.
module.exports = defineConfig({
  testDir: path.resolve(__dirname, 'backend/tests'),
  workers: 1,
  use: {
    headless: true,
    launchOptions: process.env.STUDYBUDDY_PLAYWRIGHT_HEADLESS_SHELL === '1'
      ? {} : { executablePath: chromium.executablePath() },
  },
  reporter: process.env.PLAYWRIGHT_REPORTER || 'line',
});
