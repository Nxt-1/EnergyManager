import {
  mountApplication
} from './application-view.js';
import {
  nativeLiveState, setChargerPhase
} from './native-live.js';
import {hasTextSelection} from './text-selection.js';

const runtimes = new Map();

export function generateDashboard(config, manifest, connection) {
  runtimes.set(connection.addon, connection);
  const tag = `energymanager-view-${manifest.version.replaceAll('.', '-').toLowerCase()}`;
  if (!customElements.get(tag)) customElements.define(tag, class extends HTMLElement {
    setConfig(value) {
      if (!['overview', 'planning', 'ev', 'settings'].includes(value.view)) throw new Error('Unknown EnergyManager view');
      if (this.config && (this.config.view !== value.view || this.config.addon !== value.addon)) this.stop();
      this.config = value;
      this.start();
    }
    set hass(value) {
      const previous = this.currentHass;
      this.currentHass = value;
      const entities = runtimes.get(this.config?.addon)?.manifest.entities;
      const phase = runtimes.get(this.config?.addon)?.manifest.phase_selector;
      const watched = !entities || this.config.view === 'settings' ? [] : this.config.view === 'ev' ? [entities.ev_soc, entities.ev_kw, entities.connected, phase] : Object.values(entities);
      if (watched.some(id => previous?.states[id] !== value.states[id]))
        this.controller?.updateLive();
      this.start();
    }
    connectedCallback() {
      this.start();
    }
    disconnectedCallback() {
      this.stop();
    }
    stop() {
      this.generation = (this.generation || 0) + 1;
      this.controller?.dispose();
      this.liveEvents?.abort();
      this.controller = null;
    }
    getCardSize() {
      return this.config?.view === 'settings' ? 12 : 10;
    }
    getGridOptions() {
      return {
        columns: 'full',
        rows: 'auto'
      };
    }
    async start() {
      if (!this.isConnected || !this.config || !this.currentHass || this.controller || this.starting) return;
      this.starting = true;
      const generation = this.generation || 0;
      const runtime = runtimes.get(this.config.addon);
      const root = this.shadowRoot || this.attachShadow({
        mode: 'open'
      });
      try {
        if (!runtime) throw new Error('Open EnergyManager through its managed dashboard strategy');
        const manifest = runtime.manifest;
        const response = await fetch(runtime.assets + 'view.html', {
          credentials: 'same-origin',
          cache: 'no-store'
        });
        if (!response.ok) throw new Error('EnergyManager interface changed or is unavailable. Reload this dashboard.');
        const markup = await response.text();
        if (!this.isConnected || generation !== (this.generation || 0)) return;
        root.innerHTML = `<link rel="stylesheet" href="${runtime.assets}style.css"><link rel="stylesheet" href="${runtime.assets}native-dashboard.css"><p id="native-error" role="alert"></p>${markup}`;
        let changed = false;
        const api = async (path, method, body) => {
          if (changed) throw new Error('EnergyManager was updated. Reload this dashboard.');
          const result = await runtime.request(path, method, body);
          if (path.split('?')[0] === 'state' && result.version !== manifest.version) {
            changed = true;
            throw new Error('EnergyManager was updated. Reload this dashboard.');
          }
          return result;
        };
        const controller = await mountApplication(root, {
          native: true,
          entities: manifest.entities,
          page: this.config.view,
          api,
          navigate: name => {
            const dashboard = location.pathname.split('/').filter(Boolean)[0];
            history.pushState(null, '', `/${dashboard}/${name}`);
            window.dispatchEvent(new Event('location-changed'));
          },
          liveState: state => nativeLiveState(state, this.currentHass, manifest),
          setPhase: option => setChargerPhase(this.currentHass, manifest, option)
        });
        if (!this.isConnected || generation !== (this.generation || 0)) controller.dispose();
        else {
          this.controller = controller;
          this.liveEvents = new AbortController();
          const moreInfo = entityId => this.dispatchEvent(new CustomEvent('hass-more-info', {
            bubbles: true,
            composed: true,
            detail: {entityId}
          }));
          const openHistory = key => {
            const keys = {
              ev: ['ev_soc', 'ev_kw', 'connected'],
              ess: ['ess_soc', 'ess_kw'],
              solar: ['pv_ac_kw', 'pv_dc_kw'],
              grid: ['grid_import_kw', 'grid_export_kw'],
              house: ['grid_import_kw', 'grid_export_kw', 'pv_ac_kw', 'ess_kw', 'ev_kw']
            } [key];
            const ids = keys.map(name => manifest.entities[name]).filter(Boolean);
            if (ids.length === 1) {
              moreInfo(ids[0]);
              return;
            }
            const body = root.querySelector('#detail-body');
            body.replaceChildren();
            const title = document.createElement('h2');
            title.textContent = key === 'house' ? 'Household demand · source histories' : 'Source histories';
            body.append(title);
            for (const id of ids) {
              const button = document.createElement('button');
              button.textContent = this.currentHass.states[id]?.attributes.friendly_name || id;
              button.onclick = () => {
                root.querySelector('#detail-dialog').close();
                moreInfo(id);
              };
              body.append(button);
            }
            root.querySelector('#detail-dialog').showModal();
          };
          root.addEventListener('click', event => {
            const entity = event.target.closest('[data-entity-key]');
            if (entity && !manifest.demo && !hasTextSelection(root)) {
              const id = manifest.entities[entity.dataset.entityKey];
              if (id) moreInfo(id);
              return;
            }
            const card = event.target.closest('[data-live]');
            if (card && !manifest.demo && !hasTextSelection(root)) openHistory(card.dataset.live);
          }, {
            signal: this.liveEvents.signal
          });
          root.addEventListener('keydown', event => {
            if (event.target.matches('[data-live]') && ['Enter', ' '].includes(event.key)) {
              event.preventDefault();
              event.target.click();
            }
          }, {
            signal: this.liveEvents.signal
          });
        }
      } catch (error) {
        root.textContent = error.message;
      } finally {
        this.starting = false;
        if (this.isConnected && generation !== (this.generation || 0)) this.start();
      }
    }
  });
  const view = (name, path, icon) => {
    const cards = [{
      type: `custom:${tag}`,
      addon: connection.addon,
      view: path,
      grid_options: {
        columns: 'full'
      }
    }];
    const sections = [];
    sections.push({
      type: 'grid',
      column_span: 3,
      cards
    });
    return {
      title: name,
      path,
      icon,
      type: 'sections',
      max_columns: 3,
      sections
    };
  };
  return {
    title: config.title || 'EnergyManager',
    views: [
      view('Overview', 'overview', 'mdi:home-lightning-bolt'),
      view('Planning', 'planning', 'mdi:chart-timeline-variant'),
      view('EV', 'ev', 'mdi:car-electric'), view('Settings', 'settings', 'mdi:cog')
    ]
  };
}
