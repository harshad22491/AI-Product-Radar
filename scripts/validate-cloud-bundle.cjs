'use strict';
// Reuse the exact delivery boundary rules rather than approximating them in Python.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const sandbox = {
  Utilities: {
    DigestAlgorithm: {SHA_256: 'sha256'}, Charset: {UTF_8: 'utf8'},
    computeDigest: (_algorithm, value) => Array.from(crypto.createHash('sha256').update(value, 'utf8').digest())
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../google/Code.js'), 'utf8'), sandbox);
const value = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = value.kind === 'validation'
  ? sandbox.validateAttestation(value, {nowMs: Date.now()})
  : sandbox.validateBundle(value, {nowMs: Date.now()});
process.stdout.write(JSON.stringify(result));
process.exitCode = result.ok ? 0 : 1;
