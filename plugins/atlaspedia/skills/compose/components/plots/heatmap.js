// plots/heatmap.js — body of the page's single qc:ready handler for heatmap.html.
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
const budgetParts = Array.from({ length: 16 }, (_, i) => i + 1);     // parts n
const budgetPerPart = [10, 20, 30, 40, 50, 60];                        // size per part s [KB]
QC.heatmap(document.getElementById('c5-heatmap-canvas'), {
  z: budgetPerPart.map(s => budgetParts.map(n => 40 + n * s - 250)),   // z[j][i] = S(n_i, s_j) − budget
  x: budgetParts, y: budgetPerPart,
  xLabel: 'parts n', yLabel: 'size per part s [KB]', zLabel: 'KB over the 250 KB budget',
  palette: 'diverging', zRange: [-300, 300], cells: true, values: true, zFormat: v => QC.fmt(v, 0),
  title: 'Single page: S − B = 40 + n·s − 250'
});
