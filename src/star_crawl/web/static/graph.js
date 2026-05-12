// Cytoscape graph initialization + interactions.

(function () {
  const dataNode = document.getElementById('cy-data');
  if (!dataNode) return;

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
    container: document.getElementById('cy'),
    elements: { nodes: payload.nodes || [], edges: payload.edges || [] },
    minZoom: 0.25,
    maxZoom: 3.0,
    wheelSensitivity: 0.25,
    layout: layoutOpts(),
    style: [
      // Base node — pill shape with cluster fill + soft border for separation
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'background-opacity': 0.95,
          'border-width': 2,
          'border-color': 'data(color)',
          'border-opacity': 1,
          'color': '#fff',
          'font-size': 12,
          'font-weight': 600,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-outline-width': 2.5,
          'text-outline-color': 'data(color)',
          'text-outline-opacity': 1,
          'width':  'mapData(doc_freq, 1, 60, 22, 78)',
          'height': 'mapData(doc_freq, 1, 60, 22, 78)',
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

      // Edges — colored from the source node, opacity ∝ NPMI for visual depth
      {
        selector: 'edge',
        style: {
          'width': 'mapData(npmi, 0.10, 1.0, 1, 6)',
          'line-color': 'data(color)',
          'line-opacity': 'mapData(npmi, 0.10, 1.0, 0.18, 0.55)',
          'curve-style': 'straight',
          'transition-property': 'line-opacity, width, line-color',
          'transition-duration': '180ms',
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
          'border-color': 'oklch(60% 0.20 30)',
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
      nodeRepulsion: 9000,
      idealEdgeLength: 70,
      edgeElasticity: 0.45,
      gravity: 0.35,
      gravityRangeCompound: 1.0,
      numIter: 3000,
      tile: true,
      tilingPaddingHorizontal: 12,
      tilingPaddingVertical: 12,
      nodeSeparation: 80,
    };
  }

  // ─────────── edge tinting from source cluster ───────────
  function tintEdgesFromSource() {
    cy.edges().forEach(function (e) {
      const src = e.source();
      const color = src.data('color');
      e.data('color', color);
    });
  }
  tintEdgesFromSource();

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
    const ind = document.getElementById('graph-zoom-ind');
    if (ind) {
      ind.textContent =
        (z * 100).toFixed(0) + '%' + ' · labels ≥ ' + threshold + ' docs';
    }
  }

  cy.on('zoom', updateLabelVisibility);
  cy.on('layoutstop', updateLabelVisibility);

  // Keep the cy canvas accurate when the surrounding column resizes
  // (window resize, fullscreen toggle, finder layout shift).
  function resizeCy() {
    cy.resize();
    cy.fit(undefined, 60);
    updateLabelVisibility();
  }
  window.addEventListener('resize', resizeCy);
  const ro = new ResizeObserver(function () { cy.resize(); });
  const cyContainer = document.getElementById('cy');
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
  document.body.addEventListener('click', function (e) {
    const link = e.target.closest('a[data-kw-id]');
    if (!link) return;
    const kwId = link.dataset.kwId;
    const node = cy.getElementById('k_' + kwId);
    if (node && node.nonempty()) {
      focusNode(node);
    }
  });

  // ─────────── refresh on HTMX data swap ───────────
  document.body.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target.id !== 'cy-data') return;
    payload = readPayload();
    cy.json({ elements: { nodes: payload.nodes || [], edges: payload.edges || [] } });
    tintEdgesFromSource();
    cy.layout(layoutOpts()).run();
    renderLegend();
    labelThresholdCache = null;  // force a recompute even if zoom unchanged
    updateLabelVisibility();
  });

  // ─────────── cluster legend ───────────
  function renderLegend() {
    const target = document.getElementById('graph-legend');
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
  document.body.addEventListener('click', function (e) {
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
    document.querySelectorAll('.legend-row.active').forEach(el => el.classList.remove('active'));
    row.classList.add('active');
  });

  renderLegend();
  updateLabelVisibility();

  // ─────────── reset filter form helper ───────────
  window.resetGraphFilters = function () {
    const form = document.getElementById('filter-form');
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
})();
