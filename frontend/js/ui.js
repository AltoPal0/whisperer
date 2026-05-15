/* ui.js — Gestion des états visuels et du DOM */

const UI = (() => {
  const body        = document.body;
  const radialGlow  = document.getElementById('radialGlow');
  const statusDot   = document.getElementById('statusDot');
  const recTimer    = document.getElementById('recTimer');
  const stateLabel  = document.getElementById('stateLabel');
  const list        = document.getElementById('transcriptionsList');
  const emptyHint   = document.getElementById('emptyHint');

  let timerInterval = null;
  let timerStart    = null;

  /* ── State transitions ── */

  function setState(state) {
    body.className = state;
    radialGlow.className = `radial-glow ${state}`;
    statusDot.className  = `status-dot ${state}`;

    if (state === 'idle') {
      stateLabel.textContent = 'Appuyer pour enregistrer';
      _stopTimer();
    } else if (state === 'recording') {
      stateLabel.textContent = 'Relâcher pour transcrire';
      _startTimer();
    } else if (state === 'processing') {
      stateLabel.textContent = 'Transcription en cours…';
      _stopTimer();
    }
  }

  /* ── Timer ── */

  function _startTimer() {
    timerStart = Date.now();
    recTimer.textContent = '00:00';
    timerInterval = setInterval(() => {
      const s = Math.floor((Date.now() - timerStart) / 1000);
      const m = Math.floor(s / 60);
      recTimer.textContent = `${String(m).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`;
    }, 500);
  }

  function _stopTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
    recTimer.textContent = '00:00';
  }

  /* ── Transcriptions list ── */

  function prependCard(t) {
    emptyHint.classList.add('hidden');
    const card = _buildCard(t);
    list.prepend(card);
  }

  function removeCard(id) {
    document.getElementById(`card-${id}`)?.remove();
    if (list.children.length === 0) emptyHint.classList.remove('hidden');
  }

  function renderList(transcriptions) {
    list.innerHTML = '';
    if (!transcriptions.length) {
      emptyHint.classList.remove('hidden');
      return;
    }
    emptyHint.classList.add('hidden');
    transcriptions.forEach(t => list.appendChild(_buildCard(t)));
  }

  function _buildCard(t) {
    const card = document.createElement('div');
    card.className = 't-card';
    card.id = `card-${t.id}`;

    const date = new Date(t.created_at);
    const timeStr = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    const dateStr = date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
    const dur = t.duration_ms ? _formatDur(t.duration_ms) : '';

    card.innerHTML = `
      <p class="t-card-text">${_esc(t.text)}</p>
      <div class="t-card-meta">
        <span class="t-card-time">${dateStr} · ${timeStr}${dur ? ' · ' + dur : ''}</span>
        ${t.language ? `<span class="t-card-lang">${t.language}</span>` : ''}
      </div>
      <button class="t-card-delete" aria-label="Supprimer" data-id="${t.id}">×</button>
    `;
    return card;
  }

  function _formatDur(ms) {
    const s = Math.round(ms / 1000);
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m${s % 60 ? String(s % 60).padStart(2,'0') + 's' : ''}`;
  }

  function _esc(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  /* ── Haptic ── */
  function vibrate(ms = 10) {
    navigator.vibrate?.(ms);
  }

  /* ── iOS install banner ── */
  function showInstallBanner() {
    const banner = document.createElement('div');
    banner.className = 'install-banner';
    banner.textContent = 'Installe l\'app → Partager → Sur l\'écran d\'accueil';
    document.body.appendChild(banner);
    setTimeout(() => banner.remove(), 6000);
  }

  /* ── Error state ── */
  function showError(message) {
    body.className = 'error';
    const label = document.getElementById('stateLabel');
    if (label) label.textContent = message;
    const btn = document.getElementById('recordBtn');
    if (btn) btn.disabled = true;
  }

  return { setState, showError, prependCard, removeCard, renderList, vibrate, showInstallBanner };
})();
