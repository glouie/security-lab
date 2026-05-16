'use strict';

// ── Socket.IO connection ──────────────────────────────────────────────
const socket = io();
let busy = false;

socket.on('connect',       ()  => setStatus('ok'));
socket.on('disconnect',    ()  => setStatus('err'));
socket.on('terminal_line', (d) => appendLine(d.panel, d.line, d.style));
socket.on('execute_done',  ()  => { busy = false; setStatus('ok'); document.getElementById('btn-run').disabled = false; });
socket.on('mitm_capture',  (d) => onMitmCapture(d));
socket.on('reset_done',    ()  => { clearAll(); pollState(); });
socket.on('config_updated',(d) => renderDefenseToggles());
socket.on('server_state',  (d) => renderState(d));

function setStatus(s) {
  const dot = document.getElementById('status-dot');
  dot.className = 'status-dot' + (s === 'ok' ? '' : s === 'busy' ? ' busy' : '');
}

// ── Lessons data (fetched from server) ──────────────────────────────
let LESSONS     = [];
let curLesson   = 0;
let curChapter  = 0;
let curPhase    = 0;
let editMode    = false;
let completed   = {};  // lessonId → set of chapterIds

// ── App bootstrap ──────────────────────────────────────────────────
const App = {

  async init() {
    const r = await fetch('/lessons');
    LESSONS = await r.json();
    this.renderIntro();
  },

  renderIntro() {
    // OSI map
    const osi = [
      { num: 'L7', name: 'Application', attacks: [
          { label: 'Webhook Forgery', sev: 'critical' },
          { label: 'Replay Attack',   sev: 'high'     },
          { label: 'Brute Force',     sev: 'high'     },
      ]},
      { num: 'L5', name: 'TLS/Session', attacks: [
          { label: 'Fake Certificate', sev: 'critical' },
          { label: 'TLS Downgrade',    sev: 'high'     },
      ]},
      { num: 'L4', name: 'Transport (TCP)', attacks: [] },
      { num: 'L3', name: 'Network (IP)', attacks: [] },
      { num: 'L2', name: 'Data Link', attacks: [
          { label: 'ARP Poisoning',   sev: 'critical' },
          { label: 'Packet Sniffing', sev: 'critical' },
      ]},
    ];
    document.getElementById('osi-map').innerHTML = osi.map(row => `
      <div class="osi-row">
        <span class="osi-num">${row.num}</span>
        <span class="osi-name">${row.name}</span>
        <span class="osi-attacks">
          ${row.attacks.map(a =>
            `<span class="osi-chip chip-${a.sev}">${a.label}</span>`
          ).join('')}
          ${row.attacks.length === 0 ? '<span style="font-size:10px;color:var(--dimmer)">no demo in this lab</span>' : ''}
        </span>
      </div>
    `).join('');

    // Lesson cards
    document.getElementById('intro-lesson-grid').innerHTML = LESSONS.map((l, i) => `
      <div class="lesson-card" onclick="App.selectLesson(${i}); App.startLab()">
        <div class="lc-layer">${l.layer}</div>
        <div class="lc-sev sev-${l.severity}">${l.severity.toUpperCase()}</div>
        <div class="lc-title">${l.title}</div>
        <div class="lc-tagline">${l.tagline}</div>
      </div>
    `).join('');
  },

  goIntro() {
    document.getElementById('lab-screen').classList.remove('active');
    document.getElementById('intro-screen').classList.add('active');
  },

  startLab() {
    document.getElementById('intro-screen').classList.remove('active');
    document.getElementById('lab-screen').classList.add('active');
    this.renderSidebar();
    this.renderLesson();
    pollState();
  },

  selectLesson(i) {
    curLesson  = i;
    curChapter = 0;
    curPhase   = 0;
    clearAll();
    this.renderSidebar();
    this.renderLesson();
    const lesson = LESSONS[i];
    if (lesson.id === 'tls-evolution') {
      document.getElementById('tls-timeline-block').style.display = 'block';
      renderTLSTimeline(lesson.timeline || []);
    } else {
      document.getElementById('tls-timeline-block').style.display = 'none';
    }
  },

  selectChapter(ci) {
    curChapter = ci;
    curPhase   = 0;
    clearAll();
    this.applyChapterConfig();
    this.renderLesson();
  },

  renderSidebar() {
    document.getElementById('lesson-sidebar').innerHTML = LESSONS.map((l, i) => `
      <div class="sidebar-lesson ${i === curLesson ? 'active' : ''}" onclick="App.selectLesson(${i})">
        <div class="sl-layer">${l.layer}</div>
        <div class="sl-title">${l.title.replace('Lesson ','L')}</div>
      </div>
    `).join('');
  },

  renderLesson() {
    const lesson  = LESSONS[curLesson];
    const chapter = lesson.chapters[curChapter];
    const phase   = chapter.phases[curPhase];

    // Header
    document.getElementById('hdr-lesson-title').textContent = lesson.title;

    // Chapter steps
    document.getElementById('chapter-steps').innerHTML = lesson.chapters.map((ch, ci) => `
      <div class="ch-step ${ci === curChapter ? 'active' : ci < curChapter ? 'done' : ''}"
           onclick="App.selectChapter(${ci})">${ch.title}</div>
    `).join('');

    // Context strip
    document.getElementById('ctx-layer').textContent  = lesson.layer;
    document.getElementById('ctx-text').textContent   = chapter.context;

    // Panel titles
    document.getElementById('title-client').textContent       = chapter.client_persona || 'client';
    document.getElementById('title-server').textContent       = chapter.server_persona || 'server';
    document.getElementById('wire-panel-title').textContent   = chapter.wire_persona   || 'wire';

    // Phase hint
    document.getElementById('phase-hint').textContent = phase.hint || '';

    // Console command
    this.renderConsoleForPhase(phase);

    // Phase dots
    document.getElementById('phase-dots').innerHTML = chapter.phases.map((_, pi) => `
      <div class="pdot ${pi === curPhase ? 'active' : pi < curPhase ? 'done' : ''}"
           onclick="App.gotoPhase(${pi})"></div>
    `).join('');

    // Nav buttons
    document.getElementById('btn-prev').disabled =
      curPhase === 0 && curChapter === 0;
    document.getElementById('btn-next').disabled =
      curPhase === chapter.phases.length - 1 && curChapter === lesson.chapters.length - 1;

    // Defense toggles
    this.renderDefenseToggles();
  },

  renderConsoleForPhase(phase) {
    const cmd = buildCommand(phase.action, phase.params);
    const el  = document.getElementById('console-cmd');
    el.textContent = cmd;
    el.contentEditable = 'false';
    editMode = false;
    document.getElementById('btn-edit').style.borderColor = '';
    document.getElementById('btn-edit').style.color = '';

    // Editable fields
    const fields = document.getElementById('console-fields');
    fields.innerHTML = (phase.editable_fields || []).map(f => `
      <div class="field-wrap">
        <div class="field-label">${f.label}</div>
        <input class="field-input" data-key="${f.key}"
               value="${f.default !== null && f.default !== undefined ? f.default : ''}"
               placeholder="${f.label}">
      </div>
    `).join('');
  },

  renderDefenseToggles() {
    const defs = [
      { key: 'hmac_enabled',              label: 'HMAC signatures'   },
      { key: 'replay_protection_enabled', label: 'Replay protection'  },
      { key: 'rate_limit_enabled',        label: 'Rate limiting'      },
    ];
    document.getElementById('defense-toggles').innerHTML = defs.map(d => `
      <div class="def-toggle">
        <span>${d.label}</span>
        <button class="toggle" data-key="${d.key}" onclick="App.toggleDefense('${d.key}', this)"></button>
      </div>
    `).join('');
  },

  toggleDefense(key, btn) {
    const on = !btn.classList.contains('on');
    btn.classList.toggle('on', on);
    socket.emit('set_config', { [key]: on });
    appendLine('server', `⚙  ${key} → ${on ? 'ENABLED' : 'DISABLED'}`, 'amber');
  },

  applyChapterConfig() {
    const ch = LESSONS[curLesson].chapters[curChapter];
    if (ch.config_on_enter) {
      socket.emit('set_config', ch.config_on_enter);
      const keys = Object.keys(ch.config_on_enter);
      appendLine('server', `⚙  Chapter config: ${JSON.stringify(ch.config_on_enter)}`, 'amber');
    }
  },

  toggleEdit() {
    editMode = !editMode;
    const el  = document.getElementById('console-cmd');
    const btn = document.getElementById('btn-edit');
    el.contentEditable = editMode ? 'true' : 'false';
    if (editMode) {
      el.focus();
      btn.style.borderColor = 'var(--amber)';
      btn.style.color       = 'var(--amber)';
    } else {
      btn.style.borderColor = '';
      btn.style.color       = '';
    }
  },

  execute() {
    if (busy) return;
    busy = true;
    setStatus('busy');
    document.getElementById('btn-run').disabled = true;
    clearAll();

    const lesson  = LESSONS[curLesson];
    const chapter = lesson.chapters[curChapter];
    const phase   = chapter.phases[curPhase];

    // Merge editable field values into params
    const params = JSON.parse(JSON.stringify(phase.params));
    document.querySelectorAll('.field-input').forEach(input => {
      setDeep(params, input.dataset.key, input.value);
    });

    socket.emit('execute', { action: phase.action, params });
    appendLine('client', `▸ executing: ${phase.action}`, 'dim');
  },

  nextPhase() {
    const lesson  = LESSONS[curLesson];
    const chapter = lesson.chapters[curChapter];
    if (curPhase < chapter.phases.length - 1) {
      curPhase++;
    } else if (curChapter < lesson.chapters.length - 1) {
      curChapter++;
      curPhase = 0;
      clearAll();
      this.applyChapterConfig();
    }
    this.renderLesson();
  },

  prevPhase() {
    if (curPhase > 0) {
      curPhase--;
    } else if (curChapter > 0) {
      curChapter--;
      curPhase = LESSONS[curLesson].chapters[curChapter].phases.length - 1;
      clearAll();
    }
    this.renderLesson();
  },

  gotoPhase(pi) {
    curPhase = pi;
    clearAll();
    this.renderLesson();
  },

  reset() {
    clearAll();
    socket.emit('reset');
    appendLine('server', '↺ Lab reset — all state cleared', 'amber');
  },
};

