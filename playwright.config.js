const { defineConfig } = require('@playwright/test');
const { chromium } = require('playwright');

// The bundled headless shell crashes on this Windows host. Run the full
// Playwright-managed Chromium binary instead, retaining headless test behavior.
module.exports = defineConfig({
  testDir: './backend/tests',
  // Browser specs start servers on fixed, spec-local ports and use shared
  // Windows test roots. Serial execution prevents cross-worker interference.
  workers: 1,
  use: {
    headless: true,
    launchOptions: { executablePath: chromium.executablePath() },
  },
});
