'use strict';

const http = require('http');
const https = require('https');
const tls = require('tls');
const { URL } = require('url');

const HOST = '127.0.0.1';
const PORT = 4242;

const PROXY_ALLOWLIST = new Set([
  'calendar.google.com',
  'www.google.com',
  'news.google.com',
]);

const IMAP_ALLOWLIST = new Set(['imap.gmail.com']);

const BROWSER_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

let tagCounter = 0;

function nextTag() {
  tagCounter += 1;
  return 'A' + String(tagCounter).padStart(3, '0');
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    ...CORS_HEADERS,
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

function sendText(res, status, text, contentType) {
  res.writeHead(status, {
    ...CORS_HEADERS,
    'Content-Type': contentType || 'text/plain; charset=utf-8',
    'Content-Length': Buffer.byteLength(text),
  });
  res.end(text);
}

function maskSecrets(text) {
  if (typeof text !== 'string') return text;
  return text.replace(/"senhaApp"\s*:\s*"[^"]*"/gi, '"senhaApp":"***"');
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function hostnameAllowed(hostname) {
  return PROXY_ALLOWLIST.has(String(hostname || '').toLowerCase());
}

function fetchProxy(targetUrl, redirectCount) {
  return new Promise((resolve, reject) => {
    let parsed;
    try {
      parsed = new URL(targetUrl);
    } catch (err) {
      reject(new Error('URL inválida'));
      return;
    }

    if (parsed.protocol !== 'https:') {
      reject(new Error('Apenas HTTPS é permitido'));
      return;
    }

    if (!hostnameAllowed(parsed.hostname)) {
      reject(new Error('Host não permitido'));
      return;
    }

    const options = {
      hostname: parsed.hostname,
      port: parsed.port || 443,
      path: parsed.pathname + parsed.search,
      method: 'GET',
      headers: {
        'User-Agent': BROWSER_UA,
        Accept: '*/*',
      },
    };

    const req = https.request(options, (res) => {
      const status = res.statusCode || 0;
      const location = res.headers.location;

      if (
        redirectCount < 3 &&
        location &&
        [301, 302, 303, 307, 308].includes(status)
      ) {
        res.resume();
        let nextUrl;
        try {
          nextUrl = new URL(location, targetUrl).href;
        } catch (err) {
          reject(new Error('Redirecionamento inválido'));
          return;
        }
        fetchProxy(nextUrl, redirectCount + 1).then(resolve).catch(reject);
        return;
      }

      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        resolve({
          status,
          headers: res.headers,
          body: Buffer.concat(chunks),
        });
      });
    });

    req.on('error', reject);
    req.end();
  });
}

function decodeMimeWords(str) {
  if (!str) return '';
  return String(str).replace(
    /=\?([^?]+)\?([BbQq])\?([^?]*)\?=/g,
    (_, charset, encoding, text) => {
      const cs = charset.toLowerCase();
      try {
        if (encoding.toUpperCase() === 'B') {
          return Buffer.from(text, 'base64').toString(
            cs === 'utf-8' || cs === 'utf8' ? 'utf8' : 'latin1'
          );
        }
        const qp = text
          .replace(/_/g, ' ')
          .replace(/=([0-9A-Fa-f]{2})/g, (_, hex) =>
            String.fromCharCode(parseInt(hex, 16))
          );
        return Buffer.from(qp, 'binary').toString(
          cs === 'utf-8' || cs === 'utf8' ? 'utf8' : 'latin1'
        );
      } catch {
        return text;
      }
    }
  );
}

function decodeQuotedPrintable(input) {
  return String(input || '')
    .replace(/=\r?\n/g, '')
    .replace(/=([0-9A-Fa-f]{2})/g, (_, hex) =>
      String.fromCharCode(parseInt(hex, 16))
    );
}

