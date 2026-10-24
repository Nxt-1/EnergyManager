import {clockValue, localDateTime, localInstants, monthDays, validLocal} from './date-time.js';

const pad = value => String(value).padStart(2, '0');
const dateLabel = (value, options) => new Date(value + 'T12:00Z').toLocaleDateString('en-GB', {
  timeZone: 'UTC', ...options
});

export class DateTimePicker {
  constructor(zone, now, root = document.body) {
    this.zone = zone;
    this.now = now;
    this.fields = new Map();
    this.dialog = document.createElement('dialog');
    this.dialog.id = 'datetime-dialog';
    this.dialog.className = 'datetime-dialog';
    this.dialog.setAttribute('aria-labelledby', 'picker-title');
    this.dialog.innerHTML = `
      <div class="picker-heading"><small>SELECT DATE & TIME</small><h2 id="picker-title"></h2>
        <div class="picker-tabs"><button type="button" data-view="date" id="picker-date"></button>
        <button type="button" data-view="time" id="picker-time"></button></div>
        <small id="picker-zone"></small></div>
      <div id="picker-body"></div>
      <label id="picker-occurrence" hidden>Clock-change occurrence<select id="picker-instant"></select></label>
      <p id="picker-error" class="error" role="alert"></p>
      <div class="picker-actions"><button type="button" id="picker-keyboard">Type date & time</button>
        <button type="button" id="picker-clear">Clear</button><span></span>
        <button type="button" id="picker-cancel">Cancel</button>
        <button type="button" class="primary" id="picker-apply">OK</button></div>`;
    (root.nodeType === 9 ? root.body : root).append(this.dialog);
    this.body = this.dialog.querySelector('#picker-body');
    this.error = this.dialog.querySelector('#picker-error');
    this.dialog.querySelector('#picker-cancel').onclick = () => this.dialog.close();
    this.dialog.querySelector('#picker-apply').onclick = () => this.apply();
    this.dialog.querySelector('#picker-clear').onclick = () => {
      this.setValue(this.input, null);
      this.dialog.close();
    };
    this.dialog.querySelector('#picker-keyboard').onclick = () => {
      if (this.view === 'keyboard' && !this.readKeyboard()) return;
      this.view = this.view === 'keyboard' ? 'date' : 'keyboard';
      this.render();
      this.body.querySelector('input, button')?.focus();
    };
    for (const button of this.dialog.querySelectorAll('[data-view]')) button.onclick = () => {
      if (this.view === 'keyboard' && !this.readKeyboard()) return;
      this.view = button.dataset.view;
      this.render();
    };
    this.dialog.querySelector('#picker-instant').onchange = event => {
      this.selectedInstant = event.target.value;
    };
    this.body.addEventListener('click', event => this.click(event));
    this.body.addEventListener('keydown', event => this.keydown(event));
    this.body.addEventListener('change', () => {
      if (this.view === 'keyboard' && this.readKeyboard()) {
        this.dialog.querySelector('#picker-date').textContent = dateLabel(this.draft.slice(0, 10), {
          weekday: 'short', day: 'numeric', month: 'short'
        });
        this.dialog.querySelector('#picker-time').textContent = this.draft.slice(11);
        this.error.textContent = '';
      }
    });
    this.dialog.addEventListener('close', () => this.fields.get(this.input)?.button.focus());
  }

  bind(input, label, required = false) {
    input.type = 'hidden';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'datetime-field';
    button.onclick = () => this.open(input);
    input.after(button);
    this.fields.set(input, {label, required, button});
    this.setValue(input, null);
  }

  setValue(input, instant) {
    input.value = instant ? localDateTime(instant, this.zone()) : '';
    input.dataset.instant = instant ? new Date(instant).toISOString() : '';
    const {label, button} = this.fields.get(input);
    const text = instant ? `${dateLabel(input.value.slice(0, 10), {
      day: 'numeric', month: 'short', year: 'numeric'
    })} · ${input.value.slice(11)}` : 'Choose date & time';
    button.textContent = text + ' ▦';
    button.setAttribute('aria-label', `${label}: ${text}`);
    button.removeAttribute('aria-invalid');
  }

  instant(input) {
    const {label, required, button} = this.fields.get(input);
    if (!input.value && !required) return null;
    const candidates = localInstants(input.value, this.zone());
    const selected = candidates.includes(input.dataset.instant) ? input.dataset.instant : candidates[0];
    if (!selected) {
      button.setAttribute('aria-invalid', 'true');
      button.focus();
      throw new Error(`Choose a valid ${label.toLowerCase()} in ${this.zone()}.`);
    }
    return selected;
  }

