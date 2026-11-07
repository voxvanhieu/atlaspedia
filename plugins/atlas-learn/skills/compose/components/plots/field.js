// plots/field.js — body of the page's single qc:ready handler for the QC.field figure in field.html (the figure.field variant needs no script).
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
QC.field(document.getElementById('c7-field-api-canvas'), {
  f: (x, y) => [-y - 0.2 * x, x - 0.2 * y],                       // [dx/dt, dy/dt] of the system in the caption
  xRange: [-3, 3], yRange: [-3, 3], grid: 14, normalize: false,
  streamlines: 12, nullclines: true, trajectories: [[2.5, 0]], labels: ['start at (2.5, 0)'],
  xLabel: 'x', yLabel: 'y', title: 'dx/dt = −y − 0.2x, dy/dt = x − 0.2y: arrow length ∝ magnitude'
});
