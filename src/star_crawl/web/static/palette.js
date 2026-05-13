/* palette.js — command palette overlay.
 *
 * Cmd/Ctrl-K opens a <dialog> with a search input. Two grouped result kinds:
 *   - Objects (articles, runs, sources, keywords) loaded once from
 *     /palette/objects.json
 *   - Workspace actions (static array below)
 *
 * Per `specs/004-obsidian-ui/contracts/keyboard-shortcuts.md` palette section.
 */
(function () {
  'use strict';

  let dialog = null;
  let input = null;
  let resultsEl = null;
  let objectsIndex = null;
  let objectsLoading = null;
  let selectedIndex = 0;
  let currentResults = [];

  const ACTIONS = [
    {
      kind: 'action', id: 'toggle-theme', label: 'Toggle theme',
      subtitle: 'Cycle light · dark · system',
      run: () => {
        const btn = document.getElementById('theme-toggle');
        if (btn) btn.click();
      },
    },
    {
      kind: 'action', id: 'toggle-cluster-color', label: 'Toggle cluster colors',
      subtitle: 'Graph monochrome ↔ colored',
      run: () => {
        if (!window.workspace) return;
        const cur = !!window.workspace.getPreference('cluster_color_enabled');
        window.workspace.setPreference('cluster_color_enabled', !cur);
        const box = document.getElementById('cluster-color-toggle');
        if (box) box.checked = !cur;
      },
    },
    {
      kind: 'action', id: 'close-all-tabs', label: 'Close all tabs',
      subtitle: 'Then auto-open a fresh Graph tab',
      run: () => { if (window.workspace) window.workspace.closeAllTabs(); },
    },
    {
      kind: 'action', id: 'open-graph', label: 'Open Graph tab',
      subtitle: 'Focus or create the topic graph tab',
      run: () => {
        if (!window.workspace) return;
        window.workspace.openTab({
          kind: 'graph', target_id: null,
          title: 'Topic graph', panel_url: '/panel/graph',
        });
      },
    },
    {
      kind: 'action', id: 'rebuild-graph', label: 'Rebuild graph',
      subtitle: 'Run extract-keywords + build-graph (background)',
      run: () => {
        fetch('/graph/rebuild', { method: 'POST' })
          .then(() => alert('Rebuild started — refresh the Graph tab in 30–60s'))
          .catch(e => alert('Rebuild failed: ' + e));
      },
    },
  ];

  // ─── lifecycle ─────────────────────────────────────────────
  function ensureDialog() {
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'palette';
    dialog.className = 'palette';
    dialog.innerHTML = `
      <input type="search" class="palette-input"
             placeholder="Search articles, sources, runs, keywords… or workspace actions"
             autocomplete="off" spellcheck="false" />
      <div class="palette-results" role="listbox"></div>
      <div class="palette-hint">↑↓ navigate · ↵ open · ⌘↵ new tab · esc close</div>
    `;
    document.body.appendChild(dialog);
    input = dialog.querySelector('.palette-input');
    resultsEl = dialog.querySelector('.palette-results');
    input.addEventListener('input', onInput);
    input.addEventListener('keydown', onInputKey);
    dialog.addEventListener('click', onResultClick);
    dialog.addEventListener('cancel', (e) => { e.preventDefault(); close(); });
    return dialog;
  }

  function open() {
    ensureDialog();
    input.value = '';
    selectedIndex = 0;
    dialog.showModal();
    loadObjects();
    render('');
    setTimeout(() => input.focus(), 0);
  }

  function close() {
    if (dialog && dialog.open) dialog.close();
  }

  // ─── object index ──────────────────────────────────────────
  function loadObjects() {
    if (objectsIndex || objectsLoading) return objectsLoading;
    objectsLoading = fetch('/palette/objects.json', { headers: { 'Accept': 'application/json' } })
      .then(r => r.ok ? r.json() : [])
      .then(arr => { objectsIndex = Array.isArray(arr) ? arr : []; return objectsIndex; })
      .catch(() => { objectsIndex = []; return []; });
    return objectsLoading;
  }

  // ─── ranker ────────────────────────────────────────────────
  function score(text, q) {
    if (!q) return 0;
    const lo = text.toLowerCase();
    const i = lo.indexOf(q);
    if (i === -1) return -1;
    // earlier match + shorter text scores higher
    return 1000 - i - text.length * 0.01;
  }

  function search(query) {
    const q = query.toLowerCase().trim();
    const actions = ACTIONS.map(a => ({ ...a, _score: q ? score(a.label, q) : 100 }))
                           .filter(a => a._score >= 0)
                           .sort((a, b) => b._score - a._score);
    if (!objectsIndex) return { actions, objects: [] };
    const objects = q
      ? objectsIndex
          .map(o => ({ ...o, _score: score(o.label, q) }))
          .filter(o => o._score >= 0)
          .sort((a, b) => b._score - a._score)
          .slice(0, 50)
      : objectsIndex.slice(0, 20);
    return { actions, objects };
  }

  // ─── render ────────────────────────────────────────────────
  function render(query) {
    const { actions, objects } = search(query);
    currentResults = [];
    let html = '';
    if (actions.length) {
      html += '<div class="palette-group-h">Workspace actions</div>';
      actions.forEach(a => {
        currentResults.push({ kind: 'action', item: a });
        html += renderRow(a, currentResults.length - 1);
      });
    }
    if (objects.length) {
      html += '<div class="palette-group-h">Objects</div>';
      objects.forEach(o => {
        currentResults.push({ kind: 'object', item: o });
        html += renderRow(o, currentResults.length - 1);
      });
    }
    if (!currentResults.length) {
      html = '<div class="palette-empty">No matches.</div>';
    }
    resultsEl.innerHTML = html;
    selectedIndex = 0;
    highlight();
  }

  function renderRow(it, idx) {
    return (
      '<button type="button" class="palette-row" role="option" data-idx="' + idx + '">' +
      '<span class="palette-row-label">' + esc(it.label) + '</span>' +
      '<span class="palette-row-sub">' + esc(it.subtitle || '') + '</span>' +
      '<span class="palette-row-kind">' + esc(it.kind) + '</span>' +
      '</button>'
    );
  }

  function highlight() {
    resultsEl.querySelectorAll('.palette-row').forEach((el, i) => {
      el.classList.toggle('active', i === selectedIndex);
      if (i === selectedIndex) el.scrollIntoView({ block: 'nearest' });
    });
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, m =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  // ─── actions ───────────────────────────────────────────────
  function activate(idx, opts) {
    const sel = currentResults[idx];
    if (!sel) return;
    if (sel.kind === 'action') {
      close();
      try { sel.item.run(); } catch (e) { console.warn('palette action failed', e); }
      return;
    }
    const obj = sel.item;
    if (!obj.panel_url) {
      // Keywords have no panel — focus on the graph tab instead.
      if (window.workspace) {
        const id = window.workspace.openTab({
          kind: 'graph', target_id: null,
          title: 'Topic graph', panel_url: '/panel/graph', focus: true,
        });
        // Future: pass kwId to focus the node.
      }
      close();
      return;
    }
    if (window.workspace) {
      window.workspace.openTab({
        kind: obj.kind, target_id: obj.id,
        title: obj.label, panel_url: obj.panel_url,
        focus: !(opts && opts.background),
      });
    }
    close();
  }

  // ─── input + keys ──────────────────────────────────────────
  function onInput() { render(input.value); }
  function onInputKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (currentResults.length) {
        selectedIndex = (selectedIndex + 1) % currentResults.length;
        highlight();
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (currentResults.length) {
        selectedIndex = (selectedIndex - 1 + currentResults.length) % currentResults.length;
        highlight();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      activate(selectedIndex, { background: e.metaKey || e.ctrlKey });
    }
  }
  function onResultClick(e) {
    const row = e.target.closest('.palette-row');
    if (!row) return;
    activate(Number(row.dataset.idx), { background: e.metaKey || e.ctrlKey });
  }

  // ─── public open ───────────────────────────────────────────
  document.addEventListener('palette:open', open);
  // Also listen directly on Cmd/Ctrl-K — kept here so shortcuts.js can stay
  // a thin dispatch table.
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      const isText = ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName);
      if (isText && !dialog?.open) return;
      e.preventDefault();
      if (dialog && dialog.open) close(); else open();
    }
  });
})();
