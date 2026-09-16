/* Advanced Gmail API transport. Requires only the gmail.modify service grant. */

function _gmailHeaderSafe(value, field) {
  if (typeof value !== 'string' || !value.trim()) throw new Error(field + ' must be non-empty');
  if (/[\r\n]/.test(value)) throw new Error(field + ' must not contain CRLF');
  return value.trim();
}

function _utf8Base64Url(value) {
  var bytes = Utilities.newBlob(String(value)).getBytes();
  return Utilities.base64EncodeWebSafe(bytes).replace(/=+$/, '');
}

function _encodedWord(value) {
  var codepoints = Array.from(String(value));
  var words = [];
  for (var i = 0; i < codepoints.length; i += 10) {
    var chunk = codepoints.slice(i, i + 10).join('');
    var bytes = Utilities.newBlob(chunk).getBytes();
    words.push('=?UTF-8?B?' + Utilities.base64Encode(bytes) + '?=');
  }
  return words.join('\r\n ');
}

function _mimeBody(value, type, boundary) {
  return '--' + boundary + '\r\n' +
    'Content-Type: ' + type + '; charset=UTF-8\r\n' +
    'Content-Transfer-Encoding: 8bit\r\n\r\n' + String(value) + '\r\n';
}

function sendRadarEmail(recipient, subject, plain, opts) {
  opts = opts || {};
  recipient = _gmailHeaderSafe(recipient, 'recipient');
  if (typeof OWNER_EMAIL_DEFAULT !== 'string' || recipient !== OWNER_EMAIL_DEFAULT) {
    throw new Error('recipient must equal OWNER_EMAIL_DEFAULT');
  }
  subject = _gmailHeaderSafe(subject, 'subject');
  plain = String(plain == null ? '' : plain);
  var name = opts.name == null ? '' : _gmailHeaderSafe(String(opts.name), 'name');
  var html = opts.htmlBody == null ? '' : String(opts.htmlBody);
  var boundary = '=_Radar_' + Utilities.getUuid().replace(/-/g, '');
  var headers = [
    'To: ' + recipient,
    'Subject: ' + _encodedWord(subject),
    'MIME-Version: 1.0',
    'Content-Type: multipart/alternative; boundary="' + boundary + '"'
  ];
  if (name) headers.splice(1, 0, 'From: ' + _encodedWord(name) + ' <' + recipient + '>');
  var raw = headers.join('\r\n') + '\r\n\r\n' +
    _mimeBody(plain, 'text/plain', boundary) +
    (html ? _mimeBody(html, 'text/html', boundary) : '') +
    '--' + boundary + '--\r\n';
  return Gmail.Users.Messages.send({raw: _utf8Base64Url(raw)}, 'me');
}

function _decodePlainPart(part) {
  if (!part) return '';
  if (part.mimeType === 'text/plain' && part.body && part.body.data) {
    var bytes = Utilities.base64DecodeWebSafe(part.body.data);
    return Utilities.newBlob(bytes).getDataAsString('UTF-8');
  }
  var children = part.parts || [];
  for (var i = 0; i < children.length; i++) {
    var found = _decodePlainPart(children[i]);
    if (found) return found;
  }
  return '';
}

function _header(message, name) {
  var headers = (message.payload && message.payload.headers) || [];
  var wanted = String(name).toLowerCase();
  for (var i = 0; i < headers.length; i++) {
    if (String(headers[i].name).toLowerCase() === wanted) {
      var value = String(headers[i].value || '').replace(/(\?=)[ \t\r\n]+(=\?)/g, '$1$2');
      return value.replace(/=\?UTF-8\?B\?([A-Za-z0-9+/=]+)\?=/gi, function(_, encoded) {
        try {
          return Utilities.newBlob(Utilities.base64Decode(encoded)).getDataAsString('UTF-8');
        } catch (error) {
          return _;
        }
      });
    }
  }
  return '';
}

function _messageWrapper(message) {
  var internal = Number(message.internalDate || 0);
  return {
    getId: function() { return String(message.id || ''); },
    getSubject: function() { return _header(message, 'Subject'); },
    getFrom: function() { return _header(message, 'From'); },
    getHeader: function(name) { return _header(message, name); },
    getPlainBody: function() { return _decodePlainPart(message.payload); },
    getDate: function() { return new Date(internal); }
  };
}

function readRadarThreads(query) {
  query = _gmailHeaderSafe(query, 'query');
  var listed = Gmail.Users.Threads.list('me', {q: query, maxResults: 50}) || {};
  return (listed.threads || []).map(function(entry) {
    var thread = Gmail.Users.Threads.get('me', String(entry.id), {format: 'full'});
    var messages = (thread.messages || []).map(_messageWrapper);
    return {getMessages: function() { return messages.slice(); }};
  });
}
