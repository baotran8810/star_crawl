/* shortcuts.js — global keyboard bindings for the workspace shell.
 *
 * Most bindings dispatch domain events so other modules stay decoupled.
 * Cmd/Ctrl-K is handled inside palette.js directly for response speed.
 *
 * Per `specs/004-obsidian-ui/contracts/keyboard-shortcuts.md`.
 */
(function () {
  'use strict';

  function inEditable() {
    const el = document.activeElement;
    if (!el) return false;
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return true;
    if (el.isContentEditable) return true;
    return false;
  }

  function activeIdx() {
    const ws = window.workspace; if (!ws) return -1;
    const state = ws.getState();
    return state.tabs.findIndex(t => t.id === state.active_tab_id);
  }
  function tabIds() {
    return window.workspace ? window.workspace.getState().tabs.map(t => t.id) : [];
  }

  document.addEventListener('keydown', (e) => {
    if (e.defaultPrevented) return;
    // Esc — close palette/help overlay handled by individual modules.
    if (e.key === 'Escape') return;

    if (inEditable()) return;

    // Tree toggle: [
    if (e.key === '[' && !e.metaKey && !e.ctrlKey && !e.altKey) {
      e.preventDefault();
      if (window.workspace) {
        const cur = !!window.workspace.getPreference('tree_collapsed');
        window.workspace.setPreference('tree_collapsed', !cur);
        document.body.dataset.treeCollapsed = String(!cur);
      }
      return;
    }

    // Help overlay: ? or Cmd/Ctrl+/
    if ((e.key === '?' && !e.metaKey && !e.ctrlKey) ||
        ((e.metaKey || e.ctrlKey) && e.key === '/')) {
      e.preventDefault();
      showHelp();
      return;
    }

    // Tab navigation: Alt+Right / Alt+Left
    if (e.altKey && (e.key === 'ArrowRight' || e.key === 'ArrowLeft') && !e.shiftKey) {
      e.preventDefault();
      const ids = tabIds(); if (!ids.length) return;
      const idx = activeIdx();
      const next = e.key === 'ArrowRight'
        ? (idx + 1) % ids.length
        : (idx - 1 + ids.length) % ids.length;
      window.workspace.activateTab(ids[next]);
      return;
    }

    // Move active tab: Alt+Shift+Right / Alt+Shift+Left
    if (e.altKey && e.shiftKey && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
      e.preventDefault();
      const ids = tabIds(); const idx = activeIdx();
      if (idx < 0) return;
      const newIdx = e.key === 'ArrowRight'
        ? Math.min(ids.length - 1, idx + 1)
        : Math.max(0, idx - 1);
      window.workspace.reorderTab(ids[idx], newIdx);
      return;
    }

    // Alt+1..9: jump to tab N
    if (e.altKey && !e.shiftKey && !e.metaKey && !e.ctrlKey
        && /^[1-9]$/.test(e.key)) {
      e.preventDefault();
      const ids = tabIds();
      const n = Number(e.key) - 1;
      if (ids[n]) window.workspace.activateTab(ids[n]);
      return;
    }

    // Cmd/Ctrl+W: close active tab. Cmd/Ctrl+Shift+W: close all.
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'w') {
      e.preventDefault();
      if (e.shiftKey) { window.workspace?.closeAllTabs(); }
      else {
        const state = window.workspace?.getState();
        if (state && state.active_tab_id) window.workspace.closeTab(state.active_tab_id);
      }
      return;
    }
  });

  // Help overlay
  let helpDialog = null;
  function showHelp() {
    if (!helpDialog) {
      helpDialog = document.createElement('dialog');
      helpDialog.className = 'help-overlay';
      helpDialog.innerHTML = `
        <h2>Keyboard shortcuts</h2>
        <table>
          <tr><td><kbd>⌘K</kbd></td><td>Command palette</td></tr>
          <tr><td><kbd>⌘W</kbd></td><td>Close active tab</td></tr>
          <tr><td><kbd>⌘⇧W</kbd></td><td>Close all tabs</td></tr>
          <tr><td><kbd>⌥→</kbd> <kbd>⌥←</kbd></td><td>Next / previous tab</td></tr>
          <tr><td><kbd>⌥⇧→</kbd> <kbd>⌥⇧←</kbd></td><td>Move active tab</td></tr>
          <tr><td><kbd>⌥1</kbd>..<kbd>⌥9</kbd></td><td>Jump to tab N</td></tr>
          <tr><td><kbd>[</kbd></td><td>Toggle navigation tree</td></tr>
          <tr><td><kbd>?</kbd></td><td>Show this help</td></tr>
        </table>
        <p><button autofocus onclick="this.closest('dialog').close()">Close</button></p>
      `;
      document.body.appendChild(helpDialog);
    }
    helpDialog.showModal();
  }
})();
