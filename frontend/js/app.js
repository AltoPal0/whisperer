/* app.js — Point d'entrée, orchestration */

// Lire le code canal depuis l'URL : /c/{code}
function getChannelCode() {
  const parts = window.location.pathname.split('/');
  if (parts[1] === 'c' && parts[2]) return parts[2];
  return null;
}

const channelCode = getChannelCode();

/* ── Init ── */
document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('versionTag').textContent = typeof APP_VERSION !== 'undefined' ? APP_VERSION : '';

  if (!channelCode) {
    UI.showError('URL invalide — aucun canal spécifié.');
    return;
  }

  // Vérifier que le canal existe
  try {
    await Api.getChannel(channelCode);
  } catch (e) {
    UI.showError('Canal introuvable.');
    return;
  }

  UI.setState('idle');

  // Charger les transcriptions existantes
  try {
    const transcriptions = await Api.listTranscriptions(channelCode);
    UI.renderList(transcriptions);
  } catch (e) {
    console.warn('Chargement transcriptions:', e.message);
  }

  // Bouton enregistrement
  document.getElementById('recordBtn').addEventListener('click', handleToggle);

  // Logo → recharge la dernière version
  document.getElementById('logoBtn').addEventListener('click', async () => {
    const overlay = document.getElementById('reloadOverlay');
    overlay.classList.add('visible');
    if ('serviceWorker' in navigator) {
      const reg = await navigator.serviceWorker.getRegistration();
      if (reg) await reg.update();
    }
    window.location.reload(true);
  });

  // Délégation des boutons delete sur la liste
  document.getElementById('transcriptionsList').addEventListener('click', async (e) => {
    const del = e.target.closest('.t-card-delete');
    if (!del) return;
    const id = del.dataset.id;
    UI.removeCard(id);
    try { await Api.deleteTranscription(id, channelCode); } catch {}
  });

  // iOS install hint (uniquement si pas en standalone)
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const hintKey = `install_hint_shown_${channelCode}`;
  if (isIOS && !isStandalone && !localStorage.getItem(hintKey)) {
    localStorage.setItem(hintKey, '1');
    UI.showInstallBanner();
  }
});

/* ── Toggle record / stop ── */
async function handleToggle() {
  if (Recorder.isRecording()) {
    await stopAndTranscribe();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  UI.vibrate(10);
  try {
    await Recorder.start();
    UI.setState('recording');
  } catch (e) {
    alert('Microphone inaccessible : ' + e.message);
  }
}

async function stopAndTranscribe() {
  UI.vibrate(15);
  UI.setState('processing');

  const result = await Recorder.stop();
  if (!result || !result.blob.size) {
    UI.setState('idle');
    return;
  }

  try {
    const transcription = await Api.transcribe(result.blob, result.ext, channelCode, result.duration_ms);
    UI.prependCard(transcription);
  } catch (e) {
    alert('Erreur de transcription : ' + e.message);
  } finally {
    UI.setState('idle');
  }
}
