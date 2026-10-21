import { request, retryRemaining } from './api.js';
import { events } from './data.js';
import { errorMessage, trust } from './p1.js';

export const p2Pages = ['Location comparison', 'Events analytics', 'News feed', 'Anomalies', 'About & data'];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const val = value => value === null || value === undefined ? '–' : typeof value === 'number' ? value.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : esc(value);
const query = values => new URLSearchParams(Object.entries(values).filter(([, value]) => value !== '' && value !== undefined && value !== null)).toString();
const options = values => Object.entries(values).map(([key, label]) => `<option value="${esc(key)}">${esc(label)}</option>`).join('');
const field = (name, label, control) => `<label class="p0-field">${label}${control}<small data-field="${name}" role="alert"></small></label>`;
const select = (name, label, values, first = '') => field(name, label, `<select name="${name}">${first}${options(values)}</select>`);
const input = (name, label, attrs = '') => field(name, label, `<input name="${name}" ${attrs}>`);
const localInput = value => { const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
const dates = () => input('from', 'From (local)', `type="datetime-local" required value="${localInput(Date.now() - 7 * 86400000)}"`) + input('to', 'To (local, exclusive)', `type="datetime-local" required value="${localInput(Date.now())}"`);
const empty = message => `<p class="empty" role="status">${message}</p>`;
function link(url, label) {
  try { const parsed = new URL(url); if (['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password) return `<a href="${esc(parsed.href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`; } catch { /* Unsupported URLs remain plain metadata. */ }
  return `<span>${esc(label)} unavailable</span>`;
}
let stop = () => {};
export function stopP2() { stop(); stop = () => {}; }
export function renderP2(page, context) {
  stopP2();
  const root = document.querySelector('#p0-content'); if (!root) return;
  const controller = new AbortController(); let read;
  stop = () => { controller.abort(); read?.abort(); };
  const alive = () => root.isConnected && !controller.signal.aborted;
  const date = value => value ? new Date(value).toLocaleString('en-IN', context.utc() ? { timeZone: 'UTC' } : {}) : '–';
  const api = (path, init = {}) => request(path, { ...init, signal: AbortSignal.any([controller.signal, ...(init.signal ? [init.signal] : [])]) });
  const zone = () => `<button type="button" class="button" data-zone aria-pressed="${context.utc()}">Time zone: ${context.utc() ? 'UTC' : 'Local time'}</button>`;
  const bindZone = redraw => root.querySelector('[data-zone]')?.addEventListener('click', () => { context.toggleUTC(); redraw(); });
  const locations = Object.fromEntries(context.locations.map(item => [item.id, item.name]));
  const locationSelect = (required = false) => field('location_id', 'Location', `<select name="location_id" ${required ? 'required' : ''}><option value="">${required ? 'Choose location' : 'All locations'}</option>${options(locations)}</select>`);
  const shell = (title, form, note = '') => `<section class="panel p0-panel"><div class="panel-head"><div><h2>${title}</h2></div></div>${note}${form ? `<form class="p0-form p0-filters">${form}<button class="primary" data-apply>Apply filters</button><p data-form-error role="alert"></p></form>` : ''}<div data-result></div></section>`;
  function countdown(button, path) {
    const label = button.dataset.label || button.textContent; button.dataset.label = label;
    const tick = () => { if (!alive() || !button.isConnected) return; const remaining = retryRemaining(path); button.disabled = remaining > 0; button.textContent = remaining ? `${label} (${remaining}s)` : label; if (remaining) setTimeout(tick, 1000); }; tick();
  }
  function failure(node, error, retry, path) {
    if (!alive() || error.name === 'AbortError' || error.status === 401) return;
    node.innerHTML = `<p role="alert">${esc(errorMessage(error))}</p>${error.status === 404 && page === 'Anomalies' ? '<p>This view is unavailable from the backend.</p>' : ''}${error.status === 403 ? '' : '<button class="button" data-retry>Retry</button>'}`;
    const button = node.querySelector('[data-retry]'); if (button) { button.onclick = retry; countdown(button, path); }
    const apply = root.querySelector('[data-apply]'); if (apply && error.status === 403) apply.hidden = true;
    const form = root.querySelector('form');
    for (const detail of error.details || []) {
      const name = String(detail.field || '').replace(/^(body|query)\./, ''), target = [...(form?.querySelectorAll('[data-field]') || [])].find(item => item.dataset.field === name);
      if (target) target.textContent = detail.issue || 'Invalid value';
    }
  }
  function range(form, max = 366) {
    const values = Object.fromEntries(new FormData(form)), from = Date.parse(values.from), to = Date.parse(values.to);
    if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) throw new Error('Choose a valid range with the end after the start.');
    if (to - from > max * 86400000) throw new Error(`Choose at most ${max} days.`);
    return { ...values, from: new Date(from).toISOString(), to: new Date(to).toISOString() };
  }
  function pager(node, data, load) {
    const footer = document.createElement('div'); footer.className = 'table-footer';
    footer.innerHTML = `<span>${data.total ? data.offset + 1 : 0}–${Math.min(data.offset + data.items.length, data.total)} of ${val(data.total)}</span><div><button data-prev ${data.offset === 0 ? 'disabled' : ''}>← Previous</button><button data-next ${data.offset + data.limit >= data.total ? 'disabled' : ''}>Next →</button></div>`;
    footer.querySelector('[data-prev]').onclick = () => load(Math.max(0, data.offset - data.limit)); footer.querySelector('[data-next]').onclick = () => load(data.offset + data.limit); node.append(footer);
  }
  function reader(path, draw, { maxDays = 366, paginate = false, initial = true } = {}) {
    const result = root.querySelector('[data-result]'), form = root.querySelector('form'); let selected = {}, current;
    async function load(offset = 0) {
      const restorePaging = result.contains(document.activeElement) && document.activeElement.matches('[data-prev],[data-next]');
      read?.abort(); const active = new AbortController(); read = active;
      result.innerHTML = empty('Loading…'); const button = form?.querySelector('[data-apply]'); if (button) button.disabled = true;
      try {
        const response = await api(`${path}?${query({ ...selected, ...(paginate ? { limit: 50, offset } : {}) })}`, { signal: active.signal });
        if (!alive() || active.signal.aborted) return;
        if (paginate && response.total > 0 && offset >= response.total) { load(Math.floor((response.total - 1) / response.limit) * response.limit); return; }
        current = response; redraw(); if (restorePaging) result.querySelector('.table-footer button:not(:disabled)')?.focus({ preventScroll: true });
      } catch (error) { if (!active.signal.aborted) failure(result, error, () => load(offset), path); }
      finally { if (button && read === active && alive()) countdown(button, path); }
    }
    function redraw() { draw(result, current, selected); bindZone(redraw); if (paginate && Number.isInteger(current.limit)) pager(result, current, load); }
    if (form) form.onsubmit = event => {
      event.preventDefault(); form.querySelectorAll('[data-field]').forEach(node => { node.textContent = ''; }); const message = form.querySelector('[data-form-error]'); message.textContent = '';
      try { selected = range(form, maxDays); load(); } catch (error) { message.textContent = error.message; }
    };
    if (initial) { if (form) form.requestSubmit(); else load(); } else result.innerHTML = empty('Choose a location and apply filters.');
  }

  if (page === 'Location comparison') {
    root.innerHTML = shell(page, dates() + select('sort', 'Sort', { name: 'Location A–Z', '-name': 'Location Z–A', '-record_count': 'Most records', record_count: 'Fewest records', '-coverage_pct': 'Highest coverage', coverage_pct: 'Lowest coverage' }), '<p>Observation statistics from the backend. Source attribution is not supplied per aggregate; see About & data for the source inventory.</p>');
    reader('/analytics/locations', (node, data) => {
      const pending = context.staff && data.items.some(item => item.report_counts?.pending !== undefined), rejected = context.staff && data.items.some(item => item.report_counts?.rejected !== undefined);
      node.innerHTML = `${zone()}<div class="table-scroll"><table><thead><tr><th>Location</th><th>Latest observation</th><th>Temperature min / mean / max °C</th><th>Rainfall mm</th><th>Wind mean / max gust km/h</th><th>Records</th><th>Coverage</th><th>Verified reports</th>${pending ? '<th>Pending review</th>' : ''}${rejected ? '<th>Rejected</th>' : ''}</tr></thead><tbody>${data.items.map(item => `<tr><td>${esc(item.location.name)}</td><td>${date(item.latest_observation_at)}</td><td>${val(item.temperature_c?.min)} / ${val(item.temperature_c?.mean)} / ${val(item.temperature_c?.max)}</td><td>${val(item.total_precipitation_mm)}</td><td>${val(item.wind?.mean_speed_kmh)} / ${val(item.wind?.max_gust_kmh)}</td><td>${val(item.record_count)}</td><td>${val(item.coverage_pct)}${item.coverage_pct === null || item.coverage_pct === undefined ? '' : `%<progress max="100" value="${Math.max(0, Math.min(100, item.coverage_pct))}" aria-label="${esc(item.location.name)} data coverage"></progress>`}</td><td>${val(item.report_counts?.verified)}<small>Verified by reviewer</small></td>${pending ? `<td>${val(item.report_counts?.pending)}</td>` : ''}${rejected ? `<td>${val(item.report_counts?.rejected)}</td>` : ''}</tr>`).join('') || `<tr><td colspan="${8 + Number(pending) + Number(rejected)}">No location statistics in this period.</td></tr>`}</tbody></table></div><p>${val(data.total)} locations · Coverage is supplied by the backend.</p>`;
    }, { paginate: true }); return;
  }
  if (page === 'Events analytics') {
    root.innerHTML = shell(page, dates() + locationSelect() + select('event_type', 'Event type', events, '<option value="">All event types</option>') + select('group_by', 'Group by', { event_type: 'Event type', location: 'Location', day: 'Day', status: 'Status' }) + (context.staff ? select('status', 'Status filter (staff)', { all: 'All statuses', verified: 'Verified', pending: 'Pending', rejected: 'Rejected' }) : ''), `<p>Citizen reports · ${context.staff ? 'Staff totals appear only when returned by the API.' : 'Public view contains reports verified by reviewer only.'}</p>`);
    reader('/analytics/events', (node, data, selected) => {
      const day = selected.group_by === 'day', items = day ? [...data.items].sort((a, b) => a.key.localeCompare(b.key)) : data.items;
      const label = item => day ? date(`${item.key}T00:00:00Z`) : selected.group_by === 'event_type' ? events[item.key] || item.key : item.key;
      const max = Math.max(1, ...items.map(item => item.count ?? 0)), x = index => 35 + index * 860 / Math.max(1, items.length - 1), y = count => 230 - count / max * 190;
      let pen = false; const path = items.map((item, index) => { if (item.count === null) { pen = false; return ''; } const next = `${pen ? 'L' : 'M'}${x(index)},${y(item.count)}`; pen = true; return next; }).join(' ');
      const totals = Object.entries(data.totals || {}).filter(([key, count]) => count !== null && (key === 'verified' || context.staff));
      node.innerHTML = `${zone()}<section class="metrics">${totals.map(([key, count]) => `<article><div>${esc(key === 'verified' ? 'Verified by reviewer' : key === 'pending' ? 'Pending review' : key === 'rejected' ? 'Rejected' : key)}</div><strong>${val(count)}</strong></article>`).join('')}</section>${items.length ? `<svg class="p0-chart" viewBox="0 0 940 270" role="img" aria-label="Citizen report counts by ${esc(data.group_by)}. Exact counts are in the table below."><text x="0" y="30" fill="currentColor">${max}</text><line x1="35" y1="230" x2="920" y2="230" stroke="currentColor" opacity=".3"/>${day ? `<path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2"/>${items.filter(item => item.count !== null).map(item => `<circle cx="${x(items.indexOf(item))}" cy="${y(item.count)}" r="3" fill="var(--accent)"><title>${esc(label(item))}: ${val(item.count)}</title></circle>`).join('')}` : items.filter(item => item.count !== null).map(item => `<rect x="${x(items.indexOf(item)) - Math.min(15, 300 / items.length)}" y="${y(item.count)}" width="${Math.max(.5, Math.min(30, 600 / items.length))}" height="${230 - y(item.count)}" fill="var(--accent)"><title>${esc(label(item))}: ${val(item.count)}</title></rect>`).join('')}</svg>` : empty('No citizen reports match this selection.')}<p>${day ? 'Day groups are UTC buckets; the time toggle changes the displayed bucket-start instant.' : 'Counts are supplied by the backend.'}</p><div class="table-scroll"><table><thead><tr><th>${day ? 'Bucket start' : 'Group'}</th><th>Report count</th></tr></thead><tbody>${items.map(item => `<tr><td>${esc(label(item))}</td><td>${val(item.count)}</td></tr>`).join('') || '<tr><td colspan="2">No groups returned.</td></tr>'}</tbody></table></div>`;
    }, { paginate: true }); return;
  }
  if (page === 'News feed') {
    root.innerHTML = shell(page, dates() + input('source', 'Source name (optional)') + select('category', 'Category', { news: 'News', advisory_feed: 'Advisory feed' }, '<option value="">All categories</option>'), '<p>News item, not verified. External links open only when you choose them.</p>');
    reader('/news', (node, data) => {
      node.innerHTML = `${zone()}${data.items.map(item => `<article class="p2-news"><div><span class="badge">${item.category === 'advisory_feed' && item.is_official === true ? 'Official advisory feed' : 'News item, not verified'}</span><span class="badge">${esc(item.category)}</span></div><h3>${esc(item.title)}</h3><p>${esc(item.summary || '')}</p><p>${esc(item.source?.display_name || item.source?.name)} · ${item.published_at ? date(item.published_at) : 'Publication time not supplied'}</p>${link(item.url, 'Read source item')}</article>`).join('') || empty('No news items match these filters.')}`;
    }, { maxDays: 31, paginate: true }); return;
  }
  if (page === 'Anomalies') {
    root.innerHTML = shell(page, locationSelect(true) + select('metric', 'Metric', { temperature_c: 'Temperature', relative_humidity_pct: 'Relative humidity', precipitation_mm: 'Rainfall', wind_speed_kmh: 'Wind speed', wind_gust_kmh: 'Wind gust' }) + dates() + input('baseline_days', 'Baseline days', 'type="number" min="7" max="366" step="1" value="30" required') + input('threshold', 'Score threshold', 'type="number" min="0.0001" step="any" value="3.5" required'), '<p class="p2-disclaimer" role="note">Statistical flag only. Not an official warning.</p>');
    reader('/analytics/anomalies', (node, data) => {
      node.innerHTML = `${zone()}<h3>${esc(data.location?.name)} · ${esc(data.metric)}</h3><p>${esc(typeof data.note === 'string' ? data.note : data.note == null ? '' : JSON.stringify(data.note))}</p><details><summary>Baseline metadata from the API</summary><pre class="p0-json">${esc(JSON.stringify(data.baseline, null, 2) ?? 'Not supplied')}</pre></details>${data.status === 'insufficient_data' ? empty('Insufficient data for statistical analysis.') : data.items.length ? `<div class="table-scroll"><table><thead><tr><th>Time</th><th>Value</th><th>Baseline median</th><th>Score</th><th>Explanation</th></tr></thead><tbody>${data.items.map(item => `<tr><td>${date(item.valid_at)}</td><td>${val(item.value)}</td><td>${val(item.baseline?.median)}</td><td>${val(item.score)}</td><td>${esc(item.explanation)}</td></tr>`).join('')}</tbody></table></div>` : empty('No statistical flags in this selection.')}`;
    }, { initial: false, paginate: true }); return;
  }
  if (page === 'About & data') {
    root.innerHTML = shell('About & data sources', '', '<div class="p2-about"><h3>Trust legend</h3><dl><dt>Model-derived observation / Forecast</dt><dd>Open-Meteo data is model-derived. It is not station readings or official observations.</dd><dt>Official data</dt><dd>Used only when the API identifies the source trust level as official.</dd><dt>News item, not verified</dt><dd>News is not a verified weather observation. “Official advisory feed” appears only for an advisory item marked is_official by the API.</dd><dt>Citizen reports</dt><dd>Pending review / Verified by reviewer / Rejected. Verification is a human review, not an official authority endorsement.</dd><dt>Statistical flags</dt><dd>Statistical flag only. Not an official warning.</dd></dl></div>');
    const node = root.querySelector('[data-result]');
    async function load() {
      node.innerHTML = empty('Loading source metadata…');
      const results = await Promise.allSettled([api('/analytics/summary'), api('/weather/latest?kind=observation')]); if (!alive()) return;
      if (results[0].status === 'rejected') { failure(node, results[0].reason, load, '/analytics/summary'); return; }
      const summary = results[0].value, weather = results[1].status === 'fulfilled' ? results[1].value.items : [], metadata = new Map(weather.map(item => [item.source?.name, item.source]));
      node.innerHTML = `<h3>Backend source inventory</h3>${results[1].status === 'rejected' ? `<p role="status">Weather attribution could not be loaded: ${esc(errorMessage(results[1].reason))}</p>` : ''}${(summary.sources || []).map(source => { const item = { ...metadata.get(source.name), ...source }; return `<article class="p2-news"><h3>${esc(item.display_name || item.name)}</h3><span class="badge">${esc(trust(item))}</span><p>${esc(item.attribution_text || 'Attribution not supplied by this API response.')}</p><p>${item.license_url ? link(item.license_url, 'View license') : 'License link not supplied by this API response.'}</p>${item.homepage_url ? `<p>${link(item.homepage_url, 'Source website')}</p>` : ''}</article>`; }).join('') || empty('No sources returned by the backend.')}<p>Attribution and license links are displayed when supplied by the API. Missing metadata is not inferred.</p>`;
    }
    load();
  }
}
