import {
  localDateTime
} from './date-time.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [c]));
let library;

function syncLabel(info) {
  const labels = {
    synchronized: 'Google Calendar up to date',
    disconnected: 'Google Calendar disconnected · local trips retained',
    unavailable: 'Calendar temporarily unavailable · local edits retained',
    reauthorization_required: 'Reconnect Google Calendar',
    push_unavailable_reconciling: 'Push updates unavailable · periodic synchronization continues. Check the webhook and proxy setup.',
    needs_correction: 'A drive needs correction'
  };
  return `${labels[info.sync] || info.sync} · ${info.pending} pending ${info.pending === 1 ? 'change' : 'changes'}`;
}

function loadCalendar() {
  if (!library) library = (async () => {
    for (const name of ['fullcalendar.global.min.js', 'luxon.min.js', 'fullcalendar-luxon.global.min.js']) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = new URL(name, import.meta.url);
        script.onload = resolve;
        script.onerror = () => reject(new Error(
          'The calendar library could not be loaded. Reload the page.'));
        document.head.append(script);
      });
    }
  })();
  return library;
}

export class TripCalendarPage {
  constructor(api, picker) {
    this.api = api;
    this.picker = picker;
    this.root = document.createElement('section');
    this.root.className = 'trip-calendar-workspace card';
    this.root.innerHTML =
      `<style>
      .trip-calendar-workspace{margin:16px 0;min-width:0}.trip-calendar-heading{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
      .trip-calendar-workspace .fc{margin-top:16px;font-size:12px;--fc-border-color:var(--line,#d9dee5);--fc-page-bg-color:var(--surface,#fff);--fc-today-bg-color:#278d8610}
      .trip-calendar-workspace .fc .fc-col-header-cell{background:var(--surface,#fff);color:inherit}
      .trip-calendar-workspace .fc .fc-event-resizable .fc-event-resizer{display:block}
      .trip-calendar-workspace .fc-toolbar{flex-wrap:wrap;gap:8px}.trip-calendar-workspace .fc-toolbar-title{font-size:18px}
      .trip-calendar-workspace dialog{color:inherit;background:var(--surface,#fff);border:1px solid var(--line,#ccd4de);border-radius:14px;width:min(620px,90vw);max-height:90vh;overflow:auto;padding:20px}
      .trip-calendar-workspace dialog::backdrop{background:#10223366}.trip-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}
      .trip-fields label{display:flex;flex-direction:column;gap:4px}.trip-fields input,.trip-fields select{min-width:0;width:100%;box-sizing:border-box}
      .trip-fields .wide{grid-column:1/-1}.trip-fields fieldset{min-width:0}.trip-search-results{display:flex;flex-direction:column;gap:4px;margin:6px 0}
      .trip-search-results button{text-align:left}.trip-weekdays{display:flex;flex-wrap:wrap;gap:10px}.trip-weekdays label{display:flex;flex-direction:row;align-items:center}
      .trip-maps-attribution{font:400 12px/1.4 sans-serif;white-space:nowrap;color:#5e5e5e;background:#fff;align-self:flex-start;padding:2px 4px}
      .trip-weekdays input{width:auto}.trip-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.trip-feedback:empty{display:none}
      .trip-feedback{white-space:pre-wrap;color:#ac351a}.trip-match{padding:8px 0;border-bottom:1px solid #d9dee5}
      @media(max-width:600px){.trip-fields{grid-template-columns:1fr}.trip-calendar-workspace dialog{padding:14px}.trip-calendar-workspace .fc-toolbar-title{font-size:16px}.trip-calendar-workspace .fc-button{padding:5px}}
    </style><div class="trip-calendar-heading"><h2>Trip calendar</h2><button data-new>＋ Drive</button><button data-sync>Sync</button><button data-setup>Calendar connection</button></div>
    <p data-sync-status role="status"></p><p class="trip-feedback" data-error role="alert"></p><div data-notices></div><div data-calendar></div><details><summary>Referee matches</summary><div data-matches></div></details>
    <dialog data-editor><form><h2 data-title>New drive</h2><div class="trip-fields">
      <label class="wide">Drive type<select name="mode"><option value="routed">Drive between places</option><option value="distance_only">Distance only · leave and return home</option></select></label>
      ${['origin','destination'].map(key=>`<div data-endpoint="${key}"><label>${key === 'origin' ? 'From' : 'To'}<input name="${key}" maxlength="1000" autocomplete="off"></label><button type="button" data-home="${key}">Home</button><button type="button" data-search="${key}">Search places</button><div class="trip-search-results" data-results="${key}"></div></div>`).join('')}
      <label>Timing<select name="timing"><option value="depart">Depart at · calculate arrival</option><option value="arrive">Arrive by · calculate departure</option><option value="fixed">Fixed start and end</option></select></label>
      <label>Distance (km, optional override)<input name="manual_km" type="number" min="0.001" step="any"><button type="button" data-calculated>Use calculated distance</button></label>
      <p class="wide subtle" data-route-detail></p>
      ${['start','end'].map(key=>`<label data-time="${key}">${key === 'start' ? 'Departure' : 'Arrival'}<input name="${key}" required></label>`).join('')}
      <fieldset class="wide" data-repeat><legend>Repeat</legend><label><select name="repeat"><option value="no">Once</option><option value="yes">Every N weeks</option></select></label><div data-rule><label>Weeks<input name="weeks" type="number" value="1" min="1" max="52"></label><div class="trip-weekdays">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((day,index)=>`<label><input type="checkbox" name="day${index}">${day}</label>`).join('')}</div><label>End date (optional)<input name="until" type="date"></label></div></fieldset>
      <label class="wide" data-scope>Apply to<select name="scope"><option value="occurrence">This drive</option><option value="following">This and following drives</option></select></label>
      </div><p class="trip-feedback" data-form-error role="alert"></p><div class="trip-actions"><button type="submit" class="primary">Save drive</button><button type="button" data-cancel>Cancel</button><button type="button" data-delete>Delete</button><button type="button" data-reverse>Add reverse drive</button></div><div data-reverse-options hidden><label>Position<select name="reverse_position"><option value="after">Immediately after</option><option value="before">Immediately before</option></select></label><label><input type="checkbox" name="reverse_recurring">Create independent reverse series</label><button type="button" data-confirm-reverse>Create reverse</button></div></form></dialog>
      <dialog data-connection><form><h2>Google Calendar connection</h2><p>Create a dedicated EV trips calendar in Google, then select it here. Local trips remain available while disconnected.</p><div class="trip-fields">
      <label class="wide">OAuth web client ID<input name="client_id" autocomplete="off"></label><label class="wide">Client secret (blank keeps saved)<input name="client_secret" type="password" autocomplete="new-password"></label><label class="wide">Exact OAuth redirect URL<input name="redirect_uri" type="url" placeholder="https://your-domain/api/ev/calendar/callback"></label><label class="wide">Exact push URL<input name="webhook_uri" type="url" placeholder="https://your-domain/api/ev/calendar/push"></label></div>
      <div class="trip-actions"><button type="submit">Save setup</button><button type="button" data-authorize>Authorize Google</button><button type="button" data-list>Load calendars</button></div><div data-calendar-list></div><div class="trip-actions"><button type="button" data-connect>Connect selected calendars</button><button type="button" data-disconnect>Disconnect</button><button type="button" data-close-connection>Close</button></div><p class="trip-feedback" data-connection-error role="alert"></p><a data-auth-link target="_blank" rel="noopener" hidden>Continue authorization with Google</a></form></dialog>`;
    this.editor = this.root.querySelector('[data-editor]');
    this.form = this.editor.querySelector('form');
    this.picker.bind(this.form.elements.start, 'Departure', true);
    this.picker.bind(this.form.elements.end, 'Arrival', true);
    this.connection = this.root.querySelector('[data-connection]');
    this.connectionForm = this.connection.querySelector('form');
    this.form.addEventListener('change', () => this.toggle());
    this.lifecycle = new AbortController();
    this.root.addEventListener('pointerdown', event => {
      if (event.target.closest('.fc-timegrid-body,.fc-daygrid-body')) this.gestureActive = true;
    });
    for (const name of ['pointerup', 'pointercancel']) window.addEventListener(name, () => {
      this.gestureActive = false;
    }, {
      signal: this.lifecycle.signal
    });
    this.form.addEventListener('submit', event => {
      event.preventDefault();
      this.perform(() => this.save(), true);
    });
    this.connectionForm.addEventListener('submit', event => {
      event.preventDefault();
      this.perform(async () => {
        const data = Object.fromEntries(new FormData(this.connectionForm));
        await this.api('ev/calendar', 'POST', {
          action: 'setup',
          ...data
        });
        this.connectionForm.elements.client_secret.value = '';
      });
    });
    this.root.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button) return;
      this.perform(async () => {
        if (button.hasAttribute('data-new')) this.open();
        if (button.hasAttribute('data-sync')) {
          await this.api('ev/calendar', 'POST', {
            action: 'sync'
          });
          await this.reload();
        }
        if (button.hasAttribute('data-setup')) this.openConnection();
        if (button.hasAttribute('data-cancel')) this.editor.close();
        if (button.hasAttribute('data-close-connection')) this.connection.close();
        if (button.dataset.home) {
          this.form.elements[button.dataset.home].value = 'Home';
          this.selectedPlaces[button.dataset.home] = null;
        }
        if (button.dataset.search) await this.search(button.dataset.search);
        if (button.hasAttribute('data-calculated')) this.form.elements.manual_km.value = '';
        if (button.hasAttribute('data-delete')) {
          await this.api(`ev/drives/${this.current.id}`, 'DELETE', {
            scope: this.form.elements.scope.value
          });
          this.editor.close();
          await this.reload();
        }
        if (button.hasAttribute('data-reverse')) this.form.querySelector('[data-reverse-options]').hidden =
          false;
        if (button.hasAttribute('data-confirm-reverse')) {
          await this.api(`ev/drives/${this.current.id}/reverse`, 'POST', {
            before: this.form.elements.reverse_position.value === 'before',
            recurring: this.form.elements.reverse_recurring.checked
          });
          this.editor.close();
          await this.reload();
        }
        if (button.hasAttribute('data-authorize')) {
          const {
            url
          } = await this.api('ev/calendar', 'POST', {
            action: 'authorize'
          });
          const link = this.root.querySelector('[data-auth-link]');
          link.href = url;
          link.hidden = false;
          link.focus();
        }
        if (button.hasAttribute('data-list')) await this.listCalendars();
        if (button.hasAttribute('data-connect')) {
          const calendar = this.connectionForm.querySelector('[name="ev_calendar"]').value;
          const selected = [...this.connectionForm.querySelectorAll('[data-visible]:checked')].map(input =>
            input.value);
          await this.api('ev/calendar', 'POST', {
            action: 'connect',
            calendar,
            selected
          });
          this.connection.close();
          await this.reload();
        }
        if (button.hasAttribute('data-disconnect')) {
          await this.api('ev/calendar', 'POST', {
            action: 'disconnect'
          });
          await this.reload();
        }
        if (button.dataset.match) {
          await this.api('ev/calendar', 'POST', {
            action: 'match',
            id: button.dataset.match,
            operation: button.dataset.operation
          });
          await this.reload();
        }
        if (button.dataset.dismiss) {
          await this.api('ev/calendar', 'POST', {
            action: 'dismiss',
            key: button.dataset.dismiss
          });
          await this.reload();
        }
      }, this.editor.open);
    });
  }

  get busy() {
    return this.editor.open || this.connection.open || this.pending || this.gestureActive;
  }

  async perform(action, form = false) {
    if (this.pending) return;
    this.pending = true;
    const target = this.root.querySelector(form ? '[data-form-error]' : this.connection.open ?
      '[data-connection-error]' : '[data-error]');
    target.textContent = '';
    try {
      await action();
    } catch (error) {
      target.textContent = error.message || 'The action failed. Try again.';
    } finally {
      this.pending = false;
    }
  }

  async update(state) {
    this.state = state;
    const info = state.trip_calendar;
    if (!info) return;
    this.info = info;
    this.root.querySelector('[data-sync-status]').textContent =
      syncLabel(info);
    if (!this.calendar) {
      if (this.loading) return;
      this.loading = true;
      try {
        await loadCalendar();
        if (this.disposed) return;
        this.calendar = new window.FullCalendar.Calendar(this.root.querySelector('[data-calendar]'), {
          initialDate: state.now,
          timeZone: state.policy.timezone,
          initialView: matchMedia('(max-width:650px)').matches ? 'timeGridDay' : 'timeGridWeek',
          headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'timeGridWeek,timeGridDay,dayGridMonth'
          },
          height: 650,
          scrollTime: '07:00:00',
          slotMinTime: '00:00:00',
          slotMaxTime: '24:00:00',
          allDaySlot: true,
          nowIndicator: true,
          buttonIcons: false,
          buttonText: {
            prev: '‹',
            next: '›'
          },
          firstDay: 1,
          eventTimeFormat: {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          },
          slotLabelFormat: {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          },
          editable: true,
          eventResizableFromStart: true,
          selectable: true,
          selectMirror: true,
          longPressDelay: 350,
          select: selection => {
            this.open(null, selection.startStr, selection.endStr);
            this.calendar.unselect();
          },
          eventClick: click => {
            const drive = this.info.trips.find(item => item.id === click.event.id);
            if (drive) this.open(drive);
          },
          eventDrop: change => this.move(change),
          eventResize: change => this.move(change),
          datesSet: () => this.perform(() => this.reload())
        });
        this.calendar.render();
        await this.reload();
      } catch (error) {
        this.root.querySelector('[data-error]').textContent = error.message;
      } finally {
        this.loading = false;
      }
    } else if (!this.busy) {
      const signature = JSON.stringify([info.trips, info.resolved, info.matches, info.notices]);
      if (signature !== this.signature) {
        this.signature = signature;
        this.renderEvents();
      }
      requestAnimationFrame(() => this.calendar?.updateSize());
    }
  }

  async reload() {
    if (!this.calendar) return;
    const sequence = (this.sequence || 0) + 1;
    this.sequence = sequence;
    const start = this.calendar.view.activeStart.toISOString(),
      end = this.calendar.view.activeEnd.toISOString();
    const info = await this.api(`ev/calendar?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
    if (sequence !== this.sequence || this.disposed) return;
    this.info = info;
    this.context = info.context;
    this.renderEvents();
  }

  renderEvents() {
    if (!this.calendar) return;
    this.calendar.batchRendering(() => {
      this.calendar.removeAllEvents();
      for (const item of this.context || []) this.calendar.addEvent({
        ...item,
        backgroundColor: '#718096',
        borderColor: '#718096'
      });
      for (const item of this.info.trips.filter(trip => !trip.deleted && !trip.series_master)) {
        const route = this.info.resolved[item.id];
        this.calendar.addEvent({
          id: item.id,
          title: item.title,
          start: item.start,
          end: item.end,
          editable: true,
          backgroundColor: route?.error ? '#a34d27' : '#167b76',
          borderColor: route?.error ? '#a34d27' : '#167b76'
        });
      }
    });
    this.root.querySelector('[data-notices]').innerHTML = Object.entries(this.info.resolved).filter(([, route]) =>
        route.warning || route.error)
      .map(([id, route]) =>
        `<p class="trip-feedback">${esc(this.info.trips.find(item=>item.id===id)?.title)}: ${esc(route.error||'Travel time exceeds allotted duration by more than 10 minutes.')}</p>`
      ).join('') +
      this.info.notices.filter(item => item.kind === 'invalid_endpoints').map(() =>
        '<p class="trip-feedback">A Google drive needs correction; its last valid planning data is retained.</p>')
      .join('');
    this.root.querySelector('[data-notices]').innerHTML += this.info.notices.filter(item => item.kind ===
        'match_changed')
      .map(item =>
        `<p>Match time or location changed; both drives were regenerated. <button data-dismiss="${esc(item.key)}">Dismiss</button></p>`
      ).join('');
    this.root.querySelector('[data-matches]').innerHTML = this.info.matches.map(match =>
      `<div class="trip-match"><strong>${esc(match.event.title)}</strong> · ${esc(match.event.start)} ${match.error?`<p class="trip-feedback">${esc(match.error)}</p>`:''}<button data-match="${esc(match.id)}" data-operation="regenerate">Regenerate drives</button>${match.missing&&!match.removed?`<p>The source match disappeared. Keep its drives or remove them?</p><button data-match="${esc(match.id)}" data-operation="retain">Keep drives</button><button data-match="${esc(match.id)}" data-operation="remove">Remove drives</button>`:''}</div>`
    ).join('') || '<p>No source matches yet.</p>';
    this.root.querySelector('[data-sync-status]').textContent =
      syncLabel(this.info);
  }

  open(drive = null, start = null, end = null) {
    if (!this.state) return;
    this.current = drive ? structuredClone(drive) : null;
    this.selectedPlaces = {};
    this.tokens = {};
    this.searchSequence = {};
    const begin = start || new Date(Date.parse(this.state.now) + 86400000).toISOString();
    const finish = end || new Date(Date.parse(begin) + 3600000).toISOString();
    const previous = this.info?.trips.filter(item => !item.deleted && !item.series_master && Date.parse(item.end) <=
      Date.parse(begin)).sort((a, b) => Date.parse(b.end) - Date.parse(a.end))[0];
    const values = {
      mode: drive?.mode || 'routed',
      origin: drive?.origin || previous?.destination || 'Home',
      destination: drive?.destination || '',
      timing: drive?.timing || 'fixed',
      start: localDateTime(drive?.start || begin, this.state.policy.timezone),
      end: localDateTime(drive?.end || finish, this.state.policy.timezone),
      manual_km: drive?.manual_km ?? '',
      repeat: 'no',
      scope: 'occurrence'
    };
    this.form.reset();
    for (const [key, value] of Object.entries(values)) this.form.elements[key].value = value;
    for (const key of ['start', 'end']) {
      this.picker.setValue(this.form.elements[key], drive?.[key] || (key === 'start' ? begin : finish));
    }
    if (drive?.series) {
      const rule = this.info.series[drive.series]?.rule;
      if (rule) {
        this.form.elements.weeks.value = rule.weeks;
        this.form.elements.until.value = rule.until || '';
        rule.weekdays.forEach(day => this.form.elements['day' + day].checked = true);
      }
    }
    this.root.querySelector('[data-title]').textContent = drive ? 'Edit drive' : 'New drive';
    this.form.querySelector('[data-scope]').hidden = !drive?.series;
    this.form.querySelector('[data-repeat]').hidden = !!drive && !drive.series;
    this.form.querySelector('[data-delete]').hidden = this.form.querySelector('[data-reverse]').hidden = !drive;
    this.form.querySelector('[data-reverse-options]').hidden = true;
    this.form.querySelector('[data-form-error]').textContent = '';
    const route = drive && this.info.resolved[drive.id];
    this.form.querySelector('[data-route-detail]').textContent = route?.distance_km != null ?
      `${route.error ? 'Last valid planning data' : 'Saved planning distance'}: ${Number(route.distance_km).toFixed(1)} km · ${(route.distance_km*this.state.policy.consumption_kwh_per_100km/100).toFixed(1)} kWh driving.${route.calculated_km != null ? ' Calculated route: '+Number(route.calculated_km).toFixed(1)+' km.' : ''} Changes are calculated after Save.` :
      'Distance and driving energy are calculated after Save.';
    this.form.querySelectorAll('[data-results]').forEach(node => node.replaceChildren());
    this.toggle();
    if (!this.editor.open) this.editor.showModal();
    this.editor.scrollTop = 0;
  }

  toggle() {
    const f = this.form.elements,
      distance = f.mode.value === 'distance_only';
    if (distance) f.timing.value = 'fixed';
    f.timing.disabled = distance;
    this.form.querySelectorAll('[data-endpoint]').forEach(node => node.hidden = distance);
    for (const key of ['origin', 'destination']) f[key].required = !distance;
    f.manual_km.required = distance;
    for (const key of ['start', 'end']) {
      const visible = f.timing.value === 'fixed' || (key === 'start' && f.timing.value === 'depart') || (key ===
        'end' && f.timing.value === 'arrive');
      this.form.querySelector(`[data-time="${key}"]`).hidden = !visible;
      f[key].required = visible;
      this.picker.fields.get(f[key]).required = visible;
    }
    this.form.querySelector('[data-rule]').hidden = f.repeat.value !== 'yes' && f.scope.value !== 'following';
  }

  instant(key) {
    return this.picker.instant(this.form.elements[key]);
  }

  async save() {
    const f = this.form.elements,
      timing = f.timing.value;
    let start, end;
    if (timing === 'depart') {
      start = this.instant('start');
      end = new Date(Date.parse(start) + 3600000).toISOString();
    } else if (timing === 'arrive') {
      end = this.instant('end');
      start = new Date(Date.parse(end) - 3600000).toISOString();
    } else {
      start = this.instant('start');
      end = this.instant('end');
    }
    const body = {
      mode: f.mode.value,
      timing,
      start,
      end,
      origin: f.origin.value.trim(),
      destination: f.destination.value.trim(),
      manual_km: f.manual_km.value === '' ? null : Number(f.manual_km.value),
      origin_city: this.selectedPlaces.origin?.city || (f.origin.value.trim() === this.current?.origin ? this
        .current?.origin_city : '') || '',
      destination_city: this.selectedPlaces.destination?.city || (f.destination.value.trim() === this.current
        ?.destination ? this.current?.destination_city : '') || ''
    };
    if (this.current) body.revision = this.current.revision;
    if (f.repeat.value === 'yes' || f.scope.value === 'following') {
      body.rule = {
        weeks: Number(f.weeks.value),
        until: f.until.value || null,
        weekdays: Array.from({
          length: 7
        }, (_, i) => i).filter(i => f['day' + i].checked)
      };
      body.scope = f.scope.value;
      const originalRule = this.current?.series && this.info.series[this.current.series]?.rule;
      if (originalRule?.week_start != null) body.rule.week_start = originalRule.week_start;
    }
    await this.api(this.current ? `ev/drives/${this.current.id}` : 'ev/drives', 'POST', body);
    this.editor.close();
    await this.reload();
  }

  async move(change) {
    this.gestureActive = false;
    if (this.busy) {
      change.revert();
      return;
    }
    const original = this.info.trips.find(item => item.id === change.event.id);
    this.pending = true;
    try {
      await this.api(`ev/drives/${original.id}`, 'POST', {
        ...original,
        timing: 'fixed',
        start: change.event.start.toISOString(),
        end: change.event.end.toISOString()
      });
      await this.reload();
    } catch (error) {
      change.revert();
      this.root.querySelector('[data-error]').textContent = error.message;
    } finally {
      this.pending = false;
    }
  }

  async search(key) {
    const token = this.tokens[key] ||= crypto.randomUUID(),
      text = this.form.elements[key].value;
    const sequence = (this.searchSequence[key] || 0) + 1;
    this.searchSequence[key] = sequence;
    const {
      result
    } = await this.api('ev/places', 'POST', {
      text,
      token
    });
    if (this.searchSequence[key] !== sequence || this.form.elements[key].value !== text) return;
    const list = this.form.querySelector(`[data-results="${key}"]`);
    list.replaceChildren();
    for (const item of result) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = item.label;
      button.onclick = () => this.perform(async () => {
        const {
          result: place
        } = await this.api('ev/places', 'POST', {
          id: item.id,
          token
        });
        if (!this.editor.open || this.form.elements[key].value !== text) return;
        this.form.elements[key].value = place.address;
        this.selectedPlaces[key] = place;
        delete this.tokens[key];
        list.replaceChildren();
      }, true);
      list.append(button);
    }
    const attribution = document.createElement('small');
    attribution.textContent = 'Google Maps';
    attribution.className = 'trip-maps-attribution';
    attribution.setAttribute('translate','no');
    list.append(attribution);
  }

  openConnection() {
    const oauth = this.info.oauth;
    for (const key of ['client_id', 'redirect_uri', 'webhook_uri']) this.connectionForm.elements[key].value = oauth[
      key] || '';
    this.connectionForm.elements.client_secret.value = '';
    this.connection.showModal();
  }

  async listCalendars() {
    const {
      calendars
    } = await this.api('ev/calendar', 'POST', {
      action: 'calendars'
    });
    this.connectionForm.querySelector('[data-calendar-list]').innerHTML =
      `<label>Dedicated writable EV calendar<select name="ev_calendar">${calendars.filter(item=>['owner','writer'].includes(item.accessRole)).map(item=>`<option value="${esc(item.id)}"${item.id===this.info.calendar?' selected':''}>${esc(item.summary)}</option>`).join('')}</select></label><fieldset><legend>Show appointments (read-only)</legend>${calendars.map(item=>`<label><input type="checkbox" data-visible value="${esc(item.id)}"${this.info.selected.includes(item.id)?' checked':''}> ${esc(item.summary)}</label>`).join('')}</fieldset>`;
  }

  dispose() {
    this.lifecycle.abort();
    this.disposed = true;
    this.sequence++;
    this.calendar?.destroy();
  }
}
