/**
 * Load biomarker JSON via fetch with script-bundle fallback (file:// and offline).
 */
(function () {
  const loaded = new Set();

  function loadScript(src) {
    if (loaded.has(src)) {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = () => {
        loaded.add(src);
        resolve();
      };
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  }

  async function fetchOrBundle(jsonPath, globalVar, bundlePath) {
    if (window[globalVar]) {
      return window[globalVar];
    }

    try {
      const res = await fetch(jsonPath);
      if (res.ok) {
        return await res.json();
      }
    } catch (_) {
      /* fetch blocked (e.g. file://) — fall through to bundle */
    }

    await loadScript(bundlePath);
    if (!window[globalVar]) {
      throw new Error(`Biomarker data unavailable (${globalVar})`);
    }
    return window[globalVar];
  }

  const api = { loadScript, fetchOrBundle };
  window.BiomarkerDataLoader = api;

  /** Wait for loader when consumer scripts run before this file (defer order). */
  window.ensureBiomarkerDataLoader = async function ensureBiomarkerDataLoader() {
    if (window.BiomarkerDataLoader) return window.BiomarkerDataLoader;
    for (let i = 0; i < 100; i++) {
      await new Promise((r) => setTimeout(r, 10));
      if (window.BiomarkerDataLoader) return window.BiomarkerDataLoader;
    }
    await loadScript('js/biomarker-data-loader.js');
    if (!window.BiomarkerDataLoader) {
      throw new Error('data loader missing');
    }
    return window.BiomarkerDataLoader;
  };
})();