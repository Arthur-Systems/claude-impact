const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('Navigator replies do not display demo or backend connection diagnostics', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'components', 'panels', 'NavigatorCard.tsx'), 'utf8');
  assert.doesNotMatch(source, /Demo answer|backend not connected/i);
});