function decodeBodySnippet(raw) {
  if (!raw) return '';
  let text = String(raw);

  const boundaryMatch = text.match(/boundary="?([^"\r\n;]+)"?/i);
  if (boundaryMatch) {
    const boundary = boundaryMatch[1];
    const parts = text.split('--' + boundary);
    for (const part of parts) {
      if (/Content-Type:\s*text\/plain/i.test(part)) {
        text = part;
        break;
      }
      if (/Content-Type:\s*text\/html/i.test(part) && !/text\/plain/i.test(text)) {
        text = part;
      }
    }
  }

  const split = text.split(/\r?\n\r?\n/);
  if (split.length > 1) {
    text = split.slice(1).join('\n\n');
  }

  text = text.replace(/<[^>]+>/g, ' ');

  if (/Content-Transfer-Encoding:\s*base64/i.test(raw)) {
    const b64 = text.replace(/\s+/g, '');
    try {
      text = Buffer.from(b64, 'base64').toString('utf8');
    } catch {
      /* keep original */
    }
  } else if (/Content-Transfer-Encoding:\s*quoted-printable/i.test(raw)) {
    text = decodeQuotedPrintable(text);
  }

  text = text.replace(/\s+/g, ' ').trim();
  if (text.length > 500) text = text.slice(0, 500);
  return text;
}

function parseHeaderBlock(block) {
  const headers = {};
  const lines = String(block || '').split(/\r?\n/);
  let currentKey = '';
  for (const line of lines) {
    if (/^\s/.test(line) && currentKey) {
      headers[currentKey] += ' ' + line.trim();
      continue;
    }
    const idx = line.indexOf(':');
    if (idx === -1) continue;
    currentKey = line.slice(0, idx).trim().toLowerCase();
    headers[currentKey] = line.slice(idx + 1).trim();
  }
  return headers;
}

function parseFetchResponse(raw) {
  const result = { id: '', flags: [], headerBlock: '', bodyText: '' };

  const uidMatch = raw.match(/UID\s+(\d+)/i);
  if (uidMatch) result.id = uidMatch[1];

  const seqMatch = raw.match(/^[\s\S]*?\*\s+(\d+)\s+FETCH/i);
  if (!result.id && seqMatch) result.id = seqMatch[1];

  const flagsMatch = raw.match(/FLAGS\s*\(([^)]*)\)/i);
  if (flagsMatch) {
    result.flags = flagsMatch[1]
      .split(/\s+/)
      .map((f) => f.replace(/\\/g, '').trim())
      .filter(Boolean);
  }

  const headerMatch = raw.match(
    /BODY\[HEADER\.FIELDS[^\]]*\]\s*\{(\d+)\}\r?\n([\s\S]*?)(?=\)|BODY\[)/i
  );
  if (headerMatch) {
    result.headerBlock = headerMatch[2].slice(0, parseInt(headerMatch[1], 10));
  } else {
    const altHeader = raw.match(
      /HEADER\.FIELDS[^\]]*\]\s*\{(\d+)\}\r?\n([\s\S]*?)(?=\)|BODY\[)/i
    );
    if (altHeader) {
      result.headerBlock = altHeader[2].slice(0, parseInt(altHeader[1], 10));
    }
  }

  const bodyMatch = raw.match(/BODY\[TEXT\]<[^>]*>\]\s*\{(\d+)\}\r?\n([\s\S]*?)\)\s*$/i);
  if (bodyMatch) {
    result.bodyText = bodyMatch[2].slice(0, parseInt(bodyMatch[1], 10));
  } else {
    const altBody = raw.match(/BODY\[TEXT\]\]\s*\{(\d+)\}\r?\n([\s\S]*?)\)\s*$/i);
    if (altBody) {
      result.bodyText = altBody[2].slice(0, parseInt(altBody[1], 10));
    }
  }

  return result;
}

