// Stable HA resource. Layouts and cards come from the installed EnergyManager release.
const connections = new WeakMap();

export function ingressBase(value) {
  if (!/^\/api\/hassio_ingress\/[A-Za-z0-9_-]+\/?$/.test(value || ''))
    throw new Error('EnergyManager did not provide a valid authenticated ingress path');
  return value.replace(/\/?$/, '/');
}

export async function connectDashboard(hass, config = {}, fresh = false) {
  if (hass.user && !hass.user.is_admin) throw new Error('EnergyManager requires an HA administrator');
  const owner = hass.connection || hass;
  let entries = connections.get(owner);
  if (!entries) {
    entries = new Map();
    connections.set(owner, entries);
  }
  const key = config.addon || 'discover';
  if (!fresh && entries.has(key)) return entries.get(key);
  const pending = (async () => {
    const supervisor = (endpoint, method = 'get') => hass.callWS({
      type: 'supervisor/api',
      endpoint,
      method
    });
    let addon = config.addon;
    if (!addon) {
      const {
        addons
      } = await supervisor('/addons');
      const matches = addons.filter(item => item.slug === 'energy_manager' || item.slug.endsWith('_energy_manager'));
      if (matches.length !== 1) throw new Error('Select the EnergyManager add-on slug in the dashboard strategy');
      addon = matches[0].slug;
    }
    if (!/^[a-z0-9_-]+$/.test(addon)) throw new Error('Invalid EnergyManager add-on slug');
    const info = await supervisor(`/addons/${addon}/info`);
    const base = ingressBase(info.ingress_url);
    const renew = async () => {
      const {
        session
      } = await supervisor('/ingress/session', 'post');
      if (!/^[A-Za-z0-9_-]+$/.test(session || '')) throw new Error('Invalid HA ingress session');
      document.cookie = `ingress_session=${session};path=/api/hassio_ingress/;SameSite=Strict${location.protocol === 'https:' ? ';Secure' : ''}`;
    };
    await renew();
    const request = async (path, method = 'GET', body) => {
      const send = () => fetch(base + 'api/' + path, {
        method,
        credentials: 'same-origin',
        cache: 'no-store',
        signal: AbortSignal.timeout(15000),
        headers: {
          'Content-Type': 'application/json',
          'X-EnergyManager': '1'
        },
        ...(body === undefined ? {} : {
          body: JSON.stringify(body)
        })
      });
      let response = await send();
      if (response.status === 401 && method === 'GET') {
        await renew();
        response = await send();
      }
      let result;
      try {
        result = await response.json();
      } catch {
        throw new Error('EnergyManager is unavailable. Check the add-on and reload the dashboard.');
      }
      if (!response.ok) {
        const error = new Error(result.error || `EnergyManager request failed (${response.status})`);
        error.fields = result.errors;
        throw error;
      }
      return result;
    };
    const manifest = await request('dashboard');
    if (manifest.protocol !== 1 || !/^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$/.test(manifest.version || ''))
      throw new Error('This EnergyManager release requires an updated dashboard loader');
    return {
      addon,
      base,
      manifest,
      request,
      assets: `${base}frontend/${manifest.version}/`
    };
  })();
  entries.set(key, pending);
  try {
    return await pending;
  } catch (error) {
    if (entries.get(key) === pending) entries.delete(key);
    throw error;
  }
}

class EnergyManagerStrategy extends HTMLElement {
  static async generate(config, hass) {
    const connection = await connectDashboard(hass, config, true);
    const release = await import(connection.assets + 'native-dashboard.js');
    return release.generateDashboard(config, connection.manifest, connection);
  }
}

if (!customElements.get('ll-strategy-dashboard-energymanager'))
  customElements.define('ll-strategy-dashboard-energymanager', EnergyManagerStrategy);
window.customStrategies = window.customStrategies || [];
if (!window.customStrategies.some(item => item.type === 'energymanager')) window.customStrategies.push({
  type: 'energymanager',
  strategyType: 'dashboard',
  name: 'EnergyManager',
  description: 'Native live sensors and managed EnergyManager planning views'
});
