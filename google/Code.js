/**
 * AI Product Radar — Google Apps Script gateway.
 *
 * Owned exclusively by the "Sonnet Google" slice of docs/BUILD-CONTRACT.md.
 * Deployed manually (see google/README.md) — nothing here runs from Git or
 * any CI system, and this file never calls out to Anthropic/OpenAI, and it
 * never mutates any GitHub repository.
 *
 * Structure:
 *   1. Configuration constants
 *   2. Pure functions (no Google services touched) — covered by
 *      google/test_gateway.cjs via a Node vm sandbox that stubs Utilities.
 *   3. Google-service orchestration (DriveApp / SpreadsheetApp / FormApp /
 *      GmailApp / LockService / ScriptApp) — exercised by
 *      google/test_gateway.cjs against an in-memory mock of those services,
 *      and by manually running setupRadar(), installRadarTriggers(),
 *      dispatchRadar() or sendTestDigest() from the Apps Script editor or a
 *      time trigger.
 *
 * Trust boundary: every bundle read from Drive's inbox/ folder is untrusted
 * input. Validation below never interprets item text as instructions or
 * HTML — every field is treated as inert data, and outbound email always
 * re-escapes it. The recipient address and email subject are never taken
 * from bundle content. A digest bundle also cannot self-declare approval —
 * "approved" only ever comes from a separate, independently validated
 * validator attestation file matched by run_id and the exact sha256 of the
 * original bundle bytes.
 */

// ===========================================================================
// 1. Configuration
// ===========================================================================

var SCHEMA_VERSION = 1;
var MIN_ITEMS = 7;
var OWNER_EMAIL_DEFAULT = 'harshad422@gmail.com';
var DIGEST_SUBJECT_PREFIX = 'AI Product Radar';
var NEWSLETTERS = ['product', 'academic'];
function newsletterName(newsletter) {
  return newsletter === 'academic' ? 'AI Research Radar' : DIGEST_SUBJECT_PREFIX;
}
function newsletterProperty(key, newsletter) {
  return newsletter === 'academic' ? key + '_ACADEMIC' : key;
}
var DISPATCH_HOUR_IST = 17; // never send before 17:00 Asia/Kolkata

var PRODUCERS = ['fable', 'astra', 'opus', 'sol'];
// Deterministic tie-break order when more than one approved, same-edition
// candidate with enough undelivered items exists. Astra is the routine
// fallback producer (it usually validates Fable rather than authoring a
// digest), so it sorts last.
var PRODUCER_PRIORITY = ['fable', 'sol', 'opus', 'astra'];
var SOURCE_TYPES = ['academic', 'product', 'tool', 'technique'];
var GUIDANCE_KEYS = ['Where', 'Try', 'Benefit', 'Effort', 'Check'];
var GUIDANCE_LABELS = ['Where this fits in your work', 'What a small first trial would involve', 'How this could help', 'Time and effort to allow', 'How to tell whether it worked'];
var RATING_ORIGINS = ['email', 'form', 'chat', 'obsidian'];
var VALIDATOR_MODELS = {sol: 'gpt-5.6-sol', opus: 'claude-opus-5'};
var VERDICTS = ['approved', 'rejected'];
var BLOCKING_DELIVERY_STATUSES = ['claimed', 'sent', 'uncertain'];

var BUNDLE_KEYS = ['schema_version', 'run_id', 'edition_date', 'generated_at', 'producer',
  'model_id', 'kind', 'items', 'newsletter'];
var ITEM_KEYS = ['item_id', 'title', 'source_url', 'published_at', 'source_type', 'summary',
  'why_it_matters', 'evidence_label', 'repository', 'guidance', 'topics', 'source_dates',
  'repository_evidence', 'user_facing_ai', 'application_example', 'publication'];
var ATTESTATION_KEYS = ['schema_version', 'run_id', 'candidate_run_id', 'candidate_sha256',
  'validator', 'model_id', 'verdict', 'checked_at', 'kind'];

var PROP = {
  FOLDER_ROOT: 'FOLDER_ROOT_ID',
  FOLDER_INBOX: 'FOLDER_INBOX_ID',
  FOLDER_ACCEPTED: 'FOLDER_ACCEPTED_ID',
  FOLDER_REJECTED: 'FOLDER_REJECTED_ID',
  FOLDER_SNAPSHOTS: 'FOLDER_SNAPSHOTS_ID',
  FOLDER_FEEDBACK: 'FOLDER_FEEDBACK_ID',
  SHEET_ID: 'SHEET_ID',
  FORM_ID: 'FORM_ID',
  OWNER_EMAIL: 'OWNER_EMAIL',
  LAST_DELIVERED_EDITION_DATE: 'LAST_DELIVERED_EDITION_DATE',
  LAST_MISSING_LOGGED_DATE: 'LAST_MISSING_LOGGED_DATE',
  STATE_REVISION: 'STATE_REVISION'
};

var DRIVE_SUBFOLDERS = [
  { key: 'inbox', prop: PROP.FOLDER_INBOX },
  { key: 'accepted', prop: PROP.FOLDER_ACCEPTED },
  { key: 'rejected', prop: PROP.FOLDER_REJECTED },
  { key: 'snapshots', prop: PROP.FOLDER_SNAPSHOTS },
  { key: 'feedback', prop: PROP.FOLDER_FEEDBACK }
];

var SHEET_SCHEMAS = {
  Items: ['item_id', 'title', 'source_url', 'published_at', 'source_type', 'summary',
    'why_it_matters', 'evidence_label', 'repository', 'guidance_where', 'guidance_try',
    'guidance_benefit', 'guidance_effort', 'guidance_check', 'topics',
    'first_delivered_edition_date', 'run_id', 'added_at', 'user_facing_ai', 'application_example', 'publication_json'],
  RatingEvents: ['event_id', 'item_id', 'score', 'reason', 'origin', 'base_revision',
    'created_at', 'status', 'recorded_at'],
  CurrentRatings: ['item_id', 'score', 'reason', 'revision', 'last_event_id', 'updated_at'],
  Repositories: ['repository', 'suppressed', 'last_reason', 'updated_at'],
  Reviews: ['repository', 'review_date', 'cursor_sha', 'status', 'evidence_summary', 'updated_at'],
  Runs: ['run_id', 'producer', 'model_id', 'edition_date', 'generated_at', 'item_count',
    'status', 'validation_notes', 'processed_at'],
  Deliveries: ['edition_date', 'run_id', 'recipient', 'subject', 'item_ids', 'delivery_key',
    'status', 'is_test', 'created_at', 'updated_at', 'newsletter'],
  Sources: ['source_url', 'canonical_url', 'item_id', 'first_seen_edition_date'],
  Preferences: ['key', 'value', 'updated_at']
};

var ITEM_ID_RE = /^RAD-[0-9a-f]{12}$/;
var RUN_ID_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
var UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
var DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
var DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
var CANDIDATE_SHA256_RE = /^[0-9a-f]{64}$/;
// RATE <item_id> <score> REV=<base_revision> <optional reason>
var RATE_LINE_RE = /^\s*RATE\s+(RAD-[0-9a-f]{12})\s+([1-5])\s+REV=(\d+)\b\s*(.*)$/i;

// ===========================================================================
// 2. Pure functions — no DriveApp/SpreadsheetApp/FormApp/GmailApp/LockService
//    reference. Utilities.computeDigest is the one native call used for
//    hashing, and Utilities.getUuid is used only in orchestration (never in
//    this section); google/test_gateway.cjs stubs computeDigest with Node's
//    crypto module so identical SHA-256 bytes are produced in both
//    environments.
// ===========================================================================

function isRealCalendarDate(y, m, d) {
  if (!Number.isInteger(y) || !Number.isInteger(m) || !Number.isInteger(d)) return false;
  if (m < 1 || m > 12 || d < 1) return false;
  var dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
}