class ImapClient {
  constructor(host, port) {
    this.host = host;
    this.port = port;
    this.socket = null;
    this.buffer = '';
    this.pending = null;
    this.queue = [];
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.socket = tls.connect(
        { host: this.host, port: this.port, servername: this.host },
        () => {
          this._waitGreeting().then(resolve).catch(reject);
        }
      );
      this.socket.setEncoding('utf8');
      this.socket.on('data', (chunk) => this._onData(chunk));
      this.socket.on('error', reject);
      this.socket.on('close', () => {
        if (this.pending) {
          const err = new Error('Conexão IMAP fechada');
          this.pending.reject(err);
          this.pending = null;
        }
      });
    });
  }

  _onData(chunk) {
    this.buffer += chunk;
    this._drainBuffer();
  }

  _drainBuffer() {
    while (this.pending) {
      const { tag, literalExpected, resolve, reject, lines } = this.pending;

      if (literalExpected !== null) {
        const idx = this.buffer.indexOf('\r\n');
        if (idx === -1) return;
        const line = this.buffer.slice(0, idx);
        this.buffer = this.buffer.slice(idx + 2);
        lines.push(line);
        this.pending.literalExpected = null;
        continue;
      }

      while (true) {
        const literalInLine = this.buffer.match(/^(.+)\r\n\{(\d+)\}\r?\n?/);
        if (literalInLine) {
          const linePart = literalInLine[1];
          const size = parseInt(literalInLine[2], 10);
          const afterBrace = this.buffer.indexOf('\r\n') + 2;
          if (this.buffer.length - afterBrace < size) return;
          const literal = this.buffer.slice(afterBrace, afterBrace + size);
          this.buffer = this.buffer.slice(afterBrace + size);
          lines.push(linePart + '\r\n{' + size + '}\r\n' + literal);
          continue;
        }

        const idx = this.buffer.indexOf('\r\n');
        if (idx === -1) return;
        const line = this.buffer.slice(0, idx);
        this.buffer = this.buffer.slice(idx + 2);
        lines.push(line);

        if (line.startsWith('+')) {
          this.pending.literalExpected = true;
          return;
        }

        if (line.startsWith(tag + ' ')) {
          const status = line.split(' ')[1];
          this.pending = null;
          if (status === 'OK') {
            resolve(lines);
          } else {
            reject(new Error(line.slice(tag.length + 2) || 'Erro IMAP'));
          }
          break;
        }
      }

      if (!this.pending) break;
    }

    if (!this.pending && this.queue.length) {
      const next = this.queue.shift();
      this._sendCommand(next.tag, next.command, next.resolve, next.reject);
    }
  }

  _waitGreeting() {
    return new Promise((resolve, reject) => {
      const check = () => {
        const idx = this.buffer.indexOf('\r\n');
        if (idx === -1) {
          this.socket.once('data', check);
          return;
        }
        const line = this.buffer.slice(0, idx);
        this.buffer = this.buffer.slice(idx + 2);
        if (line.startsWith('* OK')) {
          resolve();
        } else {
          reject(new Error('Saudação IMAP inválida'));
        }
      };
      check();
    });
  }

  command(cmd) {
    return new Promise((resolve, reject) => {
      const tag = nextTag();
      if (this.pending) {
        this.queue.push({ tag, command: cmd, resolve, reject });
      } else {
        this._sendCommand(tag, cmd, resolve, reject);
      }
    });
  }

  _sendCommand(tag, cmd, resolve, reject) {
    this.pending = {
      tag,
      lines: [],
      literalExpected: null,
      resolve,
      reject,
    };
    this.socket.write(tag + ' ' + cmd + '\r\n');
  }

  login(user, pass) {
    const esc = (s) => String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    return this.command('LOGIN "' + esc(user) + '" "' + esc(pass) + '"');
  }

  selectInbox() {
    return this.command('SELECT INBOX');
  }

  searchAll() {
    return this.command('SEARCH ALL');
  }

  fetchMessages(ids) {
    if (!ids.length) return Promise.resolve([]);
    const idList = ids.join(',');
    const cmd =
      'UID FETCH ' +
      idList +
      ' (UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] BODY.PEEK[TEXT]<0.500>)';
    return this.command(cmd);
  }

  logout() {
    return this.command('LOGOUT').catch(() => {});
  }

  close() {
    if (this.socket && !this.socket.destroyed) {
      this.socket.end();
      this.socket.destroy();
    }
  }
}

function extractSearchUids(lines) {
  const uids = [];
  for (const line of lines) {
    const match = line.match(/^\*\ SEARCH (.+)$/i);
    if (match && match[1].trim()) {
      const parts = match[1].trim().split(/\s+/);
      for (const p of parts) {
        const n = parseInt(p, 10);
        if (!Number.isNaN(n)) uids.push(n);
      }
    }
  }
  return uids;
}

function extractFetchBlocks(lines) {
  const blocks = [];
  let current = null;
  for (const line of lines) {
    if (/^\*\ \d+ FETCH/i.test(line) || /^\* \d+ FETCH/i.test(line)) {
      if (current) blocks.push(current);
      current = line;
    } else if (current) {
      current += '\r\n' + line;
    }
  }
  if (current) blocks.push(current);
  return blocks;
}