// ── Helpers ──────────────────────────────────────────────────────────
function buildCommand(action, params) {
  const map = {
    'normal-login':      () =>
      `curl -X POST http://victim:8080/login \\\n  -H 'Content-Type: application/json' \\\n  -d '{"username":"${params.username}","password":"${params.password}"}'`,
    'sniff-login':       () =>
      `curl -x http://mitm:8888 \\\n  -X POST http://victim:8080/login \\\n  -d '{"username":"${params.username}","password":"${params.password}"}'`,
    'modify-response':   () =>
      `# mitmproxy intercepts /balance response\n# and modifies the JSON before forwarding`,
    'tls-secure':        () =>
      `curl --cacert /certs/victim.crt \\\n  https://victim:8443/login \\\n  -d '{"username":"alice","password":"hunter2"}'`,
    'fake-cert':         () =>
      `curl -k -x http://mitm:8888 \\\n  https://victim:8443/login \\\n  -d '{"username":"alice","password":"hunter2"}'`,
    'legitimate-webhook':() =>
      `# Stripe fires a real webhook\n# Signed with shared secret\ncurl -X POST http://victim:8080/webhooks/payment \\\n  -H "X-Signature: sha256=<valid_hmac>" \\\n  -d '{"type":"payment.succeeded","amount":4200}'`,
    'forge-webhook':     () => {
      const p = params.payload || {};
      return `curl -X POST http://victim:8080/webhooks/payment \\\n  -H 'Content-Type: application/json' \\\n  -d '${JSON.stringify(p)}'`;
    },
    'capture-webhook':   () =>
      `# Capture a signed webhook from the wire\n# Save body + X-Signature header to replay.json`,
    'replay-webhook':    () =>
      `for i in $(seq 1 ${params.count || 3}); do\n  curl -X POST http://victim:8080/webhooks/payment \\\n    -H "X-Signature: <captured_valid_sig>" \\\n    -d @replay.json\ndone`,
    'brute-force':       () =>
      `python3 brute.py --user ${params.username || 'alice'} \\\n  --wordlist common-passwords.txt \\\n  --url http://victim:8080/login`,
    'tls-probe':         () =>
      `python3 -c "\nimport ssl,socket\nctx=ssl.create_default_context()\nctx.check_hostname=False\nctx.verify_mode=ssl.CERT_NONE\nwith socket.create_connection(('victim',8443)) as s:\n  with ctx.wrap_socket(s) as t:\n    print(t.version(), t.cipher())\n"`,
  };
  return (map[action] || (() => `# ${action}\n${JSON.stringify(params, null, 2)}`))(params);
}

