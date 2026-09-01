const { defineConfig } = require('@playwright/test');
const { chromium } = require('playwright');

// The bundled headless shell crashes on this Windows host. Run the full
// Playwright-managed Chromium binary instead, retaining headless test behavior.
module.exports = defineConfig({
  testDir: './backend/tests',
  use: {
    headless: true,
    launchOptions: { executablePath: chromium.executablePath() },
  },
});
