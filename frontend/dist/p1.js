import { request, retryRemaining } from './api.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const value = n => n === null || n === undefined ? '–' : typeof n === 'number' ? n.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : esc(n);
export const errorMessage = error => `${error.status === 403 ? 'Not permitted.' : error.message}${error.request_id ? ` · Request ID: ${error.request_id}` : ''}`;
export function trust(source, kind = 'observation') {
  return source?.trust_level === 'provider_model' ? kind === 'forecast' ? 'Forecast · model-derived' : 'Model-derived observation' : source?.trust_level === 'official' ? 'Official data' : source?.trust_level === 'news' ? 'News item, not verified' : source?.trust_level === 'citizen' ? 'Citizen reports' : 'Trust not specified';
}
export function summaryCards(summary, staff) {
  const weather = summary.weather || {}, counts = weather.records_by_kind || weather.record_counts || {}, temperature = weather.temperature_c || {}, wind = weather.wind || {};
  const cards = [
    ['Weather records', value(counts.observation), `Observations · ${value(counts.forecast)} forecasts`],
    ['Locations with data', value(weather.locations_with_data), 'For the selected period and location'],
    ['Temperature °C', value(temperature.mean_of_location_means), `Min ${value(temperature.min)} · Max ${value(temperature.max)} · Mean of location means`],
    ['Wind km/h', value(wind.mean_speed_kmh), `Mean speed · Max gust ${value(wind.max_gust_kmh)}`],
    ['Verified reports', value(summary.reports?.by_status?.verified), 'Verified by reviewer']
  ];
  if (staff) for (const [key, label] of [['pending', 'Awaiting review'], ['rejected', 'Rejected reports']]) {
    if (summary.reports?.by_status?.[key] !== undefined) cards.push([label, value(summary.reports.by_status[key]), key === 'pending' ? 'Pending review' : 'Rejected']);
  }
  return `<section class="metrics" aria-label="Weather summary">${cards.map(([label, n, detail]) => `<article><div>${label}</div><strong>${n}</strong><small>${detail}</small></article>`).join('')}</section>`;
}
export function latestCards(latest, locations, time, selectedLocation) {
  const records = latest.items || [], missing = latest.missing_location_ids || [];
  return `<section class="panel p0-panel"><div class="panel-head"><div><h2>Latest weather</h2><p>Latest observations · As of ${esc(time(latest.as_of))}</p></div></div><div class="p1-weather-grid">${records.map(record => `<article class="settings"><h3>${esc(record.location?.name)}</h3><p>${esc(time(record.valid_at))}</p><span class="badge">${esc(trust(record.source, record.kind))}</span><span class="badge">${esc(record.kind)}</span><span class="badge">${esc(record.measurement_basis)}</span><dl><dt>Temperature</dt><dd>${value(record.measurements?.temperature_c)} °C</dd><dt>Humidity</dt><dd>${value(record.measurements?.relative_humidity_pct)} %</dd><dt>Rainfall</dt><dd>${value(record.measurements?.precipitation_mm)} mm</dd><dt>Wind</dt><dd>${value(record.measurements?.wind_speed_kmh)} km/h</dd></dl><p>${esc(record.source?.display_name || record.source?.name)}</p><small>${esc(record.source?.attribution_text)}</small></article>`).join('')}${missing.filter(id => !selectedLocation || String(id) === String(selectedLocation)).map(id => `<article class="settings"><h3>${esc(locations.find(location => String(location.id) === String(id))?.name || `Location ${id}`)}</h3><p>No data yet</p></article>`).join('')}${!records.length&&!missing.length?'<p class="empty" role="status">No latest weather data yet.</p>':''}</div></section>`;
}
export function freshnessPanel(sources, time) {
  return `<section class="panel p0-panel"><div class="panel-head"><div><h2>Source freshness</h2><p>Status supplied by the backend</p></div></div><div>${sourceRows(sources, time)}</div></section>`;
}
function sourceRows(items, time) {
  return items.map(source => `<article class="source-row"><div><h3>${esc(source.display_name || source.name)}</h3><p>${esc(source.attribution_text || source.name)}</p></div><span class="badge">${esc(trust(source))}</span><span class="freshness">${esc(source.freshness)}</span><small>${source.last_success_at ? esc(time(source.last_success_at)) : 'No successful ingestion yet'}</small></article>`).join('') || '<div class="empty" role="status">No sources configured.</div>';
}
let stop = () => {};
export function stopSources() { stop(); stop = () => {}; }
export async function renderSources(root, context) {
  stopSources();
  const controller = new AbortController(); stop = () => controller.abort();
  const path = context.role === 'admin' ? '/admin/sources' : '/analytics/summary';
  const api = (route, init = {}) => request(route, { ...init, signal: controller.signal });
  root.innerHTML = '<div class="empty" role="status">Loading sources…</div>';
  let items = [], collection = null;
  const alive = () => root.isConnected && !controller.signal.aborted;
  async function load(offset = 0) {
    const restorePaging = root.contains(document.activeElement) && document.activeElement.matches('[data-source-prev],[data-source-next]');
    root.innerHTML = '<div class="empty" role="status">Loading sources…</div>';
    try { const response = await api(context.role === 'admin' ? `${path}?limit=50&offset=${offset}` : path); if (!alive()) return; collection = response; items = response.items || response.sources || []; draw(); if (restorePaging) root.querySelector('.table-footer button:not(:disabled)')?.focus({ preventScroll: true }); }
    catch (error) {
      if (!alive() || error.name === 'AbortError' || error.status === 401) return;
      root.innerHTML = `<div class="empty"><p role="alert">${esc(errorMessage(error))}</p>${error.status === 403 ? '' : '<button class="button" data-retry>Retry</button>'}</div>`;
      const button = root.querySelector('[data-retry]'); if (button) { button.onclick = () => load(); countdown(button, path); }
    }
  }
  function countdown(button, route, method = 'GET') {
    const label = button.dataset.label || button.textContent; button.dataset.label = label;
    const tick = () => { if (!alive() || !button.isConnected) return; const remaining = retryRemaining(route, method); button.disabled = remaining > 0; button.textContent = remaining ? `${label} (${remaining}s)` : label; if (remaining) setTimeout(tick, 1000); }; tick();
  }
  function draw() {
    if (context.role !== 'admin') { root.innerHTML = sourceRows(items, context.time); return; }
    root.innerHTML = items.map(source => `<article class="p1-source" data-source="${esc(source.id)}"><div class="source-row"><div><h3>${esc(source.display_name)}</h3><p>${esc(source.name)} · ${source.configured ? 'Configured' : 'Not configured'}</p></div><span class="badge">${esc(trust(source))}</span><span class="freshness">${esc(source.freshness)}</span><small>Last success: ${esc(context.time(source.last_success_at))}</small></div><details><summary>Edit source</summary><form class="p0-form"><label class="p0-field">Display name<input name="display_name" required maxlength="100" value="${esc(source.display_name)}"><small data-field="display_name" role="alert"></small></label><label class="p0-field">Interval (seconds)<input name="interval_seconds" type="number" min="300" max="86400" step="1" required value="${esc(source.interval_seconds)}"><small data-field="interval_seconds" role="alert"></small></label><label class="p0-field">Attribution<textarea name="attribution_text" required rows="3">${esc(source.attribution_text)}</textarea><small data-field="attribution_text" role="alert"></small></label><label class="p0-field">Configuration (JSON object)<textarea name="config" rows="5" spellcheck="false">${esc(JSON.stringify(source.config || {}, null, 2))}</textarea><small data-field="config" role="alert"></small></label><label><input name="is_enabled" type="checkbox" ${source.is_enabled ? 'checked' : ''}> Enabled</label><small data-field="is_enabled" role="alert"></small><button class="primary">Save source</button><p data-save-result role="status"></p></form></details></article>`).join('') || '<div class="empty" role="status">No sources configured.</div>';
    if (Number.isInteger(collection?.limit)) {
      const footer = document.createElement('div'); footer.className = 'table-footer';
      footer.innerHTML = `<span>${collection.total ? collection.offset + 1 : 0}–${Math.min(collection.offset + items.length, collection.total)} of ${collection.total}</span><div><button data-source-prev ${collection.offset === 0 ? 'disabled' : ''}>← Previous</button><button data-source-next ${collection.offset + collection.limit >= collection.total ? 'disabled' : ''}>Next →</button></div>`;
      footer.querySelector('[data-source-prev]').onclick = () => load(Math.max(0, collection.offset - collection.limit));
      footer.querySelector('[data-source-next]').onclick = () => load(collection.offset + collection.limit); root.append(footer);
    }
    root.querySelectorAll('[data-source]').forEach(article => {
      const source = items.find(item => String(item.id) === article.dataset.source), form = article.querySelector('form'), button = form.querySelector('button'), message = form.querySelector('[data-save-result]'), route = `/admin/sources/${encodeURIComponent(source.id)}`;
      countdown(button, route, 'PATCH');
      form.onsubmit = async event => {
        event.preventDefault(); form.querySelectorAll('[data-field]').forEach(node => { node.textContent = ''; }); message.textContent = '';
        const values = Object.fromEntries(new FormData(form)); let config;
        try { config = JSON.parse(values.config); if (config === null || Array.isArray(config) || typeof config !== 'object') throw new Error(); }
        catch { form.querySelector('[data-field=config]').textContent = 'Enter a valid JSON object.'; return; }
        if (!values.display_name.trim() || !values.attribution_text.trim()) { message.textContent = 'Display name and attribution cannot be blank.'; return; }
        const body = { display_name: values.display_name.trim(), interval_seconds: Number(values.interval_seconds), attribution_text: values.attribution_text.trim(), config, is_enabled: form.elements.is_enabled.checked };
        button.disabled = true; message.textContent = 'Saving…';
        try {
          const updated = await api(route, { method: 'PATCH', body }); if (!alive()) return;
          Object.assign(source, updated); draw(); const updatedArticle = [...root.querySelectorAll('[data-source]')].find(node => node.dataset.source === String(source.id)); updatedArticle.querySelector('details').open = true; updatedArticle.querySelector('[data-save-result]').textContent = 'Source saved.';
        } catch (error) {
          if (!alive() || error.name === 'AbortError' || error.status === 401) return;
          message.textContent = errorMessage(error);
          for (const detail of error.details || []) {
            const name = String(detail.field || '').replace(/^body\./, ''), target = [...form.querySelectorAll('[data-field]')].find(node => node.dataset.field === name || name.startsWith(`${node.dataset.field}.`));
            if (target) target.textContent = detail.issue || 'Invalid value';
          }
          if (error.code === 'source_not_configured') { form.querySelector('[data-field=is_enabled]').textContent = 'Configure this source before enabling it.'; form.elements.is_enabled.checked = source.is_enabled; }
          if (error.status === 403) { form.hidden = true; article.append(message); }
        } finally { if (button.isConnected) countdown(button, route, 'PATCH'); }
      };
    });
  }
  await load();
}
