// demos/demo-plot.js — body of the page's single qc:ready handler for demo-plot.html.
// Paste inside document.addEventListener('qc:ready', () => { … }); rename ids together with the markup.
// Every number below is a documented input: B and F from the compose skill's single-page plan, n from the brief template.
const B = 250, F = 40;                                   // KB: page budget and frame
const allowance = [];
for (let n = 2; n <= 6; n++) allowance.push([n, (B - F) / n]);
QC.plot(document.getElementById('demo-allowance-canvas'), {
  series: [{ data: allowance, label: 'allowance per part a = (B − F) / n', points: true }],
  xLabel: 'parts on the page n', yLabel: 'allowance per part [KB]', xTicks: [2, 3, 4, 5, 6], legend: true
});
