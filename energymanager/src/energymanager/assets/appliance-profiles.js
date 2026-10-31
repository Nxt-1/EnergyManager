import {ProfileChart} from './profile-chart.js';
export {profileGraph} from './profile-chart.js';

const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, character =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
const machineName = machine => ({dishwasher: 'Dishwasher', washing_machine: 'Washing machine'}[machine]);
const decimal = (value, digits = 2) => value === null || value === undefined ? '—' : Number(value).toFixed(digits);

export class ApplianceProfilesPage {
  constructor(root, api, signal) {
    this.root = root;
    this.api = api;
    this.signal = signal;
    this.visible = false;
    this.loading = false;
    this.library = null;
    this.previewGeneration = 0;
    root.addEventListener('input', event => {
      if (['start_seconds','end_seconds'].includes(event.target.name)) this.syncTrim(event.target.form);
    }, {signal});
    signal.addEventListener('abort', () => {
      clearTimeout(this.previewTimer);
      this.chart?.close();
    }, {once:true});
    root.addEventListener('submit', event => {
      event.preventDefault();
      this.perform(() => this.submit(event.target));
    }, {signal});
    root.addEventListener('click', event => {
      const button = event.target.closest('[data-profile-command]');
      if (button) this.perform(() => this.command(button));
    }, {signal});
    this.timer = setInterval(() => { if (this.visible) this.refresh(); }, 5000);
    signal.addEventListener('abort', () => clearInterval(this.timer), {once: true});
  }

  setVisible(visible) {
    const newlyVisible = visible && !this.visible;
    this.visible = visible;
    if (newlyVisible) this.refresh();
  }

  async perform(action) {
    if (this.busy) return;
    this.busy = true;
    const buttons = [...this.root.querySelectorAll('button')];
    buttons.forEach(button => { button.disabled = true; });
    try {
      this.message('');
      await action();
    } catch (error) {
      if (!this.signal.aborted) this.message(error.message, true);
    } finally {
      this.busy = false;
      buttons.forEach(button => { button.disabled = false; });
    }
  }

  message(text, error = false) {
    const element = this.root.querySelector('[data-profile-message]');
    if (element) { element.textContent = text; element.className = error ? 'error' : 'muted'; }
  }

  async refresh() {
    if (this.loading || this.signal.aborted) return;
    this.loading = true;
    try {
      const library = await this.api('profiles');
      if (this.signal.aborted) return;
      this.library = library;
      if (!this.mounted) { this.mount(); this.mounted = true; }
      this.renderRecordings();
      if (library.sampler_error) this.message(library.sampler_error, true);
    } catch (error) {
      if (!this.root.querySelector('[data-profile-message]')) this.root.innerHTML = '<p data-profile-message role="alert"></p>';
      this.message(error.message, true);
    } finally { this.loading = false; }
  }

  mount() {
    const library = this.library;
    const machineForms = Object.entries(library.machines).map(([machine, settings]) => `<article class="card">
      <h2>${machineName(machine)}</h2><form data-profile-form="configure" data-machine="${machine}" data-revision="${library.revision}" class="profile-form">
      <label>Dedicated power sensor<input name="entity_id" list="profile-power-entities" value="${escapeHTML(settings.entity_id)}" placeholder="sensor.…" autocomplete="off"></label>
      <label>Idle / start threshold (W)<input name="start_threshold_w" type="number" min="0.1" max="100000" step="0.1" required value="${settings.start_threshold_w}"></label>
      <label>Finish after idle (minutes)<input name="idle_timeout_minutes" type="number" min="1" max="120" step="0.1" required value="${settings.idle_timeout_minutes}"></label>
      <button type="submit">Save recording settings</button></form>
      <form data-profile-form="arm" data-machine="${machine}" class="profile-form">
      <label>Program<select name="program">${Object.entries(library.programs[machine]).map(([id, label]) => `<option value="${id}">${escapeHTML(label)}</option>`).join('')}</select></label>
      <label>Load / options / notes<input name="notes" maxlength="500" placeholder="e.g. full load, extra rinse"></label>
      <button type="submit">Record next cycle</button></form></article>`).join('');
    this.root.innerHTML = `<div class="page-heading"><div><h1>Appliance profiles</h1>
      <p class="muted">Arm a program, run the machine normally, then review the recording before saving it.</p></div>
      <button type="button" data-profile-command="entities">Load HA power sensors</button></div>
      <p data-profile-message role="status"></p>
      <p class="notice">${library.mode === 'demo' ? 'Demo library · live recording is disabled. ' : ''}Recording waits for idle, then power above the threshold. A continuous idle period finishes the cycle; renewed activity resets the timer. Use a timeout longer than quiet phases in your program. Initial 10 W / 15 min settings are provisional.</p>
      <datalist id="profile-power-entities"></datalist><div class="profile-machines">${machineForms}</div>
      <article class="card"><h2>Mazak · provisional average loads</h2><form data-profile-form="mazak" data-revision="${library.revision}" class="profile-form">
      ${Object.entries(library.mazak).map(([mode, power]) => `<label>${mode[0].toUpperCase() + mode.slice(1)} (W)<input name="${mode}" type="number" min="0" max="100000" step="1" required value="${power}"></label>`).join('')}
      <button type="submit">Save Mazak averages</button></form><p class="muted">Flat average loads for later planning; no cycle duration is assumed.</p></article>
      <article class="card"><h2>Averaged profiles</h2><div data-profile-selected></div></article>
      <article class="card"><h2>Recordings</h2><div data-profile-recordings></div><p class="muted">Latest 100 recordings shown. Original samples and earlier saved cycles are retained.</p></article>
      <article class="card" data-profile-review hidden></article>
      <p class="muted">Profiles are stored in EnergyManager. This first milestone does not schedule or start appliances.</p>`;
  }

