const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const sent = [];
const threads = [{id: 'thread-1'}];
const full = {messages: [{id: 'm1', internalDate: '1735689600123', payload: {
  headers: [{name: 'Subject', value: 'Résumé ✓'}, {name: 'From', value: 'owner@example.test'}],
  mimeType: 'multipart/alternative', parts: [{mimeType: 'text/html', body: {data: 'aHRtbA'}}, {mimeType: 'multipart/mixed', parts: [{mimeType: 'text/plain', body: {data: 'UsOpc3Vtw6kg4pyT'}}]}]
}}]};
const Utilities = {
  getUuid: () => 'uuid-1',
  base64Encode: value => Buffer.from(value).toString('base64'),
  base64Decode: value => Buffer.from(value, 'base64'),
  base64EncodeWebSafe: value => Buffer.from(value).toString('base64').replace(/\+/g, '-').replace(/\//g, '_'),
  base64DecodeWebSafe: value => Buffer.from(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4), 'base64'),
  newBlob: value => ({getBytes: () => Buffer.isBuffer(value) ? value : Buffer.from(String(value), 'utf8'), getDataAsString: enc => Buffer.from(value).toString(enc || 'utf8')})
};
const Gmail = {Users: {Messages: {send: (body, user) => { sent.push({body, user}); return {id: 'sent-1'}; }}, Threads: {
  list: (user, opts) => { assert.equal(user, 'me'); assert.equal(opts.maxResults, 50); return {threads}; },
  get: (user, id, opts) => { assert.equal(user, 'me'); assert.equal(id, 'thread-1'); assert.equal(opts.format, 'full'); return full; }
}}};
const context = {Utilities, Gmail, OWNER_EMAIL_DEFAULT: 'owner@example.test'};
vm.createContext(context);
vm.runInContext(fs.readFileSync('google/GmailTransport.js', 'utf8'), context);

context.sendRadarEmail('owner@example.test', 'Résumé ✓'.repeat(8), 'plain ✓', {htmlBody: '<b>ok</b>', name: 'Radar ✓'});
assert.equal(sent.length, 1);
assert.equal(sent[0].user, 'me');
const raw = Buffer.from(sent[0].body.raw.replace(/-/g, '+').replace(/_/g, '/') + '==', 'base64').toString('utf8');
assert.match(raw, /Subject: =\?UTF-8\?B\?/);
assert.match(raw, /plain ✓/);
assert.match(raw, /<b>ok<\/b>/);
const subjectLines = raw.split('\r\n').filter(line => line.startsWith('Subject:') || line.startsWith(' =?UTF-8?B?'));
assert.ok(subjectLines.length > 1, 'long Unicode subject should fold into encoded words');
assert.ok(subjectLines.every(line => line.length <= 75), 'RFC2047 encoded words must stay within 75 characters');
assert.throws(() => context.sendRadarEmail('attacker@example.test', 'x', 'x'), /OWNER_EMAIL_DEFAULT/);
assert.throws(() => context.sendRadarEmail('owner@example.test', 'x\r\nBcc: attacker', 'x'), /CRLF/);

const result = context.readRadarThreads('from:owner@example.test');
assert.equal(result.length, 1);
const message = result[0].getMessages()[0];
assert.equal(message.getId(), 'm1');
assert.equal(message.getSubject(), 'Résumé ✓');
assert.equal(message.getHeader('subject'), 'Résumé ✓');
assert.equal(message.getPlainBody(), 'Résumé ✓');
assert.equal(message.getDate().getTime(), 1735689600123);

const folded = '=?UTF-8?B?' + Buffer.from('Résumé ').toString('base64') + '?=\r\n =?UTF-8?B?' + Buffer.from('✓').toString('base64') + '?=';
full.messages[0].payload.headers[0].value = folded;
assert.equal(result[0].getMessages()[0].getSubject(), 'Résumé ✓');
console.log('gmail transport tests passed');
