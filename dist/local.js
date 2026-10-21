"use strict";
// Imported records remain separate from the original demonstration dashboard.
async function updateLocalStatus() {
  if (!/^https?:$/.test(location.protocol)) return;
  try {
    const response = await fetch('/api/summary');
    if (!response.ok) return;
    const data = await response.json();
    if (!Number.isInteger(data.total)) return;
    const status = document.getElementById('local-status');
    status.textContent = `Python · importuota: ${data.total}`;
    status.title = `Demonstracinių: ${data.demo}; kitų: ${data.non_demo}. ${window.SignalLiveData?.active()?'Rodoma tikra gauta Diasporos imtis.':'Analitiniai vaizdai rodo atskirą demonstracinį rinkinį.'}`;
    status.hidden = false;
  } catch (_) { /* Static preview also works without the local API. */ }
}
updateLocalStatus();
window.addEventListener('focus', updateLocalStatus);
