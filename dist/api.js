const config = window.MONSOON_CONFIG;
let token = null;
const cooldowns = new Map();
export function setToken(value) { token = value; }
export function retryRemaining(path, method = 'GET') {
  return Math.max(0, Math.ceil(((cooldowns.get(`${method}:${path.split('?')[0]}`) || 0) - Date.now()) / 1000));
}
export async function request(path, { method = 'GET', body, signal, headers = {} } = {}) {
  const remaining = retryRemaining(path, method);
  if (remaining) throw Object.assign(new Error(`Try again in ${remaining} seconds.`), { status: 429, retry_after: remaining });
  const response = await fetch(`${config.API_BASE_URL.replace(/\/$/, '')}/api/v1${path}`, {
    method, signal, cache: 'no-store', credentials: 'omit', headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {})
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) { token = null; window.dispatchEvent(new Event('session-expired')); }
    let retry_after = 0;
    if (response.status === 429) {
      const value = response.headers.get('Retry-After');
      retry_after = Math.max(1, Number(value) || Math.ceil((Date.parse(value) - Date.now()) / 1000) || 60);
      cooldowns.set(`${method}:${path.split('?')[0]}`, Date.now() + retry_after * 1000);
    }
    throw Object.assign(new Error(response.status === 403 ? 'Not permitted.' : data.error?.message || `Request failed (${response.status})`), {
      status: response.status, code: data.error?.code, details: data.error?.details, retry_after,
      request_id: data.error?.request_id || response.headers.get('X-Request-ID')
    });
  }
  return data;
}