  renderRecordings() {
    const library = this.library;
    this.root.querySelector('[data-profile-selected]').innerHTML = Object.entries(library.programs).map(([machine, programs]) =>
      Object.entries(programs).map(([program, label]) => {
        const profile = library.profiles[`${machine}/${program}`];
        return `<p>${machineName(machine)} · ${escapeHTML(label)}: ${profile ?
          `${profile.recording_count} recording${profile.recording_count === 1 ? '' : 's'} ·
          ${decimal(profile.summary.mean_duration_seconds / 60, 1)} min mean cycle ·
          ${decimal(profile.summary.energy_kwh, 3)} kWh mean
          <button data-profile-command="average" data-machine="${machine}" data-program="${program}">Inspect average</button>` :
          'No reviewed recordings included'}</p>`;
      }).join('')).join('');
    this.root.querySelector('[data-profile-recordings]').innerHTML = library.recordings.length ? library.recordings.map(recording => {
      const status = recording.status === 'saved' && recording.trimmed_from ? 'saved · trim revision' : recording.status === 'armed' ? (recording.idle_seen ? 'Armed · waiting for start' : 'Armed · waiting for idle') : recording.status;
      return `<section class="profile-recording"><strong>${machineName(recording.machine)} · ${escapeHTML(library.programs[recording.machine][recording.program])}</strong>
        <p>${escapeHTML(status)} · ${escapeHTML(new Date(recording.armed_at).toLocaleString('en-GB', {timeZone: this.timezone || 'Europe/Brussels'}))} · ${recording.sample_count} samples · ${recording.last_power_w === null ? 'Power unavailable' : Math.round(recording.last_power_w) + ' W'}</p>
        <p>${escapeHTML(recording.notes)}${recording.error ? ' · ' + escapeHTML(recording.error) : ''}</p>
        <div class="actions"><button data-profile-command="review" data-id="${recording.id}">Inspect / review</button>
        ${recording.status === 'recording' ? `<button data-profile-command="finish" data-id="${recording.id}">Finish now</button>` : ''}
        ${recording.status === 'saved' ? `<button data-profile-command="select" data-id="${recording.id}" data-included="${!recording.included}">${recording.included ? 'Remove from average' : 'Add to average'}</button>` : `<button data-profile-command="discard" data-id="${recording.id}">Discard recording</button>`}</div></section>`;
    }).join('') : '<p class="muted">No cycles recorded yet.</p>';
  }