async function fetchEmails(host, user, pass, quantidade) {
  if (!IMAP_ALLOWLIST.has(String(host || '').toLowerCase())) {
    throw new Error('Host IMAP não permitido');
  }

  const qty = Math.max(1, Math.min(parseInt(quantidade, 10) || 10, 100));
  const client = new ImapClient(host, 993);

  try {
    await client.connect();
    await client.login(user, pass);
    await client.selectInbox();
    const searchLines = await client.searchAll();
    const uids = extractSearchUids(searchLines);
    if (!uids.length) return [];

    const selected = uids.slice(-qty);
    const fetchLines = await client.fetchMessages(selected);
    const blocks = extractFetchBlocks(fetchLines);
    const emails = [];

    for (const block of blocks) {
      const parsed = parseFetchResponse(block);
      const headers = parseHeaderBlock(parsed.headerBlock);
      const from = decodeMimeWords(headers.from || '');
      const subject = decodeMimeWords(headers.subject || '(sem assunto)');
      const date = headers.date || '';
      const trecho = decodeBodySnippet(parsed.bodyText);
      const lido = parsed.flags.some(
        (f) => f.toLowerCase() === 'seen' || f === '\\Seen'
      );

      emails.push({
        id: parsed.id || String(selected[emails.length] || ''),
        remetente: from,
        assunto: subject,
        data: date,
        trecho,
        lido,
      });
    }

    emails.sort((a, b) => Number(a.id) - Number(b.id));
    return emails.reverse();
  } finally {
    try {
      await client.logout();
    } catch {
      /* ignore */
    }
    client.close();
  }
}

async function handleProxy(req, res, parsedUrl) {
  const target = parsedUrl.searchParams.get('url');
  if (!target) {
    sendJson(res, 400, { erro: 'Parâmetro url é obrigatório' });
    return;
  }

  try {
    const result = await fetchProxy(target, 0);
    const contentType = result.headers['content-type'] || 'application/octet-stream';
    res.writeHead(result.status, {
      ...CORS_HEADERS,
      'Content-Type': contentType,
      'Content-Length': result.body.length,
    });
    res.end(result.body);
  } catch (err) {
    sendJson(res, 502, { erro: err.message || 'Falha no proxy' });
  }
}

async function handleEmails(req, res) {
  let raw;
  try {
    raw = await readBody(req);
    console.log('[emails] corpo recebido:', maskSecrets(raw));
  } catch {
    sendJson(res, 400, { erro: 'Corpo inválido' });
    return;
  }

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    sendJson(res, 400, { erro: 'JSON inválido' });
    return;
  }

  const { host, usuario, senhaApp, quantidade } = payload;
  if (!host || !usuario || !senhaApp) {
    sendJson(res, 400, { erro: 'host, usuario e senhaApp são obrigatórios' });
    return;
  }

  try {
    const emails = await fetchEmails(host, usuario, senhaApp, quantidade);
    sendJson(res, 200, emails);
  } catch (err) {
    console.error('[emails] erro:', err.message);
    sendJson(res, 502, { erro: err.message || 'Falha ao buscar e-mails' });
  }
}

function handleHealth(res) {
  sendJson(res, 200, { ok: true });
}

const server = http.createServer(async (req, res) => {
  const parsedUrl = new URL(req.url || '/', 'http://' + HOST);

  if (req.method === 'OPTIONS') {
    res.writeHead(204, CORS_HEADERS);
    res.end();
    return;
  }

  try {
    if (req.method === 'GET' && parsedUrl.pathname === '/health') {
      handleHealth(res);
      return;
    }

    if (req.method === 'GET' && parsedUrl.pathname === '/proxy') {
      await handleProxy(req, res, parsedUrl);
      return;
    }

    if (req.method === 'POST' && parsedUrl.pathname === '/emails') {
      await handleEmails(req, res);
      return;
    }

    sendJson(res, 404, { erro: 'Rota não encontrada' });
  } catch (err) {
    console.error('[servidor] erro:', err.message);
    sendJson(res, 500, { erro: 'Erro interno do servidor' });
  }
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(
      'Erro: a porta ' + PORT + ' já está em uso. Encerre o processo anterior e tente novamente.'
    );
    process.exit(1);
  }
  console.error('Erro do servidor:', err.message);
  process.exit(1);
});

server.listen(PORT, HOST, () => {
  console.log(
    'Servidor AURA antenna ativo em http://' + HOST + ':' + PORT
  );
  console.log('Rotas: GET /health, GET /proxy?url=..., POST /emails');
});
