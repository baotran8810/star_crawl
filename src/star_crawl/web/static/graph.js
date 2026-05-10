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

  cy.on('tap', 'node', function (evt) {
    const node = evt.target;
    const kwId = node.data('kw_id');
    if (!kwId) return;
    cy.elements().removeClass('faded');
    const visible = node.closedNeighborhood();
    cy.elements().difference(visible).addClass('faded');
    htmx.ajax('GET', '/keywords/' + kwId, { target: '#keyword-panel', swap: 'innerHTML' });
  });
  cy.on('tap', function (evt) {
    if (evt.target === cy) cy.elements().removeClass('faded');
  });

  // Refresh elements when filter HTMX swaps the data div
  document.body.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target.id !== 'cy-data') return;
    payload = readPayload();
    cy.json({ elements: { nodes: payload.nodes || [], edges: payload.edges || [] } });
    cy.layout({ name: 'fcose', animate: false, randomize: false }).run();
  });
})();
