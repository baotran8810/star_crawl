// Cytoscape graph initialization + interactions.
//
// Two entry paths:
//   1. Legacy direct route /graph (base.html chrome) — auto-boots on DOMContentLoaded
//      against `document` as root, like before.
//   2. Workspace shell — `window.starcrawlGraph.boot(rootEl)` is called by
//      workspace.js after a graph tab's content is fetched into a panel.
//      Multiple graph tabs each get their own cy instance scoped to rootEl.

(function () {
  function bootGraph(rootEl) {
    rootEl = rootEl || document;
    const root = rootEl;
    const $ = (sel) => root.querySelector(sel);
    const dataNode = $('#cy-data');
    if (!dataNode) return null;

  // ─────────── palette & helpers ───────────
  function readPayload() {
    try {
      return JSON.parse(dataNode.textContent || '{}');
    } catch (e) {
      console.error('graph: invalid payload', e);
      return { nodes: [], edges: [] };
    }
  }

  // Smaller label-threshold for cleanliness; big nodes get labels, small
  // nodes only on hover.
  const LABEL_FREQ_THRESHOLD = 5;

  let payload = readPayload();

  // ─────────── cytoscape instance ───────────
  const cy = cytoscape({
    container: $('#cy'),
    elements: { nodes: payload.nodes || [], edges: payload.edges || [] },
    minZoom: 0.25,
    maxZoom: 3.0,
    wheelSensitivity: 0.25,
    layout: layoutOpts(),
    style: [
      // Base node — pill shape with cluster fill + soft border. Size + font
      // scale with doc_freq via a precomputed `size` field (sqrt of doc_freq)
      // so the long tail compresses and the top hubs visibly dominate.
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'background-opacity': 0.95,
          'border-width': 1.5,
          'border-color': 'data(color)',
          'border-opacity': 1,
          'color': '#fff',
          'font-size': 'mapData(size, 0, 10, 8, 15)',
          'font-weight': 600,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-outline-width': 2,
          'text-outline-color': 'data(color)',
          'text-outline-opacity': 1,
          'width':  'mapData(size, 0, 10, 10, 96)',
          'height': 'mapData(size, 0, 10, 10, 96)',
          'min-zoomed-font-size': 6,
          'overlay-opacity': 0,
          'transition-property': 'background-color, border-color, border-width, opacity',
          'transition-duration': '180ms',
        },
      },
      // Default: no label. A dynamic zoom handler (below) toggles per-node
      // labels by adding/removing the .show-label class. This lets the
      // graph progressively reveal smaller nodes as the user zooms in,
      // instead of being stuck at a single static threshold.
      {
        selector: 'node',
        style: { 'label': '' },
      },
      {
        selector: 'node.show-label',
        style: { 'label': 'data(display)' },
      },

      // Edges — intra-cluster edges keep the cluster colour (creates a soft
      // "halo" around each community); inter-cluster edges fade to neutral
      // gray so they no longer dominate the canvas. Opacity scales with NPMI.
      {
        selector: 'edge',
        style: {
          'width': 'mapData(npmi, 0.10, 1.0, 0.8, 5)',
          'line-color': 'data(color)',
          'line-opacity': 'mapData(npmi, 0.10, 1.0, 0.10, 0.45)',
          'curve-style': 'straight',
          'transition-property': 'line-opacity, width, line-color',
          'transition-duration': '180ms',
        },
      },
      {
        selector: 'edge.cross-cluster',
        style: {
          'line-color': '#bdc3c7',
          'line-opacity': 'mapData(npmi, 0.10, 1.0, 0.06, 0.22)',
        },
      },

      // Hover state — node grows a tiny border halo + label appears
      {
        selector: 'node.hovered',
        style: {
          'border-width': 5,
          'border-opacity': 0.55,
          'label': 'data(display)',
          'z-index': 99,
        },
      },
      {
        selector: 'edge.hovered',
        style: {
          'line-opacity': 0.9,
          'width': 'mapData(npmi, 0.10, 1.0, 2, 8)',
        },
      },
      {
        selector: 'node.neighbor-of-hovered',
        style: {
          'label': 'data(display)',
          'border-width': 3,
          'z-index': 50,
        },
      },

      // Selected (click-locked focus) state
      {
        selector: 'node.selected',
        style: {
          'border-width': 6,
          'border-color': '#d95f3a',
          'border-opacity': 0.9,
          'label': 'data(display)',
          'z-index': 100,
        },
      },

      // Faded — used while focus-mode is active to demote non-neighbors
      { selector: '.faded', style: { opacity: 0.08 } },
    ],
  });

  function layoutOpts() {
    return {
      name: 'fcose',
      animate: false,
      randomize: true,
      quality: 'default',
      nodeRepulsion: 14000,
      idealEdgeLength: 100,
      edgeElasticity: 0.35,
      gravity: 0.30,
      gravityRangeCompound: 1.0,
      numIter: 3000,
      tile: true,
      tilingPaddingHorizontal: 18,
      tilingPaddingVertical: 18,
      nodeSeparation: 110,
    };
  }

  // ─────────── per-node size + edge tinting ───────────
  // Precompute a sqrt-compressed `size` so big hubs visibly dominate
  // without crowding the small nodes; Cytoscape's mapData then linearly
  // ramps this into pixel width.
  function annotateNodes() {
    let maxFreq = 1;
    cy.nodes().forEach(function (n) {
      const f = n.data('doc_freq') || 1;
      if (f > maxFreq) maxFreq = f;
    });
    const denom = Math.sqrt(maxFreq) || 1;
    cy.nodes().forEach(function (n) {
      const f = n.data('doc_freq') || 1;
      // 0..10 scale so the style `mapData(size, 0, 10, ...)` lines up
      n.data('size', (Math.sqrt(f) / denom) * 10);
    });
  }

  // Edge colour follows the source node's cluster; if the two endpoints
  // belong to different clusters we mark the edge so it falls into the
  // neutral-gray `.cross-cluster` style above.
  function tintEdgesFromSource() {
    cy.edges().forEach(function (e) {
      const src = e.source();
      const dst = e.target();
      e.data('color', src.data('color'));
      const srcC = src.data('cluster_id');
      const dstC = dst.data('cluster_id');
      if (srcC && dstC && srcC !== dstC) {
        e.addClass('cross-cluster');
      } else {
        e.removeClass('cross-cluster');
      }
    });
  }

  // Monochrome mode — replace each node's color with a CSS-variable-driven
  // grayscale shade chosen by doc_freq (hub = darker, rare = lighter).
  // Keeps cluster_id intact so toggling colors back works.
  function readCssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }
  function applyColorMode() {
    const useCluster = !!(window.workspace && window.workspace.getPreference('cluster_color_enabled'));
    if (useCluster) {
      cy.nodes().forEach(function (n) {
        const orig = n.data('cluster_color') || n.data('color');
        n.data('color', orig);
      });
      tintEdgesFromSource();
      return;
    }
    // Monochrome — pick three shades from CSS vars.
    const hub = readCssVar('--graph-node-hub', '#18181b');
    const mid = readCssVar('--graph-node', '#3f3f46');
    const faint = readCssVar('--graph-node-faint', '#71717a');
    const edge = readCssVar('--graph-edge', '#d4d4d8');
    // Save original cluster color once so we can restore on toggle.
    cy.nodes().forEach(function (n) {
      if (!n.data('cluster_color')) n.data('cluster_color', n.data('color'));
      const f = n.data('doc_freq') || 0;
      const shade = f >= 30 ? hub : (f >= 6 ? mid : faint);
      n.data('color', shade);
    });
    cy.edges().forEach(function (e) {
      e.data('color', edge);
      e.removeClass('cross-cluster');
    });
  }

  annotateNodes();
  applyColorMode();
  // Sync the cluster-color toggle checkbox to the persisted preference.
  const ccBox = $('#cluster-color-toggle');
  if (ccBox && window.workspace) {
    ccBox.checked = !!window.workspace.getPreference('cluster_color_enabled');
  }

  // ─────────── zoom-aware labels ───────────
  // As the user zooms in we progressively reveal labels on smaller nodes
  // so detail is visible at every scale. Hover/select still force a label
  // via their own selectors regardless of zoom.
  function labelThresholdFor(zoom) {
    // More aggressive: small zoom-ins reveal many more keywords.
    if (zoom >= 1.3) return 1;   // ≥130%: every node (all keywords)
    if (zoom >= 1.0) return 2;   // ≥100%: skip only the very rarest
    if (zoom >= 0.75) return 4;
    return 6;                     // zoomed-out: clean view
  }

  let labelThresholdCache = null;
  function updateLabelVisibility() {
    const z = cy.zoom();
    const threshold = labelThresholdFor(z);
    if (threshold === labelThresholdCache) return;
    labelThresholdCache = threshold;
    cy.batch(function () {
      cy.nodes().forEach(function (n) {
        const visible = (n.data('doc_freq') || 0) >= threshold;
        n.toggleClass('show-label', visible);
      });
    });
    const ind = $('#graph-zoom-ind');
    if (ind) {
      ind.textContent =
        (z * 100).toFixed(0) + '%' + ' · labels ≥ ' + threshold + ' docs';
    }
  }

  cy.on('zoom', updateLabelVisibility);
  cy.on('layoutstop', updateLabelVisibility);

  // Keep the cy canvas accurate when the surrounding column resizes
  // (window resize, fullscreen toggle, finder layout shift, tab activate).
  function resizeCy() {
    cy.resize();
    cy.fit(undefined, 60);
    updateLabelVisibility();
  }
  window.addEventListener('resize', resizeCy);
  const ro = new ResizeObserver(function () { cy.resize(); });
  const cyContainer = $('#cy');
  if (cyContainer) ro.observe(cyContainer);

  // ─────────── hover interaction ───────────
  cy.on('mouseover', 'node', function (evt) {
    const node = evt.target;
    node.addClass('hovered');
    node.connectedEdges().addClass('hovered');
    node.neighborhood('node').addClass('neighbor-of-hovered');
  });
  cy.on('mouseout', 'node', function (evt) {
    const node = evt.target;
    node.removeClass('hovered');
    node.connectedEdges().removeClass('hovered');
    cy.nodes('.neighbor-of-hovered').removeClass('neighbor-of-hovered');
  });

  // ─────────── click-to-focus ───────────
  function focusNode(node) {
    cy.elements().removeClass('faded');
    cy.nodes('.selected').removeClass('selected');
    const visible = node.closedNeighborhood();
    cy.elements().difference(visible).addClass('faded');
    node.addClass('selected');
    cy.animate(
      { fit: { eles: visible, padding: 80 } },
      { duration: 300, easing: 'ease-out-quad' }
    );
  }

  cy.on('tap', 'node', function (evt) {
    const node = evt.target;
    const kwId = node.data('kw_id');
    if (!kwId) return;
    focusNode(node);
    htmx.ajax('GET', '/keywords/' + kwId, { target: '#keyword-panel', swap: 'innerHTML' });
  });
  cy.on('tap', function (evt) {
    if (evt.target === cy) {
      cy.elements().removeClass('faded');
      cy.nodes('.selected').removeClass('selected');
    }
  });

  // Type-ahead suggestion / side-panel neighbor click → focus the matching node
  root.addEventListener('click', function (e) {
    const link = e.target.closest('a[data-kw-id]');
    if (!link) return;
    const kwId = link.dataset.kwId;
    const node = cy.getElementById('k_' + kwId);
    if (node && node.nonempty()) {
      focusNode(node);
    }
  });

  // ─────────── refresh on HTMX data swap ───────────
  root.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target.id !== 'cy-data') return;
    payload = readPayload();
    cy.json({ elements: { nodes: payload.nodes || [], edges: payload.edges || [] } });
    annotateNodes();
    applyColorMode();
    cy.layout(layoutOpts()).run();
    renderLegend();
    labelThresholdCache = null;  // force a recompute even if zoom unchanged
    updateLabelVisibility();
  });

  // ─────────── workspace events: toggle cluster color, theme change ───────────
  document.addEventListener('workspace:cluster-color-changed', () => {
    applyColorMode();
    renderLegend();
  });
  document.addEventListener('workspace:theme-changed', () => {
    // CSS vars are now whatever the new theme defines — re-apply monochrome
    // shades so the canvas matches the new palette.
    applyColorMode();
  });

  // ─────────── cluster legend ───────────
  function renderLegend() {
    const target = $('#graph-legend');
    if (!target) return;
    const byCluster = new Map();
    cy.nodes().forEach(function (n) {
      const cid = n.data('cluster_id');
      if (!cid || cid === 0) return;
      const entry = byCluster.get(cid) || {
        id: cid,
        label: n.data('cluster_label') || `cluster ${cid}`,
        color: n.data('color'),
        count: 0,
      };
      entry.count += 1;
      byCluster.set(cid, entry);
    });
    const items = Array.from(byCluster.values()).sort((a, b) => b.count - a.count);
    target.innerHTML = items.map(function (c) {
      return (
        '<button type="button" class="legend-row" data-cluster-id="' + c.id + '">' +
        '<span class="legend-swatch" style="background:' + c.color + '"></span>' +
        '<span class="legend-label">' + escapeHtml(c.label) + '</span>' +
        '<span class="legend-count">' + c.count + '</span>' +
        '</button>'
      );
    }).join('');
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (m) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m];
    });
  }

  // Click a legend row → focus that cluster: hide everything else, fit to cluster
  root.addEventListener('click', function (e) {
    const row = e.target.closest('.legend-row');
    if (!row) return;
    const cid = Number(row.dataset.clusterId);
    cy.elements().removeClass('faded');
    cy.nodes('.selected').removeClass('selected');
    const inCluster = cy.nodes().filter(function (n) {
      return n.data('cluster_id') === cid;
    });
    const visible = inCluster.union(inCluster.connectedEdges());
    cy.elements().difference(visible).addClass('faded');
    cy.animate(
      { fit: { eles: inCluster, padding: 80 } },
      { duration: 350, easing: 'ease-out-quad' }
    );
    root.querySelectorAll('.legend-row.active').forEach(el => el.classList.remove('active'));
    row.classList.add('active');
  });

  renderLegend();
  updateLabelVisibility();

  // ─────────── reset filter form helper ───────────
  window.resetGraphFilters = function () {
    const form = $('#filter-form');
    if (!form) return;
    form.reset();
    form.querySelectorAll('output').forEach(function (out) {
      const input = form.querySelector('input[name="' + out.id.replace('-out', '') + '"]');
      if (input) out.textContent = input.value;
    });
    htmx.trigger(form, 'change');
  };

  // Convenience: "fit graph" + "clear focus" double-click on empty canvas
  cy.on('dblclick', function (evt) {
    if (evt.target === cy) {
      cy.elements().removeClass('faded');
      cy.nodes('.selected').removeClass('selected');
      cy.animate({ fit: { eles: cy.elements(), padding: 40 } }, { duration: 300 });
    }
  });

    return cy;
  }  // end bootGraph

  // Public API for workspace.js to drive graph tabs.
  window.starcrawlGraph = { boot: bootGraph };

  // Legacy auto-boot for direct route /graph (no workspace shell on the page).
  // The shell explicitly calls boot() per tab via workspace.js, so skip this
  // when the workspace shell is loaded.
  document.addEventListener('DOMContentLoaded', function () {
    if (document.body.classList.contains('shell')) return;
    bootGraph(document);
  });
})();
