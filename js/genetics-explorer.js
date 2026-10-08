/**
 * Renders the PACVS evidence map (window.__gceEvidenceMap) as a small tiered
 * SVG graph: target -> related phenotypes -> shared loci -> genes.
 * No layout library — node counts in this dataset are small enough for a
 * fixed tier layout to read cleanly.
 */
(function () {
  const data = window.__gceEvidenceMap;
  const el = document.getElementById('gce-evidence-map');
  if (!el) return;
  if (!data || !data.nodes || !data.nodes.length) {
    el.innerHTML = '<p class="gce-evidence-map-empty">No evidence map data for this build.</p>';
    return;
  }

  const tierOf = (kind) => ({ phenotype: 0, locus: 1, gene: 2 }[kind] ?? 1);
  const tiers = [[], [], []];
  data.nodes.forEach((n) => {
    if (n.id === data.target) return; // placed separately as the root
    tiers[tierOf(n.kind)].push(n);
  });

  const width = el.clientWidth || 900;
  const tierX = [80, width / 2, width - 80];
  const nodePos = {};
  nodePos[data.target] = { x: tierX[0], y: 60 };

  tiers.forEach((tierNodes, i) => {
    const x = i === 0 ? tierX[0] : tierX[i];
    tierNodes.forEach((n, j) => {
      nodePos[n.id] = { x, y: 60 + (j + (i === 0 ? 1 : 0)) * 60 };
    });
  });

  const height = Math.max(240, 60 + Math.max(...tiers.map((t) => t.length)) * 60 + 40);

  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', height);

  data.edges.forEach((e) => {
    const from = nodePos[e.from];
    const to = nodePos[e.to];
    if (!from || !to) return;
    const line = document.createElementNS(svgNS, 'line');
    line.setAttribute('x1', from.x);
    line.setAttribute('y1', from.y);
    line.setAttribute('x2', to.x);
    line.setAttribute('y2', to.y);
    line.setAttribute('stroke', e.gap ? '#c98a2e' : '#9aa5bd');
    line.setAttribute('stroke-dasharray', e.gap ? '4 3' : '');
    line.setAttribute('stroke-width', '1.5');
    svg.appendChild(line);
  });

  const allNodes = [{ id: data.target, kind: 'phenotype', root: true }, ...tiers.flat()];
  allNodes.forEach((n) => {
    const pos = nodePos[n.id];
    if (!pos) return;
    const g = document.createElementNS(svgNS, 'g');

    const circle = document.createElementNS(svgNS, 'circle');
    circle.setAttribute('cx', pos.x);
    circle.setAttribute('cy', pos.y);
    circle.setAttribute('r', n.root ? 10 : n.gap ? 7 : 8);
    circle.setAttribute('fill', n.gap ? '#fde8e8' : n.kind === 'gene' ? '#e6f4ea' : n.kind === 'locus' ? '#eef1f8' : '#dbe4fb');
    circle.setAttribute('stroke', n.gap ? '#c98a2e' : '#33415c');
    g.appendChild(circle);

    const label = document.createElementNS(svgNS, 'text');
    label.setAttribute('x', pos.x + 14);
    label.setAttribute('y', pos.y + 4);
    label.setAttribute('font-size', '11');
    label.setAttribute('fill', '#22283a');
    label.textContent = n.id + (n.gap ? ' (gap)' : '');
    g.appendChild(label);

    svg.appendChild(g);
  });

  el.appendChild(svg);
})();
