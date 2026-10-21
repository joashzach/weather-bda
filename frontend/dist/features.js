import { request, retryRemaining } from './api.js';

export const featurePages = ['Submit report', 'Track report', 'Weather explorer', 'Weather trends', 'Review queue', 'Ingestion monitor'];
const events = { heavy_rain: 'Heavy rain', flood: 'Flood', heatwave: 'Heatwave', cold_wave: 'Cold wave', storm: 'Storm', cyclone: 'Cyclone', drought: 'Drought', landslide: 'Landslide', lightning: 'Lightning', hail: 'Hail', fog: 'Fog', other: 'Other' };
const metrics = { temperature_c: 'Temperature', relative_humidity_pct: 'Relative humidity', precipitation_mm: 'Rainfall', wind_speed_kmh: 'Wind speed', wind_gust_kmh: 'Wind gust' };
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const number = value => value === null || value === undefined ? '–' : esc(value);
const query = values => new URLSearchParams(Object.entries(values).filter(([, value]) => value !== '' && value !== undefined && value !== null)).toString();
const options = (values, selected = '') => Object.entries(values).map(([value, label]) => `<option value="${esc(value)}" ${String(selected) === value ? 'selected' : ''}>${esc(label)}</option>`).join('');
const field = (name, label, control) => `<label class="p0-field">${label}${control}<small data-error="${name}" role="alert"></small></label>`;
const input = (name, label, attributes = '') => field(name, label, `<input name="${name}" ${attributes}>`);
const statusLabel = status => status === 'verified' ? 'Verified by reviewer' : status === 'pending' ? 'Pending review' : 'Rejected';
const statusBadge = value => `<span class="badge ${esc(value)}">${esc(statusLabel(value))}</span>`;
function safeLink(url, label) {
  try { const parsed = new URL(url); if (parsed.protocol === 'https:' || parsed.protocol === 'http:') return `<a href="${esc(parsed.href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`; } catch { /* Plain metadata for invalid URLs. */ }
  return esc(label);
}
function errorText(error) { return `${error.message}${error.request_id ? ` · Request ID: ${error.request_id}` : ''}`; }
function showError(node, error) { node.textContent = errorText(error); node.setAttribute('role', 'alert'); }
function mapErrors(form, error) {
  form.querySelectorAll('[data-error]').forEach(node => { node.textContent = ''; });
  for (const detail of error.details || []) {
    const name = String(detail.field || '').replace(/^body\./, '').replace(/\[(\d+)\]/g, '.$1');
    const node = [...form.querySelectorAll('[data-error]')].find(item => item.dataset.error === name);
    if (node) node.textContent = detail.issue || 'Invalid value';
  }
}
function cooldown(button, path, method = 'GET') {
  const label = button.textContent;
  function tick() {
    if (!button.isConnected) return;
    const remaining = retryRemaining(path, method);
    button.disabled = remaining > 0;
    button.textContent = remaining ? `${label} (${remaining}s)` : label;
    if (remaining) setTimeout(tick, 1000);
  }
  tick();
}
let stopActive = () => {};
export function stopFeature() { stopActive(); stopActive = () => {}; }
export function renderFeature(page, context) {
  stopFeature();
  const root = document.querySelector('#p0-content');
  if (!root) return;
  const abort = new AbortController();
  let poll;
  stopActive = () => { abort.abort(); clearTimeout(poll); };
  const reads = new Map();
  const api = (path, init = {}) => {
    const signals = [abort.signal, ...(init.signal ? [init.signal] : [])];
    if (!init.method || init.method === 'GET') {
      const key = path.split('?')[0].replace(/^(\/weather\/|\/admin\/ingestion\/runs\/)\d+$/, '$1detail');
      reads.get(key)?.abort(); const current = new AbortController(); reads.set(key, current); signals.push(current.signal);
    }
    return request(path, { ...init, signal: AbortSignal.any(signals) });
  };
  const date = value => value ? new Date(value).toLocaleString('en-IN', context.utc() ? { timeZone: 'UTC' } : {}) : '–';
  const locations = context.locations;
  const locationOptions = () => options(Object.fromEntries(locations.map(item => [item.id, item.name])));
  const blank = text => `<div class="empty" role="status">${text}</div>`;
  const panel = (title, content) => `<section class="panel p0-panel"><div class="panel-head"><div><h2>${title}</h2></div></div>${content}</section>`;
  const utcButton = () => `<button class="button" type="button" data-utc aria-pressed="${context.utc()}">Time zone: ${context.utc() ? 'UTC' : 'Local time'}</button>`;
  function bindUTC(redraw) { root.querySelector('[data-utc]')?.addEventListener('click', () => { context.toggleUTC(); redraw(); }); }
  function failure(node, error, retry) {
    if (error.name === 'AbortError' || abort.signal.aborted) return;
    node.replaceChildren();
    const message = document.createElement('p'); showError(message, error); node.append(message);
    if (error.status !== 403) {
      const button = document.createElement('button'); button.className = 'button'; button.textContent = 'Retry'; button.onclick = retry; node.append(button);
      if (error.status === 429) { button.disabled = true; let remaining = error.retry_after; const tick = () => { if (!button.isConnected) return; button.textContent = remaining ? `Retry (${remaining--}s)` : 'Retry'; button.disabled = remaining >= 0; if (remaining >= 0) setTimeout(tick, 1000); }; tick(); }
    }
  }
  function pager(data, change) {
    const wrap = document.createElement('div'); wrap.className = 'table-footer';
    wrap.innerHTML = `<span>${data.total ? data.offset + 1 : 0}–${Math.min(data.offset + data.items.length, data.total)} of ${data.total}</span><div><button data-prev ${data.offset === 0 ? 'disabled' : ''}>← Previous</button><button data-next ${data.offset + data.limit >= data.total ? 'disabled' : ''}>Next →</button></div>`;
    wrap.querySelector('[data-prev]').onclick = () => change(Math.max(0, data.offset - data.limit));
    wrap.querySelector('[data-next]').onclick = () => change(data.offset + data.limit);
    return wrap;
  }
  const getValues = form => Object.fromEntries(new FormData(form));
  function range(values, maxDays) {
    const start = Date.parse(values.from), end = Date.parse(values.to);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) throw new Error('Choose a valid date range with the end after the start.');
    if (end - start > maxDays * 86400000) throw new Error(`Choose a range of at most ${maxDays} days.`);
    return { from: new Date(start).toISOString(), to: new Date(end).toISOString() };
  }
  const localInput = value => { const d = new Date(value); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
  const dateFilters = (days = 7) => input('from', 'From (local)', `type="datetime-local" required value="${localInput(Date.now() - days * 86400000)}"`) + input('to', 'To (local, exclusive)', `type="datetime-local" required value="${localInput(Date.now())}"`);
  const selectLocation = (required = false) => field('location_id', 'Location', `<select name="location_id" ${required ? 'required' : ''}><option value="">${required ? 'Choose location' : 'All locations'}</option>${locationOptions()}</select>`);
  const selectKind = () => field('kind', 'Kind', `<select name="kind">${options({ observation: 'Observation', forecast: 'Forecast' })}</select>`);

  if (page === 'Submit report') {
    root.innerHTML = panel('Submit a citizen report', `<form id="submit-report" class="p0-form">${field('event_type', 'Event type', `<select name="event_type" required><option value="">Choose event</option>${options(events)}</select>`)}${field('severity', 'Severity (optional)', `<select name="severity"><option value="">Not specified</option>${options({ low: 'Low', moderate: 'Moderate', high: 'High', extreme: 'Extreme' })}</select>`)}${field('description', 'Description', '<textarea name="description" required minlength="10" maxlength="2000" rows="4"></textarea>')}${input('location_name', 'Location name (optional)', 'maxlength="200"')}${input('latitude', 'Latitude', 'type="number" min="-90" max="90" step="any" required')}${input('longitude', 'Longitude', 'type="number" min="-180" max="180" step="any" required')}<button type="button" class="button" id="geolocate">Use my location</button>${input('event_time', 'Event time (local)', 'type="datetime-local" required')}${input('contact_email', 'Contact email (optional; stays private)', 'type="email"')}<fieldset class="p0-evidence"><legend>Evidence links (optional, up to 5)</legend><p>Metadata only. Links are never fetched or embedded.</p><div id="evidence-entries"></div><button type="button" class="button" id="add-evidence">Add evidence</button><small data-error="evidence"></small></fieldset><button class="primary" id="submit-action">Submit report</button><p id="submit-result" role="status"></p></form>`);
    const form = root.querySelector('form'), result = root.querySelector('#submit-result');
    let entries = [], sequence = 0;
    const drawEvidence = () => {
      root.querySelector('#evidence-entries').innerHTML = entries.map((item, index) => `<div class="p0-evidence-row" data-entry="${item.key}">${field(`evidence.${index}.type`, 'Type', `<select data-key="type">${options({ photo: 'Photo', video: 'Video', link: 'Link', other: 'Other' }, item.type)}</select>`)}${field(`evidence.${index}.url`, 'HTTPS URL', `<input data-key="url" type="url" required maxlength="2048" value="${esc(item.url)}">`)}${field(`evidence.${index}.description`, 'Description (optional)', `<input data-key="description" maxlength="200" value="${esc(item.description)}">`)}<button type="button" class="button" data-remove="${item.key}">Remove evidence ${index + 1}</button></div>`).join('');
      root.querySelector('#add-evidence').disabled = entries.length >= 5;
      root.querySelectorAll('[data-entry] [data-key]').forEach(node => node.oninput = () => { entries.find(item => item.key === Number(node.closest('[data-entry]').dataset.entry))[node.dataset.key] = node.value; });
      root.querySelectorAll('[data-remove]').forEach(node => node.onclick = () => { entries = entries.filter(item => item.key !== Number(node.dataset.remove)); drawEvidence(); });
    };
    root.querySelector('#add-evidence').onclick = () => { entries.push({ key: sequence++, type: 'photo', url: '', description: '' }); drawEvidence(); };
    root.querySelector('#geolocate').onclick = () => {
      if (!navigator.geolocation) { result.textContent = 'Geolocation is unavailable. Enter coordinates manually.'; return; }
      navigator.geolocation.getCurrentPosition(position => { if (!form.isConnected) return; form.elements.latitude.value = position.coords.latitude; form.elements.longitude.value = position.coords.longitude; }, () => { result.textContent = 'Could not get your location. Enter coordinates manually.'; });
    };
    form.onsubmit = async event => {
      event.preventDefault(); const button = root.querySelector('#submit-action'); const values = getValues(form); const errors = [];
      const at = Date.parse(values.event_time);
      if (values.description.trim().length < 10) errors.push({ field: 'description', issue: 'Enter 10 to 2000 characters.' });
      if (!Number.isFinite(at) || at > Date.now() + 300000 || at < Date.now() - 30 * 86400000) errors.push({ field: 'event_time', issue: 'Use a time within the last 30 days and no more than 5 minutes ahead.' });
      entries.forEach((item, index) => { try { if (new URL(item.url).protocol !== 'https:') throw new Error(); } catch { errors.push({ field: `evidence.${index}.url`, issue: 'Use a valid HTTPS URL.' }); } });
      mapErrors(form, { details: errors }); if (errors.length) { result.textContent = 'Check the highlighted fields.'; return; }
      const body = { event_type: values.event_type, description: values.description.trim(), latitude: Number(values.latitude), longitude: Number(values.longitude), event_time: new Date(at).toISOString(), evidence: entries.map(({ type, url, description }) => ({ type, url, description })) };
      for (const key of ['severity', 'location_name', 'contact_email']) if (values[key]) body[key] = values[key];
      button.disabled = true; result.textContent = 'Submitting…';
      try {
        const response = await api('/reports', { method: 'POST', body });
        form.reset(); entries = []; drawEvidence(); result.textContent = 'Report submitted. Pending review.';
        const dialog = document.querySelector('#detail');
        dialog.innerHTML = `<div class="dialog-head"><h2>Save your tracking token</h2><button type="button" data-close aria-label="Close token dialog">×</button></div><div class="dialog-body"><p>This token is shown once. Save it with the report ID before closing. It cannot be displayed again.</p><dl><dt>Report ID</dt><dd>${esc(response.id)}</dd><dt>Tracking token</dt><dd class="p0-token">${esc(response.tracking_token)}</dd><dt>Status</dt><dd>Pending review</dd><dt>Submitted</dt><dd>${date(response.submitted_at)}</dd></dl><button class="primary" data-copy>Copy ID and token</button><p data-copy-status role="status"></p><button class="button" data-close>I have saved the token</button></div>`;
        dialog.querySelectorAll('[data-close]').forEach(node => node.onclick = () => dialog.close());
        dialog.querySelector('[data-copy]').onclick = async () => { try { await navigator.clipboard.writeText(`Report ID: ${response.id}\nTracking token: ${response.tracking_token}`); dialog.querySelector('[data-copy-status]').textContent = 'Copied.'; } catch { dialog.querySelector('[data-copy-status]').textContent = 'Copy unavailable. Select and save the ID and token manually.'; } };
        dialog.addEventListener('close', () => { dialog.replaceChildren(); response.tracking_token = null; }, { once: true }); dialog.showModal();
      } catch (error) { if (error.name !== 'AbortError') { mapErrors(form, error); showError(result, error); if (error.status === 403) { button.hidden = true; } } }
      finally { cooldown(button, '/reports', 'POST'); }
    };
    cooldown(root.querySelector('#submit-action'), '/reports', 'POST'); return;
  }
  if (page === 'Track report') {
    root.innerHTML = panel('Track my report', `<form class="p0-form">${input('id', 'Report ID', 'required autocomplete="off"')}${input('token', 'Tracking token', 'type="password" required autocomplete="off"')}<button class="primary">Check status</button></form><div id="track-result" role="status"></div>`);
    const form = root.querySelector('form'), result = root.querySelector('#track-result');
    form.onsubmit = async event => {
      event.preventDefault(); const values = getValues(form), path = `/reports/${encodeURIComponent(values.id.trim())}`, button = form.querySelector('button'); button.disabled = true; result.textContent = 'Checking…';
      try { const report = await api(path, { headers: { 'X-Tracking-Token': values.token.trim() } }); result.innerHTML = `<dl><dt>Report</dt><dd>${esc(report.id)}</dd><dt>Status</dt><dd>${statusBadge(report.status)}</dd><dt>Reviewed</dt><dd>${date(report.reviewed_at)}</dd></dl>`; }
      catch (error) { if (error.status === 404) { result.textContent = `Not found or token invalid.${error.request_id ? ` Request ID: ${error.request_id}` : ''}`; } else if (error.name !== 'AbortError') showError(result, error); }
      finally { cooldown(button, path); }
    }; return;
  }
  if (page === 'Weather explorer' || page === 'Weather trends') {
    const trends = page === 'Weather trends';
    root.innerHTML = panel(page, `<form class="p0-form p0-filters">${selectLocation(trends)}${selectKind()}${dateFilters()}${trends ? field('metric', 'Metric', `<select name="metric">${options(metrics)}</select>`) + field('interval', 'Interval', `<select name="interval">${options({ day: 'Day', hour: 'Hour', week: 'Week', month: 'Month' })}</select>`) + field('agg', 'Aggregation', `<select name="agg">${options({ avg: 'Average', min: 'Minimum', max: 'Maximum', count: 'Count' })}</select>`) + '<label><input type="checkbox" name="include_trend"> Show trend line</label>' : input('source', 'Source name (optional)', 'placeholder="Backend source name"') + field('sort', 'Sort by valid time', `<select name="sort">${options({ '-valid_at': 'Newest first', valid_at: 'Oldest first' })}</select>`)}<button class="primary">Apply filters</button><p data-filter-error role="alert"></p></form><div id="weather-result"></div>`);
    const form = root.querySelector('form'), result = root.querySelector('#weather-result');
    let selected = null, current = null, readAbort;
    if (trends) form.elements.metric.onchange = () => { const rain = form.elements.metric.value === 'precipitation_mm'; form.elements.agg.innerHTML = options(rain ? { sum: 'Sum', avg: 'Average', min: 'Minimum', max: 'Maximum', count: 'Count' } : { avg: 'Average', min: 'Minimum', max: 'Maximum', count: 'Count' }); };
    const attribution = (source, kind) => `<span class="badge">${source?.trust_level === 'provider_model' ? kind === 'forecast' ? 'Forecast · model-derived' : 'Model-derived observation' : source?.trust_level === 'official' ? 'Official data' : esc(source?.trust_level || 'Unknown trust')}</span> ${esc(source?.display_name || source?.name || '')}<small>${esc(source?.attribution_text || '')}</small>`;
    const draw = () => {
      if (!current) return;
      if (trends) { drawSeries(); return; }
      result.innerHTML = `${utcButton()}<div class="table-scroll"><table><thead><tr><th>Valid time</th><th>Location</th><th>Temperature °C</th><th>Humidity %</th><th>Rain mm</th><th>Wind km/h</th><th>Kind / basis / trust</th></tr></thead><tbody>${current.items.map(record => `<tr><td><button class="report-link" data-weather="${esc(record.id)}">${date(record.valid_at)}</button></td><td>${esc(record.location?.name)}</td>${['temperature_c', 'relative_humidity_pct', 'precipitation_mm', 'wind_speed_kmh'].map(metric => `<td>${number(record.measurements?.[metric])}</td>`).join('')}<td><span class="badge">${esc(record.kind)}</span> <span class="badge">${esc(record.measurement_basis)}</span>${attribution(record.source, record.kind)}</td></tr>`).join('') || '<tr><td colspan="7">No weather records in this range.</td></tr>'}</tbody></table></div>`;
      result.append(pager(current, load)); bindUTC(draw);
      result.querySelectorAll('[data-weather]').forEach(button => button.onclick = () => weatherDetail(button.dataset.weather));
    };
    async function weatherDetail(id) {
      const dialog = document.querySelector('#detail'); dialog.innerHTML = '<div class="dialog-body" role="status">Loading weather detail…</div>'; dialog.showModal();
      try { const record = await api(`/weather/${encodeURIComponent(id)}`); if (!dialog.open) return; dialog.innerHTML = `<div class="dialog-head"><h2>Weather record ${esc(record.id)}</h2><button data-close aria-label="Close weather detail">×</button></div><div class="dialog-body"><p>${esc(record.location?.name)} · ${date(record.valid_at)}</p><p>${esc(record.kind)} · ${esc(record.measurement_basis)}</p>${attribution(record.source, record.kind)}<dl>${Object.entries(record.measurements || {}).map(([key, value]) => `<dt>${esc(key.replaceAll('_', ' '))}</dt><dd>${number(value)}</dd>`).join('')}</dl><p>Issued: ${date(record.issued_at)} · Fetched: ${date(record.fetched_at)}</p></div>`; dialog.querySelector('[data-close]').onclick = () => dialog.close(); }
      catch (error) { if (error.name !== 'AbortError' && error.status !== 401) { dialog.innerHTML = '<div class="dialog-head"><button data-close>Close</button></div><div class="dialog-body" data-error></div>'; showError(dialog.querySelector('[data-error]'), error); dialog.querySelector('[data-close]').onclick = () => dialog.close(); } }
    }
    function drawSeries() {
      const buckets = current.buckets || [], values = buckets.map(item => item.value).filter(value => value !== null && value !== undefined);
      const min = Math.min(0, ...values), max = Math.max(1, ...values), x = i => 40 + i * 860 / Math.max(1, buckets.length - 1), y = value => 230 - (value - min) / (max - min) * 190;
      let pen = false; const path = buckets.map((bucket, index) => { if (bucket.value === null || bucket.value === undefined) { pen = false; return ''; } const command = pen ? 'L' : 'M'; pen = true; return `${command}${x(index)},${y(bucket.value)}`; }).join(' ');
      const rain = selected.metric === 'precipitation_mm';
      const valid = buckets.map((bucket, index) => ({ ...bucket, index })).filter(bucket => bucket.value !== null && bucket.value !== undefined);
      const first = valid[0];
      const trendPath = selected.include_trend === 'true' && current.trend?.slope_per_day != null && first ? `<path class="p0-trendline" d="M${x(first.index)},${y(first.value)} L${x(buckets.length - 1)},${y(first.value + current.trend.slope_per_day * (Date.parse(buckets.at(-1).start) - Date.parse(first.start)) / 86400000)}"/>` : '';
      result.innerHTML = `${utcButton()}<h3>${esc(metrics[current.metric] || current.metric)} (${esc(current.unit)})</h3>${buckets.length ? `<svg class="p0-chart" viewBox="0 0 940 270" role="img" aria-label="${esc(metrics[current.metric] || current.metric)}. Missing values are gaps. Values and sample counts are in the table below."><line x1="40" y1="${y(0)}" x2="920" y2="${y(0)}" stroke="currentColor" opacity=".3"/><text x="0" y="30" fill="currentColor">${esc(max.toFixed(1))}</text><text x="0" y="245" fill="currentColor">${esc(min.toFixed(1))}</text>${rain ? valid.map(bucket => `<rect x="${x(bucket.index) - Math.min(20, 350 / buckets.length)}" y="${Math.min(y(bucket.value), y(0))}" width="${Math.max(.3, Math.min(40, 700 / buckets.length))}" height="${Math.abs(y(bucket.value) - y(0))}" fill="var(--accent)"><title>${esc(bucket.start)}: ${number(bucket.value)} ${esc(current.unit)}; sample_count ${number(bucket.sample_count)}</title></rect>`).join('') : `<path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2"/>${valid.map(bucket => `<circle cx="${x(bucket.index)}" cy="${y(bucket.value)}" r="3" fill="var(--accent)"><title>${esc(bucket.start)}: ${number(bucket.value)} ${esc(current.unit)}; sample_count ${number(bucket.sample_count)}</title></circle>`).join('')}`}${trendPath}</svg>` : blank('No buckets returned.')}<p>Missing measurements are gaps. ${current.trend ? `Trend slope: ${number(current.trend.slope_per_day)} ${esc(current.unit)}/day. Dashed line is anchored to the first available bucket.` : ''}</p><div>${(current.sources || []).map(source => attribution(source, current.kind)).join('<br>')}</div><details><summary>Chart values and sample counts</summary><div class="table-scroll"><table><thead><tr><th>Bucket start</th><th>Value (${esc(current.unit)})</th><th>Sample count</th></tr></thead><tbody>${buckets.map(bucket => `<tr><td>${date(bucket.start)}</td><td>${number(bucket.value)}</td><td>${number(bucket.sample_count)}</td></tr>`).join('') || '<tr><td colspan="3">No data</td></tr>'}</tbody></table></div></details>`;
      bindUTC(drawSeries);
    }
    async function load(offset = 0) {
      readAbort?.abort(); readAbort = new AbortController();
      result.innerHTML = blank('Loading weather…'); const button = form.querySelector('button'); button.disabled = true;
      const path = trends ? '/analytics/timeseries' : '/weather';
      try { current = await api(`${path}?${query({ ...selected, ...(trends ? {} : { limit: 50, offset }) })}`, { signal: readAbort.signal }); draw(); }
      catch (error) { mapErrors(form, error); failure(result, error, () => load(offset)); }
      finally { cooldown(button, path); }
    }
    form.onsubmit = event => {
      event.preventDefault(); const error = form.querySelector('[data-filter-error]'); error.textContent = '';
      try {
        const values = getValues(form); selected = { ...values, ...range(values, trends ? 366 : 31) };
        if (trends) {
          selected.fill_gaps = 'true'; selected.include_trend = form.elements.include_trend.checked ? 'true' : 'false';
          const start = new Date(selected.from), end = new Date(selected.to); let buckets = 0;
          start.setUTCMinutes(0, 0, 0);
          if (selected.interval !== 'hour') start.setUTCHours(0, 0, 0, 0);
          if (selected.interval === 'week') start.setUTCDate(start.getUTCDate() - (start.getUTCDay() + 6) % 7);
          if (selected.interval === 'month') start.setUTCDate(1);
          while (start < end && buckets <= 2000) { buckets++; if (selected.interval === 'month') start.setUTCMonth(start.getUTCMonth() + 1, 1); else start.setTime(start.getTime() + ({ hour: 3600000, day: 86400000, week: 604800000 }[selected.interval])); }
          if (buckets > 2000) throw new Error('This range exceeds 2000 buckets. Choose a larger interval or shorter range.');
        }
        load();
      } catch (problem) { error.textContent = problem.message; }
    };
    if (!trends) form.requestSubmit(); else result.innerHTML = blank('Choose a location and apply filters.'); return;
  }

  if (page === 'Review queue') {
    if (!context.staff) { root.innerHTML = blank('Not permitted. Sign in as a reviewer or administrator.'); return; }
    root.innerHTML = panel('Moderation queue', `<form class="p0-form p0-filters">${selectLocation()}${field('event_type', 'Event type', `<select name="event_type"><option value="">All events</option>${options(events)}</select>`)}${dateFilters(30)}<button class="primary">Apply filters</button><p data-filter-error role="alert"></p></form><p>Pending reports, oldest submission first. Contact details and review notes are private.</p><div id="queue-result"></div>`);
    const form = root.querySelector('form'), result = root.querySelector('#queue-result'); let filters = {}, current;
    const draw = () => {
      result.innerHTML = `${utcButton()}<div class="table-scroll"><table><thead><tr><th>Event / ID</th><th>Location</th><th>Submitted / event time</th><th>Contact (private)</th><th>Status</th></tr></thead><tbody>${current.items.map(report => `<tr><td><button class="report-link" data-review="${esc(report.id)}">${esc(events[report.event_type] || report.event_type)}<small>${esc(report.id)}</small></button></td><td>${esc(report.location?.name || report.location_name || 'Unassigned')}</td><td>${date(report.submitted_at)}<small>${date(report.event_time)}</small></td><td>${esc(report.contact_email || '–')}</td><td>${statusBadge(report.status)}</td></tr>`).join('') || '<tr><td colspan="5">No pending reports match these filters.</td></tr>'}</tbody></table></div>`;
      result.append(pager(current, load)); bindUTC(draw);
      result.querySelectorAll('[data-review]').forEach(button => button.onclick = () => openReview(button.dataset.review, context, () => load(current.offset)));
    };
    async function load(offset = 0) {
      result.innerHTML = blank('Loading pending reports…');
      try { current = await api(`/admin/reports/pending?${query({ ...filters, limit: 50, offset })}`); draw(); }
      catch (error) { failure(result, error, () => load(offset)); }
    }
    form.onsubmit = event => { event.preventDefault(); try { const values = getValues(form); filters = { ...values, ...range(values, 31) }; form.querySelector('[data-filter-error]').textContent = ''; load(); } catch (error) { form.querySelector('[data-filter-error]').textContent = error.message; } }; form.requestSubmit(); return;
  }
  if (page === 'Ingestion monitor') {
    if (context.role !== 'admin') { root.innerHTML = blank('Not permitted. Administrator access is required.'); return; }
    root.innerHTML = panel('Ingestion monitor', `<p>Runs stay queued until the backend worker is running. Sources must be configured and enabled.</p><div id="run-sources" role="status">Loading sources…</div><form class="p0-form p0-filters">${input('source', 'Source name (optional)')}${field('status', 'Status', `<select name="status"><option value="">All statuses</option>${options(Object.fromEntries(['queued', 'running', 'succeeded', 'partial', 'failed', 'abandoned'].map(value => [value, value])))}</select>`)}${dateFilters()}<button class="primary">Apply filters</button><p data-filter-error role="alert"></p></form><div id="runs-result"></div>`);
    const sourceRoot = root.querySelector('#run-sources'), result = root.querySelector('#runs-result'), form = root.querySelector('form'); let filters = {}, current, selectedRun = null;
    const draw = () => {
      result.innerHTML = `${utcButton()}<div class="table-scroll"><table><thead><tr><th>Run</th><th>Source</th><th>Status</th><th>Queued</th><th>Fetched / inserted / updated / skipped / failed</th></tr></thead><tbody>${current.items.map(run => `<tr><td><button class="report-link" data-run="${esc(run.id)}">${esc(run.id)}</button></td><td>${esc(run.source_name)}</td><td><span class="badge">${esc(run.status)}</span></td><td>${date(run.queued_at)}</td><td>${['records_fetched', 'inserted', 'updated', 'skipped', 'failed'].map(key => number(run[key])).join(' / ')}</td></tr>`).join('') || '<tr><td colspan="5">No ingestion runs match these filters.</td></tr>'}</tbody></table></div><div id="run-detail"></div>`;
      result.append(pager(current, load)); bindUTC(() => { draw(); if (selectedRun) detail(selectedRun); }); result.querySelectorAll('[data-run]').forEach(button => button.onclick = () => detail(button.dataset.run));
    };
    async function load(offset = 0) { result.innerHTML = blank('Loading ingestion runs…'); try { current = await api(`/admin/ingestion/runs?${query({ ...filters, limit: 50, offset })}`); draw(); } catch (error) { failure(result, error, () => load(offset)); } }
    async function detail(id) {
      selectedRun = id; clearTimeout(poll); const node = root.querySelector('#run-detail'); if (!node) return; node.innerHTML = blank('Loading run detail…');
      try {
        const run = await api(`/admin/ingestion/runs/${encodeURIComponent(id)}`); if (selectedRun !== id || !node.isConnected) return;
        const listed = current?.items.find(item => String(item.id) === String(id));
        if (listed) Object.assign(listed, run);
        const row = [...result.querySelectorAll('[data-run]')].find(button => button.dataset.run === String(id))?.closest('tr');
        if (row) { row.children[2].textContent = run.status; row.children[4].textContent = ['records_fetched', 'inserted', 'updated', 'skipped', 'failed'].map(key => run[key] ?? '–').join(' / '); }
        node.innerHTML = `<h3>Run ${esc(run.id)} · ${esc(run.status)}</h3><p>${esc(run.source_name)} · ${esc(run.trigger)}</p><dl><dt>Started</dt><dd>${date(run.started_at)}</dd><dt>Finished</dt><dd>${date(run.finished_at)}</dd>${['records_fetched', 'inserted', 'updated', 'skipped', 'failed'].map(key => `<dt>${esc(key)}</dt><dd>${number(run[key])}</dd>`).join('')}</dl><p>${esc(run.error_summary || '')}</p><pre class="p0-json">${esc(JSON.stringify(run.details, null, 2) || 'No additional details.')}</pre>${run.status === 'queued' ? '<p>Waiting for the backend worker. This run may remain queued if the worker is stopped.</p>' : ''}`;
        if (['queued', 'running'].includes(run.status)) poll = setTimeout(() => { if (!document.hidden && root.isConnected) detail(id); else if (root.isConnected) poll = setTimeout(() => detail(id), 5000); }, 5000);
      } catch (error) { failure(node, error, () => detail(id)); }
    }
    async function sources() {
      try {
        const response = await api('/admin/sources');
        sourceRoot.innerHTML = response.items.map(source => `<article class="source-row"><div><h3>${esc(source.display_name)}</h3><p>${source.configured ? 'Configured' : 'Not configured'} · ${source.is_enabled ? 'Enabled' : 'Disabled'}</p></div><button class="button" data-trigger="${esc(source.name)}" ${!source.configured || !source.is_enabled ? 'disabled' : ''}>Run now</button><p data-trigger-result="${esc(source.name)}" role="status"></p></article>`).join('') || blank('No sources configured.');
        sourceRoot.querySelectorAll('[data-trigger]').forEach(button => { const path = `/admin/ingestion/${encodeURIComponent(button.dataset.trigger)}/run`; if (!button.disabled) cooldown(button, path, 'POST'); button.onclick = async () => {
          const message = [...sourceRoot.querySelectorAll('[data-trigger-result]')].find(node => node.dataset.triggerResult === button.dataset.trigger); button.disabled = true; let blocked = false;
          try { const run = await api(path, { method: 'POST' }); message.textContent = `Run ${run.run_id} queued.`; await load(); detail(run.run_id); }
          catch (error) { if (error.name !== 'AbortError') { showError(message, error); if (error.status === 403) button.hidden = true; if (error.code === 'already_running') await load(); if (error.code === 'source_not_configured') blocked = true; } }
          finally { if (!blocked) cooldown(button, path, 'POST'); }
        }; });
      } catch (error) { failure(sourceRoot, error, sources); }
    }
    form.onsubmit = event => { event.preventDefault(); try { const values = getValues(form); filters = { ...values, ...range(values, 31) }; form.querySelector('[data-filter-error]').textContent = ''; load(); } catch (error) { form.querySelector('[data-filter-error]').textContent = error.message; } }; form.requestSubmit(); sources();
  }
}

