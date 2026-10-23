const element = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

class EntityPicker extends HTMLElement {
  configure(field, value, entities) {
    this.field = field;
    this.entities = entities;
    this.selected = value || '';
    this.replaceChildren();
    this.input = element('input');
    this.input.id = `setting-${field.path.replaceAll('.', '-')}`;
    this.input.type = 'text';
    this.input.required = true;
    this.input.autocomplete = 'off';
    this.input.spellcheck = false;
    this.input.setAttribute('role', 'combobox');
    this.input.setAttribute('aria-autocomplete', 'list');
    this.input.setAttribute('aria-expanded', 'false');
    this.input.setAttribute('aria-label', field.label);
    this.input.placeholder = 'Search by name or entity ID';
    this.list = element('div', 'entity-options');
    this.list.id = `${this.input.id}-options`;
    this.list.setAttribute('role', 'listbox');
    this.list.hidden = true;
    this.input.setAttribute('aria-controls', this.list.id);
    this.summary = element('small', 'entity-selection');
    this.append(this.input, this.summary, this.list);
    this.showSelection();
    this.input.addEventListener('focus', () => {
      this.input.value = '';
      this.open();
    });
    this.input.addEventListener('input', event => {
      event.stopPropagation();
      this.open();
    });
    this.input.addEventListener('keydown', event => this.keydown(event));
    this.input.addEventListener('blur', () => this.close());
    this.list.addEventListener('mousedown', event => event.preventDefault());
    this.list.addEventListener('click', event => {
      const option = event.target.closest('[data-entity]');
      if (option) this.choose(option.dataset.entity);
    });
  }

  get value() { return this.selected; }
  set value(value) { this.selected = value || ''; this.showSelection(); }

  updateEntities(entities) {
    this.entities = entities;
    if (document.activeElement !== this.input) this.showSelection();
    else this.open();
  }

  showSelection() {
    const match = this.entities.find(entity => entity.entity_id === this.selected);
    this.input.value = match ? match.name : this.selected;
    this.summary.textContent = match ?
      `${match.entity_id} · ${match.state}${match.unit ? ' ' + match.unit : ''}` :
      this.selected ? `${this.selected} · not in the current entity list` :
        'Choose an entity, or enter its ID if Home Assistant is unavailable.';
  }

  open() {
    const query = this.input.value.toLocaleLowerCase().trim();
    const matches = this.entities.filter(entity => {
      const domain = entity.entity_id.split('.')[0];
      const unitMatches = !this.field.units.length || !entity.unit || this.field.units.includes(entity.unit);
      return this.field.domains.includes(domain) && unitMatches &&
        `${entity.name} ${entity.entity_id}`.toLocaleLowerCase().includes(query);
    });
    this.matches = matches.slice(0, 40);
    this.active = -1;
    this.input.removeAttribute('aria-activedescendant');
    this.list.replaceChildren();
    for (const [index, entity] of this.matches.entries()) {
      const row = element('div', 'entity-option');
      row.id = `${this.list.id}-${index}`;
      row.dataset.entity = entity.entity_id;
      row.setAttribute('role', 'option');
      row.setAttribute('aria-selected', 'false');
      row.append(element('strong', '', entity.name),
        element('small', '', `${entity.entity_id} · ${entity.state}${entity.unit ? ' ' + entity.unit : ''}`));
      this.list.append(row);
    }
    if (!matches.length) this.list.append(element('div', 'entity-empty',
      'No matching entities. You can enter an entity ID directly.'));
    if (matches.length > 40) this.list.append(element('div', 'entity-empty',
      `${matches.length} matches · type more to narrow the list`));
    this.list.hidden = false;
    this.input.setAttribute('aria-expanded', 'true');
  }

  close(commitTypedId = true) {
    const typed = this.input.value.trim();
    if (commitTypedId && !this.list.hidden && /^[a-z_][a-z0-9_]*\.[a-z0-9_]+$/.test(typed) &&
        typed !== this.selected) {
      this.selected = typed;
      this.dispatchEvent(new Event('change', {bubbles: true}));
    }
    this.list.hidden = true;
    this.input.setAttribute('aria-expanded', 'false');
    this.input.removeAttribute('aria-activedescendant');
    this.showSelection();
  }

