// Phase 30 D-19a fixture extension — JS package-local test.
// Imports the package's index.js via a relative path so the
// test_suites.emit tests-edge derivation produces TestSuite -> Package(jspkg).

const main = require('../index.js');

test('smoke', () => {
  expect(main).toBeDefined();
});
