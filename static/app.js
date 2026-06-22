/* app.js — fetch from FastAPI, render UI */
const API = '';   /* same origin */

/* ── helpers ── */
const $ = id => document.getElementById(id);
const fmt = (n, dec) => Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
const fmtUSD = n => '$' + fmt(n, 2);
const pnlColor = n => n >= 0 ? '#54c98a' : '#e5746c';
const pnlSign  = n => n >= 0 ? '+' : '−';

/* ── fetch helpers ── */
async function apiFetch(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

/* ── initial load ── */
async function loadAll() {
  try {
    const [summary, positions, watchlist, advice] = await Promise.all([
      apiFetch('/api/summary'),
      apiFetch('/api/positions'),
      apiFetch('/api/watchlist'),
      apiFetch('/api/advice'),
    ]);
    renderHeader(summary);
    renderKPIs(summary);
    renderPositions(positions);
    renderWatchlist(watchlist);
    renderAlerts(watchlist);
    renderAdvice(advice);
  } catch (e) {
    console.error('loadAll error:', e);
  }
}

/* ── header ── */
function renderHeader(s) {
  const bookILS = s.book_value * 3.7;
  $('hdr-total').textContent = '₪' + fmt(bookILS, 0);
  const pct = s.pnl_percent;
  const badge = $('hdr-pct');
  badge.textContent = (pct >= 0 ? '▲ ' : '▼ ') + Math.abs(pct).toFixed(2) + '%';
  badge.style.color = pnlColor(pct);
  badge.style.background = pct >= 0 ? 'rgba(84,201,138,0.12)' : 'rgba(229,116,108,0.12)';
}

/* ── KPIs ── */
function renderKPIs(s) {
  $('kpi-book').textContent = '$' + fmt(s.book_value, 0);
  const pnlEl = $('kpi-pnl');
  const pctEl = $('kpi-pnl-pct');
  pnlEl.textContent = pnlSign(s.pnl_amount) + '$' + fmt(Math.abs(s.pnl_amount), 0);
  pnlEl.style.color = pnlColor(s.pnl_amount);
  pctEl.textContent = pnlSign(s.pnl_percent) + fmt(Math.abs(s.pnl_percent), 2) + '%';
  pctEl.style.color = pnlColor(s.pnl_percent);
  $('kpi-count').textContent = s.position_count;
  $('kpi-cash').textContent = '₪716,896';
}

/* ── positions ── */
function renderPositions(positions) {
  $('pos-count-label').textContent = positions.length + ' ניירות';
  $('pos-updated').textContent = 'עודכן · ' + new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });

  const tbody = $('positions-body');
  tbody.innerHTML = '';
  let totalValue = 0, totalPnl = 0;

  for (const p of positions) {
    totalValue += p.holding_value || 0;
    totalPnl   += p.pnl_amount   || 0;
    const isSwing = p.trade_type === 'SHORT_TERM';
    const typeLabel = isSwing ? 'סווינג' : 'טווח ארוך';
    const typeColor = isSwing ? '#c9a3e8' : '#7fb5e6';
    const typeBg    = isSwing ? 'rgba(176,130,214,0.13)' : 'rgba(110,165,224,0.13)';
    const pc = pnlColor(p.pnl_amount);
    const dynStop = p.dynamic_stop_loss > 0 ? fmtUSD(p.dynamic_stop_loss) : '—';
    const stopDist = p.stop_distance_pct != null ? p.stop_distance_pct.toFixed(1) + '% מרחק' : '—';
    let riskLabel = 'יציב', riskColor = '#7d8893', riskBg = 'rgba(255,255,255,0.05)';
    if (p.pnl_percent < -20) {
      riskLabel = 'סיכון גבוה'; riskColor = '#e5746c'; riskBg = 'rgba(229,116,108,0.13)';
    } else if (p.dynamic_stop_loss === 0) {
      riskLabel = 'ללא סטופ'; riskColor = '#e0b257'; riskBg = 'rgba(224,178,87,0.13)';
    }
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <span class="ticker-name">${p.symbol}</span>
          <span class="ticker-type" style="color:${typeColor};background:${typeBg}">${typeLabel}</span>
        </div>
        <div class="asset-name">${p.asset_name}</div>
      </td>
      <td class="ltr" style="font-family:'IBM Plex Mono',monospace;color:#c4c9d0">${fmt(p.quantity,0)}</td>
      <td class="ltr" style="font-family:'IBM Plex Mono',monospace;color:#9ba1ab">${fmtUSD(p.avg_cost_price)}</td>
      <td class="ltr" style="font-family:'IBM Plex Mono',monospace;font-weight:600">${fmtUSD(p.current_price)}</td>
      <td class="ltr" style="font-family:'IBM Plex Mono',monospace;color:#c4c9d0">$${fmt(p.holding_value,0)}</td>
      <td class="ltr">
        <div class="pnl-amt" style="color:${pc}">${pnlSign(p.pnl_amount)}$${fmt(Math.abs(p.pnl_amount),0)}</div>
        <div class="pnl-pct" style="color:${pc}">${pnlSign(p.pnl_percent)}${fmt(Math.abs(p.pnl_percent),2)}%</div>
      </td>
      <td class="ltr">
        <div class="stop-val">${dynStop}</div>
        <div class="stop-dist">${stopDist}</div>
      </td>
      <td><span class="risk-badge" style="color:${riskColor};background:${riskBg}">${riskLabel}</span></td>`;
    tbody.appendChild(tr);
  }

  const totalPct  = totalValue > 0 ? ((totalValue - (totalValue - totalPnl)) / (totalValue - totalPnl) * 100) : 0;
  const tfoot = $('positions-foot');
  tfoot.innerHTML = `<tr>
    <td>סה״כ ספר המסחר</td><td></td><td></td><td></td>
    <td class="ltr mono" style="font-weight:700">$${fmt(totalValue,0)}</td>
    <td class="ltr"><span class="pnl-amt" style="color:${pnlColor(totalPnl)}">${pnlSign(totalPnl)}$${fmt(Math.abs(totalPnl),0)}</span></td>
    <td></td><td></td>
  </tr>`;
}

/* ── watchlist ── */
function renderWatchlist(items) {
  $('watch-count-label').textContent = items.length + ' ניירות';
  const container = $('watchlist-body');
  container.innerHTML = '';
  if (!items.length) {
    container.innerHTML = '<div class="loading-row">רשימת המעקב ריקה.</div>';
    return;
  }
  for (const w of items) {
    const triggered = w.current_status.includes('Triggered');
    const statusLabel = triggered ? 'הופעלה' : 'ממתין';
    const statusColor = triggered ? '#f0c87a' : '#7d8893';
    const statusBg    = triggered ? 'rgba(224,178,87,0.15)' : 'rgba(255,255,255,0.05)';
    const cardBg      = triggered ? 'rgba(224,178,87,0.06)' : '#1a1e24';
    const cardBorder  = triggered ? 'rgba(224,178,87,0.3)' : 'rgba(255,255,255,0.06)';
    const div = document.createElement('div');
    div.className = 'watch-card';
    div.style.background = cardBg;
    div.style.border = `1px solid ${cardBorder}`;
    div.innerHTML = `
      <div class="watch-header">
        <div class="watch-left">
          <span class="watch-ticker">${w.symbol}</span>
          <span class="watch-status" style="color:${statusColor};background:${statusBg}">${statusLabel}</span>
        </div>
        <div class="watch-prices">
          <span><span class="label">טריגר </span><span style="color:#c4c9d0;font-weight:600">$${fmt(w.trigger_price_zone,2)}</span></span>
          <span><span class="label">סטופ </span><span style="color:#e5746c;font-weight:600">$${fmt(w.stop_loss,2)}</span></span>
        </div>
      </div>
      <div class="watch-thesis">${w.thesis_summary || w.required_setup_conditions || '—'}</div>`;
    container.appendChild(div);
  }
}

/* ── triggered alerts ── */
function renderAlerts(watchlist) {
  const triggered = watchlist.filter(w => w.current_status.includes('Triggered'));
  const container = $('alerts-container');
  container.innerHTML = '';
  for (const w of triggered) {
    const ts = w.activation_trigger_time || '—';
    const price = w.activation_trigger_price ? fmtUSD(w.activation_trigger_price) : '—';
    const div = document.createElement('div');
    div.className = 'alert-card';
    div.innerHTML = `
      <div class="alert-header">
        <div style="display:flex;align-items:center;gap:10px">
          <span class="alert-dot"></span>
          <span class="alert-title">⚡ התראת TradingView הופעלה — ממתינה לאישור</span>
        </div>
        <span class="alert-ts">${ts}</span>
      </div>
      <div class="alert-body">
        <div style="display:flex;align-items:center;gap:12px">
          <span class="alert-ticker">${w.symbol}</span>
          <div class="alert-divider"></div>
          <div>
            <div class="alert-price-label">שער הפעלה</div>
            <div class="alert-price">${price}</div>
          </div>
        </div>
        <div class="alert-thesis">${w.thesis_summary || '⚠️ חסרה תזה — הופעל ישירות מ-TradingView'}</div>
      </div>
      <div class="alert-actions">
        <button class="btn-investigate" onclick="investigate('${w.symbol}')">🔍 פתח תחקור ומצב החלטה</button>
        <button class="btn-ghost" onclick="dismissAlert('${w.symbol}','notes')">📝 ביטול עם תחקור</button>
        <button class="btn-ghost" onclick="dismissAlert('${w.symbol}','quick')">❌ ביטול מהיר</button>
      </div>`;
    container.appendChild(div);
  }
}

/* ── latest advice ── */
function renderAdvice(advice) {
  if (!advice || !advice.advice_text) return;
  $('advice-panel').style.display = '';
  $('advice-ts').textContent = advice.timestamp || '';
  $('advice-body').textContent = advice.advice_text;
}

/* ── sync ── */
async function syncMarket() {
  const btn = $('sync-btn');
  btn.disabled = true;
  btn.textContent = 'מסנכרן...';
  try {
    await fetch(API + '/api/sync', { method: 'POST' });
    await loadAll();
  } catch (e) {
    console.error('sync error:', e);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>⟳</span> סנכרן נתוני שוק';
  }
}

/* ── alert actions ── */
async function investigate(symbol) {
  alert('מצב תחקיר: ' + symbol + ' — יחובר לצ\'אט בשלב הבא');
}

async function dismissAlert(symbol, mode) {
  if (mode === 'quick') {
    await fetch(API + `/api/watchlist/${symbol}/dismiss`, { method: 'POST' });
    await loadAll();
  } else {
    const notes = prompt('סיבת הביטול:');
    if (notes !== null) {
      await fetch(API + `/api/watchlist/${symbol}/dismiss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes }),
      });
      await loadAll();
    }
  }
}

