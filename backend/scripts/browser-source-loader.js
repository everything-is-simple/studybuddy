/* Resolve legacy browser-test literals without intercepting child processes. */
const fs = require('fs');
const path = require('path');
const Module = require('module');

const original = Module._extensions['.js'];
const testMarker = `${path.sep}backend${path.sep}tests${path.sep}`;
const testRoot = '(process.env.STUDYBUDDY_TEST_ROOT || require("path").resolve(__dirname, "../../../studybuddy-test"))';
const backendRoot = '(process.env.STUDYBUDDY_BACKEND_ROOT || require("path").resolve(__dirname, ".."))';
const python = '(process.env.STUDYBUDDY_PYTHON || "python")';
const baseUrl = '(process.env.STUDYBUDDY_BASE_URL || "http://localhost:8787")';

function rewrite(source) {
  source = source.replace(/(['"])C:\/miniconda\/py310\/python\.exe\1/g, python);
  source = source.replace(/(['"])H:\/studybuddy\/backend\1/g, backendRoot);
  source = source.replace(/(['"])http:\/\/localhost:8787\1/g, baseUrl);
  source = source.replace(/(['"])H:\/studybuddy-test(\/[^'"`]*)\1/g, (_, quote, suffix) => {
    return `${testRoot} + ${JSON.stringify(suffix)}`;
  });
  source = source.replace(/`([^`]*)`/g, (literal, body) => {
    const rewritten = body
      .replaceAll('H:/studybuddy-test', `\${${testRoot}}`)
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