  async submit(form) {
    const values = Object.fromEntries(new FormData(form));
    const action = form.dataset.profileForm;
    if (action === 'arm') {
      await this.api('profiles/arm', 'POST', {...values, machine: form.dataset.machine});
      this.message('Armed. Start the machine after the recorder has observed idle power.');
    } else if (action === 'configure' || action === 'mazak') {
      const body = {revision: Number(form.dataset.revision), machine: form.dataset.machine};
      if (action === 'mazak') Object.assign(body, {machine: 'mazak', powers_w: Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value)]))});
      else Object.assign(body, {entity_id: values.entity_id, start_threshold_w: Number(values.start_threshold_w), idle_timeout_minutes: Number(values.idle_timeout_minutes)});
      this.library = await this.api('profiles/configure', 'POST', body);
      // Refresh this form's revision; other unsaved forms retain their original conflict guard.
      this.advanceRevision(body.revision, this.library.revision);
      this.message(action === 'mazak' ? 'Provisional Mazak average loads saved.' : 'Saved. Recording settings apply to the next armed cycle.');
    } else if (action === 'accept' || action === 'revise') {
      const body = {reviewed: values.reviewed === 'on', revision: Number(form.dataset.revision),
        start_seconds: Number(values.start_seconds), end_seconds: Number(values.end_seconds)};
      const saved = await this.api(`profile-recordings/${form.dataset.id}/${action}`, 'POST', body);
      this.advanceRevision(body.revision, saved.library_revision);
      await this.review(saved.id,saved.library_revision);
      this.message(action === 'revise' ? 'Revised trim saved. The original is retained; this cycle contributes once to the average.' : 'Reviewed cycle saved and added to the program average. Original recordings are retained.');
    }
    await this.refresh();
  }

  advanceRevision(previous, next) {
    if (next !== previous + 1) return;
    for (const form of this.root.querySelectorAll('form[data-revision]')) {
      if (Number(form.dataset.revision) === previous) form.dataset.revision = next;
    }
  }

  async command(button) {
    const command = button.dataset.profileCommand, id = button.dataset.id;
    if (command === 'entities') {
      const result = await this.api('settings/entities');
      if (this.signal.aborted) return;
      this.root.querySelector('#profile-power-entities').innerHTML = result.entities.filter(entity => entity.entity_id.startsWith('sensor.') && ['W', 'kW'].includes(entity.unit))
        .map(entity => `<option value="${escapeHTML(entity.entity_id)}">${escapeHTML(entity.name)} · ${escapeHTML(entity.state)} ${escapeHTML(entity.unit)}</option>`).join('');
      this.message('Power sensors loaded. Select a dedicated sensor for each machine.');
      return;
    }
    if (command === 'review') return this.review(id);
    if (command === 'average') return this.reviewAverage(button.dataset.machine,button.dataset.program);
    if (command === 'preview') return this.previewSelection(button.closest('form'));
    const revision = this.library.revision;
    const result = await this.api(`profile-recordings/${id}/${command}`, 'POST', {revision,...(command === 'select' ? {included:button.dataset.included !== 'false'} : {})});
    if (command === 'select') this.advanceRevision(revision, result.library_revision);
    if (command === 'finish') await this.review(id);
    if (command === 'discard') {
      this.chart?.close();
      this.root.querySelector('[data-profile-review]').hidden = true;
    }
    await this.refresh();
    if (command === 'select' && this.reviewed?.averaged) {
      const key = this.reviewed.machine + '/' + this.reviewed.program;
      if (this.library.profiles[key]) await this.reviewAverage(this.reviewed.machine,this.reviewed.program);
      else { this.chart?.close(); this.root.querySelector('[data-profile-review]').hidden = true; }
    }
  }

  summaryText(summary) {
    return `${decimal(summary.duration_seconds / 60, 1)} min · ${decimal(summary.energy_kwh, 3)} kWh${summary.complete ? '' : ' measured portion only · MISSING DATA'} · ${decimal(summary.average_w, 0)} W average · ${decimal(summary.peak_w, 0)} W peak`;
  }

  trimValues(form) {
    const start = form.elements.start_seconds, end = form.elements.end_seconds;
    end.setCustomValidity('');
    const selection = {start_seconds:start.valueAsNumber,end_seconds:end.valueAsNumber};
    const maximum = this.reviewed.points.at(-1)?.seconds || 0;
    if (!Number.isFinite(selection.start_seconds) || !Number.isFinite(selection.end_seconds) ||
        selection.start_seconds < 0 || selection.end_seconds > maximum ||
        selection.end_seconds <= selection.start_seconds) {
      end.setCustomValidity('Choose an end after the start, within this recording.');
      return null;
    }
    return selection;
  }

  syncTrim(form) {
    clearTimeout(this.previewTimer);
    const selection = this.trimValues(form);
    if (!selection) return;
    this.chart.setSelection(selection);
    form.elements.reviewed.checked = false;
    form.querySelector('[data-profile-summary]').textContent = 'Updating selection…';
    this.previewTimer = setTimeout(() => {
      this.previewSelection(form).catch(error => this.message(error.message,true));
    },250);
  }

  async previewSelection(form) {
    const selection = this.trimValues(form);
    if (!selection) { form.reportValidity(); return; }
    const generation = ++this.previewGeneration;
    const identity = this.reviewed.id;
    const summary = await this.api(`profile-recordings/${identity}/preview`,'POST',selection);
    if (this.signal.aborted || generation !== this.previewGeneration || !form.isConnected ||
        this.reviewed.id !== identity) return;
    const current = this.trimValues(form);
    if (!current || current.start_seconds !== selection.start_seconds ||
        current.end_seconds !== selection.end_seconds) return;
    form.querySelector('[data-profile-summary]').textContent = this.summaryText(summary);
  }

  mountChart(recording, selection, editable) {
    this.chart?.close();
    this.chart = new ProfileChart(this.root.querySelector('[data-profile-graph]'),
      {...recording,timezone:this.timezone},selection,editable,this.signal,(next,finished) => {
        const form = this.root.querySelector('form[data-profile-trim]');
        if (!form) return;
        form.elements.reviewed.checked = false;
        form.elements.start_seconds.value = next.start_seconds;
        form.elements.end_seconds.value = next.end_seconds;
        form.elements.end_seconds.setCustomValidity('');
        form.querySelector('[data-profile-summary]').textContent = 'Updating selection…';
        if (finished) this.syncTrim(form);
      });
  }

  async reviewAverage(machine,program) {
    const profile = await this.api(`profiles/${machine}/${program}`);
    if (this.signal.aborted) return;
    this.reviewed = profile;
    clearTimeout(this.previewTimer);
    this.previewGeneration++;
    const panel = this.root.querySelector('[data-profile-review]');
    panel.hidden = false;
    panel.innerHTML = `<h2>Average · ${machineName(machine)} · ${escapeHTML(this.library.programs[machine][program])}</h2>
      <p>${profile.recording_count} reviewed recording${profile.recording_count === 1 ? '' : 's'} ·
      ${escapeHTML(this.summaryText(profile.summary))}</p>
      <p class="muted">Starts are aligned without stretching time. Each complete cycle contributes zero after its selected end.
      Mean cycle duration: ${decimal(profile.summary.mean_duration_seconds/60,1)} min;
      graph extends to the longest cycle: ${decimal(profile.summary.duration_seconds/60,1)} min.</p>
      <div data-profile-graph></div>
      <h3>Included recordings</h3><div class="actions profile-contributors">
      ${profile.recording_ids.map((identity,index) => `<span>Recording ${index+1}
      <button data-profile-command="review" data-id="${identity}">Inspect</button>
      <button data-profile-command="select" data-id="${identity}" data-included="false">Remove from average</button></span>`).join('')}
      </div>`;
    this.mountChart(profile,null,false);
    panel.scrollIntoView({block:'start'});
  }

  async review(id, revision = this.library.revision) {
    const recording = await this.api(`profile-recordings/${id}`);
    if (this.signal.aborted) return;
    this.reviewed = recording;
    clearTimeout(this.previewTimer);
    this.previewGeneration++;
    const panel = this.root.querySelector('[data-profile-review]');
    const duration = recording.points.at(-1)?.seconds || 0;
    const selection = recording.summary || {start_seconds:0,
      end_seconds:recording.suggested_end_seconds ?? duration};
    const saved = recording.status === 'saved';
    const editable = (recording.status === 'review' || saved) && duration > 0;
    panel.hidden = false;
    panel.innerHTML = `<h2>Review · ${machineName(recording.machine)} · ${escapeHTML(this.library.programs[recording.machine][recording.program])}</h2>
      <p>${escapeHTML(recording.notes)} · ${escapeHTML(recording.entity_id)} · ${escapeHTML(recording.status)}</p>
      ${saved ? '<p class="notice">You can adjust this saved trim. Saving keeps the original and uses the revised range once in the average.</p>' : ''}
      <div data-profile-graph></div>
      <p class="muted">Gaps are unknown; short measured peaks remain visible. Trim seconds are relative to the detected start.</p>
      ${recording.interrupted ? '<p class="error">Interrupted recording. Inspect it for diagnosis and record a complete cycle before saving a profile.</p>' : ''}
      ${editable ? `<form data-profile-trim data-profile-form="${saved ? 'revise' : 'accept'}" data-id="${id}" data-revision="${revision}" class="profile-form">
      <label>Start (seconds)<input name="start_seconds" type="number" min="0" max="${duration}" step="any" value="${selection.start_seconds}" required></label>
      <label>End (seconds)<input name="end_seconds" type="number" min="0" max="${duration}" step="any" value="${selection.end_seconds}" required></label>
      <button type="button" data-profile-command="preview">Preview selection</button><p data-profile-summary></p>
      <label class="profile-check"><input name="reviewed" type="checkbox" required>I reviewed a complete cycle and want to include it in this program's average.</label>
      <button type="submit">${saved ? 'Save revised trim' : 'Save and add to average'}</button></form>` : recording.summary ?
      `<p>${escapeHTML(this.summaryText(recording.summary))} · Selected ${selection.start_seconds}–${selection.end_seconds} seconds (shaded)</p>` :
      '<p>Finish the recording before saving a profile.</p>'}`;
    this.mountChart(recording,duration > 0 ? selection : null,editable);
    if (editable) this.syncTrim(panel.querySelector('form'));
    panel.scrollIntoView({block:'start'});
  }
}
