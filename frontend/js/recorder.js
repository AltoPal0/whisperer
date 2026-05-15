/* recorder.js — MediaRecorder wrapper avec détection du format audio */

const Recorder = (() => {
  let mediaRecorder = null;
  let chunks = [];
  let startTime = null;

  function getSupportedMimeType() {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ];
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return '';
  }

  function mimeToExtension(mime) {
    if (mime.includes('webm')) return 'webm';
    if (mime.includes('ogg'))  return 'ogg';
    if (mime.includes('mp4'))  return 'mp4';
    return 'audio';
  }

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = getSupportedMimeType();
    const options = mimeType ? { mimeType } : {};

    chunks = [];
    startTime = Date.now();
    mediaRecorder = new MediaRecorder(stream, options);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    mediaRecorder.start(250);
    return stream;
  }

  function stop() {
    return new Promise((resolve) => {
      if (!mediaRecorder) { resolve(null); return; }

      const duration = Date.now() - startTime;
      const mimeType = mediaRecorder.mimeType || 'audio/webm';

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType });
        const ext  = mimeToExtension(mimeType);

        // Libère le micro
        mediaRecorder.stream.getTracks().forEach(t => t.stop());
        mediaRecorder = null;
        chunks = [];

        resolve({ blob, ext, duration_ms: duration });
      };

      mediaRecorder.stop();
    });
  }

  function isRecording() {
    return mediaRecorder !== null && mediaRecorder.state === 'recording';
  }

  return { start, stop, isRecording };
})();