  open(input) {
    this.input = input;
    const departure = [...this.fields].find(([, field]) => field.required)?.[0].value;
    this.draft = input.value || departure || localDateTime(this.now(), this.zone());
    this.selectedInstant = input.dataset.instant;
    this.month = this.draft.slice(0, 7);
    this.view = 'date';
    this.part = 'hour';
    this.error.textContent = '';
    this.dialog.querySelector('#picker-title').textContent = this.fields.get(input).label;
    this.dialog.querySelector('#picker-clear').hidden = this.fields.get(input).required;
    this.render();
    this.dialog.showModal();
    (this.body.querySelector('[aria-selected="true"]') || this.body.querySelector('button'))?.focus();
  }

  render() {
    const date = this.draft.slice(0, 10);
    const dateButton = this.dialog.querySelector('#picker-date');
    dateButton.textContent = dateLabel(date, {weekday: 'short', day: 'numeric', month: 'short'});
    const timeButton = this.dialog.querySelector('#picker-time');
    timeButton.textContent = this.draft.slice(11);
    dateButton.setAttribute('aria-pressed', String(this.view === 'date'));
    timeButton.setAttribute('aria-pressed', String(this.view === 'time'));
    this.dialog.querySelector('#picker-zone').textContent = this.zone();
    this.dialog.querySelector('#picker-keyboard').textContent = this.view === 'keyboard' ?
      'Calendar & clock' : 'Type date & time';
    if (this.view === 'date') this.renderCalendar();
    else if (this.view === 'time') this.renderClock();
    else this.body.innerHTML = `<div class="picker-keyboard">
      <label>Date<input id="picker-date-input" type="date" min="1900-01-01" max="9999-12-31" value="${date}"></label>
      <label>Time · 24-hour<input id="picker-time-input" type="time" step="60" value="${this.draft.slice(11)}"></label>
      </div>`;
    this.renderOccurrences();
  }

  renderOccurrences() {
    const candidates = localInstants(this.draft, this.zone());
    if (!candidates.includes(this.selectedInstant)) this.selectedInstant = candidates[0];
    const select = this.dialog.querySelector('#picker-instant');
    select.replaceChildren();
    for (const [index, instant] of candidates.entries()) {
      const option = document.createElement('option');
      option.value = instant;
      const offset = new Intl.DateTimeFormat('en-GB', {timeZone: this.zone(), timeZoneName: 'shortOffset'})
        .formatToParts(new Date(instant)).find(part => part.type === 'timeZoneName').value;
      option.textContent = `${index === 0 ? 'First' : 'Second'} · ${offset}`;
      select.append(option);
    }
    select.value = this.selectedInstant || '';
    this.dialog.querySelector('#picker-occurrence').hidden = candidates.length < 2;
  }

  renderCalendar() {
    const [year, month] = this.month.split('-').map(Number);
    const title = dateLabel(this.month + '-01', {month: 'long', year: 'numeric'});
    this.body.innerHTML = `<div class="calendar-heading">
      <button type="button" data-month="-1" aria-label="Previous month">‹</button>
      <strong aria-live="polite">${title}</strong>
      <button type="button" data-month="1" aria-label="Next month">›</button></div>
      <div class="calendar-weekdays" aria-hidden="true">${['M', 'T', 'W', 'T', 'F', 'S', 'S']
        .map(day => `<span>${day}</span>`).join('')}</div>
      <div class="calendar-days" role="grid" aria-label="${title}">${monthDays(year, month).map(day => {
        if (day === null) return '<span role="presentation"></span>';
        const value = `${this.month}-${pad(day)}`;
        const selected = value === this.draft.slice(0, 10);
        return `<button type="button" role="gridcell" data-day="${value}" aria-selected="${selected}"
          tabindex="${selected || value.endsWith('-01') && this.month !== this.draft.slice(0, 7) ? 0 : -1}"
          aria-label="${dateLabel(value, {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'})}">${day}</button>`;
      }).join('')}</div>`;
  }

