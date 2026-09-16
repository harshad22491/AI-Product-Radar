# Google email and rating gateway

This is the cloud delivery component. It does not call a paid model API. Fable researches and a separate allowed reviewer writes a hash-matched attestation before a daily edition can be sent.

## Deploy

Use the authenticated Google `clasp` CLI. Stage only `Code.js`, `GmailTransport.js`, `Activate.js`, `appsscript.json`, and the generated local `DeploymentConfig.js` (plus optional `Preview.js`). Never upload credentials, tests or the repository wholesale.

`DeploymentConfig.js` contains `RADAR_DEPLOYMENT_CONFIG`, generated from ignored `deployment.local.json`. Configure the existing private folder IDs and canonical Sheet ID, with the fixed recipient harshad422@gmail.com. The script refuses a different recipient.

The manifest enables the Advanced Gmail service v1. This deliberately uses `gmail.modify`, the permission authorized for the application, rather than the broader GmailApp scope. The default Apps Script Google project enables advanced services through the manifest.

Publish the web application with access MYSELF and executeAs USER_ACCESSING. The owner opens it and completes Google's authorization. `activateRadar()` checks the owner and existing configuration, provisions the database headers, installs the triggers, and writes `activation-status.json` into the private project folder. Reopening the page replaces this project's triggers rather than duplicating them. No Form is required for email ratings.

- `dispatchRadar`: every five minutes; ordinary delivery never before 17:00 Asia/Kolkata.
- `processGmailReplies`: every fifteen minutes.
- Optional `onFormSubmit`: only installed if a Form exists.

After changes, push the source, update the private deployment, reopen the owner activation page, and verify fresh runtime and reply-scan records.

## Delivery and feedback rules

Candidates need seven items and at least one `user_facing_ai: true` item with a concrete `application_example`. The five guidance entries remain a positional string array. Primary-source facts and proposed applications are reviewed separately; passing JSON checks is not factual verification.

A matching attestation must name Sol/gpt-5.6-sol or Opus/claude-opus-5 and the SHA-256 of the exact original candidate bytes. A producer cannot approve its own bundle. Repeated/partial candidates are not silently trimmed after approval.

Before sending, a claimed delivery record is flushed to the Sheet. Unknown send outcomes remain blocked for manual reconciliation. Check the exact subject/delivery key in Gmail before retrying. Never delete a claim just to force another send.

The top legend explains ratings. Each item gives a copyable command with a SCORE placeholder. The reply reader accepts only owner replies in known newsletter threads, ignores quoted originals, and does not mark mail read. Event IDs and revisions make replay safe. The journal reconstructs one current rating per item.

An optional reviewed `RADAR_PREVIEW` is sent once as [TEST]. Its items can be rated, but the preview does not claim a daily edition or suppress items from a regular delivery. The next dispatcher run recovers item registration if sending succeeded before an interruption.

`runtime-status.json` records the latest dispatcher success or error. `reply-status.json` records the latest reply scan and command count. `snapshot.json` and `preferences.json` are the exchange for Obsidian and research. Preview records have no first-delivered date; producers must use the delivered-item list rather than assuming every snapshot item was sent in a regular edition.

## Tests

Run the four Node suites listed in the main README and the Python suite. These tests do not substitute for checking the live delivery ledger, received email and a real rating reply. See `docs/VERIFICATION.md`.
