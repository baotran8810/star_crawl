/* theme.js — light/dark/system theme controller.
 *
 * Runs synchronously in <head> before first paint to avoid flash-of-wrong-theme,
 * then attaches a click handler to the status-bar toggle once DOM is ready.
 *
 * State stored on `window.workspace.theme`. Cycle: system → dark → light → system.
 */
(function () {
  'use strict';
  const STORAGE_KEY = 'star_crawl.workspace.v1';

  function readSavedTheme() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      const t = raw && raw.theme;
      return ['light', 'dark', 'system'].includes(t) ? t : 'system';
    } catch (_) { return 'system'; }
  }

  function resolve(pref) {
    if (pref === 'light' || pref === 'dark') return pref;
    return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark' : 'light';
  }

  function apply(pref) {
    document.documentElement.dataset.theme = resolve(pref);
  }

  // Boot synchronously.
  apply(readSavedTheme());

  // Re-apply if user picks "system" and OS preference changes.
  if (window.matchMedia) {
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      const t = (window.workspace && window.workspace.getPreference('theme')) || readSavedTheme();
      if (t === 'system') apply('system');
    });
  }

  function wireToggle() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const cur = (window.workspace && window.workspace.getPreference('theme')) || 'system';
      const next = cur === 'system' ? 'dark' : (cur === 'dark' ? 'light' : 'system');
      if (window.workspace) window.workspace.setPreference('theme', next);
      apply(next);
      btn.title = 'Theme: ' + next;
    });
  }

  // workspace:theme-changed → re-apply (handles palette command palette toggles too).
  document.addEventListener('workspace:theme-changed', (e) => {
    apply(e.detail && e.detail.theme || readSavedTheme());
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireToggle);
  } else {
    wireToggle();
  }
})();
