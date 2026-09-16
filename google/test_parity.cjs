// Cross-runtime contracts: test real Python-produced JSON against Apps Script.
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const context = vm.createContext({
  Utilities: {DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'utf8'},
    computeDigest: (_,text) => [...crypto.createHash('sha256').update(text,'utf8').digest()]},
  console
});
vm.runInContext(fs.readFileSync('google/Code.js','utf8'),context);
const urls = ['https://EXAMPLE.com:443/path/', 'https://example.com/search?q=a%20b&ref=release',
  'https://example.com/x?reference=2&utm_source=mail', 'https://example.com/a/../b/%7e/',
  'https://example.com/x?a=z&a=a', 'https://example.com/x#heading'];
const python = cp.execFileSync('python',['-c',
  'import json,sys; from radar.domain import canonical_url; print(json.dumps([canonical_url(u) for u in json.load(sys.stdin)]))'],
  {input:JSON.stringify(urls),encoding:'utf8'});
JSON.parse(python).forEach((expected,index) => assert.equal(context.canonicalUrl(urls[index]),expected,urls[index]));
const bundle=JSON.parse(fs.readFileSync('examples/test-digest.json','utf8'));
assert.equal(context.validateBundle(bundle,{nowMs:Date.now()}).ok,true,
  JSON.stringify(context.validateBundle(bundle,{nowMs:Date.now()}).errors));
assert.equal(context.canonicalUrl('https://user:password@example.com/x'),null);
assert.equal(context.canonicalUrl('https://example.com/x y'),null);
const academic=JSON.parse(fs.readFileSync('examples/academic-digest.json','utf8'));
assert.equal(context.validateBundle(academic,{nowMs:Date.now()}).ok,true,
  JSON.stringify(context.validateBundle(academic,{nowMs:Date.now()}).errors));
const normalized=JSON.parse(cp.execFileSync('python',['-c',
  'import json,sys; from radar.domain import validate_bundle; print(json.dumps(validate_bundle(json.load(sys.stdin))))'],
  {input:JSON.stringify(academic),encoding:'utf8'}));
assert.equal(normalized.newsletter,'academic');
assert.equal(context.validateBundle(normalized,{nowMs:Date.now()}).ok,true);
assert.equal(normalized.items[0].publication.publication_url,context.canonicalUrl(academic.items[0].source_url));
console.log('Cross-runtime URL identity and real digest validation passed.');
