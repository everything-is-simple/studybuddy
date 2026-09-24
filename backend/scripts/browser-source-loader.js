/* Resolve legacy browser-test literals without intercepting child processes. */
const fs = require('fs');
const path = require('path');
const Module = require('module');

const original = Module._extensions['.js'];
const testMarker = `${path.sep}backend${path.sep}tests${path.sep}`;
// Rewritten specs can be either CommonJS or ESM. Do not inject `require()` into
// their source because ESM specs do not have that binding at runtime.
const testRoot = '(process.env.STUDYBUDDY_TEST_ROOT || "H:/studybuddy-test")';
const fixtureRoot = '(process.env.STUDYBUDDY_FIXTURE_ROOT || process.env.STUDYBUDDY_TEST_ROOT || "H:/studybuddy-test")';
const backendRoot = '(process.env.STUDYBUDDY_BACKEND_ROOT || (process.cwd() + "/backend"))';
const python = '(process.env.STUDYBUDDY_PYTHON || "python")';
const baseUrl = '(process.env.STUDYBUDDY_BASE_URL || "http://localhost:8787")';

function rewrite(source) {
  source = source.replace(/(['"])C:\/miniconda\/py310\/python\.exe\1/g, python);
  source = source.replace(/(['"])H:\/studybuddy\/backend\1/g, backendRoot);
  source = source.replace(/(['"])http:\/\/localhost:8787\1/g, baseUrl);
  source = source.replace(/(['"])H:\/studybuddy-test(\/[^'"`]*)\1/g, (_, quote, suffix) => {
    const root = suffix.startsWith('/fixtures/') ? fixtureRoot : testRoot;
    return `${root} + ${JSON.stringify(suffix)}`;
  });
  source = source.replace(/`([^`]*)`/g, (literal, body) => {
    const fixtureMarker = "__STUDYBUDDY_FIXTURE_ROOT__";
    const testMarker = "__STUDYBUDDY_TEST_ROOT__";
    const rewritten = body
      .replaceAll('H:/studybuddy-test/fixtures', fixtureMarker)
      .replaceAll('H:/studybuddy-test', testMarker)
      .replaceAll(fixtureMarker, `\${${fixtureRoot}}/fixtures`)
      .replaceAll(testMarker, `\${${testRoot}}`)
      .replaceAll('H:/studybuddy/backend', `\${${backendRoot}}`);
    return rewritten === body ? literal : `\`${rewritten}\``;
  });
  return source;
}

Module._extensions['.js'] = function loadBrowserTest(module, filename) {
  if (!filename.includes(testMarker) || filename.endsWith('browser-source-loader.js')) {
    return original(module, filename);
  }
  module._compile(rewrite(fs.readFileSync(filename, 'utf8')), filename);
};

module.exports = { rewrite };