export async function openReview(id, context, refresh = () => {}) {
  const dialog = document.querySelector('#detail');
  const date = value => value ? new Date(value).toLocaleString('en-IN', context.utc() ? { timeZone: 'UTC' } : {}) : '–';
  let generation = 0;
  const historyPath = `/admin/reports/${encodeURIComponent(id)}/reviews`;
  function drawHistory(history) {
    const target = dialog.querySelector('[data-history]'); if (!target) return;
    target.innerHTML = history.items.map(review => `<article><p>${esc(review.reviewer?.display_name)} · ${esc(review.from_status)} → ${esc(review.to_status)} · ${date(review.created_at)}</p><p>${esc(review.reason_code || '')}</p><p>${esc(review.private_notes || '')}</p></article>`).join('') || '<p>No reviews yet.</p>';
    if (!Number.isInteger(history.limit)) return;
    const footer = document.createElement('div'); footer.className = 'table-footer';
    footer.innerHTML = `<span>${history.total ? history.offset + 1 : 0}–${Math.min(history.offset + history.items.length, history.total)} of ${history.total} reviews</span><div><button type="button" data-history-prev ${history.offset === 0 ? 'disabled' : ''}>← Previous</button><button type="button" data-history-next ${history.offset + history.limit >= history.total ? 'disabled' : ''}>Next →</button></div>`;
    footer.querySelector('[data-history-prev]').onclick = () => loadHistory(Math.max(0, history.offset - history.limit));
    footer.querySelector('[data-history-next]').onclick = () => loadHistory(history.offset + history.limit); target.append(footer);
  }
  async function loadHistory(offset) {
    const target = dialog.querySelector('[data-history]'); if (!target) return;
    const restorePaging = target.contains(document.activeElement);
    target.innerHTML = '<p role="status">Loading review history…</p>'; const version = generation;
    try { const history = await request(`${historyPath}?limit=50&offset=${offset}`); if (dialog.open && version === generation) { drawHistory(history); if (restorePaging) target.querySelector('.table-footer button:not(:disabled)')?.focus({ preventScroll: true }); } }
    catch (error) {
      if (!dialog.open || version !== generation || error.status === 401) return;
      target.innerHTML = '<p role="alert"></p>'; showError(target.firstElementChild, error);
      if (error.status !== 403) { const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'button'; retry.textContent = 'Retry history'; retry.onclick = () => loadHistory(offset); target.append(retry); cooldown(retry, historyPath); }
    }
  }
  async function load(message = '') {
    const requestGeneration = ++generation;
    dialog.innerHTML = '<div class="dialog-head"><button data-close>Close</button></div><div class="dialog-body" role="status">Loading report and review history…</div>'; dialog.querySelector('[data-close]').onclick = () => dialog.close(); if (!dialog.open) dialog.showModal();
    try {
      const [report, history] = await Promise.all([request(`/reports/${encodeURIComponent(id)}`), ...(context.staff ? [request(`${historyPath}?limit=50&offset=0`)] : [Promise.resolve({ items: [] })])]);
      if (!dialog.open || generation !== requestGeneration) return;
      const permitted = context.staff && (report.status === 'pending' || context.role === 'admin') && Number.isInteger(report.row_version);
      dialog.innerHTML = `<div class="dialog-head"><h2>Report detail</h2><button data-close aria-label="Close report">×</button></div><div class="dialog-body"><h3>${esc(events[report.event_type] || report.event_type)} · ${esc(report.location?.name || report.location_name)}</h3>${statusBadge(report.status)}<p>${esc(report.id)}</p><p class="description">${esc(report.description)}</p><dl><dt>Event time</dt><dd>${date(report.event_time)}</dd><dt>Severity</dt><dd>${esc(report.severity || 'Not specified')}</dd><dt>Coordinates</dt><dd>${number(report.latitude)}, ${number(report.longitude)}</dd>${context.staff ? `<dt>Contact (private)</dt><dd>${esc(report.contact_email || '–')}</dd>` : ''}</dl><h3>Evidence</h3>${(report.evidence || []).map(item => `<p>${esc(item.type)} · ${esc(item.description)}${context.staff && item.url ? ` · ${safeLink(item.url, 'Open evidence')}` : item.has_link ? '<small>Link supplied; not publicly available.</small>' : ''}</p>`).join('') || '<p>No evidence provided.</p>'}${context.staff ? `<h3>Review history (private)</h3><div data-history></div>` : ''}<p data-review-message role="status">${esc(message)}</p>${permitted ? `<form class="p0-form" id="review-form">${field('notes', 'Private notes', '<textarea name="notes" maxlength="2000" rows="3"></textarea>')}${input('reason_code', 'Reason code (optional)', 'maxlength="50"')}<div class="review-actions">${report.status === 'pending' ? '<button class="primary" name="decision" value="verify">Verify report</button><button class="button" name="decision" value="reject">Reject report</button>' : report.status === 'verified' ? '<button class="button" name="decision" value="reject">Retract verification</button>' : '<button class="button" name="decision" value="reopen">Reopen report</button>'}</div><p data-review-error role="alert"></p></form>` : ''}</div>`;
      dialog.querySelector('[data-close]').onclick = () => dialog.close();
      if (context.staff) drawHistory(history);
      const form = dialog.querySelector('form'); if (!form) return;
      const path = `/admin/reports/${encodeURIComponent(id)}/review`; form.querySelectorAll('button').forEach(button => cooldown(button, path, 'POST'));
      form.onsubmit = async event => {
        event.preventDefault(); const decision = event.submitter.value, values = Object.fromEntries(new FormData(form)), result = form.querySelector('[data-review-error]');
        if ((report.status !== 'pending' || decision === 'reopen') && !values.notes.trim()) { result.textContent = 'Notes are required to retract or reopen a report.'; return; }
        if (decision === 'reject' && !values.notes.trim() && !values.reason_code.trim()) { result.textContent = 'Add notes or a reason code before rejecting.'; return; }
        form.querySelectorAll('button').forEach(button => { button.disabled = true; });
        try {
          await request(path, { method: 'POST', body: { decision, notes: values.notes.trim() || null, reason_code: values.reason_code.trim() || null, expected_row_version: report.row_version } });
          refresh(); await load('Review saved.');
        } catch (error) {
          if (error.status === 409 && ['stale_version', 'invalid_transition'].includes(error.code)) { refresh(); await load(error.code === 'stale_version' ? 'Someone else changed this report. Data and allowed actions have been reloaded. Check before trying again.' : 'This transition is no longer available. Data and allowed actions have been reloaded.'); }
          else { showError(result, error); mapErrors(form, error); if (error.status === 403) form.querySelector('.review-actions').hidden = true; }
        } finally { if (form.isConnected) form.querySelectorAll('button').forEach(button => cooldown(button, path, 'POST')); }
      };
    } catch (error) {
      if (error.status === 401 || !dialog.open || generation !== requestGeneration) return;
      dialog.innerHTML = '<div class="dialog-head"><button data-close>Close</button></div><div class="dialog-body"><p data-error></p><button data-retry class="button">Retry</button></div>'; showError(dialog.querySelector('[data-error]'), error); dialog.querySelector('[data-close]').onclick = () => dialog.close(); dialog.querySelector('[data-retry]').onclick = () => load(); if (error.status === 403) dialog.querySelector('[data-retry]').hidden = true;
      if (error.status === 429) { const button = dialog.querySelector('[data-retry]'); let remaining = error.retry_after; const tick = () => { if (!button.isConnected) return; button.disabled = remaining > 0; button.textContent = remaining ? `Retry (${remaining--}s)` : 'Retry'; if (button.disabled) setTimeout(tick, 1000); }; tick(); }
    }
  }
  await load();
}