/* ── boot ── */
loadAll();

/* ── Chat ── */
let chatHistory = [];

/* ── Session state ── */
let _session = null;

/* ── chip definitions ── */
const _CHIPS_DEFAULT = [
  { label: 'עדכן סטופים כללי', action: () => sendChip('עדכן סטופים כללי') },
  { label: 'מצב התיק',          action: () => sendChip('מה המצב של התיק שלי') },
  { label: 'הצג פוזיציות',      action: () => sendChip('הצג פוזיציות') },
];

/* ── עדכון צ'יפים לפי מצב ── */
function _updateChips() {
  const container = $('chat-chips-container');
  if (!container) return;
  container.innerHTML = '';

  if (!_session) {
    _CHIPS_DEFAULT.forEach(c => {
      const btn = document.createElement('button');
      btn.className = 'chip';
      btn.textContent = c.label;
      btn.onclick = c.action;
      container.appendChild(btn);
    });
    return;
  }

  // session פעיל — בדיקת pendingResult
  const hasResult = !!(_session.pendingResult &&
    _session.pendingResult.symbol &&
    _session.pendingResult.trigger_price_zone);

  const btnAdd = document.createElement('button');
  btnAdd.className = 'chip chip-accent';
  btnAdd.id = 'btn-add-watchlist';
  btnAdd.textContent = '💾 הוסף ל-Watchlist';
  btnAdd.disabled = !hasResult;
  btnAdd.onclick = addToWatchlist;
  container.appendChild(btnAdd);

  const btnEnd = document.createElement('button');
  btnEnd.className = 'chip chip-danger';
  btnEnd.textContent = '✕ סיום תחקיר';
  btnEnd.onclick = _closeSession;
  container.appendChild(btnEnd);
}

