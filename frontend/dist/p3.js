// Shared accessibility behavior for the existing DOM-rendered screens.
export function debounce(callback, delay = 300) {
  let timer;
  const run = (...args) => { clearTimeout(timer); timer = setTimeout(() => callback(...args), delay); };
  run.cancel = () => clearTimeout(timer);
  return run;
}

export function focusPage() {
  document.querySelector('main')?.focus({ preventScroll: true });
}

export function preserveFocus(root) {
  const element = document.activeElement;
  if (!root?.contains(element)) return () => {};
  const id = element.id;
  const key = ['data-period', 'data-event', 'data-loc'].find(name => element.hasAttribute(name));
  const value = key && element.getAttribute(key);
  const start = element.selectionStart, end = element.selectionEnd;
  return () => {
    const replacement = id ? document.getElementById(id) : key ? [...root.querySelectorAll(`[${key}]`)].find(node => node.getAttribute(key) === value) : null;
    if (!replacement || replacement.disabled) return;
    replacement.focus({ preventScroll: true });
    if (typeof start === 'number' && replacement.setSelectionRange) replacement.setSelectionRange(start, end);
  };
}

let sequence = 0;
const identify = node => node.id || (node.id = `accessible-${++sequence}`);
export function installAccessibility() {
  const dialog = document.querySelector('#detail');
  let opener;
  document.addEventListener('focusin', event => { if (!dialog.contains(event.target)) opener = event.target; });
  dialog.addEventListener('close', () => {
    dialog.removeAttribute('aria-labelledby');
    if (opener?.isConnected) opener.focus({ preventScroll: true }); else focusPage();
  });
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const stops = [...dialog.querySelectorAll('button, input, select, textarea, a[href], summary, [tabindex]')].filter(node => !node.disabled && node.tabIndex >= 0 && node.getClientRects().length);
    if (!stops.length) { event.preventDefault(); dialog.focus(); return; }
    const first = stops[0], last = stops.at(-1);
    if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
  });
  document.addEventListener('submit', event => { event.target.dataset.a11ySubmitted = 'true'; }, true);
  function enhance() {
    document.querySelectorAll('nav').forEach((nav, index) => { nav.setAttribute('aria-label', index ? 'Administration' : 'Workspace'); });
    document.querySelectorAll('th').forEach(node => { if (!node.hasAttribute('scope')) node.scope = 'col'; });
    document.querySelectorAll('table').forEach(table => {
      if (!table.caption) {
        const caption = table.createCaption(); caption.className = 'sr-only';
        caption.textContent = table.closest('details')?.querySelector('summary')?.textContent || table.closest('section')?.querySelector('h2')?.textContent || 'API data';
      }
    });
    document.querySelectorAll('.table-scroll').forEach(node => {
      node.tabIndex = 0; node.setAttribute('role', 'region');
      node.setAttribute('aria-label', `${node.querySelector('caption')?.textContent || 'Data table'}; scroll horizontally for more columns`);
    });
    document.querySelectorAll('[data-error], [data-field]').forEach(error => {
      if (!error.matches('small')) return;
      const form = error.closest('form');
      const name = error.dataset.error || error.dataset.field;
      const control = error.closest('label')?.querySelector('input,select,textarea') || [...(form?.elements || [])].find(node => node.name === name);
      if (!control) return;
      const id = identify(error), described = new Set((control.getAttribute('aria-describedby') || '').split(' ').filter(Boolean));
      described.add(id); control.setAttribute('aria-describedby', [...described].join(' '));
      const invalid = Boolean(error.textContent.trim()); control.setAttribute('aria-invalid', String(invalid));
      if (invalid && form?.dataset.a11ySubmitted === 'true') { form.dataset.a11ySubmitted = 'false'; control.focus({ preventScroll: false }); }
    });
    if (dialog.open) {
      const heading = dialog.querySelector('h2');
      if (heading) { dialog.setAttribute('aria-labelledby', identify(heading)); dialog.removeAttribute('aria-label'); }
      else { dialog.removeAttribute('aria-labelledby'); dialog.setAttribute('aria-label', 'Data details'); }
      if (!dialog.contains(document.activeElement)) dialog.querySelector('button,input,select,textarea')?.focus();
    }
    document.querySelectorAll('.p0-chart').forEach(chart => {
      const container = chart.parentElement, table = container.querySelector('table');
      if (table) chart.setAttribute('aria-details', identify(table));
      if (!container.querySelector('[data-chart-description]')) {
        const description = document.createElement('p'); description.className = 'sr-only'; description.dataset.chartDescription = 'true';
        const rows = [...(table?.tBodies[0]?.rows || [])];
        description.textContent = `${rows.length} data rows. Exact values${container.querySelector('details') ? ' are available by expanding Chart values and sample counts' : ' follow in the table'}. Missing measurements are shown as an en dash and chart gaps.`;
        chart.after(description);
      }
      chart.setAttribute('aria-describedby', identify(container.querySelector('[data-chart-description]')));
    });
  }
  const observer = new MutationObserver(enhance);
  observer.observe(document.querySelector('#app'), { childList: true, characterData: true, subtree: true });
  observer.observe(dialog, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['open'] });
  enhance();
}
