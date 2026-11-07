// demos/demo-uncertainty.js — body of the page's single qc:ready handler for demo-uncertainty.html.
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
const uncEl = id => document.getElementById(id);
const uncModel = v => v['d4-len'] * v['d4-scale'] * v['d4-shrink'] / 1e6;            // ground distance [km] = mm × N × s
QC.bindControls('#demo-uncertainty', v => {
  const inputs = QC.tolerancesOf('#demo-uncertainty');                                 // { 'd4-len': { nominal: 120, tol: 0.01 }, … } from data-tol
  const r = QC.mc(uncModel, inputs, { n: +v['d4-samples'] || 2000, seed: 1 });
  uncEl('d4-ro-nominal').textContent = QC.fmt(r.nominal, 2) + ' km';
  uncEl('d4-ro-mean').textContent = QC.fmt(r.mean, 2) + ' ± ' + QC.fmt(r.sd, 3) + ' km';
  uncEl('d4-ro-p').textContent = QC.fmt(r.p5, 2) + ' – ' + QC.fmt(r.p95, 2) + ' km';
  uncEl('d4-ro-worst').textContent = QC.fmt(r.worst.min.value, 2) + ' – ' + QC.fmt(r.worst.max.value, 2) + ' km';
  QC.tornado(uncEl('d4-tornado'), r.tornado, { baseline: r.nominal, unit: 'km', digits: 2 });
});
