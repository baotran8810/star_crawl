/* workspace.js — Obsidian-style tab manager + localStorage persistence.
 *
 * Owns:
 *   - the WorkspaceState envelope (see contracts/workspace-state.md)
 *   - the tab bar DOM
 *   - the per-tab panel containers + content lifecycle
 *   - browser history integration (back/forward switches tabs)
 *   - drag-and-drop reorder
 *   - inline-unavailable handling
 *
 * Other modules subscribe via `document.addEventListener('workspace:*', …)`.
 */

(function () {
  'use strict';

  // ─────────────────────────────────────── constants ──
  const STORAGE_KEY = 'star_crawl.workspace.v1';
  const SCHEMA_VERSION = 1;
  const MAX_TABS = 50;
  const ALLOWED_KINDS = new Set(['article', 'run', 'source', 'search', 'graph']);
  const DEFAULT_GRAPH = {
    kind: 'graph', target_id: null,
    title: 'Topic graph', panel_url: '/panel/graph',
  };

  // ─────────────────────────────────────── helpers ────
  const $ = (sel, root) => (root || document).querySelector(sel);
  function newId() {
    return (crypto.randomUUID && crypto.randomUUID()) ||
           ('t-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 9));
  }
  function nowISO() { return new Date().toISOString(); }
  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail }));
  }

  // ──────────────────────────────────── state schema ──
  function defaultState() {
    const id = newId();
    return {
      schema_version: SCHEMA_VERSION,
      tabs: [{
        id, ...DEFAULT_GRAPH,
        scroll_y: 0,
        graph_state: { zoom: 1.0, pan_x: 0, pan_y: 0, focused_kw_id: null },
        created_at: nowISO(),
      }],
      active_tab_id: id,
      theme: 'system',
      cluster_color_enabled: false,
      tree_collapsed: false,
      tree_expanded_sections: ['sources'],
      updated_at: nowISO(),
    };
  }

  function validate(raw) {
    if (!raw || typeof raw !== 'object' || raw.schema_version !== SCHEMA_VERSION) {
      return defaultState();
    }
    const tabs = Array.isArray(raw.tabs) ? raw.tabs : [];
    const clean = [];
    for (const t of tabs.slice(0, MAX_TABS)) {
      if (!t || !t.id || !ALLOWED_KINDS.has(t.kind)) continue;
      if (typeof t.panel_url !== 'string' || !t.panel_url.startsWith('/panel/')) continue;
      const sy = Number(t.scroll_y) || 0;
      const tab = {
        id: String(t.id),
        kind: t.kind,
        target_id: t.target_id == null ? null : String(t.target_id),
        title: typeof t.title === 'string' ? t.title.slice(0, 80) : t.kind,
        panel_url: t.panel_url,
        scroll_y: Math.max(0, Math.min(100000, sy)),
        graph_state: null,
        created_at: t.created_at || nowISO(),
      };
      if (tab.kind === 'graph') {
        const gs = t.graph_state || {};
        tab.graph_state = {
          zoom: Math.max(0.1, Math.min(5.0, Number(gs.zoom) || 1.0)),
          pan_x: Number(gs.pan_x) || 0,
          pan_y: Number(gs.pan_y) || 0,
          focused_kw_id: gs.focused_kw_id == null ? null : Number(gs.focused_kw_id) || null,
        };
      }
      clean.push(tab);
    }
    const active = clean.find(t => t.id === raw.active_tab_id)
      ? raw.active_tab_id
      : (clean[0] ? clean[0].id : null);
    return {
      schema_version: SCHEMA_VERSION,
      tabs: clean,
      active_tab_id: active,
      theme: ['light', 'dark', 'system'].includes(raw.theme) ? raw.theme : 'system',
      cluster_color_enabled: !!raw.cluster_color_enabled,
      tree_collapsed: !!raw.tree_collapsed,
      tree_expanded_sections: Array.isArray(raw.tree_expanded_sections)
        ? raw.tree_expanded_sections.slice(0, 20).map(String)
        : ['sources'],
      updated_at: raw.updated_at || nowISO(),
    };
  }

  function loadState() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      return validate(raw);
    } catch (_) {
      return defaultState();
    }
  }

  let _persistTimer = null;
  function persist(sync) {
    state.updated_at = nowISO();
    const write = () => {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
      catch (e) { console.warn('workspace: persist failed', e); }
    };
    if (sync) { if (_persistTimer) { clearTimeout(_persistTimer); _persistTimer = null; } write(); return; }
    if (_persistTimer) return;
    const sched = window.requestIdleCallback || ((cb) => setTimeout(cb, 250));
    _persistTimer = sched(() => { _persistTimer = null; write(); });
  }

  // ─────────────────────────────── state singleton ────
  let state = loadState();

  // ───────────────────────────── DOM accessors ────────
  function $tabBar() { return $('.tab-bar'); }
  function $panels() { return $('#workspace-panels'); }
  function $tabEl(id) { return $('.tab[data-tab-id="' + cssEsc(id) + '"]'); }
  function $panelEl(id) { return $('.tab-panel[data-tab-id="' + cssEsc(id) + '"]'); }
  function cssEsc(s) { return CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); }

  // ─────────────────────────── rendering: tab bar ─────
  function renderTabBar() {
    const bar = $tabBar();
    if (!bar) return;
    bar.innerHTML = state.tabs.map(t => tabHTML(t)).join('');
    setupTabBarHandlers();
  }
  function tabHTML(t) {
    const isActive = t.id === state.active_tab_id;
    return (
      '<button type="button" class="tab" role="tab"' +
        ' draggable="true"' +
        ' data-tab-id="' + esc(t.id) + '"' +
        ' aria-selected="' + (isActive ? 'true' : 'false') + '"' +
        ' tabindex="' + (isActive ? '0' : '-1') + '">' +
      '<span class="label">' + esc(t.title || t.kind) + '</span>' +
      '<span class="close" data-close="' + esc(t.id) + '" title="Close (⌘W)">×</span>' +
      '</button>'
    );
  }
  function setupTabBarHandlers() {
    const bar = $tabBar();
    if (!bar || bar.dataset.wired === '1') return;
    bar.dataset.wired = '1';
    bar.addEventListener('click', onTabBarClick);
    bar.addEventListener('dragstart', onDragStart);
    bar.addEventListener('dragover', onDragOver);
    bar.addEventListener('drop', onDrop);
    bar.addEventListener('dragend', onDragEnd);
    bar.addEventListener('auxclick', e => { // middle-click close
      if (e.button === 1) {
        const tab = e.target.closest('.tab');
        if (tab) { e.preventDefault(); closeTab(tab.dataset.tabId); }
      }
    });
  }
  function onTabBarClick(e) {
    const closeBtn = e.target.closest('[data-close]');
    if (closeBtn) { e.stopPropagation(); closeTab(closeBtn.dataset.close); return; }
    const tabEl = e.target.closest('.tab');
    if (tabEl) activateTab(tabEl.dataset.tabId);
  }

  // ─────────────────────────── rendering: panels ──────
  function renderPanel(tab) {
    const panels = $panels();
    if (!panels) return null;
    let el = $panelEl(tab.id);
    if (el) return el;
    el = document.createElement('section');
    el.className = 'tab-panel';
    el.dataset.tabId = tab.id;
    el.setAttribute('role', 'tabpanel');
    el.hidden = true;
    el.addEventListener('scroll', () => onPanelScroll(tab.id, el.scrollTop));
    panels.appendChild(el);
    return el;
  }
  function fetchPanel(tab) {
    const el = $panelEl(tab.id) || renderPanel(tab);
    if (!el) return Promise.resolve(null);
    if (el.dataset.loaded === '1') return Promise.resolve(el);
    if (!window.htmx) {
      el.innerHTML = '<div class="placeholder">HTMX not loaded; cannot fetch panel.</div>';
      return Promise.resolve(el);
    }
    return new Promise((resolve) => {
      htmx.ajax('GET', tab.panel_url, { target: el, swap: 'innerHTML' })
        .then(() => {
          el.dataset.loaded = '1';
          if (tab.kind === 'graph' && window.starcrawlGraph) {
            try {
              const cy = window.starcrawlGraph.boot(el);
              if (cy) attachGraphPersistence(tab, cy);
            } catch (e) { console.warn('graph boot failed', e); }
          }
          resolve(el);
        })
        .catch((err) => {
          console.warn('panel fetch failed', tab.panel_url, err);
          el.innerHTML = renderUnavailable(tab, err && err.message);
          resolve(el);
        });
    });
  }
  function renderUnavailable(tab, reason) {
    return (
      '<div class="panel-unavailable">' +
      '<h2>This tab can no longer be opened.</h2>' +
      (reason ? '<p class="muted">' + esc(String(reason)) + '</p>' : '') +
      '<p class="muted">Original URL: <code>' + esc(tab.panel_url) + '</code></p>' +
      '<p><button type="button" class="pill" data-action="close-active-tab">Close this tab</button></p>' +
      '</div>'
    );
  }
  function onPanelScroll(id, top) {
    const tab = state.tabs.find(t => t.id === id);
    if (!tab) return;
    tab.scroll_y = Math.max(0, Math.min(100000, Math.round(top)));
    persist();
  }

  // ───────────────────── graph tab persistence ────────
  function attachGraphPersistence(tab, cy) {
    if (!tab.graph_state) tab.graph_state = { zoom: 1, pan_x: 0, pan_y: 0, focused_kw_id: null };
    if (tab.graph_state.zoom && tab.graph_state.zoom !== 1) {
      try { cy.zoom(tab.graph_state.zoom); cy.pan({ x: tab.graph_state.pan_x, y: tab.graph_state.pan_y }); }
      catch (_) {}
    }
    let saveTimer = null;
    const save = () => {
      saveTimer = null;
      try {
        tab.graph_state.zoom = cy.zoom();
        const p = cy.pan();
        tab.graph_state.pan_x = p.x;
        tab.graph_state.pan_y = p.y;
        persist();
      } catch (_) {}
    };
    const schedule = () => {
      if (saveTimer) return;
      saveTimer = setTimeout(save, 300);
    };
    cy.on('zoom pan', schedule);
    cy.on('tap', 'node', (evt) => {
      const kwId = evt.target.data('kw_id');
      tab.graph_state.focused_kw_id = kwId || null;
      persist();
    });
  }
  function resizeGraphTab(tab) {
    const el = $panelEl(tab.id);
    if (!el) return;
    const cy = window.starcrawlGraph && el._cy;
    // graph.js doesn't expose cy externally — call boot()'s side-effect:
    // schedule a resize via window event which our refactor listens to.
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'));
    });
  }

  // ───────────────────────── tab API ──────────────────
  function openTab(opts) {
    if (!opts || !ALLOWED_KINDS.has(opts.kind)) {
      console.warn('openTab: bad kind', opts);
      return null;
    }
    if (!opts.panel_url || !opts.panel_url.startsWith('/panel/')) {
      console.warn('openTab: bad panel_url', opts);
      return null;
    }
    // De-dupe: same kind + target_id reuses the existing tab.
    const existing = state.tabs.find(t =>
      t.kind === opts.kind && String(t.target_id) === String(opts.target_id ?? null)
    );
    if (existing) {
      if (opts.focus !== false) activateTab(existing.id);
      return existing.id;
    }
    if (state.tabs.length >= MAX_TABS) {
      console.warn('openTab: MAX_TABS reached');
      return null;
    }
    const tab = {
      id: newId(),
      kind: opts.kind,
      target_id: opts.target_id == null ? null : String(opts.target_id),
      title: (opts.title || opts.kind).slice(0, 80),
      panel_url: opts.panel_url,
      scroll_y: 0,
      graph_state: opts.kind === 'graph'
        ? { zoom: 1.0, pan_x: 0, pan_y: 0, focused_kw_id: null }
        : null,
      created_at: nowISO(),
    };
    state.tabs.push(tab);
    persist(true);
    emit('workspace:tab-opened', { tab });
    renderTabBar();
    renderPanel(tab);
    fetchPanel(tab);
    if (opts.focus !== false) activateTab(tab.id);
    return tab.id;
  }

  function closeTab(id) {
    const idx = state.tabs.findIndex(t => t.id === id);
    if (idx === -1) return;
    const wasActive = (state.active_tab_id === id);
    const closed = state.tabs[idx];
    state.tabs.splice(idx, 1);
    const panelEl = $panelEl(id);
    if (panelEl) panelEl.remove();

    if (state.tabs.length === 0) {
      // FR-021: auto-open default graph tab.
      state.active_tab_id = null;
      persist(true);
      emit('workspace:tab-closed', { tab_id: id, was_active: wasActive });
      openTab({ ...DEFAULT_GRAPH, focus: true });
      return;
    }
    if (wasActive) {
      const next = state.tabs[Math.min(idx, state.tabs.length - 1)];
      activateTab(next.id);
    } else {
      renderTabBar();
    }
    persist(true);
    emit('workspace:tab-closed', { tab_id: id, was_active: wasActive });
  }

  function activateTab(id) {
    const tab = state.tabs.find(t => t.id === id);
    if (!tab) return;
    const prev = state.active_tab_id;
    if (prev === id) {
      // still ensure DOM visibility on first activation
      const el = $panelEl(id);
      if (el && el.hidden) showPanel(tab);
      return;
    }
    if (prev) hidePanel(prev);
    state.active_tab_id = id;
    persist();
    renderTabBar();
    showPanel(tab);
    pushHistory(id);
    emit('workspace:tab-activated', { tab_id: id, prev_tab_id: prev });
  }

  function showPanel(tab) {
    const el = $panelEl(tab.id) || renderPanel(tab);
    if (!el) return;
    el.hidden = false;
    // Restore scroll on the next frame so the panel has size first.
    requestAnimationFrame(() => {
      el.scrollTop = tab.scroll_y || 0;
      if (tab.kind === 'graph') {
        // Cy needs a resize after becoming visible.
        window.dispatchEvent(new Event('resize'));
      }
    });
  }
  function hidePanel(id) {
    const el = $panelEl(id);
    if (!el) return;
    const tab = state.tabs.find(t => t.id === id);
    if (tab) tab.scroll_y = el.scrollTop || 0;
    el.hidden = true;
  }

  function reorderTab(id, newIdx) {
    const idx = state.tabs.findIndex(t => t.id === id);
    if (idx === -1) return;
    const clamped = Math.max(0, Math.min(state.tabs.length - 1, newIdx));
    if (clamped === idx) return;
    const [tab] = state.tabs.splice(idx, 1);
    state.tabs.splice(clamped, 0, tab);
    persist(true);
    renderTabBar();
    emit('workspace:tab-reordered', { tab_id: id, new_index: clamped });
  }

  function closeAllTabs() {
    const ids = state.tabs.map(t => t.id);
    state.tabs = [];
    state.active_tab_id = null;
    persist(true);
    $panels().querySelectorAll('.tab-panel').forEach(el => el.remove());
    ids.forEach(id => emit('workspace:tab-closed', { tab_id: id, was_active: false }));
    // FR-021 — re-open default.
    openTab({ ...DEFAULT_GRAPH, focus: true });
  }

  // ────────────────────────── drag-and-drop ───────────
  let _dragId = null;
  function onDragStart(e) {
    const tab = e.target.closest('.tab');
    if (!tab) return;
    _dragId = tab.dataset.tabId;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', _dragId);
    tab.classList.add('dragging');
  }
  function onDragOver(e) {
    if (!_dragId) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const over = e.target.closest('.tab');
    if (over && over.dataset.tabId !== _dragId) {
      $tabBar().querySelectorAll('.tab.drop-target').forEach(el => el.classList.remove('drop-target'));
      over.classList.add('drop-target');
    }
  }
  function onDrop(e) {
    if (!_dragId) return;
    e.preventDefault();
    const target = e.target.closest('.tab');
    if (target && target.dataset.tabId !== _dragId) {
      const targetIdx = state.tabs.findIndex(t => t.id === target.dataset.tabId);
      reorderTab(_dragId, targetIdx);
    }
    onDragEnd();
  }
  function onDragEnd() {
    const bar = $tabBar();
    if (bar) {
      bar.querySelectorAll('.tab.dragging').forEach(el => el.classList.remove('dragging'));
      bar.querySelectorAll('.tab.drop-target').forEach(el => el.classList.remove('drop-target'));
    }
    _dragId = null;
  }

  // ────────────────────────── history ─────────────────
  function pushHistory(id) {
    try {
      if (history.state && history.state.tabId === id) return;
      history.pushState({ tabId: id }, '', null);
    } catch (_) {}
  }
  function onPopState(e) {
    const st = e.state || {};
    if (st.tabId && state.tabs.find(t => t.id === st.tabId)) {
      // Avoid pushing again from inside activateTab.
      const target = st.tabId;
      const prev = state.active_tab_id;
      if (prev !== target) {
        if (prev) hidePanel(prev);
        state.active_tab_id = target;
        renderTabBar();
        const tab = state.tabs.find(t => t.id === target);
        if (tab) showPanel(tab);
        emit('workspace:tab-activated', { tab_id: target, prev_tab_id: prev });
      }
    }
  }

  // ───────────────────────── activation links ─────────
  // Any element with data-panel-url + data-kind opens a tab on click.
  // Middle-click / Cmd/Ctrl-click → background tab.
  function onActivationClick(e) {
    const trig = e.target.closest('[data-panel-url][data-kind]');
    if (!trig) return;
    e.preventDefault();
    const focus = !(e.metaKey || e.ctrlKey || e.button === 1);
    openTab({
      kind: trig.dataset.kind,
      target_id: trig.dataset.targetId || null,
      title: trig.dataset.title || trig.textContent.trim(),
      panel_url: trig.dataset.panelUrl,
      focus,
    });
  }
  function onActivationAux(e) {
    if (e.button !== 1) return;
    const trig = e.target.closest('[data-panel-url][data-kind]');
    if (!trig) return;
    e.preventDefault();
    openTab({
      kind: trig.dataset.kind,
      target_id: trig.dataset.targetId || null,
      title: trig.dataset.title || trig.textContent.trim(),
      panel_url: trig.dataset.panelUrl,
      focus: false,
    });
  }

  // ────────────────────── unavailable button ──────────
  function onUnavailableClick(e) {
    const btn = e.target.closest('[data-action="close-active-tab"]');
    if (!btn) return;
    if (state.active_tab_id) closeTab(state.active_tab_id);
  }

  // ────────────────────────────── init ────────────────
  function init() {
    // Remove the bootstrap empty-state placeholder once we take over panels.
    const empty = $('#empty-state');
    if (empty) empty.remove();

    // Render panels for restored tabs; fetch their content lazily.
    state.tabs.forEach(tab => {
      renderPanel(tab);
      fetchPanel(tab);
    });
    renderTabBar();

    if (state.tabs.length === 0) {
      openTab({ ...DEFAULT_GRAPH, focus: true });
    } else {
      const id = state.tabs.find(t => t.id === state.active_tab_id)
        ? state.active_tab_id : state.tabs[0].id;
      activateTab(id);
    }

    document.addEventListener('click', onActivationClick);
    document.addEventListener('auxclick', onActivationAux);
    document.addEventListener('click', onUnavailableClick);
    window.addEventListener('popstate', onPopState);

    emit('workspace:state-restored', {
      tab_count: state.tabs.length,
      restored_from_storage: state.tabs.length > 1, // >1 means more than the default
    });
  }

  // ─────────────────────────── escape helpers ─────────
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, m =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  // ─────────────────────────── public API ─────────────
  window.workspace = {
    openTab, closeTab, activateTab, reorderTab, closeAllTabs,
    getState: () => JSON.parse(JSON.stringify(state)),
    getActiveTab: () => state.tabs.find(t => t.id === state.active_tab_id) || null,
    setPreference: (key, val) => {
      const allowed = ['theme', 'cluster_color_enabled', 'tree_collapsed', 'tree_expanded_sections'];
      if (!allowed.includes(key)) { console.warn('unknown pref', key); return; }
      state[key] = val;
      persist(true);
      const evt = 'workspace:' + key.replace(/_/g, '-') + '-changed';
      emit(evt, { [key]: val });
    },
    getPreference: (key) => state[key],
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