/* ── שמירה ל-watchlist ── */
async function addToWatchlist() {
  if (!_session || !_session.pendingResult) return;

  const btn = $('btn-add-watchlist');
  if (btn) { btn.disabled = true; btn.textContent = 'שומר...'; }

  try {
    const res = await fetch('/api/watchlist/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_session.pendingResult),
    });
    const data = await res.json();

    if (data.ok) {
      addBubble(`✅ ${_session.pendingResult.symbol} נוסף לרשימת המעקב`, 'assistant');
      await loadAll();
      _closeSession();
    } else {
      addBubble(`⚠️ שגיאה: ${data.message || 'לא ניתן לשמור'}`, 'assistant');
      if (btn) { btn.disabled = false; btn.textContent = '💾 הוסף ל-Watchlist'; }
    }
  } catch (e) {
    addBubble('⚠️ שגיאת חיבור בשמירה ל-watchlist', 'assistant');
    if (btn) { btn.disabled = false; btn.textContent = '💾 הוסף ל-Watchlist'; }
  }
}

function addBubble(text, role) {
  const container = $('chat-messages');
  const div = document.createElement('div');
  div.className = `bubble bubble-${role}`;
  div.textContent = text;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

function addAgentBadge(agent, context) {
  const container = $('chat-messages');
  const div = document.createElement('div');
  div.className = 'bubble bubble-agent';
  const labels = {
    chart_analyst: '📊 ניתוח גרף', short_term: '⚡ סווינג',
    long_term: '📈 טווח ארוך', portfolio: '🗂 תיק',
    trade_monitor: '💼 עסקה', data_loader: '📂 נתונים', general: '🤖 כללי'
  };
  div.textContent = (labels[agent] || agent) + ' · ' + context;
  container.appendChild(div);
  const badge = $('chat-agent-badge');
  if (badge) badge.textContent = labels[agent] || agent;
}

async function sendMessage() {
  const input = $('chat-input');
  const text  = (input.value || '').trim();
  const pendingImage = window._pendingImage || null;
  if (!text && !pendingImage) return;

  input.value = '';
  if (pendingImage) {
    window._lastSentImage = pendingImage.data;
    window._pendingImage = null;
  }

  const displayText = text || '📊 שולח גרף לניתוח...';
  addBubble(displayText, 'user');

  const btn = document.querySelector('.send-btn');
  btn.disabled = true;
  const assistantBubble = addBubble('', 'assistant');
  let fullText = '';

  if (_session) {
    const newImages = pendingImage ? [pendingImage.data] : [];
    if (newImages.length > 0) {
      _session.session_images = (_session.session_images || []).concat(newImages);
    }
    _session.history.push({ role: 'user', text: displayText });

    const payload = {
      agent:          _session.agent,
      context:        _session.context,
      message:        text,
      history:        _session.history.slice(-20),
      session_images: _session.session_images || [],
    };
    await _streamRequest('/api/chat/session', payload, assistantBubble,
      (data) => _handleSessionEvent(data, fullText, (t) => { fullText = t; }));
    btn.disabled = false;
    return;
  }

  if (text) chatHistory.push({ role: 'user', text: displayText });

  const endpoint = pendingImage ? '/api/chat/image' : '/api/chat';
  const payload  = pendingImage
    ? { message: text || '', image_data: pendingImage.data, image_mime: pendingImage.mime, history: chatHistory.slice(-10) }
    : { message: text, history: chatHistory.slice(-10) };

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const lines = decoder.decode(value).split('\n');
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.agent && !data.clarify) addAgentBadge(data.agent, data.context || '');
          if (data.clarify) {
            assistantBubble.remove();
            addBubble('🤔 ' + data.text, 'assistant');
          }
          if (data.text && !data.clarify) { fullText += data.text; assistantBubble.textContent = fullText; }
          if (data.error) { assistantBubble.textContent = '⚠️ שגיאה: ' + data.error; }
          if (data.done) {
            if (!data.keep_image) window._pendingImage = null;
            if (fullText) chatHistory.push({ role: 'assistant', text: fullText });
            if (data.pending_watchlist && data.agent) {
              const firstImg = window._lastSentImage || null;
              _openSession(data.agent, data.context || 'SHORT_TERM', data.pending_watchlist, firstImg);
            }
            $('chat-messages').scrollTop = 99999;
          }
        } catch {}
      }
    }
  } catch (e) {
    assistantBubble.textContent = '⚠️ שגיאת חיבור';
  } finally {
    btn.disabled = false;
    $('chat-input').focus();
  }
}

