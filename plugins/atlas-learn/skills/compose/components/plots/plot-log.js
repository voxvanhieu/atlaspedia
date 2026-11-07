// plots/plot-log.js — body of the page's single qc:ready handler for plot-log.html.
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
// Data = figures as the source states them (here: the compose skill's size targets) — never interpolated, averaged or estimated.
const sizes = [            // [label, low KB, high KB]; low === high for a single stated figure
  ['overview', 30, 50], ['bibliography', 60, 120], ['module', 70, 160], ['synthesis', 80, 160],
  ['priority module', 250, 250], ['offline bundle', 1000, 1000], ['vendor folder', 2500, 2500]
];
const x = sizes.map((_, i) => i + 1);
QC.plot(document.getElementById('c5-plot-log-canvas'), {
  title: 'Documented size figures of atlas-learn outputs',
  yScale: 'log',
  series: [{ type: 'scatter', size: 4, label: 'stated figure or range (dot = upper end)',
             data: sizes.map((r, i) => [x[i], r[2]]), errors: sizes.map((r, i) => [x[i], r[2], r[1], r[2]]) }],
  hlines: [{ y: 250, label: 'single-page budget 250 KB', color: 'var(--muted)' }],
  xRange: [0.5, sizes.length + 0.5], xTicks: x, xFormat: v => (sizes[Math.round(v) - 1] || [''])[0],
  xLabel: 'output', yLabel: 'size [KB]', legend: true
});
