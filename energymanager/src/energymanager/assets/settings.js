import {displaySetting, entityState, powerText, settingLabel, storedSetting} from './display.js';

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
    this.selected = value?.id || value || '';
    this.selectedKind = value?.kind || 'entity';
    this.replaceChildren();
    this.input = element('input');
    this.input.id = `setting-${field.path.replaceAll('.', '-')}`;
    this.input.type = 'text';
    this.input.required = field.required;
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
    this.clearButton = element('button', 'entity-clear', '×');
    this.clearButton.type = 'button';
    this.clearButton.setAttribute('aria-label', `Clear ${field.label}`);
    this.clearButton.onclick = () => this.choose('');
    this.append(this.input, this.clearButton, this.summary, this.list);
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

  get value() {
    if (this.field.kind !== 'notification') return this.selected;
    return this.selected ? {id: this.selected, kind: this.selectedKind} : null;
  }
  set value(value) {
    this.selected = value?.id || value || '';
    this.selectedKind = value?.kind || 'entity';
    this.showSelection();
  }

  updateEntities(entities) {
    this.entities = entities;
    if (this.getRootNode().activeElement !== this.input) this.showSelection();
    else this.open();
  }

  showSelection() {
    const match = this.entities.find(entity => entity.entity_id === this.selected);
    this.input.value = match ? match.name : this.selected;
    this.clearButton.hidden = !this.selected;
    this.summary.textContent = match ?
      `${match.entity_id}${match.state ? ' · ' + entityState(match) : ''}` :
      this.selected;

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
        element('small', '', `${entity.entity_id}${entity.state ? ' · ' + entityState(entity) : ''}`));
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
      this.selectedKind = this.entities.find(entity => entity.entity_id === typed)?.kind ||
        (typed.startsWith('notify.mobile_app_') ? 'action' : 'entity');
      this.dispatchEvent(new Event('change', {bubbles: true}));
    }
    this.list.hidden = true;
    this.input.setAttribute('aria-expanded', 'false');
    this.input.removeAttribute('aria-activedescendant');
    this.showSelection();
  }

  choose(entityId) {
    this.selected = entityId;
    this.selectedKind = this.entities.find(entity => entity.entity_id === entityId)?.kind || 'entity';
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
  constructor(container, api, signal) {
    this.container = container;
    this.api = api;
    this.entities = [];
    this.notificationTargets = [];
    this.entitiesLoaded = false;
    this.dirty = false;
    this.controls = new Map();
    window.addEventListener('beforeunload', event => {
      if (this.dirty) { event.preventDefault(); event.returnValue = ''; }
    }, {signal});
  }

  async show() {
    if (this.dirty) return;
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
      this.notificationTargets = result.notification_targets || [];
      this.entitiesLoaded = true;
      this.notificationsLoaded = !result.notification_error;
      this.entityStatus.textContent = `${result.entities.length} Home Assistant entities loaded`;
      for (const control of this.controls.values()) {
        if (control instanceof EntityPicker) control.updateEntities(
          control.field.kind === 'notification' ? this.notificationTargets : this.entities);
      }
    } catch (error) {
      this.entityStatus.textContent = `${error.message} Current mappings are kept; you can still edit settings.`;
    } finally {
      this.validateFields();
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
    this.issueSummary = element('p', 'settings-issues');
    this.issueSummary.id = 'settings-issues';
    this.issueSummary.setAttribute('role', 'status');
    this.container.append(this.issueSummary);
    this.form = element('form', 'settings-form');
    this.form.noValidate = true;
    const groups = new Map();
    for (const field of this.document.fields) {
      if (!groups.has(field.group)) {
        const card = element('section', 'card settings-group');
        const content = element('div', 'settings-fields');
        if (field.group === 'Advanced') {
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
      const label = element('label', '', settingLabel(field));
      const id = `setting-${field.path.replaceAll('.', '-')}`;
      label.htmlFor = id;
      let control;
      const value = this.document.values[field.path];
      if (['entity', 'notification'].includes(field.kind)) {
        control = document.createElement('em-entity-picker');
        control.configure(field, value, field.kind === 'notification' ? this.notificationTargets : this.entities);
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
        else control.value = ['number', 'integer'].includes(field.kind) ? displaySetting(field, value) : value ?? '';
        if (['number', 'integer'].includes(field.kind)) {
          if (field.minimum !== null) control.min = displaySetting(field, field.minimum);
          if (field.maximum !== null) control.max = displaySetting(field, field.maximum);
          // Keep exact existing tariffs/efficiencies; server validation enforces physical bounds.
          control.step = field.kind === 'integer' ? '1' : 'any';
          control.inputMode = 'decimal';
        }
        control.required = field.required && field.kind !== 'boolean';
        control.autocomplete = 'off';
        control.dataset.savedValue = control.value;
      }
      if (!(control instanceof EntityPicker)) control.id = id;
      control.dataset.path = field.path;
      this.controls.set(field.path, control);
      if (field.kind === 'boolean') {
        wrapper.append(control, label);
      } else wrapper.append(label, control);
      if (field.help) wrapper.append(element('small', 'muted field-help', field.help));
      const error = element('small', 'error field-error');
      error.id = `${id}-error`;
      error.setAttribute('aria-live', 'polite');
      (control.input || control).setAttribute('aria-describedby', error.id);
      wrapper.append(error);
      groups.get(field.group).append(wrapper);
    }
    this.form.addEventListener('input', () => this.markDirty());
    this.form.addEventListener('change', () => this.markDirty());
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
    this.validateFields();
  }

  markDirty() {
    this.dirty = true;
    this.message.textContent = 'Unsaved changes';
    this.message.className = '';
    this.validateFields();
  }

  validateFields() {
    if (!this.form) return;
    let count = 0;
    for (const field of this.document.fields) {
      const control = this.controls.get(field.path);
      const input = control.input || control;
      let message = '';
      if (control instanceof EntityPicker) {
        const identifier = control.selected;
        const rows = field.kind === 'notification' ? this.notificationTargets : this.entities;
        const loaded = field.kind === 'notification' ? this.notificationsLoaded : this.entitiesLoaded;
        const match = rows.find(row => row.entity_id === identifier);
        if (field.required && (!identifier || identifier.split('.')[1]?.startsWith('replace_')))
          message = 'Select an entity';
        else if (identifier && loaded && !match) message = 'Not found in Home Assistant';
        else if (match && (match.state === 'unavailable' || match.state === 'unknown' && field.kind !== 'notification'))
          message = 'Value unavailable';
        else if (match && field.units.length && match.unit && !field.units.includes(match.unit))
          message = 'Incompatible unit';
      } else if (field.required && control.value.trim() === '') message = 'Required';
      else if (control.validity && !control.validity.valid) message = 'Check this value';
      const wrapper = control.closest('.setting-field');
      wrapper.classList.toggle('field-missing', !!message);
      wrapper.querySelector('.field-error').textContent = message;
      if (message) {
        input.setAttribute('aria-invalid', 'true');
        count += 1;
        const details = control.closest('details');
        if (details) details.open = true;
      } else input.removeAttribute('aria-invalid');
    }
    this.issueSummary.textContent = count ? `${count} setting${count === 1 ? '' : 's'} need attention.` : '';
    this.issueSummary.hidden = !count;
  }

  async save() {
    const values = {};
    for (const field of this.document.fields) {
      const control = this.controls.get(field.path);
      control.closest('.setting-field').querySelector('.field-error').textContent = '';
      (control.input || control).removeAttribute('aria-invalid');
      if (field.kind === 'boolean') values[field.path] = control.checked;
      else if (field.kind === 'notification') values[field.path] = control.value;
      else if (field.kind === 'phases') values[field.path] = control.value.split(',').filter(Boolean).map(Number);
      else if (['number', 'integer'].includes(field.kind)) values[field.path] =
        control.value === control.dataset.savedValue ? this.document.values[field.path] : storedSetting(field, control.value);
      else values[field.path] = control.value.trim();
    }
    this.saveButton.disabled = true;
    this.message.textContent = 'Saving settings…';
    try {
      const result = await this.api('settings', 'POST', {revision: this.document.revision, values});
      this.document = result;
      for (const field of this.document.fields) {
        const control = this.controls.get(field.path);
        if (['number', 'integer'].includes(field.kind)) control.dataset.savedValue = control.value;
      }
      this.dirty = false;
      this.validateFields();
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
        control.closest('.setting-field').querySelector('.field-error').textContent = powerText(message);
        (control.input || control).setAttribute('aria-invalid', 'true');
        const details = control.closest('details');
        if (details) details.open = true;
      }
    } finally {
      this.saveButton.disabled = false;
    }
  }
}
