// demos/demo-units.js — body of the page's single qc:ready handler for demo-units.html.
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
// bindControls hands the model base units (data-unit: km and cm here; the data-si text field as a plain number)
// whatever unit the reader picked in the unit menus, so the model never changes.
const unitsEl = id => document.getElementById(id);
QC.bindControls('#demo-units', v => {
  const D = v['d3-ground'] * 1000, N = v['d3-scale'], paper = v['d3-paper'] / 100;   // metres · — · metres
  const ok = isFinite(N) && N > 0;
  const l = ok ? D / N : NaN;                                                          // map length [m]
  unitsEl('d3-ro-map').textContent = QC.fmtSI(l, 'm');
  unitsEl('d3-ro-permm').textContent = ok ? QC.fmtSI(N * 1e-3, 'm') : '—';
  const fits = ok && l <= paper;
  unitsEl('d3-ro-fit').textContent = !ok ? 'enter a scale like 250k or 1M' : fits ? 'yes, ' + QC.fmtSI(paper - l, 'm') + ' to spare' : 'no, ' + QC.fmtSI(l - paper, 'm') + ' too long';
  unitsEl('d3-ro-fit-wrap').className = 'readout ' + (!ok ? 'warn' : fits ? 'good' : 'bad');
});