function sendChip(text) {
  $('chat-input').value = text;
  sendMessage();
}

window.addEventListener('load', () => {
  _updateChips();   // ← אתחול צ'יפים רגילים
  setTimeout(() => {
    addBubble('שלום! אני עוזר המסחר שלך.\nאפשר לשאול שאלות על התיק, לבקש ניתוח טכני, לעדכן עסקאות, או להעלות גרף מ-TradingView.', 'assistant');
  }, 600);
});

/* ── Paste from clipboard ── */
document.addEventListener('paste', (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile();
      const reader = new FileReader();
      reader.onload = ev => {
        const base64 = ev.target.result.split(',')[1];
        window._pendingImage = { data: base64, mime: item.type };
        addBubble('📋 תמונה מה-clipboard — מוכנה לשליחה', 'user');
      };
      reader.readAsDataURL(file);
      break;
    }
  }
});

/* ── session helpers ── */
function _openSession(agent, context, pendingResult, firstImage = null) {
  const images = firstImage ? [firstImage] : [];
  _session = { agent, context, history: [], pendingResult, session_images: images };
  _updateChips();          // ← עדכון צ'יפים ל-session
  _renderSessionBanner(true);
  console.log(`[session] opened: ${agent} / ${context}`);
}

function _closeSession() {
  _session = null;
  _updateChips();          // ← חזרה לצ'יפים רגילים
  _renderSessionBanner(false);
  console.log('[session] closed');
}