  renderClock() {
    const hour = Number(this.draft.slice(11, 13)), minute = Number(this.draft.slice(14));
    const selected = this.part === 'hour' ? hour : minute;
    const values = this.part === 'hour' ? Array.from({length: 24}, (_, index) => index) :
      Array.from({length: 12}, (_, index) => index * 5);
    const angle = selected / (this.part === 'hour' ? 12 : 60) * Math.PI * 2;
    const radius = this.part === 'hour' && (selected === 0 || selected > 12) ? 30 : 41;
    this.body.innerHTML = `<div class="clock-parts">
      <button type="button" data-part="hour" aria-label="Choose hours" aria-pressed="${this.part === 'hour'}">${pad(hour)}</button><span>:</span>
      <button type="button" data-part="minute" aria-label="Choose minutes" aria-pressed="${this.part === 'minute'}">${pad(minute)}</button></div>
      <div class="clock-face" aria-label="${this.part === 'hour' ? 'Hours · 24-hour' : 'Minutes'}">
      <div class="clock-hand" aria-hidden="true" style="height:${radius}%;transform:rotate(${angle}rad)"></div>
      <span class="clock-center" aria-hidden="true"></span>${values.map(value => {
        const turn = value / (this.part === 'hour' ? 12 : 60) * Math.PI * 2;
        const ring = this.part === 'hour' && (value === 0 || value > 12) ? 30 : 41;
        return `<button type="button" data-clock="${value}" aria-label="${this.part === 'hour' ? 'Hour' : 'Minute'} ${pad(value)}"
          aria-pressed="${value === selected}" style="left:${50 + Math.sin(turn) * ring}%;top:${50 - Math.cos(turn) * ring}%">${this.part === 'minute' || value === 0 ? pad(value) : value}</button>`;
      }).join('')}</div>`;
    this.body.querySelector('.clock-face').onpointerup = event => {
      if (event.target.closest('button')) return;
      const rect = event.currentTarget.getBoundingClientRect();
      this.selectClock(clockValue((event.clientX - rect.left - rect.width / 2) * 256 / rect.width,
        (event.clientY - rect.top - rect.height / 2) * 256 / rect.height, this.part));
    };
  }

  selectClock(value) {
    const [hour, minute] = this.draft.slice(11).split(':');
    this.draft = `${this.draft.slice(0, 10)}T${this.part === 'hour' ? pad(value) : hour}:${this.part === 'minute' ? pad(value) : minute}`;
    if (this.part === 'hour') this.part = 'minute';
    this.error.textContent = '';
    this.render();
    this.body.querySelector(`[data-part="${this.part}"]`)?.focus();
  }

  click(event) {
    const button = event.target.closest('button');
    if (!button) return;
    this.error.textContent = '';
    if (button.dataset.month) {
      const date = new Date(this.month + '-01T12:00Z');
      date.setUTCMonth(date.getUTCMonth() + Number(button.dataset.month));
      if (date.getUTCFullYear() < 1900 || date.getUTCFullYear() > 9999) return;
      this.month = date.toISOString().slice(0, 7);
      this.render();
      this.body.querySelector(`[data-month="${button.dataset.month}"]`).focus();
    } else if (button.dataset.day) {
      this.draft = button.dataset.day + this.draft.slice(10);
      this.view = 'time';
      this.part = 'hour';
      this.render();
      this.body.querySelector('[data-part="hour"]').focus();
    } else if (button.dataset.part) {
      this.part = button.dataset.part;
      this.render();
      this.body.querySelector(`[data-part="${this.part}"]`).focus();
    } else if (button.dataset.clock !== undefined) this.selectClock(Number(button.dataset.clock));
  }

  keydown(event) {
    const value = event.target.dataset.day;
    if (!value) return;
    const date = new Date(value + 'T12:00Z');
    const days = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7,
      Home: -((date.getUTCDay() + 6) % 7), End: 6 - ((date.getUTCDay() + 6) % 7)};
    if (!(event.key in days) && !['PageUp', 'PageDown'].includes(event.key)) return;
    event.preventDefault();
    if (event.key in days) date.setUTCDate(date.getUTCDate() + days[event.key]);
    else {
      const day = date.getUTCDate();
      date.setUTCDate(1);
      date.setUTCMonth(date.getUTCMonth() + (event.key === 'PageUp' ? -1 : 1));
      const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
      date.setUTCDate(Math.min(day, lastDay));
    }
    if (date.getUTCFullYear() < 1900 || date.getUTCFullYear() > 9999) return;
    this.draft = date.toISOString().slice(0, 10) + this.draft.slice(10);
    this.month = this.draft.slice(0, 7);
    this.render();
    this.body.querySelector('[aria-selected="true"]').focus();
  }

  readKeyboard() {
    const date = this.body.querySelector('#picker-date-input').value;
    const time = this.body.querySelector('#picker-time-input').value;
    if (!validLocal(`${date}T${time}`)) {
      this.error.textContent = 'Enter a complete date and a 24-hour time.';
      return false;
    }
    this.draft = `${date}T${time}`;
    this.month = date.slice(0, 7);
    this.renderOccurrences();
    return true;
  }

  apply() {
    if (this.view === 'keyboard' && !this.readKeyboard()) return;
    if (!this.selectedInstant) {
      this.error.textContent = `This local time does not exist in ${this.zone()}. Choose another time.`;
      return;
    }
    this.setValue(this.input, this.selectedInstant);
    this.input.dispatchEvent(new Event('change', {bubbles: true}));
    this.dialog.close();
  }
}