function daysInMonth(y, m) {
  // m is 1-based; day 0 of month m+1 is the last day of month m.
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

function isValidDateString(s) {
  if (typeof s !== 'string') return false;
  var match = DATE_RE.exec(s);
  if (!match) return false;
  return isRealCalendarDate(Number(match[1]), Number(match[2]), Number(match[3]));
}

function addCalendarMonths(ymd, deltaMonths) {
  var match = DATE_RE.exec(ymd);
  if (!match) return null;
  var y = Number(match[1]);
  var m = Number(match[2]);
  var d = Number(match[3]);
  var total = (m - 1) + deltaMonths;
  var newY = y + Math.floor(total / 12);
  var newM0 = ((total % 12) + 12) % 12;
  var newM = newM0 + 1;
  var newD = Math.min(d, daysInMonth(newY, newM));
  return newY + '-' + pad2(newM) + '-' + pad2(newD);
}

function addCalendarYears(ymd, deltaYears) {
  var match = DATE_RE.exec(ymd);
  if (!match) return null;
  var y = Number(match[1]) + deltaYears;
  var m = Number(match[2]);
  var d = Number(match[3]);
  var newD = Math.min(d, daysInMonth(y, m));
  return y + '-' + pad2(m) + '-' + pad2(newD);
}

function pad2(n) {
  return n < 10 ? '0' + n : String(n);
}

function ageCapOk(sourceType, publishedAt, editionDate) {
  if (!isValidDateString(publishedAt) || !isValidDateString(editionDate)) {
    return { ok: false, reason: 'invalid_date' };
  }
  if (publishedAt > editionDate) return { ok: false, reason: 'future_date' };
  var cutoff = sourceType === 'academic'
    ? addCalendarYears(editionDate, -2)
    : addCalendarMonths(editionDate, -6);
  if (publishedAt < cutoff) return { ok: false, reason: 'too_old', cutoff: cutoff };
  return { ok: true, cutoff: cutoff };
}

function parseIsoTimestamp(s) {
  if (typeof s !== 'string') return null;
  var match = DATETIME_RE.exec(s);
  if (!match) return null;
  var y = Number(match[1]);
  var m = Number(match[2]);
  var d = Number(match[3]);
  var hh = Number(match[4]);
  var mm = Number(match[5]);
  var ss = Number(match[6]);
  var offset = match[7];
  if (!isRealCalendarDate(y, m, d)) return null;
  if (hh > 23 || mm > 59 || ss > 59) return null;
  var ms = Date.UTC(y, m - 1, d, hh, mm, ss);
  if (offset !== 'Z') {
    var sign = offset[0] === '-' ? -1 : 1;
    var offH = Number(offset.slice(1, 3));
    var offM = Number(offset.slice(4, 6));
    ms -= sign * (offH * 3600000 + offM * 60000);
  }
  return { ms: ms, dateOnly: y + '-' + pad2(m) + '-' + pad2(d) };
}

function canonicalUrl(url) {
  if (typeof url !== 'string') return null;
  var value = url.trim();
  if (/[\x00-\x20\x7f\\]/.test(value) || /%(?![0-9a-f]{2})/i.test(value)) return null;
  var match = /^https:\/\/([^\/?#]+)([^?#]*)(?:\?([^#]*))?(?:#.*)?$/i.exec(value);
  if (!match || /@/.test(match[1])) return null;
  var authority = match[1].toLowerCase();
  if (!/^(?:[a-z0-9._-]+|\[[0-9a-f:]+\])(?::[0-9]+)?$/.test(authority)) return null;
  var port = /:(\d+)$/.exec(authority);
  if (port && Number(port[1]) > 65535) return null;
  if (port && Number(port[1]) === 443) authority = authority.slice(0,port.index);
  var segments=[];
  (match[2] || '/').split('/').forEach(function(part) {
    if (!part || part === '.') return;
    if (part === '..') segments.pop(); else segments.push(part);
  });
  var path='/' + segments.join('/');
  path=path.replace(/%([0-9a-f]{2})/gi,function(_,hex) {
    var ch=String.fromCharCode(parseInt(hex,16));
    return /[a-z0-9._~-]/i.test(ch) ? ch : '%'+hex.toUpperCase();
  });
  path=path.replace(/[^a-z0-9\-._~\/%:@!$&'()*+,;=]/gi,function(ch){return encodeURIComponent(ch);});
  function quoteQuery(text) { return encodeURIComponent(text).replace(/[!'()*]/g,function(ch) {
    return '%'+ch.charCodeAt(0).toString(16).toUpperCase();
  }).replace(/%20/g,'+'); }
  var pairs=[];
  try {
    if (match[3]) match[3].split('&').forEach(function(pair) {
      var i=pair.indexOf('=');
      if (i < 0) throw new Error('bare query');
      pairs.push([decodeURIComponent(pair.slice(0,i).replace(/\+/g,' ')),
        decodeURIComponent(pair.slice(i+1).replace(/\+/g,' '))]);
    });
  } catch(e) { return null; }
  pairs.sort(function(a,b){return a[0]<b[0]?-1:a[0]>b[0]?1:a[1]<b[1]?-1:a[1]>b[1]?1:0;});
  return 'https://'+authority+path+(pairs.length?'?'+pairs.map(function(p){return quoteQuery(p[0])+'='+quoteQuery(p[1]);}).join('&'):'');
}

function bytesToHex(bytes) {
  var hex = '';
  for (var i = 0; i < bytes.length; i++) {
    var b = bytes[i];
    if (b < 0) b += 256;
    var h = b.toString(16);
    hex += h.length === 1 ? '0' + h : h;
  }
  return hex;
}

function sha256Hex(str) {
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, str, Utilities.Charset.UTF_8);
  return bytesToHex(bytes);
}

function stableItemId(url) {
  var canon = canonicalUrl(url);
  if (!canon) return null;
  return 'RAD-' + sha256Hex(canon).slice(0, 12);
}

function isValidItemId(id) {
  return typeof id === 'string' && ITEM_ID_RE.test(id);
}

function isValidRunId(id) {
  return typeof id === 'string' && RUN_ID_RE.test(id);
}

/** Deterministic RFC4122-shaped (but not truly random) UUID string derived
 * from a stable input, e.g. "<gmailMessageId>#<lineIndex>" or a Form
 * response ID. Same input always yields the same event_id, so retries never
 * mint a fresh random ID and duplicate detection (validateRatingEvent /
 * reduceRatingEvent) works across retries and restarts. */
function deterministicUuidFromString(str) {
  var hex = sha256Hex(String(str)).slice(0, 32);
  return hex.slice(0, 8) + '-' + hex.slice(8, 12) + '-' + hex.slice(12, 16) + '-'
    + hex.slice(16, 20) + '-' + hex.slice(20, 32);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function isNonEmptyTrimmedString(v, maxLen) {
  return typeof v === 'string' && v.trim().length > 0 && v.length <= (maxLen || 4000);
}

/** Bundle v1 guidance is an array of exactly 5 nonempty strings, positionally
 * Where/Try/Benefit/Effort/Check (see GUIDANCE_KEYS) — never a keyed object.
 * Renderers zip GUIDANCE_KEYS with this array by position. */
function validateGuidance(guidance) {
  if (!Array.isArray(guidance) || guidance.length !== 5) {
    return {
      ok: false,
      errors: ['guidance must be an array of exactly 5 strings, positionally ' + GUIDANCE_KEYS.join('/')]
    };
  }
  var errors = [];
  guidance.forEach(function (v, idx) {
    if (!isNonEmptyTrimmedString(v, 1000)) {
      errors.push('guidance[' + idx + '] (' + GUIDANCE_KEYS[idx] + ') must be a nonempty string');
    }
  });
  return { ok: errors.length === 0, errors: errors };
}

function validateTopics(topics) {
  if (!Array.isArray(topics) || topics.length === 0) {
    return { ok: false, errors: ['topics must be a nonempty array of strings'] };
  }
  var bad = topics.some(function (t) { return !isNonEmptyTrimmedString(t, 200); });
  return bad ? { ok: false, errors: ['topics must all be nonempty strings'] } : { ok: true, errors: [] };
}

function validateRepositoryName(repo) {
  if (!isNonEmptyTrimmedString(repo, 200)) return { ok: false, errors: ['repository must be a nonempty string'] };
  if (repo !== repo.trim()) return { ok: false, errors: ['repository must not have leading/trailing whitespace'] };
  if (repo.indexOf('..') !== -1 || /[\\\x00-\x1f]/.test(repo)) {
    return { ok: false, errors: ['repository contains disallowed characters'] };
  }
  return { ok: true, errors: [] };
}

function validateItem(item, editionDate) {
  var errors = [];
  if (typeof item !== 'object' || item === null || Array.isArray(item)) {
    return { ok: false, errors: ['item must be an object'] };
  }

  var unknownItemKeys = Object.keys(item).filter(function (k) { return ITEM_KEYS.indexOf(k) === -1; });
  if (unknownItemKeys.length) errors.push('item has unexpected field(s): ' + unknownItemKeys.join(','));

  if (!isNonEmptyTrimmedString(item.title, 300)) errors.push('title must be a nonempty string');

  var canon = canonicalUrl(item.source_url);
  if (!canon) errors.push('source_url must be an https URL');

  if (!isValidItemId(item.item_id)) {
    errors.push('item_id must match RAD-<12 hex>');
  } else if (canon && item.item_id !== stableItemId(item.source_url)) {
    errors.push('item_id does not match sha256(canonical source_url)');
  }

  if (!isValidDateString(item.published_at)) {
    errors.push('published_at must be a real YYYY-MM-DD date');
  } else if (SOURCE_TYPES.indexOf(item.source_type) !== -1) {
    var cap = ageCapOk(item.source_type, item.published_at, editionDate);
    if (!cap.ok) errors.push('published_at fails age cap (' + cap.reason + ')');
  }

  if (SOURCE_TYPES.indexOf(item.source_type) === -1) {
    errors.push('source_type must be one of ' + SOURCE_TYPES.join('/'));
  }

  if (!isNonEmptyTrimmedString(item.summary, 4000)) errors.push('summary must be a nonempty string');
  if (!isNonEmptyTrimmedString(item.why_it_matters, 4000)) errors.push('why_it_matters must be a nonempty string');
  if (!isNonEmptyTrimmedString(item.evidence_label, 500)) errors.push('evidence_label must be a nonempty string');
  if (item.user_facing_ai !== undefined && typeof item.user_facing_ai !== 'boolean') errors.push('user_facing_ai must be a boolean');
  if (item.application_example !== undefined && !isNonEmptyTrimmedString(item.application_example, 4000)) errors.push('application_example must be a nonempty string');
  if (item.user_facing_ai === true && !isNonEmptyTrimmedString(item.application_example, 4000)) errors.push('user-facing AI products require a concrete application_example');

  if (item.publication !== undefined) {
    var pub = item.publication;
    if (!pub || typeof pub !== 'object' || Array.isArray(pub)
        || Object.keys(pub).some(function(k) { return ['status','venue','publication_url'].indexOf(k) === -1; })
        || pub.status !== 'published' || !isNonEmptyTrimmedString(pub.venue, 300)
        || !canonicalUrl(pub.publication_url) || canonicalUrl(pub.publication_url) !== canon
        || /^https:\/\/(?:[^/]+\.)?(?:arxiv\.org|biorxiv\.org|medrxiv\.org)(?:\/|$)/i.test(canon || '')) {
      errors.push('publication must identify a published paper venue and matching primary publication URL, not a preprint');
    }
  }
  var repoCheck = validateRepositoryName(item.repository);
  if (!repoCheck.ok) errors = errors.concat(repoCheck.errors);

  var guidanceCheck = validateGuidance(item.guidance);
  if (!guidanceCheck.ok) errors = errors.concat(guidanceCheck.errors);

  var topicsCheck = validateTopics(item.topics);
  if (!topicsCheck.ok) errors = errors.concat(topicsCheck.errors);

  if (item.source_dates !== undefined) {
    var sourceDates = item.source_dates;
    var dateValues = Array.isArray(sourceDates) ? sourceDates :
      (sourceDates && typeof sourceDates === 'object' ? Object.keys(sourceDates).map(function(k){return sourceDates[k];}) : null);
    if (!dateValues || dateValues.some(function (d) { return !isValidDateString(d) || d > editionDate; })) {
      errors.push('source_dates, when present, must be real non-future YYYY-MM-DD dates');
    }
  }

  if (item.repository_evidence !== undefined) {
    var ev = item.repository_evidence;
    var evOk = (typeof ev === 'string' && ev.trim().length > 0) || (typeof ev === 'object' && ev !== null);
    if (!evOk) errors.push('repository_evidence, when present, must be a nonempty string or object');
  }

  return { ok: errors.length === 0, errors: errors };
}

function validateBundle(bundle, opts) {
  opts = opts || {};
  var errors = [];
  if (typeof bundle !== 'object' || bundle === null || Array.isArray(bundle)) {
    return { ok: false, errors: ['bundle must be a JSON object'] };
  }

  var unknownBundleKeys = Object.keys(bundle).filter(function (k) { return BUNDLE_KEYS.indexOf(k) === -1; });
  if (unknownBundleKeys.length) errors.push('bundle has unexpected field(s): ' + unknownBundleKeys.join(','));

  if (bundle.schema_version !== SCHEMA_VERSION) errors.push('schema_version must equal ' + SCHEMA_VERSION);
  if (!isValidRunId(bundle.run_id)) errors.push('run_id must be a safe slug');
  if (!isValidDateString(bundle.edition_date)) errors.push('edition_date must be a real YYYY-MM-DD date');
  if (bundle.edition_date > istDateString(new Date(typeof opts.nowMs === 'number' ? opts.nowMs : Date.now()))) errors.push('edition_date is in the future');
  var generated = parseIsoTimestamp(bundle.generated_at);
  if (!generated) {
    errors.push('generated_at must be a UTC-aware ISO 8601 timestamp');
  } else if (typeof opts.nowMs === 'number' && generated.ms > opts.nowMs + 5 * 60 * 1000) {
    errors.push('generated_at is in the future');
  }
  if (PRODUCERS.indexOf(bundle.producer) === -1) errors.push('producer must be one of ' + PRODUCERS.join('/'));
  if (!isNonEmptyTrimmedString(bundle.model_id, 200)) errors.push('model_id must be a nonempty string');
  if (bundle.kind !== 'digest') errors.push('kind must equal "digest"');
  if (bundle.newsletter !== undefined && NEWSLETTERS.indexOf(bundle.newsletter) === -1) errors.push('newsletter must be product or academic');

  if (!Array.isArray(bundle.items) || bundle.items.length < MIN_ITEMS) {
    errors.push('items must be an array with at least ' + MIN_ITEMS + ' entries');
  } else if (isValidDateString(bundle.edition_date)) {
    if (!bundle.items.some(function(item) { return item && item.user_facing_ai === true; })) {
      errors.push('items must include at least one user-facing AI product');
    }
    var seenIds = {};
    var seenUrls = {};
    bundle.items.forEach(function (item, idx) {
      var check = validateItem(item, bundle.edition_date);
      if (bundle.newsletter === 'academic' && (!item || item.source_type !== 'academic' || !item.publication)) {
        errors.push('items[' + idx + ']: academic newsletter requires only published academic papers with publication evidence');
      }
      check.errors.forEach(function (e) { errors.push('items[' + idx + ']: ' + e); });
      if (isValidItemId(item && item.item_id)) {
        if (seenIds[item.item_id]) errors.push('items[' + idx + ']: duplicate item_id ' + item.item_id);
        seenIds[item.item_id] = true;
      }
      var canon = item && canonicalUrl(item.source_url);
      if (canon) {
        if (seenUrls[canon]) errors.push('items[' + idx + ']: duplicate source_url (canonical) ' + canon);
        seenUrls[canon] = true;
      }
    });
  }

  return { ok: errors.length === 0, errors: errors };
}

/** Validator attestation (kind: "validation"). A digest bundle can never
 * self-set its own approval — the only source of truth for "approved" is a
 * separately validated attestation file whose candidate_sha256 matches the
 * exact bytes of the original accepted bundle. */
function validateAttestation(att, opts) {
  opts = opts || {};
  var errors = [];
  if (typeof att !== 'object' || att === null || Array.isArray(att)) {
    return { ok: false, errors: ['attestation must be an object'] };
  }
  var unknown = Object.keys(att).filter(function (k) { return ATTESTATION_KEYS.indexOf(k) === -1; });
  if (unknown.length) errors.push('attestation has unexpected field(s): ' + unknown.join(','));

  if (att.schema_version !== SCHEMA_VERSION) errors.push('schema_version must equal ' + SCHEMA_VERSION);
  if (att.kind !== 'validation') errors.push('kind must equal "validation"');
  if (!isValidRunId(att.run_id)) errors.push('run_id must be a safe slug');
  if (!isValidRunId(att.candidate_run_id)) errors.push('candidate_run_id must be a safe slug');
  if (typeof att.candidate_sha256 !== 'string' || !CANDIDATE_SHA256_RE.test(att.candidate_sha256)) {
    errors.push('candidate_sha256 must be a 64-character lowercase hex sha256');
  }
  if (!Object.prototype.hasOwnProperty.call(VALIDATOR_MODELS, att.validator)) errors.push('validator must equal sol or opus');
  else if (att.model_id !== VALIDATOR_MODELS[att.validator]) errors.push('model_id must equal "' + VALIDATOR_MODELS[att.validator] + '"');
  if (VERDICTS.indexOf(att.verdict) === -1) errors.push('verdict must be one of ' + VERDICTS.join('/'));
  var checked = parseIsoTimestamp(att.checked_at);
  if (!checked) {
    errors.push('checked_at must be a UTC-aware ISO 8601 timestamp');
  } else if (typeof opts.nowMs === 'number' && checked.ms > opts.nowMs + 5 * 60 * 1000) {
    errors.push('checked_at is in the future');
  }
  return { ok: errors.length === 0, errors: errors };
}

function attestationApprovesCandidate(att, candidateRunId, candidateSha256) {
  return !!att && att.verdict === 'approved'
    && att.candidate_run_id === candidateRunId
    && att.candidate_sha256 === candidateSha256;
}

/** Deterministic winner among same-edition, sufficiently-fresh, validator-
 * approved candidates. Ties broken by PRODUCER_PRIORITY, then run_id. Pure
 * and total: candidates missing edition_date/freshness/approval are simply
 * excluded, never silently trimmed down to fit. */
function selectDeliverableCandidate(candidates, todayEditionDate) {
  var eligible = (candidates || []).filter(function (c) {
    return c.bundle && c.bundle.edition_date === todayEditionDate
      && Array.isArray(c.freshItems) && c.freshItems.length >= MIN_ITEMS
      && c.approved === true;
  });
  eligible.sort(function (a, b) {
    var pa = PRODUCER_PRIORITY.indexOf(a.bundle.producer);
    var pb = PRODUCER_PRIORITY.indexOf(b.bundle.producer);
    if (pa === -1) pa = PRODUCER_PRIORITY.length;
    if (pb === -1) pb = PRODUCER_PRIORITY.length;
    if (pa !== pb) return pa - pb;
    return a.bundle.run_id < b.bundle.run_id ? -1 : (a.bundle.run_id > b.bundle.run_id ? 1 : 0);
  });
  return eligible.length ? eligible[0] : null;
}

function filterUndeliveredItems(items, deliveredIdSet) {
  return items.filter(function (item) { return !deliveredIdSet.has(item.item_id); });
}

// --- Ratings --------------------------------------------------------------

function validateRatingEvent(event, opts) {
  opts = opts || {};
  var errors = [];
  if (typeof event !== 'object' || event === null) return { ok: false, errors: ['event must be an object'] };
  if (typeof event.event_id !== 'string' || !UUID_RE.test(event.event_id)) errors.push('event_id must be a UUID');
  if (!isValidItemId(event.item_id)) errors.push('item_id must match RAD-<12 hex>');
  if (typeof event.score !== 'number' || !Number.isInteger(event.score) || event.score < 1 || event.score > 5) {
    errors.push('score must be an integer 1..5');
  }
  if (event.reason !== undefined && typeof event.reason !== 'string') errors.push('reason must be a string when present');
  if (RATING_ORIGINS.indexOf(event.origin) === -1) errors.push('origin must be one of ' + RATING_ORIGINS.join('/'));
  if (!Number.isInteger(event.base_revision) || event.base_revision < 0) errors.push('base_revision must be a non-negative integer');
  var created = parseIsoTimestamp(event.created_at);
  if (!created) {
    errors.push('created_at must be a UTC-aware ISO 8601 timestamp');
  } else if (typeof opts.nowMs === 'number' && created.ms > opts.nowMs + 5 * 60 * 1000) {
    errors.push('created_at is in the future');
  }
  return { ok: errors.length === 0, errors: errors };
}

function ratingPayloadEquals(a, b) {
  return a.item_id === b.item_id
    && a.score === b.score
    && (a.reason || '') === (b.reason || '')
    && a.origin === b.origin
    && a.base_revision === b.base_revision
    && a.created_at === b.created_at;
}

function checkDuplicateOrConflict(existingEventRecord, incomingEvent) {
  if (!existingEventRecord) return { status: 'new' };
  return ratingPayloadEquals(existingEventRecord, incomingEvent)
    ? { status: 'duplicate' }
    : { status: 'error', reason: 'event_id_payload_mismatch' };
}

function reduceRatingEvent(existingEventRecord, currentRating, event) {
  var dupCheck = checkDuplicateOrConflict(existingEventRecord, event);
  if (dupCheck.status === 'duplicate') return { status: 'duplicate' };
  if (dupCheck.status === 'error') return { status: 'error', reason: dupCheck.reason };

  var currentRevision = currentRating ? currentRating.revision : 0;
  if (event.base_revision !== currentRevision) {
    return { status: 'conflict', currentRevision: currentRevision };
  }
  return {
    status: 'applied',
    rating: {
      item_id: event.item_id,
      score: event.score,
      reason: event.reason || '',
      revision: currentRevision + 1,
      last_event_id: event.event_id,
      updated_at: event.created_at
    }
  };
}

/** Rebuilds CurrentRatings from scratch by replaying every structurally
 * valid RatingEvents journal row, in persisted order, through the same
 * reduceRatingEvent logic used for a single live event. This is what lets
 * the gateway recover full projection state after a crash between
 * "event persisted" and "CurrentRatings updated" — the journal alone is
 * always sufficient, and replaying it twice yields the same result
 * (duplicate event_ids are re-detected identically on every replay, never
 * skipped as "already handled"). knownItemIds, when given, rejects rating
 * events for items the gateway has never recorded as delivered. */
function replayRatingEvents(eventRows, knownItemIds) {
  var currentRatings = {};
  var seenEvents = {};
  var eventStatuses = {};
  (eventRows || []).forEach(function (raw) {
    var event = {
      event_id: raw.event_id,
      item_id: raw.item_id,
      score: raw.score,
      reason: raw.reason ? String(raw.reason) : undefined,
      origin: raw.origin,
      base_revision: raw.base_revision,
      created_at: raw.created_at
    };
    var validation = validateRatingEvent(event, {});
    if (!validation.ok) {
      eventStatuses[event.event_id || raw.event_id] = 'error:' + validation.errors.join(',');
      return;
    }
    if (knownItemIds && !knownItemIds.has(event.item_id)) {
      eventStatuses[event.event_id] = 'error:unknown_item';
      return;
    }
    var existing = seenEvents[event.event_id] || null;
    var current = currentRatings[event.item_id] || null;
    var result = reduceRatingEvent(existing, current, event);
    if (result.status === 'error') {
      eventStatuses[event.event_id] = 'error:' + result.reason;
    } else {
      eventStatuses[event.event_id] = result.status;
    }
    seenEvents[event.event_id] = event;
    if (result.status === 'applied') currentRatings[event.item_id] = result.rating;
  });
  return { currentRatings: currentRatings, eventStatuses: eventStatuses };
}

function classifyReasonTags(reasonText) {
  var text = (reasonText || '').toLowerCase();
  return {
    technical: /too technical|too complex|hard to follow/.test(text),
    alreadyKnew: /already knew|already aware|knew already|not new to me/.test(text),
    tooMuchEffort: /too much effort|too much work|high effort|too time.?consuming/.test(text)
  };
}

function derivePreferences(currentRatingsList, itemsById) {
  itemsById = itemsById || {};
  var suppressedRepositories = {};
  var suppressedItemIds = [];
  var pairSignals = {};
  var presentationSimplifyItemIds = [];
  var queueInvestigationItemIds = [];
  var experimentProposalItemIds = [];
  var smallScopeFavoredItemIds = [];

  (currentRatingsList || []).forEach(function (rating) {
    var tags = classifyReasonTags(rating.reason);
    var item = itemsById[rating.item_id];
    if (tags.alreadyKnew) suppressedItemIds.push(rating.item_id);
    if (item && Array.isArray(item.topics)) item.topics.forEach(function(topic) {
      var key = JSON.stringify([String(topic).toLowerCase(),String(item.repository).toLowerCase()]);
      if (!pairSignals[key]) pairSignals[key]=[];
      pairSignals[key].push((rating.score-3)/2);
    });
    if (tags.technical) presentationSimplifyItemIds.push(rating.item_id);
    if (tags.tooMuchEffort) smallScopeFavoredItemIds.push(rating.item_id);
    if (rating.score === 4) queueInvestigationItemIds.push(rating.item_id);
    if (rating.score === 5) experimentProposalItemIds.push(rating.item_id);
  });

  function sorted(arr) { return arr.slice().sort(); }

  return {
    schema_version: SCHEMA_VERSION,
    suppressed_repositories: sorted(Object.keys(suppressedRepositories)),
    suppressed_item_ids: sorted(suppressedItemIds),
    relevance_weights: Object.keys(pairSignals).sort().map(function(key) {
      var pair=JSON.parse(key), signals=pairSignals[key];
      return {topic:pair[0],repository:pair[1],weight:1+0.25*signals.reduce(function(a,b){return a+b;},0)/signals.length};
    }),
    presentation_simplify_item_ids: sorted(presentationSimplifyItemIds),
    small_scope_favored_item_ids: sorted(smallScopeFavoredItemIds),
    queue_investigation_item_ids: sorted(queueInvestigationItemIds),
    experiment_proposal_item_ids: sorted(experimentProposalItemIds)
  };
}

// --- Scheduling / delivery -------------------------------------------------

var IST_OFFSET_MINUTES = 330; // Asia/Kolkata is a fixed UTC+5:30 offset, no DST.

function istPartsFromUtc(date) {
  var istMs = date.getTime() + IST_OFFSET_MINUTES * 60000;
  var ist = new Date(istMs);
  return {
    year: ist.getUTCFullYear(),
    month: ist.getUTCMonth() + 1,
    day: ist.getUTCDate(),
    hour: ist.getUTCHours(),
    minute: ist.getUTCMinutes()
  };
}

function istDateString(date) {
  var p = istPartsFromUtc(date);
  return p.year + '-' + pad2(p.month) + '-' + pad2(p.day);
}

function isAtOrAfter17Ist(date) {
  var p = istPartsFromUtc(date);
  return (p.hour * 60 + p.minute) >= (DISPATCH_HOUR_IST * 60);
}

function isDueForDispatch(date, lastDeliveredEditionDate) {
  var editionDate = istDateString(date);
  var due = isAtOrAfter17Ist(date) && editionDate !== lastDeliveredEditionDate;
  return { due: due, editionDate: editionDate };
}

function classifySendOutcome(threw, errorMessage) {
  if (!threw) return 'sent';
  var text = (errorMessage || '').toLowerCase();
  var permanentPatterns = [/invalid email/, /no such user/, /recipient address rejected/, /daily (sending )?limit/, /quota/];
  var isPermanent = permanentPatterns.some(function (re) { return re.test(text); });
  return isPermanent ? 'failed_permanent' : 'uncertain';
}

function shouldAutoRetry(outcome) {
  // Contract: an uncertain SMTP result is never blind-retried. Permanent
  // failures also require manual reconciliation, not an automatic resend.
  return false;
}

function extractSenderEmail(fromHeader) {
  if (typeof fromHeader !== 'string') return null;
  var angleMatch = fromHeader.match(/<([^>]+)>/);
  var raw = angleMatch ? angleMatch[1] : fromHeader;
  return raw.trim().toLowerCase();
}

function isAuthorizedSender(fromHeader, configuredEmail) {
  var sender = extractSenderEmail(fromHeader);
  if (!sender || !configuredEmail) return false;
  return sender === String(configuredEmail).trim().toLowerCase();
}

function parseRateCommand(line) {
  var match = RATE_LINE_RE.exec(line);
  if (!match) return null;
  var reason = match[4] ? match[4].trim() : '';
  return {
    item_id: match[1],
    score: Number(match[2]),
    base_revision: Number(match[3]),
    reason: reason || undefined
  };
}

function extractRateCommands(bodyText) {
  if (typeof bodyText !== 'string') return [];
  var results = [];
  bodyText.split(/\r?\n/).forEach(function (line) {
    var parsed = parseRateCommand(line);
    if (parsed) results.push(parsed);
  });
  return results;
}

// --- Email content ----------------------------------------------------------

function buildRatingLegendHtml() {
  return '<div style="border:1px solid #ccc;padding:12px;margin-bottom:16px;font-family:sans-serif;font-size:13px;">'
    + '<strong>Rating legend (1-5)</strong>'
    + '<ul style="margin:6px 0;padding-left:20px;">'
    + '<li>1 — Skip: suppress similar items</li>'
    + '<li>2 — Weak match: reduce similar items</li>'
    + '<li>3 — Useful: keep the mix balanced</li>'
    + '<li>4 — queue for investigation</li>'
    + '<li>5 — experiment proposal only (do not use for anything less than a genuine experiment candidate)</li>'
    + '</ul>'
    + '<p>Ratings change what gets surfaced again, never the factual credibility of a finding.</p>'
    + '<p><strong>Reason tags</strong> (put any of these in your reply reason to steer future editions): '
    + '"too technical" simplifies presentation, "already knew" suppresses that item, '
    + '"too much effort" favors smaller-scope suggestions.</p>'
    + '<p><strong>Reply syntax:</strong> reply to this email with one line per rating, e.g. '
    + '<code>RATE RAD-abc123def456 5 REV=0 good match</code> — REV is the revision shown next to the item.</p>'
    + '</div>';
}

function buildRatingLegendText() {
  return 'Rating legend (1-5): 1 not relevant, 2 low relevance, 3 worth knowing, '
    + '4 queue for investigation, 5 experiment proposal only. Ratings change relevance, never credibility.\n'
    + 'Reason tags: "too technical" simplifies presentation, "already knew" suppresses that item, '
    + '"too much effort" favors smaller-scope suggestions.\n'
    + 'Reply syntax: RATE RAD-abc123def456 5 REV=0 good match\n';
}

function buildDigestSubject(editionDate, isTest, deliveryKey, newsletter) {
  var prefix = isTest ? '[TEST] ' : '';
  var suffix = deliveryKey ? ' [' + deliveryKey + ']' : '';
  return prefix + newsletterName(newsletter) + ' — ' + editionDate + suffix;
}

function buildDigestHtml(bundle) {
  var parts = [];
  parts.push('<div style="font-family:sans-serif;font-size:14px;color:#111;">');
  parts.push('<h1 style="font-size:18px;">' + escapeHtml(newsletterName(bundle.newsletter)) + ' — ' + escapeHtml(bundle.edition_date) + '</h1>');
  parts.push(buildRatingLegendHtml());
  bundle.items.forEach(function (item) {
    parts.push('<div style="border-top:1px solid #eee;padding:12px 0;">');
    if (item.user_facing_ai === true) parts.push('<p><strong>' + (bundle.newsletter === 'academic' ? 'Paper-backed AI product idea for your users' : 'AI product your users could interact with') + '</strong></p>');
    parts.push('<h2 style="font-size:16px;margin:0 0 4px;">'
      + '<a href="' + escapeHtml(item.source_url) + '">' + escapeHtml(item.title) + '</a></h2>');
    parts.push('<p style="margin:2px 0;color:#555;">' + escapeHtml(item.item_id) + ' · '
      + escapeHtml(item.source_type) + ' · ' + escapeHtml(item.published_at) + ' · '
      + escapeHtml(item.evidence_label) + '</p>');
    if (item.publication) parts.push('<p><strong>Published in:</strong> ' + escapeHtml(item.publication.venue) + ' · <a href="' + escapeHtml(item.publication.publication_url) + '">Read the published paper</a></p>');
    parts.push('<p><strong>What this means in everyday terms:</strong> ' + escapeHtml(item.summary) + '</p>');
    parts.push('<p><strong>Why this could be useful in your work:</strong> ' + escapeHtml(item.why_it_matters) + '</p>');
    if (item.application_example) parts.push('<p><strong>A practical example (proposed trial):</strong> ' + escapeHtml(item.application_example) + '</p>');
    parts.push('<p><strong>Project to try it in:</strong> ' + escapeHtml(item.repository) + '</p>');
    parts.push('<ul>');
    GUIDANCE_KEYS.forEach(function (k, idx) {
      var value = item.guidance[idx].replace(new RegExp('^' + k + ':\\s*'), '');
      parts.push('<li><strong>' + escapeHtml(GUIDANCE_LABELS[idx]) + ':</strong> ' + escapeHtml(value) + '</li>');
    });
    parts.push('</ul>');
    parts.push('<p style="color:#888;">Topics: ' + item.topics.map(escapeHtml).join(', ') + '</p>');
    parts.push('<p>To rate this idea, copy this line into your reply, replace SCORE with 1 to 5, and add your reason:<br><code>' + escapeHtml('RATE ' + item.item_id + ' SCORE REV=0 your reason') + '</code></p>');
    parts.push('</div>');
  });
  parts.push('</div>');
  return parts.join('\n');
}

function buildDigestText(bundle) {
  var lines = [];
  lines.push(newsletterName(bundle.newsletter) + ' — ' + bundle.edition_date);
  lines.push('');
  lines.push(buildRatingLegendText());
  bundle.items.forEach(function (item) {
    lines.push('---');
    lines.push(item.title + ' (' + item.item_id + ')');
    if (item.user_facing_ai === true) lines.push(bundle.newsletter === 'academic' ? 'PAPER-BACKED AI PRODUCT IDEA FOR YOUR USERS' : 'AI PRODUCT YOUR USERS COULD INTERACT WITH');
    lines.push(item.source_url);
    lines.push(item.source_type + ' · ' + item.published_at + ' · ' + item.evidence_label);
    if (item.publication) lines.push('Published in: ' + item.publication.venue + ' | ' + item.publication.publication_url);
    lines.push('What this means in everyday terms: ' + item.summary);
    lines.push('Why this could be useful in your work: ' + item.why_it_matters);
    if (item.application_example) lines.push('A practical example (proposed trial): ' + item.application_example);
    lines.push('Project to try it in: ' + item.repository);
    GUIDANCE_KEYS.forEach(function (k, idx) {
      lines.push(GUIDANCE_LABELS[idx] + ': ' + item.guidance[idx].replace(new RegExp('^' + k + ':\\s*'), ''));
    });
    lines.push('Topics: ' + item.topics.join(', '));
    lines.push('To rate: replace SCORE with 1 to 5 and add your reason.');
    lines.push('RATE ' + item.item_id + ' SCORE REV=0 your reason');
  });
  return lines.join('\n');
}

function buildOutboxRecord(bundle, recipient, subject, isTest, deliveryKey, nowIso) {
  return {
    edition_date: bundle.edition_date,
    run_id: bundle.run_id,
    recipient: recipient,
    subject: subject,
    item_ids: bundle.items.map(function (i) { return i.item_id; }).join(','),
    delivery_key: deliveryKey,
    status: 'claimed',
    is_test: !!isTest,
    created_at: nowIso,
    updated_at: nowIso,
    newsletter: bundle.newsletter || 'product'
  };
}

function buildSnapshotJson(items, digests, ratings, stateRevision, nowIso) {
  return {
    schema_version: SCHEMA_VERSION,
    state_revision: stateRevision || 0,
    items: items || [],
    digests: digests || [],
    ratings: ratings || {},
    updated_at: nowIso
  };
}

/** Rebuilds one Items-sheet row back into a bundle-item-shaped object:
 * guidance and topics are stored flattened across columns / as a
 * comma-joined string, so the snapshot must reconstruct both arrays rather
 * than exporting the flattened row as-is. */
function reconstructSnapshotItem(row) {
  return {
    item_id: row.item_id,
    title: row.title,
    source_url: row.source_url,
    published_at: row.published_at,
    source_type: row.source_type,
    summary: row.summary,
    why_it_matters: row.why_it_matters,
    evidence_label: row.evidence_label,
    repository: row.repository,
    user_facing_ai: row.user_facing_ai === true || row.user_facing_ai === 'true',
    application_example: row.application_example || undefined,
    publication: row.publication_json ? JSON.parse(row.publication_json) : undefined,
    guidance: [row.guidance_where, row.guidance_try, row.guidance_benefit, row.guidance_effort, row.guidance_check],
    topics: row.topics ? String(row.topics).split(',').filter(function (t) { return t.length > 0; }) : [],
    first_delivered_edition_date: row.first_delivered_edition_date,
    run_id: row.run_id
  };
}

// ===========================================================================
// 3. Google-service orchestration.
//    Exercised by google/test_gateway.cjs's mock DriveApp/SpreadsheetApp/
//    PropertiesService/LockService/GmailApp/Utilities, and otherwise only
//    runnable inside the Apps Script editor against real owned resources.
// ===========================================================================

function getProp(key, fallback) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  return v === null ? (fallback === undefined ? null : fallback) : v;
}

function setProp(key, value) {
  PropertiesService.getScriptProperties().setProperty(key, value);
}

function deleteProp(key) {
  PropertiesService.getScriptProperties().deleteProperty(key);
}

function getOwnerEmail() {
  var value = getProp(PROP.OWNER_EMAIL, OWNER_EMAIL_DEFAULT);
  if (value !== OWNER_EMAIL_DEFAULT) throw new Error('Recipient must be harshad422@gmail.com');
  return OWNER_EMAIL_DEFAULT;
}

function withScriptLock(fn) {
  var lock = LockService.getScriptLock();
  var acquired = lock.tryLock(30000);
  if (!acquired) throw new Error('Could not acquire radar script lock within 30s');
  try {
    return fn();
  } finally {
    lock.releaseLock();
  }
}

function bumpStateRevision() {
  var current = Number(getProp(PROP.STATE_REVISION, '0')) || 0;
  var next = current + 1;
  setProp(PROP.STATE_REVISION, String(next));
  return next;
}

function getStateRevision() {
  return Number(getProp(PROP.STATE_REVISION, '0')) || 0;
}

function getOrCreateSubfolder(parent, name) {
  var existing = parent.getFoldersByName(name);
  if (existing.hasNext()) return existing.next();
  return parent.createFolder(name);
}

function resolveFolderById(prop) {
  var id = getProp(prop);
  if (!id) return null;
  try {
    return DriveApp.getFolderById(id);
  } catch (e) {
    return null;
  }
}

function getOrCreateDriveTree() {
  var root = resolveFolderById(PROP.FOLDER_ROOT);
  if (!root) {
    root = DriveApp.createFolder('AI Product Radar');
    setProp(PROP.FOLDER_ROOT, root.getId());
  }
  var folders = { root: root };
  DRIVE_SUBFOLDERS.forEach(function (spec) {
    var folder = resolveFolderById(spec.prop);
    if (!folder) {
      folder = getOrCreateSubfolder(root, spec.key);
      setProp(spec.prop, folder.getId());
    }
    folders[spec.key] = folder;
  });
  return folders;
}

function ensureSheetTab(ss, tabName) {
  var sheet = ss.getSheetByName(tabName);
  if (!sheet) sheet = ss.insertSheet(tabName);
  var headers = SHEET_SCHEMAS[tabName];
  var firstRow = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  var hasHeaders = headers.every(function (h, i) { return firstRow[i] === h; });
  if (!hasHeaders) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  return sheet;
}

function getOrCreateSpreadsheet(folder) {
  var id = getProp(PROP.SHEET_ID);
  var ss = null;
  if (id) {
    try { ss = SpreadsheetApp.openById(id); } catch (e) { ss = null; }
  }
  if (!ss) {
    ss = SpreadsheetApp.create('AI Product Radar');
    var file = DriveApp.getFileById(ss.getId());
    folder.addFile(file);
    DriveApp.getRootFolder().removeFile(file);
    setProp(PROP.SHEET_ID, ss.getId());
    var defaultSheet = ss.getSheets()[0];
    defaultSheet.setName('Items');
  }
  Object.keys(SHEET_SCHEMAS).forEach(function (tab) { ensureSheetTab(ss, tab); });
  return ss;
}

function getOrCreateForm(folder) {
  var id = getProp(PROP.FORM_ID);
  var form = null;
  if (id) {
    try { form = FormApp.openById(id); } catch (e) { form = null; }
  }
  if (!form) {
    form = FormApp.create('AI Product Radar — Rating');
    var file = DriveApp.getFileById(form.getId());
    folder.addFile(file);
    DriveApp.getRootFolder().removeFile(file);
    form.setCollectEmail(true);
    form.setRequireLogin(true);
    form.setLimitOneResponsePerUser(false);
    form.addTextItem().setTitle('Item ID (RAD-...)').setRequired(true);
    var scoreItem = form.addListItem().setTitle('Score').setRequired(true);
    scoreItem.setChoiceValues(['1', '2', '3', '4', '5']);
    // Known, fixed index (2): the rater copies this from the digest email
    // next to the item so the gateway never has to invent a base_revision
    // for them — a stale value simply surfaces as a "conflict" event.
    form.addTextItem().setTitle('Base revision (REV= shown next to the item)').setRequired(true);
    form.addParagraphTextItem().setTitle('Reason (optional)').setRequired(false);
    setProp(PROP.FORM_ID, form.getId());
  }
  return form;
}

/**
 * Idempotent, setup-only: provisions the Drive folder tree, Sheet tabs and
 * rating Form under Script Properties. Safe to re-run; it reuses whatever it
 * already provisioned instead of creating duplicates. Run manually from the
 * Apps Script editor once per Google account — see google/README.md.
 */
function setupRadar() {
  if (!getProp(PROP.OWNER_EMAIL)) setProp(PROP.OWNER_EMAIL, OWNER_EMAIL_DEFAULT);
  var folders = getOrCreateDriveTree();
  var ss = getOrCreateSpreadsheet(folders.root);
  var form = getOrCreateForm(folders.root);
  Logger.log('Radar provisioned. Sheet: %s Form: %s', ss.getUrl(), form.getPublishedUrl());
  return { sheetId: ss.getId(), formId: form.getId(), rootFolderId: folders.root.getId() };
}

/**
 * Idempotent trigger installation: removes any previously installed radar
 * triggers by handler name before recreating them, so re-running this never
 * produces duplicate triggers.
 */
function installRadarTriggers() {
  var handlers = ['dispatchRadar', 'processGmailReplies', 'onFormSubmit'];
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (handlers.indexOf(t.getHandlerFunction()) !== -1) ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('dispatchRadar').timeBased().everyMinutes(5).create();
  ScriptApp.newTrigger('processGmailReplies').timeBased().everyMinutes(15).create();
  var formId = getProp(PROP.FORM_ID);
  if (formId) {
    ScriptApp.newTrigger('onFormSubmit').forForm(FormApp.openById(formId)).onFormSubmit().create();
  }
}

function listInboxFiles(folders) {
  var files = folders.inbox.getFiles();
  var out = [];
  while (files.hasNext()) {
    var f = files.next();
    if (f.getName().toLowerCase().endsWith('.json')) out.push(f);
  }
  return out;
}

function readRawFile(file) {
  return file.getBlob().getDataAsString('UTF-8');
}

function readJsonFile(file) {
  return JSON.parse(readRawFile(file));
}

function writeJsonFile(folder, name, obj) {
  var content = JSON.stringify(obj, null, 2);
  var existing = folder.getFilesByName(name);
  if (existing.hasNext()) {
    existing.next().setContent(content);
  } else {
    folder.createFile(name, content, MimeType.PLAIN_TEXT);
  }
}

/** Writes the exact original bytes unmodified — used for accepted digest
 * bundles and attestations so the file content that candidate_sha256 must
 * match never drifts from what the producer/validator actually sent, and so
 * an accepted bundle's items are never trimmed or rewritten in place. */
function writeRawFile(folder, name, rawText) {
  var existing = folder.getFilesByName(name);
  if (existing.hasNext()) {
    existing.next().setContent(rawText);
  } else {
    folder.createFile(name, rawText, MimeType.PLAIN_TEXT);
  }
}

function getDeliveredItemIds(sheet) {
  var set = new Set();
  getSheetRows(sheet, 'Items').forEach(function (row) {
    if (row.item_id && row.first_delivered_edition_date) set.add(row.item_id);
  });
  return set;
}

function writeTypedRow(sheet, rowNumber, values) {
  var range = sheet.getRange(rowNumber, 1, 1, values.length);
  range.setNumberFormat('@');
  values.forEach(function(value, index) {
    if (typeof value === 'number' || typeof value === 'boolean') {
      sheet.getRange(rowNumber, index + 1, 1, 1).setNumberFormat('General');
    }
  });
  range.setValues(values.length ? [values] : []);
}

function appendRow(sheet, tabName, rowObject) {
  var headers = SHEET_SCHEMAS[tabName];
  var row = headers.map(function (h) {
    var v = rowObject[h] !== undefined ? rowObject[h] : '';
    return typeof v === 'string' && /^[=+\-@]/.test(v) ? "'" + v : v;
  });
  var next = sheet.getLastRow() + 1;
  if (typeof sheet.getMaxRows === 'function' && next > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(),100);
  writeTypedRow(sheet, next, row);
}

function recordItems(ss, bundle, nowIso, isPreview) {
  var sheet = ss.getSheetByName('Items');
  var sourcesSheet = ss.getSheetByName('Sources');
  var existingRows = getSheetRows(sheet, 'Items');
  bundle.items.forEach(function (item) {
    var existing = existingRows.filter(function(row) { return row.item_id === item.item_id; })[0];
    var record = {
      item_id: item.item_id,
      title: item.title,
      source_url: item.source_url,
      published_at: item.published_at,
      source_type: item.source_type,
      summary: item.summary,
      why_it_matters: item.why_it_matters,
      evidence_label: item.evidence_label,
      repository: item.repository,
      guidance_where: item.guidance[0],
      guidance_try: item.guidance[1],
      guidance_benefit: item.guidance[2],
      guidance_effort: item.guidance[3],
      guidance_check: item.guidance[4],
      topics: item.topics.join(','),
      first_delivered_edition_date: existing && existing.first_delivered_edition_date || (isPreview ? '' : bundle.edition_date),
      run_id: bundle.run_id,
      added_at: nowIso,
      user_facing_ai: item.user_facing_ai === true,
      application_example: item.application_example || '',
      publication_json: item.publication ? JSON.stringify(item.publication) : ''
    };
    if (existing) {
      var values = SHEET_SCHEMAS.Items.map(function(key) {
        var value = record[key] === undefined ? '' : record[key];
        return typeof value === 'string' && /^[=+\-@]/.test(value) ? "'" + value : value;
      });
      writeTypedRow(sheet, existing._row, values);
      return;
    }
    appendRow(sheet, 'Items', record);
    appendRow(sourcesSheet, 'Sources', {
      source_url: item.source_url,
      canonical_url: canonicalUrl(item.source_url),
      item_id: item.item_id,
      first_seen_edition_date: bundle.edition_date
    });
  });
}

function recordRun(ss, bundle, status, notes, nowIso) {
  bundle = bundle && typeof bundle === 'object' ? bundle : {};
  var sheet = ss.getSheetByName('Runs');
  appendRow(sheet, 'Runs', {
    run_id: bundle.run_id,
    producer: bundle.producer,
    model_id: bundle.model_id,
    edition_date: bundle.edition_date,
    generated_at: bundle.generated_at,
    item_count: bundle.items ? bundle.items.length : 0,
    status: status,
    validation_notes: notes,
    processed_at: nowIso
  });
}

function recordDelivery(ss, record) {
  var sheet = ss.getSheetByName('Deliveries');
  appendRow(sheet, 'Deliveries', record);
}

function getSheetRows(sheet, tabName) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = SHEET_SCHEMAS[tabName];
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row, idx) {
    var obj = { _row: idx + 2 };
    headers.forEach(function (h, i) { obj[h] = row[i]; });
    // Recover typed values from early text-formatted sheets as well as new rows.
    if (tabName === 'Deliveries') obj.is_test = obj.is_test === true || String(obj.is_test).toLowerCase() === 'true';
    var numeric = tabName === 'RatingEvents' ? ['score','base_revision'] : tabName === 'CurrentRatings' ? ['score','revision'] : [];
    numeric.forEach(function(key) {
      if (typeof obj[key] === 'string' && /^\d+$/.test(obj[key])) obj[key] = Number(obj[key]);
    });
    return obj;
  });
}

/** True when today's edition already has a Deliveries row that is claimed,
 * sent, or uncertain — including a crash between claim and send outcome, or
 * a restart that lost LAST_DELIVERED_EDITION_DATE. Either case must block a
 * second send attempt until a human reconciles it; only failed_permanent
 * (an unambiguous, well-understood failure) does not block a later retry. */
function hasBlockingDeliveryForEdition(ss, editionDate, newsletter) {
  var rows = getSheetRows(ss.getSheetByName('Deliveries'), 'Deliveries');
  return rows.some(function (r) {
    return (r.newsletter || 'product') === (newsletter || 'product') && r.edition_date === editionDate && !r.is_test && BLOCKING_DELIVERY_STATUSES.indexOf(r.status) !== -1;
  });
}

function isKnownItemId(ss, itemId) {
  var rows = getSheetRows(ss.getSheetByName('Items'), 'Items');
  return rows.some(function (r) { return r.item_id === itemId; });
}

function getKnownItemIdSet(ss) {
  var rows = getSheetRows(ss.getSheetByName('Items'), 'Items');
  var set = new Set();
  rows.forEach(function (r) { if (r.item_id) set.add(r.item_id); });
  return set;
}

function getItemsById(ss) {
  var rows = getSheetRows(ss.getSheetByName('Items'), 'Items');
  var byId = {};
  rows.forEach(function (r) { byId[r.item_id] = reconstructSnapshotItem(r); });
  return byId;
}

/** Ingests every *.json file currently in inbox/. Digest bundles
 * (kind:"digest") are validated with validateBundle and, if valid, written
 * byte-for-byte into accepted/ (never trimmed to fresh items — freshness is
 * re-checked against the current Items sheet on every dispatch instead, so
 * a bundle is never mutated after acceptance). Validator attestations
 * (kind:"validation") are validated with validateAttestation and written
 * into accepted/ with a "validation-" filename prefix, kept separate from
 * digest bundle files. Anything else, or anything that fails validation, is
 * reported into rejected/ and the original inbox file is removed either
 * way — inbox itself is never rewritten, only drained. */
function ingestInboxFiles(folders, ss, nowIso, nowMs) {
  var files = listInboxFiles(folders);
  files.forEach(function (file) {
    var rawText;
    try {
      rawText = readRawFile(file);
    } catch (e) {
      file.setTrashed(true);
      return;
    }
    var parsed;
    try {
      parsed = JSON.parse(rawText);
    } catch (e) {
      writeJsonFile(folders.rejected, file.getName() + '.rejected.json', { errors: ['invalid JSON: ' + e.message] });
      file.setTrashed(true);
      return;
    }

    if (parsed && parsed.kind === 'validation') {
      var attResult = validateAttestation(parsed, { nowMs: nowMs });
      if (!attResult.ok) {
        writeJsonFile(folders.rejected, file.getName() + '.rejected.json', { errors: attResult.errors });
      } else {
        writeRawFile(folders.accepted, 'validation-' + file.getName(), rawText);
      }
      file.setTrashed(true);
      return;
    }

    var result = validateBundle(parsed, { nowMs: nowMs });
    if (!result.ok) {
      writeJsonFile(folders.rejected, file.getName() + '.rejected.json', { errors: result.errors });
      recordRun(ss, parsed, 'rejected', result.errors.join('; '), nowIso);
      file.setTrashed(true);
      return;
    }
    writeRawFile(folders.accepted, file.getName(), rawText);
    recordRun(ss, parsed, 'accepted', '', nowIso);
    file.setTrashed(true);
  });
}

function listAcceptedDigestCandidates(folders) {
  var files = folders.accepted.getFiles();
  var candidates = [];
  while (files.hasNext()) {
    var f = files.next();
    var name = f.getName();
    if (name.indexOf('validation-') === 0 || !name.toLowerCase().endsWith('.json')) continue;
    var rawText;
    try { rawText = readRawFile(f); } catch (e) { continue; }
    var bundle;
    try { bundle = JSON.parse(rawText); } catch (e) { continue; }
    if (!bundle || bundle.kind !== 'digest') continue;
    candidates.push({ bundle: bundle, sha256: sha256Hex(rawText) });
  }
  return candidates;
}

function listAcceptedAttestations(folders) {
  var files = folders.accepted.getFiles();
  var attestations = [];
  while (files.hasNext()) {
    var f = files.next();
    if (f.getName().indexOf('validation-') !== 0) continue;
    var rawText;
    try { rawText = readRawFile(f); } catch (e) { continue; }
    var att;
    try { att = JSON.parse(rawText); } catch (e) { continue; }
    if (att && att.kind === 'validation') attestations.push(att);
  }
  return attestations;
}

function findApprovedAttestation(attestations, runId, sha256) {
  return attestations.filter(function (a) {
    return attestationApprovesCandidate(a, runId, sha256);
  })[0] || null;
}

function buildCandidateDescriptors(digestCandidates, attestations, deliveredIds) {
  return digestCandidates.map(function (c) {
    var freshItems = filterUndeliveredItems(c.bundle.items, deliveredIds);
    var approvedAtt = findApprovedAttestation(attestations, c.bundle.run_id, c.sha256);
    return { bundle: c.bundle, freshItems: freshItems,
      approved: !!approvedAtt && approvedAtt.validator !== c.bundle.producer && freshItems.length === c.bundle.items.length,
      sha256: c.sha256 };
  });
}

function sendDigestEmail(bundleView, isTest) {
  var ss = SpreadsheetApp.openById(getProp(PROP.SHEET_ID));
  var recipient = getOwnerEmail();
  var deliveryKey = bundleView.edition_date + '-' + Utilities.getUuid().slice(0, 8);
  var subject = buildDigestSubject(bundleView.edition_date, isTest, deliveryKey, bundleView.newsletter);
  var nowIso = new Date().toISOString();

  // Durable outbox write BEFORE the send attempt, per contract — flushed to
  // the Sheet (appendRow commits synchronously) before GmailApp is called.
  var outbox = buildOutboxRecord(bundleView, recipient, subject, isTest, deliveryKey, nowIso);
  recordDelivery(ss, outbox);
  SpreadsheetApp.flush();

  var threw = false;
  var errorMessage = '';
  try {
    sendRadarEmail(recipient, subject, buildDigestText(bundleView), {
      htmlBody: buildDigestHtml(bundleView),
      name: newsletterName(bundleView.newsletter)
    });
  } catch (e) {
    threw = true;
    errorMessage = String(e && e.message ? e.message : e);
  }

  var outcome = classifySendOutcome(threw, errorMessage);
  recordDelivery(ss, {
    edition_date: bundleView.edition_date,
    run_id: bundleView.run_id,
    recipient: recipient,
    subject: subject,
    item_ids: outbox.item_ids,
    delivery_key: deliveryKey,
    status: outcome,
    is_test: !!isTest,
    created_at: nowIso,
    updated_at: new Date().toISOString(),
    newsletter: bundleView.newsletter || 'product'
  });

  return { outcome: outcome, deliveryKey: deliveryKey };
}

/** Logged at most once per India calendar day (LAST_MISSING_LOGGED_DATE
 * gates it) so a persistently-missing candidate doesn't spam Runs or imply
 * repeated failure — the absence itself is the fact worth recording once. */
function logMissingCandidateOnce(ss, editionDate, nowIso, newsletter) {
  var missingKey = newsletterProperty(PROP.LAST_MISSING_LOGGED_DATE, newsletter);
  if (getProp(missingKey) === editionDate) return;
  recordRun(ss, {
    run_id: 'missing-' + (newsletter === 'academic' ? 'academic-' : '') + editionDate,
    producer: 'system',
    model_id: 'n/a',
    edition_date: editionDate,
    generated_at: nowIso,
    items: []
  }, 'missing_candidate', 'no validator-approved candidate with >= ' + MIN_ITEMS + ' undelivered items for ' + editionDate, nowIso);
  setProp(missingKey, editionDate);
}

function exportSnapshot(folders, ss) {
  var itemRows = getSheetRows(ss.getSheetByName('Items'), 'Items');
  var items = itemRows.map(reconstructSnapshotItem);

  var ratingsSheet = ss.getSheetByName('CurrentRatings');
  var ratingsLastRow = ratingsSheet.getLastRow();
  var ratings = {};
  if (ratingsLastRow >= 2) {
    var ratingValues = ratingsSheet.getRange(2, 1, ratingsLastRow - 1, SHEET_SCHEMAS.CurrentRatings.length).getValues();
    ratingValues.forEach(function (row) {
      ratings[row[0]] = { score: row[1], reason: row[2], revision: row[3] };
    });
  }

  // Digests are full accepted bundle objects (not bare run_ids) so a vault
  // sync can render/inspect a past edition without a second round trip.
  var digestFiles = folders.accepted.getFiles();
  var digests = [];
  while (digestFiles.hasNext()) {
    var f = digestFiles.next();
    if (f.getName().indexOf('validation-') === 0) continue;
    var raw;
    try { raw = readRawFile(f); } catch (e) { continue; }
    var parsed;
    try { parsed = JSON.parse(raw); } catch (e) { continue; }
    if (parsed && parsed.kind === 'digest') digests.push(parsed);
  }

  var nowIso = new Date().toISOString();
  if (typeof RADAR_PREVIEW !== 'undefined' && getProp('PREVIEW_SENT_RUN') === RADAR_PREVIEW.run_id) {
    digests.push(RADAR_PREVIEW);
  }
  if (typeof RADAR_ACADEMIC_PREVIEW !== 'undefined' && getProp('PREVIEW_SENT_RUN_ACADEMIC') === RADAR_ACADEMIC_PREVIEW.run_id) {
    digests.push(RADAR_ACADEMIC_PREVIEW);
  }
  var snapshot = buildSnapshotJson(items, digests, ratings, getStateRevision(), nowIso);
  writeJsonFile(folders.snapshots, 'snapshot.json', snapshot);
  var prefs = derivePreferences(Object.keys(ratings).map(function(id) {
    return Object.assign({item_id:id},ratings[id]);
  }), getItemsById(ss));
  prefs.ratings = ratings;
  prefs.delivered_item_ids = items.filter(function(item){return !!item.first_delivered_edition_date;}).map(function(item){return item.item_id;});
  writeJsonFile(folders.snapshots, 'preferences.json', prefs);
}

/**
 * Main scheduled entry point. Idempotent and safe to run on any interval:
 * it ingests inbox/ and feedback/ every tick, but only ever sends mail once
 * per India calendar day, never before 17:00 Asia/Kolkata, and never sends
 * a candidate whose edition_date isn't today or that lacks a matching
 * validator-approved attestation.
 */
function dispatchRadar() {
  try {
    dispatchRadarWork();
    writeJsonFile(resolveFolderById(PROP.FOLDER_ROOT), 'runtime-status.json', {checked_at:new Date().toISOString(),status:'ok'});
  } catch (e) {
    try { writeJsonFile(resolveFolderById(PROP.FOLDER_ROOT), 'runtime-status.json', {checked_at:new Date().toISOString(),status:'error',message:String(e)}); } catch (ignored) {}
    throw e;
  }
}

function dispatchRadarWork() {
  withScriptLock(function () {
    var folders = getOrCreateDriveTree();
    var ss = SpreadsheetApp.openById(getProp(PROP.SHEET_ID) || getOrCreateSpreadsheet(folders.root).getId());
    var now = new Date();
    var nowIso = now.toISOString();
    var nowMs = now.getTime();

    if (typeof sendConfiguredPreview === 'function') sendConfiguredPreview(folders, ss, nowIso);
    ingestInboxFiles(folders, ss, nowIso, nowMs);
    ingestFeedbackFiles(folders, ss, nowIso);
    rebuildRatingsProjection(ss);

    var todayEditionDate = istDateString(now);
    var deliveredIds = getDeliveredItemIds(ss.getSheetByName('Items'));
    var digestCandidates = listAcceptedDigestCandidates(folders);
    var attestations = listAcceptedAttestations(folders);
    NEWSLETTERS.forEach(function(newsletter) {
      // Re-read delivered IDs after each channel to avoid cross-mailer repeats.
      var descriptors = buildCandidateDescriptors(digestCandidates.filter(function(c) {
        return (c.bundle.newsletter || 'product') === newsletter;
      }), attestations, getDeliveredItemIds(ss.getSheetByName('Items')));
      var winner = selectDeliverableCandidate(descriptors, todayEditionDate);
      var lastKey = newsletterProperty(PROP.LAST_DELIVERED_EDITION_DATE, newsletter);
      var due = isDueForDispatch(now, getProp(lastKey)).due
        && !hasBlockingDeliveryForEdition(ss, todayEditionDate, newsletter);
      if (due && winner) {
        var view = Object.assign({}, winner.bundle, {items: winner.freshItems});
        var result = sendDigestEmail(view, false);
        if (result.outcome === 'sent') {
          recordItems(ss, view, nowIso);
          setProp(lastKey, todayEditionDate);
          bumpStateRevision();
        }
      } else if (due && !winner) {
        logMissingCandidateOnce(ss, todayEditionDate, nowIso, newsletter);
      }
    });

    exportSnapshot(folders, ss);
  });
}

/**
 * Manual/test send only. Always labeled [TEST], always logged with
 * is_test=true, and never updates LAST_DELIVERED_EDITION_DATE or Items — so
 * it can never mark a regular edition as delivered or suppress a future
 * real item as already-sent.
 */
function sendTestDigest() {
  getOrCreateDriveTree();
  var testBundle = {
    schema_version: SCHEMA_VERSION,
    run_id: 'test-send-' + Utilities.getUuid().slice(0, 8),
    edition_date: istDateString(new Date()),
    generated_at: new Date().toISOString(),
    producer: 'fable',
    model_id: 'test-fixture',
    kind: 'digest',
    items: buildTestItems()
  };
  return sendDigestEmail(testBundle, true).outcome;
}

function buildTestItems() {
  var items = [];
  for (var i = 0; i < MIN_ITEMS; i++) {
    var url = 'https://example.com/radar-test-item-' + i;
    items.push({
      item_id: stableItemId(url),
      title: 'Test digest item ' + (i + 1),
      source_url: url,
      published_at: istDateString(new Date()),
      source_type: 'tool',
      summary: 'This is a test send used only to confirm delivery.',
      why_it_matters: 'Confirms the gateway can reach the configured recipient.',
      evidence_label: 'test fixture',
      repository: 'ai-product-radar',
      guidance: ['n/a', 'n/a', 'n/a', 'n/a', 'n/a'],
      topics: ['test']
    });
  }
  return items;
}

/** Appends the raw event row and fully rebuilds CurrentRatings/Preferences
 * from the whole RatingEvents journal (see replayRatingEvents) so a crash
 * between the two steps always self-heals on the next call — nothing here
 * short-circuits because "this event_id was already seen". */
function persistAndReplay(ss, event) {
  var eventsSheet = ss.getSheetByName('RatingEvents');
  var alreadyRecorded = getSheetRows(eventsSheet, 'RatingEvents').some(function(row) {
    return row.event_id === event.event_id && ratingPayloadEquals(row, event);
  });
  if (alreadyRecorded) {
    rebuildRatingsProjection(ss);
    return;
  }
  var nowIso = new Date().toISOString();
  appendRow(eventsSheet, 'RatingEvents', {
    event_id: event.event_id, item_id: event.item_id, score: event.score, reason: event.reason || '',
    origin: event.origin, base_revision: event.base_revision, created_at: event.created_at,
    status: 'recorded', recorded_at: nowIso
  });
  rebuildRatingsProjection(ss);
}

function rebuildRatingsProjection(ss) {
  var eventsSheet = ss.getSheetByName('RatingEvents');
  var eventRows = getSheetRows(eventsSheet, 'RatingEvents');
  var knownItemIds = getKnownItemIdSet(ss);
  var replay = replayRatingEvents(eventRows, knownItemIds);

  // Correct every journal row's status to what deterministic replay says it
  // is, so re-running this never drifts from what CurrentRatings reflects.
  eventRows.forEach(function (row) {
    var status = replay.eventStatuses[row.event_id];
    if (status !== undefined && status !== row.status) {
      eventsSheet.getRange(row._row, 8, 1, 1).setValues([[status]]);
    }
  });

  var ratingsSheet = ss.getSheetByName('CurrentRatings');
  var lastRow = ratingsSheet.getLastRow();
  if (lastRow >= 2) {
    ratingsSheet.getRange(2, 1, lastRow - 1, SHEET_SCHEMAS.CurrentRatings.length).clearContent();
  }
  var itemIds = Object.keys(replay.currentRatings).sort();
  itemIds.forEach(function (itemId) {
    var r = replay.currentRatings[itemId];
    appendRow(ratingsSheet, 'CurrentRatings', {
      item_id: r.item_id, score: r.score, reason: r.reason, revision: r.revision,
      last_event_id: r.last_event_id, updated_at: r.updated_at
    });
  });

  var itemsById = getItemsById(ss);
  var prefs = derivePreferences(itemIds.map(function (id) { return replay.currentRatings[id]; }), itemsById);
  upsertPreferencesRow(ss, prefs, new Date().toISOString());
  bumpStateRevision();
  return replay;
}

function upsertPreferencesRow(ss, prefs, nowIso) {
  var sheet = ss.getSheetByName('Preferences');
  var rows = getSheetRows(sheet, 'Preferences');
  var existing = rows.filter(function (r) { return r.key === 'current'; })[0] || null;
  var value = JSON.stringify(prefs);
  if (existing) {
    sheet.getRange(existing._row, 1, 1, SHEET_SCHEMAS.Preferences.length).setValues([['current', value, nowIso]]);
  } else {
    appendRow(sheet, 'Preferences', { key: 'current', value: value, updated_at: nowIso });
  }
}

/** Single event entry point shared by the Form trigger, Gmail reply
 * processing, and feedback-folder ingestion. Unknown item_ids are rejected
 * (recorded, never applied) rather than silently accepted. */
function applyRatingEvent(ss, event) {
  if (!isKnownItemId(ss, event.item_id)) {
    var eventsSheet = ss.getSheetByName('RatingEvents');
    appendRow(eventsSheet, 'RatingEvents', {
      event_id: event.event_id, item_id: event.item_id, score: event.score, reason: event.reason || '',
      origin: event.origin, base_revision: event.base_revision, created_at: event.created_at,
      status: 'error:unknown_item', recorded_at: new Date().toISOString()
    });
    return;
  }
  persistAndReplay(ss, event);
}

/** Ingests {schema_version:1, kind:"ratings", events:[...]} bundles from
 * feedback/ under the same ScriptLock as the rest of dispatchRadar (there is
 * no separate lock for feedback). Each event must already carry an explicit
 * base_revision from its origin (email/form/chat/obsidian) — this ingestion
 * path never invents one. Files are trashed only after every event in them
 * has been persisted. */
function ingestFeedbackFiles(folders, ss, nowIso) {
  var files = folders.feedback.getFiles();
  var fileList = [];
  while (files.hasNext()) {
    var f = files.next();
    if (f.getName().toLowerCase().endsWith('.json')) fileList.push(f);
  }
  var touchedAny = false;
  var knownItemIds = getKnownItemIdSet(ss);
  var eventsSheet = ss.getSheetByName('RatingEvents');
  fileList.forEach(function (file) {
    var rawText;
    try {
      rawText = readRawFile(file);
    } catch (e) {
      file.setTrashed(true);
      return;
    }
    var parsed;
    try {
      parsed = JSON.parse(rawText);
    } catch (e) {
      file.setTrashed(true);
      return;
    }
    if (!parsed || parsed.kind !== 'ratings' || !Array.isArray(parsed.events)) {
      file.setTrashed(true);
      return;
    }
    parsed.events.forEach(function (rawEvent) {
      if (typeof rawEvent !== 'object' || rawEvent === null) return;
      var itemId = rawEvent.item_id;
      if (!knownItemIds.has(itemId)) {
        appendRow(eventsSheet, 'RatingEvents', {
          event_id: rawEvent.event_id || deterministicUuidFromString(file.getName() + '#' + JSON.stringify(rawEvent)),
          item_id: itemId, score: rawEvent.score, reason: rawEvent.reason || '',
          origin: rawEvent.origin, base_revision: rawEvent.base_revision, created_at: rawEvent.created_at,
          status: 'error:unknown_item', recorded_at: new Date().toISOString()
        });
        return;
      }
      appendRow(eventsSheet, 'RatingEvents', {
        event_id: rawEvent.event_id, item_id: rawEvent.item_id, score: rawEvent.score,
        reason: rawEvent.reason || '', origin: rawEvent.origin, base_revision: rawEvent.base_revision,
        created_at: rawEvent.created_at, status: 'recorded', recorded_at: new Date().toISOString()
      });
      touchedAny = true;
    });
    file.setTrashed(true);
  });
  if (touchedAny) rebuildRatingsProjection(ss);
}

/**
 * Installable Form submit trigger. Discards any response not collected from
 * the configured owner email; never widens ratings beyond that address.
 * base_revision is read from the Form's own "known index" answer (index 2)
 * rather than computed fresh, so a submission always binds the revision the
 * rater actually saw.
 */
function onFormSubmit(e) {
  withScriptLock(function () {
    var respondentEmail = e.response.getRespondentEmail();
    var ownerEmail = getOwnerEmail();
    if (!respondentEmail || respondentEmail.trim().toLowerCase() !== ownerEmail.trim().toLowerCase()) {
      return; // Not the configured owner — ignore silently, no state mutation.
    }
    var ss = SpreadsheetApp.openById(getProp(PROP.SHEET_ID));
    var answers = e.response.getItemResponses();
    var itemId = answers[0] ? String(answers[0].getResponse()).trim() : '';
    var score = answers[1] ? Number(answers[1].getResponse()) : NaN;
    var baseRevision = answers[2] ? Number(answers[2].getResponse()) : NaN;
    var reason = answers[3] ? String(answers[3].getResponse()).trim() : '';

    var event = {
      event_id: deterministicUuidFromString('form:' + e.response.getId()),
      item_id: itemId,
      score: score,
      reason: reason || undefined,
      origin: 'form',
      base_revision: baseRevision,
      created_at: e.response.getTimestamp().toISOString()
    };
    applyRatingEvent(ss, event);
  });
}

/** Ignore quoted originals so copying an email never submits its instructions
 * as the owner's feedback. Missing or invalid commands leave ratings unchanged. */
function replyCommandLines(body) {
  var lines = String(body || '').split(/\r?\n/), result = [];
  for (var i = 0; i < lines.length; i++) {
    if (/^\s*>/.test(lines[i]) || /^\s*On .+wrote:\s*$/i.test(lines[i]) || /^\s*-{2,}\s*(Original Message|Forwarded message)/i.test(lines[i])) break;
    var command = parseRateCommand(lines[i]);
    if (command) result.push({command: command, lineIndex: i});
  }
  return result;
}

/** Reads actual replies in issued newsletter threads. Deterministic event IDs
 * make re-reading safe; opening an email must not prevent feedback import. */
function processGmailReplies() {
  withScriptLock(function () {
    var ownerEmail = getOwnerEmail();
    var ss = SpreadsheetApp.openById(getProp(PROP.SHEET_ID));
    var deliveredSubjects = {};
    getSheetRows(ss.getSheetByName('Deliveries'), 'Deliveries').forEach(function(row) {
      if (row.status === 'sent' || row.status === 'uncertain') deliveredSubjects[row.subject] = true;
    });
    var threads = readRadarThreads('from:' + ownerEmail + ' newer_than:30d {subject:"AI Product Radar" subject:"AI Research Radar"}');
    var commandCount = 0;
    threads.forEach(function (thread) {
      var messages = thread.getMessages();
      var issued = messages.some(function(message) { return !!deliveredSubjects[message.getSubject()]; });
      if (!issued) return;
      messages.forEach(function (message) {
        if (!isAuthorizedSender(message.getFrom(), ownerEmail) || !message.getHeader('In-Reply-To')) return;
        var messageId = message.getId();
        replyCommandLines(message.getPlainBody()).forEach(function (entry) {
          commandCount += 1;
          var cmd = entry.command;
          applyRatingEvent(ss, {
            event_id: deterministicUuidFromString('email:' + messageId + '#' + entry.lineIndex),
            item_id: cmd.item_id,
            score: cmd.score,
            reason: cmd.reason,
            origin: 'email',
            base_revision: cmd.base_revision,
            created_at: message.getDate().toISOString()
          });
        });
      });
    });
    writeJsonFile(resolveFolderById(PROP.FOLDER_ROOT), 'reply-status.json', {
      checked_at: new Date().toISOString(), status: 'ok', threads_scanned: threads.length,
      rating_commands_examined: commandCount
    });
  });
}

/**
 * Manual-only reconciliation for deliveries left "uncertain" by sendDigestEmail.
 * Never auto-invoked by a trigger — the contract requires a human to confirm
 * outcome (e.g. by checking the Gmail Sent folder for the delivery_key
 * subject token) before this is run.
 */
function reconcileUncertainDeliveries() {
  var ss = SpreadsheetApp.openById(getProp(PROP.SHEET_ID));
  var sheet = ss.getSheetByName('Deliveries');
  var rows = getSheetRows(sheet, 'Deliveries');
  return rows.filter(function (r) { return r.status === 'uncertain'; });
}