function _renderSessionBanner(active) {
  let banner = $('session-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'session-banner';
    banner.style.cssText = 'padding:6px 14px;background:rgba(84,201,138,0.12);color:#54c98a;font-size:12px;display:flex;justify-content:space-between;align-items:center;';
    const chatBox = $('chat-messages');
    chatBox.parentNode.insertBefore(banner, chatBox);
  }
  if (active && _session) {
    const labels = { chart_analyst: '📊 ניתוח גרף', short_term: '⚡ סווינג', long_term: '📈 טווח ארוך' };
    banner.innerHTML = `<span>🔍 תחקיר פעיל — ${labels[_session.agent] || _session.agent}</span>`;
    banner.style.display = 'flex';
  } else {
    banner.style.display = 'none';
  }
}

async function _streamRequest(endpoint, payload, bubble, onEvent) {
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const lines = decoder.decode(value).split('\n');
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.text && !data.clarify) { fullText += data.text; bubble.textContent = fullText; }
          onEvent(data, fullText, (t) => { fullText = t; });
        } catch {}
      }
    }
    $('chat-messages').scrollTop = 99999;
  } catch (e) {
    bubble.textContent = '⚠️ שגיאת חיבור';
  }
}

function _handleSessionEvent(data, fullText, setFullText) {
  if (data.agent && !data.clarify) addAgentBadge(data.agent, data.context || '');

  if (data.session_closed) {
    _closeSession();
    chatHistory.push({ role: 'assistant', text: fullText });
    return;
  }

  // pending_watchlist הגיע — מפעיל כפתור "הוסף"
  if (data.pending_watchlist) {
    if (_session) {
      _session.pendingResult = data.pending_watchlist;
      _updateChips();      // ← מפעיל את כפתור "הוסף"
    }
    if (data.session_closed) {
      chatHistory.push({ role: 'assistant', text: fullText });
      return;
    }
  }

  if (data.done && data.session_active) {
    if (_session) _session.history.push({ role: 'assistant', text: fullText });
    return;
  }
}