  choose(entityId) {
    this.selected = entityId;
    this.close(false);
    this.dispatchEvent(new Event('change', {bubbles: true}));
  }

  keydown(event) {
    if (event.key === 'Escape') { event.preventDefault(); this.close(false); return; }
    if (event.key === 'Enter' && !this.list.hidden) {
      event.preventDefault();
      if (this.active >= 0) this.choose(this.matches[this.active].entity_id);
      else this.close();
      return;
    }
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
    event.preventDefault();
    if (this.list.hidden) { this.input.value = ''; this.open(); }
    if (!this.matches.length) return;
    this.active = (this.active + (event.key === 'ArrowDown' ? 1 : -1) + this.matches.length) % this.matches.length;
    for (const [index, row] of [...this.list.querySelectorAll('[role=option]')].entries()) {
      row.setAttribute('aria-selected', String(index === this.active));
      if (index === this.active) {
        this.input.setAttribute('aria-activedescendant', row.id);
        row.scrollIntoView({block: 'nearest'});
      }
    }
  }
}

if (!customElements.get('em-entity-picker')) customElements.define('em-entity-picker', EntityPicker);

export class SettingsPage {
  constructor(container, api) {
    this.container = container;
    this.api = api;
    this.entities = [];
    this.dirty = false;
    this.controls = new Map();
    window.addEventListener('beforeunload', event => {
      if (this.dirty) { event.preventDefault(); event.returnValue = ''; }
    });
  }

  async show() {
    if (this.document) return;
    await this.load();
  }

  async load() {
    this.container.textContent = 'Loading settings…';
    try {
      this.document = await this.api('settings');
      this.render();
      this.dirty = false;
      await this.loadEntities();
    } catch (error) {
      this.container.replaceChildren(element('p', 'error', error.message));
      const retry = element('button', '', 'Retry');
      retry.onclick = () => this.load();
      this.container.append(retry);
    }
  }

  async loadEntities() {
    this.entityStatus.textContent = 'Loading Home Assistant entities…';
    this.entityButton.disabled = true;
    try {
      const result = await this.api('settings/entities');
      this.entities = result.entities;
      this.entityStatus.textContent = `${result.entities.length} Home Assistant entities loaded`;
      for (const control of this.controls.values()) {
        if (control instanceof EntityPicker) control.updateEntities(this.entities);
      }
    } catch (error) {
      this.entityStatus.textContent = `${error.message} Current mappings are kept; you can still edit settings.`;
    } finally {
      this.entityButton.disabled = false;
    }
  }

