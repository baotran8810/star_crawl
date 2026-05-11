// Cytoscape graph initialization + interactions.

(function () {
  const dataNode = document.getElementById('cy-data');
  if (!dataNode) return;

  function readPayload() {
    try {
      return JSON.parse(dataNode.textContent || '{}');
    } catch (e) {
      console.error('graph: invalid payload', e);
      return { nodes: [], edges: [] };
    }
  }

  let payload = readPayload();
  const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: { nodes: payload.nodes || [], edges: payload.edges || [] },
    layout: { name: 'fcose', animate: false, randomize: true },
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'label': 'data(display)',
          'color': 'oklch(20% 0.01 80)',
          'font-size': 10,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-outline-width': 2,
          'text-outline-color': 'data(color)',
          'width': 'mapData(doc_freq, 1, 100, 14, 60)',
          'height': 'mapData(doc_freq, 1, 100, 14, 60)',
          'border-width': 0,
          'transition-property': 'opacity, border-width',
          'transition-duration': '150ms',
        },
      },
      {
        selector: 'edge',
        style: {
          'width': 'mapData(npmi, 0.15, 1.0, 0.5, 4)',
          'line-color': 'oklch(82% 0.008 80)',
          'opacity': 0.5,
          'curve-style': 'haystack',
          'transition-property': 'opacity',
          'transition-duration': '150ms',
        },
      },
      {
        selector: 'node:selected',
        style: { 'border-width': 3, 'border-color': 'oklch(52% 0.18 30)' },
      },
      { selector: '.faded', style: { opacity: 0.1 } },
    ],
  });

  function focusNode(node) {
    cy.elements().removeClass('faded');
    const visible = node.closedNeighborhood();
    cy.elements().difference(visible).addClass('faded');
    cy.animate(
      { fit: { eles: visible, padding: 60 } },
      { duration: 300 }
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
    if (evt.target === cy) cy.elements().removeClass('faded');
  });

  // Focus a node when the user picks one from the type-ahead search results
  // or a neighbor in the side panel (both render <a data-kw-id="...">).
  document.body.addEventListener('click', function (e) {
    const link = e.target.closest('a[data-kw-id]');
    if (!link) return;
    const kwId = link.dataset.kwId;
    const node = cy.getElementById('k_' + kwId);
    if (node && node.nonempty()) {
      focusNode(node);
    }
    // HTMX continues to load the side-panel via the element's hx-get.
  });

  // Refresh elements when filter HTMX swaps the data div
  document.body.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target.id !== 'cy-data') return;
    payload = readPayload();
    cy.json({ elements: { nodes: payload.nodes || [], edges: payload.edges || [] } });
    cy.layout({ name: 'fcose', animate: false, randomize: false }).run();
  });

  // Reset filter form helper — wired from the template's Reset button
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
})();
