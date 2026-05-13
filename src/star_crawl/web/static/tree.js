/* tree.js — navigation tree interactions.
 *
 * Expand/collapse sources sub-tree via HTMX swap.
 * Click handlers for tree rows are delegated through workspace.js
 * (any element with data-panel-url + data-kind opens a tab).
 *
 * Persists `tree_collapsed` and `tree_expanded_sections` via workspace.setPreference.
 */
(function () {
  'use strict';

  function init() {
    const root = document.getElementById('tree-root');
    if (!root) return;

    // Apply persisted collapsed state to the shell.
    const collapsed = window.workspace && window.workspace.getPreference('tree_collapsed');
    if (collapsed) document.body.dataset.treeCollapsed = 'true';

    // Wire the rail's tree-toggle button.
    const toggleBtn = document.querySelector('.icon-rail [data-section="tree-toggle"]');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const isCollapsed = document.body.dataset.treeCollapsed === 'true';
        const next = !isCollapsed;
        document.body.dataset.treeCollapsed = next ? 'true' : 'false';
        if (window.workspace) window.workspace.setPreference('tree_collapsed', next);
      });
    }

    // Track expand/collapse on section headers. The h3 has hx-get for
    // server-side expand; we toggle the chevron locally on htmx:after-swap.
    root.addEventListener('click', (e) => {
      const h = e.target.closest('h3.tree-section-h[hx-get], h3.tree-section-h[role="button"]');
      if (!h) return;
      // For sections without hx-get (e.g., bookmarks), just toggle chevron.
      const chev = h.querySelector('.chev');
      if (chev && !h.getAttribute('hx-get')) {
        const expanded = chev.textContent.includes('▾');
        chev.textContent = expanded ? '▸' : '▾';
        h.setAttribute('aria-expanded', String(!expanded));
      }
    });

    root.addEventListener('htmx:afterSwap', (e) => {
      // After expanding a section subtree, flip its chevron.
      const sec = e.detail.target.closest('.tree-section');
      if (!sec) return;
      const chev = sec.querySelector('.tree-section-h .chev');
      if (chev) chev.textContent = '▾';
      // Track expanded section in preferences
      const id = sec.dataset.section;
      if (id && window.workspace) {
        const cur = window.workspace.getPreference('tree_expanded_sections') || [];
        if (!cur.includes(id)) {
          window.workspace.setPreference(
            'tree_expanded_sections',
            cur.concat([id]).slice(0, 20)
          );
        }
      }
    });

    // ResponSive — auto-collapse on narrow viewport.
    function syncCollapse() {
      if (window.innerWidth < 900) {
        document.body.dataset.treeCollapsed = 'true';
      }
    }
    window.addEventListener('resize', syncCollapse);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