  render() {
    this.controls.clear();
    this.container.replaceChildren();
    const heading = element('div', 'page-heading');
    const title = element('div');
    title.append(element('h1', '', 'Settings'), element('p', 'muted',
      'Choose your entities and installation settings. Your configuration stays with the app across updates.'));
    heading.append(title);
    this.container.append(heading);
    const info = element('div', 'notice');
    info.append(element('strong', '', 'Saved settings apply in configured mode after restarting EnergyManager.'), element('p', '',
      `Current input mode: ${this.document.mode}. ${this.document.restart_required ? 'Saved changes are waiting for a restart.' : ''}`),
      element('small', '', `Configuration: ${this.document.path}`));
    this.container.append(info);
    const entityBar = element('div', 'settings-entities');
    this.entityStatus = element('span', 'muted');
    this.entityStatus.setAttribute('role', 'status');
    this.entityButton = element('button', '', 'Refresh entities');
    this.entityButton.type = 'button';
    this.entityButton.onclick = () => this.loadEntities();
    entityBar.append(this.entityStatus, this.entityButton);
    this.container.append(entityBar);
    if (this.document.addon) {
      const connection = element('button', '', 'Use Home Assistant connection');
      connection.type = 'button';
      connection.onclick = () => {
        this.controls.get('home_assistant_url').value = 'http://supervisor/core/api';
        this.controls.get('token_environment').value = 'SUPERVISOR_TOKEN';
        this.controls.get('allow_remote').checked = true;
        this.markDirty();
        this.message.textContent = 'Home Assistant connection selected. Save settings to keep it.';
      };
      entityBar.append(connection);
    }
    this.form = element('form', 'settings-form');
    this.form.noValidate = true;
    const groups = new Map();
    for (const field of this.document.fields) {
      if (!groups.has(field.group)) {
        const card = element('section', 'card settings-group');
        const content = element('div', 'settings-fields');
        if (['Advanced', 'Commissioning'].includes(field.group)) {
          const details = element('details');
          details.append(element('summary', '', field.group), content);
          card.append(details);
        } else {
          card.append(element('h2', '', field.group), content);
        }
        groups.set(field.group, content);
        this.form.append(card);
      }
      const wrapper = element('div', `setting-field${field.kind === 'boolean' ? ' boolean-field' : ''}`);
      const label = element('label', '', field.label);
      const id = `setting-${field.path.replaceAll('.', '-')}`;
      label.htmlFor = id;
      let control;
      const value = this.document.values[field.path];
      if (field.kind === 'entity') {
        control = document.createElement('em-entity-picker');
        control.configure(field, value, this.entities);
      } else if (field.kind === 'choice') {
        control = element('select');
        for (const [val, text] of field.choices) {
          const option = element('option', '', text);
          option.value = val;
          control.append(option);
        }
        control.value = value;
      } else if (field.kind === 'phases') {
        control = element('select');
        for (const [val, text] of [['1', 'Single phase'], ['3', 'Three phase'], ['1,3', 'Single and three phase']]) {
          const option = element('option', '', text);
          option.value = val;
          control.append(option);
        }
        control.value = [...(value || [])].sort().join(',');
      } else {
        control = element('input');
        control.type = field.kind === 'boolean' ? 'checkbox' :
          ['number', 'integer'].includes(field.kind) ? 'number' :
            ['url', 'optional_url'].includes(field.kind) ? 'url' : field.kind === 'time' ? 'time' : 'text';
        if (field.kind === 'boolean') control.checked = value === true;
        else control.value = value ?? '';
        if (['number', 'integer'].includes(field.kind)) {
          if (field.minimum !== null) control.min = field.minimum;
          if (field.maximum !== null) control.max = field.maximum;
          // Keep exact existing tariffs/efficiencies; server validation enforces physical bounds.
          control.step = field.kind === 'integer' ? '1' : 'any';
          control.inputMode = 'decimal';
        }
        control.required = !['boolean', 'optional_url'].includes(field.kind) && field.path !== '_description';
        control.autocomplete = 'off';
      }
      if (field.kind !== 'entity') control.id = id;
      control.dataset.path = field.path;
      this.controls.set(field.path, control);
      if (field.kind === 'boolean') {
        wrapper.append(control, label);
      } else wrapper.append(label, control);
      wrapper.append(element('small', 'muted field-help', field.help || ''));
      const error = element('small', 'error field-error');
      error.id = `${id}-error`;
      error.setAttribute('aria-live', 'polite');
      (control.input || control).setAttribute('aria-describedby', error.id);
      wrapper.append(error);
      groups.get(field.group).append(wrapper);
    }
    this.form.addEventListener('input', () => this.markDirty());
    this.form.addEventListener('change', () => { this.updateMeasurementFields(); this.markDirty(); });
    const actions = element('div', 'settings-save card');
    this.message = element('p', '', 'No unsaved changes.');
    this.message.id = 'settings-message';
    this.message.setAttribute('role', 'status');
    const buttons = element('div', 'actions');
    const reload = element('button', '', 'Reload saved settings');
    reload.type = 'button';
    reload.onclick = () => {
      if (!this.dirty || window.confirm('Discard your unsaved settings edits?')) this.load();
    };
    this.saveButton = element('button', 'primary', 'Save settings');
    this.saveButton.type = 'submit';
    this.saveButton.id = 'save-settings';
    buttons.append(reload, this.saveButton);
    actions.append(this.message, buttons);
    this.form.append(actions);
    this.form.onsubmit = event => { event.preventDefault(); this.save(); };
    this.container.append(this.form);
    this.updateMeasurementFields();
  }