function appendLine(panel, line, style) {
  const id   = { client: 'out-client', server: 'out-server', wire: 'out-wire' }[panel];
  if (!id) return;
  const el   = document.getElementById(id);
  const div  = document.createElement('div');
  div.className = `l-${style || 'out'}`;
  div.textContent = line;
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

function clearAll() {
  ['out-client', 'out-server', 'out-wire'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
  });
}

function onMitmCapture(d) {
  if (d.event === 'request') {
    appendLine('wire', `>>> INTERCEPTED ${d.method} ${d.url}`, 'red');
    if (d.body) appendLine('wire', d.body.substring(0, 200), 'red');
  } else if (d.event === 'response') {
    appendLine('wire', `<<< RESPONSE ${d.status} ${d.url}`, 'amber');
    if (d.body) appendLine('wire', d.body.substring(0, 200), 'amber');
  }
}

function renderState(state) {
  const orders  = state.orders || [];
  const credits = state.credits || {};
  const accounts= state.accounts || {};

  document.getElementById('state-orders').innerHTML = `
    <div class="state-row"><span>Orders fulfilled</span><span class="state-val ${orders.length > 1 ? 'changed' : ''}">${orders.length}</span></div>
    <div class="state-row"><span>alice credit</span><span class="state-val ${credits.alice > 0 ? 'changed' : ''}">$${((credits.alice||0)/100).toFixed(2)}</span></div>
    <div class="state-row"><span>alice balance</span><span class="state-val">$${(accounts.alice||0).toLocaleString()}</span></div>
  `;
}

function renderTLSTimeline(timeline) {
  document.getElementById('tls-timeline').innerHTML = timeline.map(t => `
    <div class="tls-row ${t.status}">
      <div class="tls-ver">${t.version} <span style="font-weight:normal;color:var(--dimmer)">(${t.year})</span></div>
      <div class="tls-note">${t.broke_by}</div>
      <div class="tls-note" style="margin-top:3px;font-style:italic">${t.note}</div>
    </div>
  `).join('');
}

function pollState() {
  socket.emit('get_state');
  setInterval(() => socket.emit('get_state'), 4000);
}

// Deep-set obj by "a.b.c" key
function setDeep(obj, key, val) {
  const parts = key.split('.');
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!(parts[i] in cur)) cur[parts[i]] = {};
    cur = cur[parts[i]];
  }
  const last = parts[parts.length - 1];
  // Try to parse numbers
  const num = Number(val);
  cur[last] = val === '' ? val : isNaN(num) ? val : num;
}

// ── Lessons API endpoint ──────────────────────────────────────────────
// Add to Flask: serve lessons as JSON
(async () => { await App.init(); })();
