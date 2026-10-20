const config = window.MONSOON_CONFIG;
let token = null;
let cooldown = 0;
export function setToken(value) { token = value; }
export async function request(path, { method = 'GET', body, signal, headers = {} } = {}) {
  if (Date.now() < cooldown) throw new Error('Too many requests. Try again after the cooldown.');
  const response = await fetch(`${config.API_BASE_URL.replace(/\/$/, '')}/api/v1${path}`, {method, signal, headers: { 'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {}), ...headers }, ...(body ? {body: JSON.stringify(body)} : {})});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) { token = null; window.dispatchEvent(new Event('session-expired')); }
    if (response.status === 429) { const retry=response.headers.get('Retry-After'); cooldown=Date.now()+(Number(retry)||60)*1000; }
    const error = new Error(data.error?.message || `Request failed (${response.status})`);
    Object.assign(error, {status:response.status, code:data.error?.code, details:data.error?.details, request_id:data.error?.request_id || response.headers.get('X-Request-ID')}); throw error;
  }
  return data;
}
