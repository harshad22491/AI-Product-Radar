/** Owner-only activation for the private Apps Script web application.
 * RADAR_DEPLOYMENT_CONFIG is generated locally from deployment.local.json.
 * No API keys, passwords or browser credentials are stored in the script.
 */
function activateRadar() {
  if (Session.getEffectiveUser().getEmail().toLowerCase() !== OWNER_EMAIL_DEFAULT) {
    throw new Error('Only the configured newsletter owner can activate this service.');
  }
  return withScriptLock(function () {
    var config = RADAR_DEPLOYMENT_CONFIG;
    Object.keys(config).forEach(function (key) {
      var existing = getProp(key);
      if (existing && existing !== config[key]) throw new Error('Existing configuration differs for ' + key);
      setProp(key, config[key]);
    });
    getOwnerEmail();
    var folders = getOrCreateDriveTree();
    var ss = getOrCreateSpreadsheet(folders.root);
    // Email reply ratings work independently of a Google Form.
    installRadarTriggers();
    exportSnapshot(folders, ss);
    var status = radarActivationStatus();
    writeJsonFile(folders.root, 'activation-status.json', status);
    return status;
  });
}

function radarActivationStatus() {
  var triggers = ScriptApp.getProjectTriggers().map(function (t) {
    return {handler: t.getHandlerFunction(), id: t.getUniqueId()};
  });
  return {
    schema_version: 1,
    checked_at: new Date().toISOString(),
    owner: getOwnerEmail(),
    reply_ratings_active: triggers.some(function(t) { return t.handler === 'processGmailReplies'; }),
    delivery_dispatcher_active: triggers.some(function(t) { return t.handler === 'dispatchRadar'; }),
    newsletters: ['AI Product Radar', 'AI Research Radar'],
    delivery_time: '17:00 Asia/Kolkata; next Google polling tick, normally within 5 minutes',
    research_and_validation_status: 'independent-provider-run-verification-required',
    triggers: triggers
  };
}

/** One authorized preview, sent once by the real gateway. Its items are
 * ratable without counting as a regular daily edition. */
function sendConfiguredPreview(folders, ss, nowIso) {
  var previews = [];
  if (typeof RADAR_PREVIEW !== 'undefined') previews.push(RADAR_PREVIEW);
  if (typeof RADAR_ACADEMIC_PREVIEW !== 'undefined') previews.push(RADAR_ACADEMIC_PREVIEW);
  previews.forEach(function(preview) {
  var previewKey = newsletterProperty('PREVIEW_SENT_RUN', preview.newsletter);
  if (getProp(previewKey) === preview.run_id) return;
  var rows = getSheetRows(ss.getSheetByName('Deliveries'), 'Deliveries');
  var matches = rows.filter(function(row) { return row.run_id === preview.run_id && row.is_test; });
  var sent = matches.some(function(row) { return row.status === 'sent'; });
  if (!sent && matches.some(function(row) { return BLOCKING_DELIVERY_STATUSES.indexOf(row.status) !== -1; })) return;
  var checked = validateBundle(preview, {nowMs: new Date(nowIso).getTime()});
  if (!checked.ok) throw new Error('Preview validation: ' + checked.errors.join('; '));
  if (!sent) sent = sendDigestEmail(preview, true).outcome === 'sent';
  if (sent) {
    recordItems(ss, preview, nowIso, true);
    setProp(previewKey, preview.run_id);
    bumpStateRevision();
  }
  });
}

function doGet() {
  try {
    var status = activateRadar();
    dispatchRadar();
    processGmailReplies();
    return HtmlService.createHtmlOutput(
      '<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1">'
      + '<body style="font:18px/1.6 system-ui;max-width:720px;margin:40px auto;padding:20px">'
      + '<h1>AI Product Radar: Google service activated</h1>'
      + '<p>The email reply reader and daily delivery checker are installed in your Google account. They continue running when your computer is off.</p>'
      + '<p>The delivery checker starts looking for today\'s approved newsletter at 5 pm India time. It runs every five minutes; Google may start it later.</p>'
      + '<p><strong>Research and independent review are separate:</strong> a newsletter is sent only after both have produced a valid edition. Activating this page alone does not prove those steps are working.</p>'
      + '<p>You can return to this page safely. It replaces this project\'s own triggers instead of adding duplicates.</p>'
      + '<pre style="white-space:pre-wrap;font-size:13px">' + escapeHtml(JSON.stringify(status, null, 2)) + '</pre></body></html>'
    ).setTitle('AI Product Radar activation');
  } catch (e) {
    return HtmlService.createHtmlOutput('<h1>Activation needs attention</h1><pre>' + escapeHtml(String(e)) + '</pre>');
  }
}
