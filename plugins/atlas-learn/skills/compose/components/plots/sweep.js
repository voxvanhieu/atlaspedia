// plots/sweep.js — body of the page's single qc:ready handler for the QC.sweep figure in sweep.html (the figure.sweep variant needs no script).
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
QC.sweep(document.getElementById('c7-sweep-api-canvas'), {
  param: { name: 'zoom', values: [0, 2, 4, 6, 8, 10, 12] },
  fn: (z, lat) => 2 * Math.PI * 6378137 * Math.cos(lat * Math.PI / 180) / (256 * Math.pow(2, z)),   // (zoom, latitude) → metres per pixel
  xRange: [-80, 80], samples: 161, yScale: 'log', highlight: 3,
  xLabel: 'latitude φ [°]', yLabel: 'ground resolution [m/px]', title: 'Web Mercator, 256 px tiles: metres per pixel'
});