  updateMeasurementFields() {
    for (const field of this.document.fields) {
      const control = this.controls.get(field.path);
      if (field.visible_when) {
        const [path, choices] = field.visible_when;
        control.closest('.setting-field').hidden = !choices.includes(this.controls.get(path).value);
      }
    }
    const describe = (path, label, help, units) => {
      const control = this.controls.get(path);
      const wrapper = control.closest('.setting-field');
      wrapper.querySelector('label').textContent = label;
      control.input.setAttribute('aria-label', label);
      wrapper.querySelector('.field-help').textContent = help;
      if (units) control.field = {...control.field, units};
    };
    const house = this.controls.get('measurement_options.house_source').value;
    describe('measurements.house_kw', {
      direct: 'House demand excluding EV', total_consumption: 'Total household consumption including EV',
      signed_grid: 'Grid power · positive import, negative export', separate_grid: 'House power (unused)',
    }[house], house === 'direct' ? 'Appliance demand before subtracting solar; EV charging is already excluded.' :
      house === 'total_consumption' ? 'Total load before solar and battery offsets. EV charging is subtracted once.' :
        'House demand is calculated from grid, AC solar, ESS AC power and EV charging.');
    const quarter = this.controls.get('measurement_options.quarter_source').value;
    describe('measurements.quarter_import_kwh', quarter === 'energy' ?
      'Import already used this quarter-hour · kWh' : 'Current Quarter Average Demand · W or kW', {
      energy: 'Imported energy since the latest 00, 15, 30 or 45 minute boundary; not a lifetime meter reading.',
      elapsed_average: 'Average over the elapsed part of this quarter. Converted using the meter reading time.',
      fixed_quarter_average: 'P1 demand builds up from zero each quarter. EnergyManager converts kW to kWh by multiplying by 0.25 h.',
    }[quarter], quarter === 'energy' ? ['kWh'] : ['W', 'kW']);
  }

  markDirty() {
    this.dirty = true;
    this.message.textContent = 'Unsaved changes';
    this.message.className = '';
  }

  async save() {
    const values = {};
    for (const field of this.document.fields) {
      const control = this.controls.get(field.path);
      control.closest('.setting-field').querySelector('.field-error').textContent = '';
      (control.input || control).removeAttribute('aria-invalid');
      if (field.kind === 'boolean') values[field.path] = control.checked;
      else if (field.kind === 'phases') values[field.path] = control.value.split(',').filter(Boolean).map(Number);
      else if (['number', 'integer'].includes(field.kind)) values[field.path] =
        control.value.trim() === '' ? null : Number(control.value);
      else values[field.path] = control.value.trim();
    }
    this.saveButton.disabled = true;
    this.message.textContent = 'Saving settings…';
    try {
      const result = await this.api('settings', 'POST', {revision: this.document.revision, values});
      this.document = result;
      this.dirty = false;
      this.message.className = 'settings-success';
      const restart = result.mode === 'demo' && result.addon ?
        'Choose configured in the HA app Configuration tab and restart to apply them.' :
        'Restart EnergyManager in configured mode to apply them.';
      this.message.textContent = result.backup ?
        `Settings saved. ${restart} Previous settings backed up as ${result.backup}.` :
        `Settings are already saved. ${restart}`;
    } catch (error) {
      this.message.className = 'error';
      this.message.textContent = error.message;
      for (const [path, message] of Object.entries(error.fields || {})) {
        const control = this.controls.get(path);
        if (!control) continue;
        control.closest('.setting-field').querySelector('.field-error').textContent = message;
        (control.input || control).setAttribute('aria-invalid', 'true');
        const details = control.closest('details');
        if (details) details.open = true;
      }
    } finally {
      this.saveButton.disabled = false;
    }
  }
}
