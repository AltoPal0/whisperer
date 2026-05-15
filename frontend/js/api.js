/* api.js — Appels vers le backend FastAPI */

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? `http://${window.location.hostname}:8080`
  : '';

const Api = (() => {

  async function handleResponse(res) {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Erreur ${res.status}`);
    }
    return res;
  }

  async function getChannel(code) {
    const res = await fetch(`${API_BASE}/api/channel/${encodeURIComponent(code)}`);
    await handleResponse(res);
    return res.json();
  }

  async function transcribe(blob, ext, channelCode, duration_ms) {
    const form = new FormData();
    form.append('audio', blob, `audio.${ext}`);

    const res = await fetch(
      `${API_BASE}/api/transcribe?channel=${encodeURIComponent(channelCode)}&duration_ms=${duration_ms}`,
      { method: 'POST', body: form }
    );
    await handleResponse(res);
    return res.json();
  }

  async function listTranscriptions(channelCode, limit = 20) {
    const res = await fetch(
      `${API_BASE}/api/transcriptions?channel=${encodeURIComponent(channelCode)}&limit=${limit}`
    );
    await handleResponse(res);
    const data = await res.json();
    return data.transcriptions;
  }

  async function deleteTranscription(id, channelCode) {
    const res = await fetch(
      `${API_BASE}/api/transcriptions/${id}?channel=${encodeURIComponent(channelCode)}`,
      { method: 'DELETE' }
    );
    if (res.status !== 204 && res.status !== 404) await handleResponse(res);
  }

  return { getChannel, transcribe, listTranscriptions, deleteTranscription };
})();
