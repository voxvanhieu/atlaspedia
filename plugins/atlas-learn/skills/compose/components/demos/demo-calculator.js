// demos/demo-calculator.js — body of the page's single qc:ready handler for demo-calculator.html.
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
const budgetCanvas = document.getElementById('demo-budget-canvas');
const budgetEl = id => document.getElementById(id);
QC.bindControls('#demo-budget', v => {
  const n = Math.max(1, Math.round(v.parts)), s = v.partkb, B = v.budget, F = v.frame;
  const total = F + n * s, allow = (B - F) / n;
  const line = [], maxN = 16;
  for (let k = 1; k <= maxN; k++) line.push([k, F + k * s]);        // page size as parts are added
  const fits = [];
  for (let k = 1; k <= maxN; k++) if (F + k * s <= B) fits.push([k, F + k * s]);
  QC.plot(budgetCanvas, {
    series: [
      { data: line, label: 'page size S(n)' },
      { data: fits, label: 'fits the budget', color: 'var(--s3)', points: true },
      { data: [[n, total]], label: 'this topic', color: 'var(--s4)', points: true }
    ],
    xLabel: 'parts n', yLabel: 'page size [KB]', xRange: [1, maxN],
    yRange: [0, Math.max(B * 1.3, F + maxN * s * 0.6)],
    hlines: [{ y: B, label: 'budget B', color: 'var(--warn)' }], legend: true
  });
  budgetEl('ro-allow').textContent = allow > 0 ? QC.fmt(Math.floor(allow), 0) + ' KB' : 'none';
  budgetEl('ro-total').textContent = QC.fmt(total, 0) + ' KB';
  const over = total - B;
  budgetEl('ro-verdict').textContent = over <= 0 ? 'single page fits' : QC.fmt(over, 0) + ' KB over: ask to switch';
  budgetEl('ro-verdict-wrap').className = 'readout ' + (over <= 0 ? 'good' : over <= B * 0.1 ? 'warn' : 'bad');
});
