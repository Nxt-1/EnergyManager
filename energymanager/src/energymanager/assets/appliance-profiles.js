import {historyReading} from './ha-history.js';
import {ProfileChart} from './profile-chart.js';
import {ApplianceDeadline} from './appliance-deadline.js';
export {profileGraph} from './profile-chart.js';

const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, character =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
const machineName = machine => ({dishwasher: 'Dishwasher', washing_machine: 'Washing machine', mazak:'Mazak'}[machine]);
const programLabel = value => {
  const text = String(value ?? '').replace(/^dishcare_dishwasher_program_/,'').replaceAll('_',' ').replace(/([a-z])(\d+)/ig,'$1 $2');
  return text.charAt(0).toUpperCase() + text.slice(1);
};
const decimal = (value, digits = 2) => value === null || value === undefined ? '—' : Number(value).toFixed(digits);

export function recorderFeedback(library, machine, elapsedSeconds = 0, statusAvailable = true) {
  if (machine === 'dishwasher' && library.bosch?.enabled) return null;
  const unavailable = program => ({state:'unavailable', text:`⚠ ${program ? program+' · ' : ''}Recorder status unavailable · Power unavailable`});
  if (!Array.isArray(library.recordings)) return unavailable('');
  const recording = library.recordings.find(row => row.machine === machine && row.source !== 'bosch'
    && !['saved','review','cancelled','discarded'].includes(row.status));
  if (!recording) return null;
  const program = library.programs?.[machine]?.[recording.program] ?? recording.program ?? '';
  const snapshotAt = Date.parse(library.now), maximumAge = library.maximum_gap_seconds;
  if (!statusAvailable || library.sampler_error || !['armed','recording'].includes(recording.status)
      || !Number.isFinite(snapshotAt) || !Number.isFinite(maximumAge) || maximumAge <= 0
      || !Number.isFinite(elapsedSeconds) || elapsedSeconds < 0 || elapsedSeconds > maximumAge) return unavailable(program);
  // Compare recorder read times with backend time, advanced by monotonic browser elapsed time.
  // HA last_changed/last_reported do not establish the age of an available unchanged read.
  const age = (snapshotAt - Date.parse(recording.last_at))/1000 + elapsedSeconds;
  const measured = Number.isFinite(recording.last_power_w) && recording.last_power_w >= 0
    && !recording.error && Number.isFinite(age) && age >= 0 && age <= maximumAge;
  if (!measured) return {state:'unavailable', text:`⚠ ${program} · ${recording.status === 'recording' ? 'Recording' : 'Waiting for idle'} · Power unavailable${age > maximumAge ? ' (stale)' : ''}`};
  const watts = `${Math.round(recording.last_power_w)} W`;
  if (recording.status === 'recording') return {state:'recording',text:`● ${program} · Recording · ${watts}`};
  if (recording.idle_seen === true) return {state:'ready',text:`✓ ${program} · Ready to record · Idle detected — start the machine · ${watts}`};
  return {state:'waiting',text:`◷ ${program} · Waiting for idle · ${watts}`};
}

const programIcon = action => {
  const paths = {add:'M12 5v14M5 12h14', rename:'m16 3 5 5-12 12-6 1 1-6Z M14 5l5 5',
    save:'m5 12 4 4L19 6', cancel:'m6 6 12 12M18 6 6 18'};
  return `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[action]}"/></svg>`;
};

export class ApplianceProfilesPage {
  constructor(root, api, signal, interaction = {}) {
    this.root = root;
    this.interaction = interaction;
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
    root.addEventListener('change', event => {
      if (event.target.matches('[data-bosch-program]')) { this.rememberProgram(event.target.value); this.renderBosch(); this.previewReady(); }
    }, {signal});
    root.addEventListener('keydown', event => {
      const form = event.target.closest('[data-program-editor]')?.closest('form');
      if (!form || !this.programEdit) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!this.busy) this.editProgram('cancel', form);
      } else if (event.key === 'Enter' && event.target.matches('[data-program-name]')) {
        event.preventDefault();
        form.requestSubmit();
      }
    }, {signal});
    root.addEventListener('submit', event => {
      event.preventDefault();
      this.perform(() => this.submit(event.target));
    }, {signal});
    root.addEventListener('click', event => {
      const programAction = event.target.closest('[data-program-action]');
      if (programAction) { if (!this.busy) this.editProgram(programAction.dataset.programAction, programAction.form); return; }
      const button = event.target.closest('[data-profile-command]');
      if (button?.dataset.profileCommand === 'program') { this.toggleProgram(button); return; }
      if (button) { this.perform(() => this.command(button)); return; }
      const toggle = event.target.closest('[data-appliance-toggle]');
      if (toggle) { this.expand(toggle.dataset.applianceToggle); return; }
      if (event.target.closest('button,input,select,label,form,a,summary,details,[data-appliance-detail]')) return;
      const card = event.target.closest('[data-appliance-card]');
      if (card) this.expand(card.dataset.applianceCard);

    }, {signal});
    this.statusTimer = setInterval(() => { if (this.visible) this.renderRecorderStatus(); }, 1000);
    signal.addEventListener('abort', () => clearInterval(this.statusTimer), {once:true});
    this.timer = setInterval(() => { if (this.visible) this.refresh(); }, 5000);
    signal.addEventListener('abort', () => clearInterval(this.timer), {once: true});
  }

  setVisible(visible) {
    const newlyVisible = visible && !this.visible;
    this.visible = visible;
    if (newlyVisible) { this.renderRecorderStatus(); this.refresh(); }
  }

  async perform(action) {
    if (this.busy) return;
    this.busy = true;
    const buttons = new Map([...this.root.querySelectorAll('button')].map(button=>[button,button.disabled]));
    buttons.forEach((disabled,button) => { button.disabled = true; });
    try {
      this.message('');
      await action();
    } catch (error) {
      if (!this.signal.aborted) this.message(error.message, true);
    } finally {
      this.busy = false;
      buttons.forEach((disabled,button) => { if (button.isConnected) button.disabled = disabled; });
      const washer = this.root.querySelector('[data-profile-form="arm"][data-machine="washing_machine"]');
      if (washer) washer.querySelector('[data-profile-arm]').disabled = !!this.programEdit;
      if (this.mounted) this.renderBosch();
    }
  }

  message(text, error = false) {
    const element = this.root.querySelector('[data-profile-message]');
    if (element) { element.textContent = text; element.className = error ? 'error' : 'muted'; }
  }

  async refresh() {
    if (this.loading || this.signal.aborted) return;
    this.loading = true;
    const requestedAt = performance.now();
    try {
      const library = await this.api('profiles');
      if (this.signal.aborted || this.library && (library.revision < this.library.revision
          || library.revision === this.library.revision && Date.parse(library.now) < Date.parse(this.library.now))) return;
      this.library = library;
      // Include request latency: a delayed response cannot renew old readiness.
      this.libraryObservedAt = requestedAt;
      this.recorderStatusUnavailable = false;
      if (this.profileRefreshError && this.root.querySelector('[data-profile-message]')?.textContent === this.profileRefreshError) this.message('');
      this.profileRefreshError = null;
      if (!this.mounted) { this.mount(); this.mounted = true; }
      this.renderManualPrograms();
      this.renderRecordings();
      this.renderBosch();
      this.renderRecorderStatus();
      if (library.sampler_error) { this.profileRefreshError = library.sampler_error; this.message(library.sampler_error, true); }
    } catch (error) {
      this.recorderStatusUnavailable = true;
      this.renderRecorderStatus();
      this.profileRefreshError = error.message;
      if (!this.root.querySelector('[data-profile-message]')) this.root.innerHTML = '<p data-profile-message role="alert"></p>';
      this.message(error.message, true);
    } finally { this.loading = false; }
  }

  mount() {
    const library = this.library;
    const machineForms = Object.entries(library.machines).map(([machine, settings]) => {
      const bosch = machine === 'dishwasher';
      return `<article class="card appliance-card" data-appliance-card="${machine}">
      <div class="appliance-heading"><span class="appliance-icon" aria-hidden="true">${bosch ? '▤' : '◉'}</span>
      <h2>${bosch ? 'Bosch dishwasher' : machineName(machine)}</h2>
      <button type="button" data-appliance-toggle="${machine}" aria-expanded="false">Expand</button></div>
      ${bosch ? `<div data-bosch-status aria-live="polite"></div>
      <form data-profile-form="bosch-select" class="profile-form appliance-program">
      <label>Dishwasher program<select name="program" data-bosch-program></select></label>
      <button type="submit">Select program</button><button type="button" data-profile-command="bosch-start">Start now and record</button>
      <button type="button" data-profile-command="bosch-power">Power on</button></form>
      <p data-bosch-command role="status"></p><div data-managed-deadline></div>
      <p data-managed-warning role="status"></p><div class="actions"><button type="button" data-profile-command="run-ready">Ready</button>
      <button type="button" data-profile-command="run-cancel" hidden>Cancel queued run</button></div><div data-managed-state></div>` : '<p>Manually started cycles · recorded with a dedicated power sensor.</p>'}
      <div data-appliance-detail="${machine}" hidden>
      ${bosch ? `<p class="notice">Automatic capture uses actual Bosch execution and the dedicated Refoss meter, including panel/app starts. Every cycle needs review before averaging. Start now sends a command immediately. Ready lets EnergyManager plan a start using a reviewed profile and the chosen latest finish.</p>
      <p class="muted" data-bosch-details></p><div class="actions" data-bosch-modifiers></div>
      <details><summary>Bosch HA mappings</summary>
      <p>Selected program only selects; active program starts a cycle. Map different entities. Leave unavailable optional readings blank.</p>
      <form data-profile-form="bosch-configure" data-revision="${library.revision}" class="profile-form">
      ${Object.entries(library.bosch.fields).map(([key,field]) => `<label>${escapeHTML(field.label)}
      <input name="${key}" list="profile-ha-entities" value="${escapeHTML(library.bosch.config[key] || '')}" placeholder="${field.domains.join(' / ')}.…" autocomplete="off"></label>`).join('')}
      <button type="submit">Save Bosch mappings</button></form></details>` : ''}
      <details><summary>Recording settings</summary>
      <form data-profile-form="configure" data-machine="${machine}" data-revision="${library.revision}" class="profile-form">
      <label>Dedicated power sensor<input name="entity_id" list="profile-power-entities" value="${escapeHTML(settings.entity_id)}" placeholder="sensor.…" autocomplete="off"></label>
      <label>Idle / start threshold (W)<input name="start_threshold_w" type="number" min="0.1" max="100000" step="0.1" required value="${settings.start_threshold_w}"></label>
      <label>Finish after idle (minutes)<input name="idle_timeout_minutes" type="number" min="1" max="120" step="0.1" required value="${settings.idle_timeout_minutes}"></label>
      <button type="submit">Save recording settings</button></form>
      <p class="muted">Idle settings apply to manually armed captures. Bosch automatic captures finish from operation feedback.</p></details>
      <form data-profile-form="arm" data-machine="${machine}" class="profile-form" ${bosch ? 'data-dishwasher-arm' : ''}>
      ${machine === 'washing_machine' ? `<div class="profile-program-field">
      <span id="washer-program-label">Program</span>
      <div class="profile-program-row" data-program-selector>
      <select name="program" aria-labelledby="washer-program-label">${Object.entries(library.programs[machine]).map(([id, label]) => `<option value="${escapeHTML(id)}">${escapeHTML(label)}</option>`).join('')}</select>
      <button type="button" class="profile-program-icon" data-program-action="create" aria-label="Add program" title="Add program">${programIcon('add')}</button>
      <button type="button" class="profile-program-icon" data-program-action="rename" aria-label="Rename selected program" title="Rename selected program">${programIcon('rename')}</button></div>
      <div class="profile-program-row" data-program-editor hidden>
      <input name="program_name" data-program-name aria-labelledby="washer-program-label" maxlength="80" required autocomplete="off" disabled>
      <button type="submit" class="profile-program-icon" aria-label="Save program name" title="Save">${programIcon('save')}</button>
      <button type="button" class="profile-program-icon" data-program-action="cancel" aria-label="Cancel program edit" title="Cancel">${programIcon('cancel')}</button></div></div>` :
      `<label>Program<select name="program">${Object.entries(library.programs[machine]).map(([id, label]) => `<option value="${escapeHTML(id)}">${escapeHTML(label)}</option>`).join('')}</select></label>`}
      <label>Load / options / notes<input name="notes" maxlength="500" placeholder="e.g. full load, extra rinse"></label>
      <button type="submit" data-profile-arm>Record next cycle</button>
      <p class="profile-recorder-status" data-recorder-status="${machine}" role="status" hidden></p></form>
      <h3>Programs and recordings</h3><div data-profile-recordings="${machine}"></div>
      </div></article>`;
    }).join('');
    this.root.innerHTML = `<div class="page-heading"><div><h1>Appliances</h1>
      <p class="muted">Choose an appliance to inspect its recordings, profiles and settings.</p></div>
      <button type="button" data-profile-command="entities">Load HA entities</button></div>
      <p data-profile-message role="status"></p>
      ${library.mode === 'demo' ? '<p class="notice">Demo library · no live appliance recording or commands.</p>' : ''}
      <datalist id="profile-power-entities"></datalist><datalist id="profile-ha-entities"></datalist>
      <div class="profile-machines">${machineForms}
      <article class="card appliance-card" data-appliance-card="mazak">
      <div class="appliance-heading"><span class="appliance-icon" aria-hidden="true">⚙</span><h2>Mazak</h2>
      <button type="button" data-appliance-toggle="mazak" aria-expanded="false">Expand</button></div>
      <p>Provisional flat average loads</p><p>${Object.entries(library.mazak).map(([key,value])=>`${escapeHTML(key)} · ${decimal(value,0)} W`).join(' / ')}</p>
      <div data-appliance-detail="mazak" hidden><form data-profile-form="mazak" data-revision="${library.revision}" class="profile-form">
      ${Object.entries(library.mazak).map(([mode, power]) => `<label>${mode[0].toUpperCase() + mode.slice(1)} (W)<input name="${mode}" type="number" min="0" max="100000" step="1" required value="${power}"></label>`).join('')}
      <button type="submit">Save Mazak averages</button></form><p class="muted">No learned cycle or assumed duration.</p></div></article>
      </div><section data-profile-review hidden></section>`;
    this.deadlinePicker=new ApplianceDeadline(this.root.querySelector('[data-managed-deadline]'),()=>this.previewReady(),this.signal);
    this.deadlinePicker.setContext(library.now,library.timezone);

  }

  expand(machine, force = false) {
    const next = !force && this.expanded === machine ? null : machine;
    this.expanded = next;
    for (const card of this.root.querySelectorAll('[data-appliance-card]')) {
      const open = card.dataset.applianceCard === next;
      card.classList.toggle('expanded',open);
      card.querySelector('[data-appliance-detail]').hidden = !open;
      const button = card.querySelector('[data-appliance-toggle]');
      button.setAttribute('aria-expanded',String(open));
      button.textContent = open ? 'Collapse' : 'Expand';
    }
    const review = this.root.querySelector('[data-profile-review]');
    if (next && this.reviewed?.machine === next) {
      const host = !this.reviewed.averaged && this.root.querySelector(`[data-recording-editor="${this.reviewed.id}"]`);
      (host || this.root.querySelector(`[data-appliance-detail="${next}"]`)).append(review);
      review.hidden = false;
    } else review.hidden = true;
  }

  programStorageKey() {
    const entity = this.library.bosch.config?.selected_program;
    return entity ? JSON.stringify(['energymanager-bosch-choice',this.library.mode,entity]) : null;
  }

  rememberProgram(program) {
    const key = this.programStorageKey();
    if (!key || typeof localStorage === 'undefined') return;
    try { localStorage.setItem(key,JSON.stringify({program,actual:this.actualProgram})); }
    catch (error) { if (error.name !== 'SecurityError' && error.name !== 'QuotaExceededError') throw error; }
  }

  restoreProgram(actual, options) {
    const key = this.programStorageKey();
    if (!key || typeof localStorage === 'undefined') return actual;
    try {
      const saved = JSON.parse(localStorage.getItem(key) || 'null');
      return saved?.actual === actual && options.includes(saved.program) ? saved.program : actual;
    } catch (error) {
      if (error instanceof SyntaxError || error.name === 'SecurityError') return actual;
      throw error;
    }
  }

  renderBosch() {
    const bosch = this.library.bosch, readings = bosch.readings;
    this.deadlinePicker?.setContext(this.library.now,this.library.timezone);
    const reading = key => readings[key]?.state ?? 'Unavailable';
    const state = this.root.querySelector('[data-bosch-status]');
    const history = (key, content, label) => historyReading(escapeHTML(content), [readings[key]?.entity_id],
      {native: this.interaction?.native, demo: this.library.mode === 'demo', label});
    const power = readings.meter?.power_w === undefined ? '— W' : decimal(readings.meter.power_w,0) + ' W';
    const text = `${history('operation',programLabel(reading('operation')),'Operation')} · ${history('meter',power,'Appliance power')} · ${history('progress',reading('progress')+(readings.progress?.unit || ''),'Progress')} · ${history('finish',reading('finish'),'Finish')}`;
    this.root.querySelector('[data-bosch-details]').innerHTML = [
      ['door','Door'],['remote_control','Remote control'],['remote_start','Remote start'],
      ['selected_program','Selected'],['active_program','Active']].map(([key,label])=>
        `${label}: ${history(key,reading(key),label)}`).join(' · ');
    state.innerHTML = bosch.enabled ? text : 'Map Bosch feedback and the dedicated power sensor.';
    state.title = bosch.at ? `Read ${new Date(bosch.at).toLocaleString('en-GB',{timeZone:this.timezone || 'Europe/Brussels'})}` : '';
    if (bosch.capture_error) state.innerHTML += ' · '+escapeHTML(bosch.capture_error);
    const feedback = this.root.querySelector('[data-bosch-command]');
    feedback.textContent = [bosch.control_error,bosch.command?.message].filter(Boolean).join(' · ');
    const select = this.root.querySelector('[data-bosch-program]');
    const options = readings.selected_program?.options || [];
    const actual = reading(reading('operation') === 'run' ? 'active_program' : 'selected_program');
    const previousChoice = select.value;
    const signature = JSON.stringify(options);
    if (signature !== this.programSignature) {
      select.innerHTML = options.map(option=>`<option value="${escapeHTML(option)}">${escapeHTML(programLabel(option))}</option>`).join('');
      this.programSignature = signature;
      select.value = options.includes(previousChoice) ? previousChoice : options.includes(actual) ? actual : options.find(item=>/eco/i.test(item)) || options[0] || '';
    }
    // A device-side change is authoritative; ordinary polls retain an unapplied UI choice.
    if (actual !== this.actualProgram && options.includes(actual)) select.value = actual;
    if (!this.choiceRestored && options.includes(actual)) {
      if (reading('operation') !== 'run') select.value = this.restoreProgram(actual,options);
      this.choiceRestored = true;
    }
    if (reading('operation') === 'run' && options.includes(actual)) select.value = actual;
    this.actualProgram = actual;
    select.disabled = !options.length || reading('operation') === 'run';
    const blocked = !!bosch.control_error || this.busy || bosch.command?.outcome === 'pending';
    const idle = ['ready','inactive','finished'].includes(reading('operation')) && reading('power') === 'on';
    const remote = reading('remote_control') === 'on';
    const canStart = idle && remote && ['off','closed'].includes(reading('door')) && reading('remote_start') === 'on' &&
      Number(readings.delay?.state ?? -1) === 0 && ['s','seconds'].includes(readings.delay?.unit) &&
      readings.meter?.power_w !== undefined && select.value === reading('selected_program');
    this.root.querySelector('[data-profile-form="bosch-select"] button[type="submit"]').disabled = blocked || !idle || !remote || !options.length;
    this.root.querySelector('[data-profile-command="bosch-start"]').disabled = blocked || !canStart || !options.length;
    this.root.querySelector('[data-profile-command="bosch-power"]').disabled = blocked || !remote || reading('power') !== 'off';
    this.root.querySelector('[data-dishwasher-arm]').hidden = bosch.enabled;
    const modifiers = this.root.querySelector('[data-bosch-modifiers]');
    const modifierMarkup = ['extra_dry','half_load','vario_speed'].map(key=>
      `<button type="button" data-profile-command="bosch-modifier" data-modifier="${key}" data-enabled="${reading(key) !== 'on'}" ${blocked || !idle || !remote || !['on','off'].includes(reading(key)) ? 'disabled' : ''}>
      ${escapeHTML(bosch.fields[key].label)}: ${escapeHTML(reading(key))}</button>`).join('');
    if (this.modifierMarkup !== modifierMarkup) { modifiers.innerHTML = modifierMarkup; this.modifierMarkup = modifierMarkup; }
    if(this.deadlinePicker)this.renderManaged();
  }

  async previewReady(){
    const generation=(this.readyGeneration||0)+1;this.readyGeneration=generation;
    this.readyPreview=null;this.renderManaged();
    const deadline=this.deadlinePicker?.value,program=this.root.querySelector('[data-bosch-program]').value;
    if(!deadline || !this.library.profiles[`dishwasher/${program}`])return;
    try{
      const preview=await this.api('profiles/run-preview','POST',{program,deadline});
      if(this.signal.aborted || generation!==this.readyGeneration)return;
      this.readyPreview=preview;this.renderManaged();
    }catch(error){if(generation===this.readyGeneration)this.message(error.message,true);}
  }

  renderManaged(){
    const managed=this.library.managed || {revision:1,run:null},run=managed.run;
    const queued=run?.phase==='queued',active=run && ['queued','starting','running','attention'].includes(run.phase);
    if(run && `${run.id}/${run.revision}`!==this.managedIdentity){
      this.managedIdentity=`${run.id}/${run.revision}`;this.deadlinePicker.setValue(run.deadline);
      this.readyPreview=null;
    }
    const program=this.root.querySelector('[data-bosch-program]').value;
    const known=!!this.library.profiles[`dishwasher/${program}`];
    const ready=this.root.querySelector('[data-profile-command="run-ready"]');
    ready.textContent=queued?'Update deadline':this.readyPreview?.asap?'Ready · start as soon as possible':'Ready';
    ready.disabled=this.busy || this.library.mode==='demo' || !known || !this.deadlinePicker.value || !this.readyPreview || active&&!queued;
    const cancel=this.root.querySelector('[data-profile-command="run-cancel"]');cancel.hidden=!active;cancel.disabled=this.busy || ['starting','running'].includes(run?.phase);
    const warning=this.root.querySelector('[data-managed-warning]');
    warning.textContent=(!known?'No usable reviewed profile. Use Start now and record. ': '')+(this.readyPreview?.warning ? `${this.readyPreview.warning} Earliest expected finish: ${this.managedTime(this.readyPreview.earliest_finish)}. `:'')+(managed.error || '');
    const panel=this.root.querySelector('[data-managed-state]');
    const conflict=run?.conflict;
    const choice=(key,label)=>conflict?.[key]?`<button type="button" data-profile-command="run-choose" data-choice="${key}" data-proposal="${escapeHTML(conflict.proposal_id)}">${escapeHTML(label)} · ${this.managedTime(conflict[key].estimated_finish)} · ${decimal(conflict[key].peak_kw*1000,0)} W · estimated bill €${decimal(conflict[key].predicted_bill_eur)}</button>`:'';
    const markup=run?`<p><strong>${escapeHTML(programLabel(run.phase))}</strong> · ${escapeHTML(programLabel(run.program))} · latest finish ${this.managedTime(run.deadline)}</p>
      <p>${run.planned_start?'Planned start: '+this.managedTime(run.planned_start):''}${run.estimated_finish?' · estimated finish: '+this.managedTime(run.estimated_finish):''}</p>
      ${run.blocked?`<p class="notice">${escapeHTML(run.blocked)}</p>`:''}
      ${conflict?`<p class="notice">This request needs a timing/peak choice. It remains queued. ${escapeHTML(managed.notification || '')}</p><div class="actions">${choice('later','Finish later within current allowance')}${choice('on_time','Approve the shown peak for an on-time finish')}</div><p>Edit the deadline above or cancel this queued run.</p>`:''}`:'';
    if(this.managedMarkup!==markup){panel.innerHTML=markup;this.managedMarkup=markup;}
  }

  managedTime(value){return value?escapeHTML(new Date(value).toLocaleString('en-GB',{timeZone:this.library.timezone || this.timezone || 'Europe/Brussels',timeZoneName:'shortOffset'})):'—';}

  renderRecorderStatus() {
    if (!this.library) return;
    const elapsed = (performance.now() - this.libraryObservedAt)/1000;
    for (const element of this.root.querySelectorAll('[data-recorder-status]')) {
      const feedback = recorderFeedback(this.library, element.dataset.recorderStatus, elapsed, !this.recorderStatusUnavailable);
      element.hidden = !feedback;
      if (feedback) {
        if (element.textContent !== feedback.text) element.textContent = feedback.text;
        element.dataset.state = feedback.state;
      }
    }
  }

  renderManualPrograms() {
    const programs = this.library.programs.washing_machine;
    const markup = Object.entries(programs).map(([id,name])=>`<option value="${escapeHTML(id)}">${escapeHTML(name)}</option>`).join('');
    for (const select of this.root.querySelectorAll('[data-profile-form="arm"][data-machine="washing_machine"] select[name="program"]')) {
      if (this.manualProgramMarkup === markup) continue;
      const previous = select.value;
      select.innerHTML = markup;
      if (Object.hasOwn(programs,previous)) select.value=previous;
    }
    this.manualProgramMarkup=markup;
    if (this.reviewed?.machine === 'washing_machine') {
      const heading=this.root.querySelector('[data-profile-review-title]');
      if (heading) heading.textContent=`${this.reviewed.averaged?'Average':'Review'} · Washing machine · ${programs[this.reviewed.program] ?? this.reviewed.program}`;
    }
  }

  closeReview() {
    clearTimeout(this.previewTimer);
    this.previewGeneration++;
    this.reviewGeneration = (this.reviewGeneration || 0)+1;
    this.chart?.close();
    const panel = this.root.querySelector('[data-profile-review]');
    panel.hidden = true;
    this.root.append(panel);
    this.reviewed = null;
    this.expandedRecording = null;
  }

  toggleProgram(button) {
    this.openPrograms ||= new Set();
    const key = button.dataset.machine+'/'+button.dataset.program;
    if (this.openPrograms.has(key)) {
      this.openPrograms.delete(key);
      if (this.reviewed?.machine+'/'+this.reviewed?.program === key && !this.reviewed?.averaged) this.closeReview();
    } else this.openPrograms.add(key);
    this.forceRecordings = true;
    this.renderRecordings();
    this.root.querySelector(`[data-profile-command="program"][data-machine="${button.dataset.machine}"][data-program="${CSS.escape(button.dataset.program)}"]`)?.focus();
  }

  renderRecordings() {
    const library = this.library;
    this.recordingMarkup ||= {};
    this.openPrograms ||= new Set();
    const review = this.root.querySelector('[data-profile-review]');
    for (const container of this.root.querySelectorAll('[data-profile-recordings]')) {
      const machine = container.dataset.profileRecordings;
      const rows = library.recordings.filter(row=>row.machine === machine);
      const markup = Object.entries(library.programs[machine]).map(([program,label])=>{
        const key = machine+'/'+program, profile = library.profiles[key];
        const recordings = rows.filter(row=>row.program === program), open = this.openPrograms.has(key);
        const average = profile ? `${profile.recording_count} included · ${decimal(profile.summary.mean_duration_seconds/60,1)} min mean · ${decimal(profile.summary.energy_kwh,3)} kWh mean` : 'No reviewed recordings included';
        return `<section class="profile-program"><div class="profile-program-heading">
          <button type="button" data-profile-command="program" data-machine="${machine}" data-program="${escapeHTML(program)}" aria-expanded="${open}">
          <strong>${open?'▾':'▸'} ${escapeHTML(machine==='washing_machine'?label:programLabel(label))}</strong><span>${recordings.length} recording${recordings.length===1?'':'s'} · ${escapeHTML(average)}</span></button>
          ${profile?`<button type="button" data-profile-command="average" data-machine="${machine}" data-program="${escapeHTML(program)}">Inspect average</button>`:''}</div>
          <div class="profile-program-recordings" ${open?'':'hidden'}>${recordings.length ? recordings.map(recording=>{
            const identity=escapeHTML(recording.id), expanded=this.expandedRecording===recording.id;
            const status=recording.status==='armed'?(recording.idle_seen?'Armed · waiting for start':'Armed · waiting for idle'):recording.status;
            const date=new Date(recording.armed_at).toLocaleString('en-GB',{timeZone:this.timezone || 'Europe/Brussels'});
            return `<section class="profile-recording" data-recording="${identity}"><div class="profile-recording-row">
              <button type="button" class="profile-recording-open" data-profile-command="review" data-id="${identity}" aria-expanded="${expanded}">${expanded?'▾':'▸'} ${escapeHTML(date)}</button>
              <span class="profile-recording-stats">${recording.summary?`${decimal(recording.summary.duration_seconds/60,1)} min · ${decimal(recording.summary.energy_kwh,3)} kWh`:`${recording.sample_count} samples`}</span>
              <span class="profile-recording-included">${recording.included?'✓ Included':recording.status==='saved'?'Not included':escapeHTML(programLabel(status))}</span>
              ${recording.status==='saved'?`<button type="button" data-profile-command="select" data-id="${identity}" data-included="${!recording.included}">${recording.included?'Remove from average':'Add to average'}</button>`:
                recording.status==='recording'?`<button type="button" data-profile-command="finish" data-id="${identity}">Finish recording now</button>`:`<button type="button" data-profile-command="discard" data-id="${identity}">Discard recording</button>`}
              </div><div class="profile-recording-details"><details><summary>Details</summary><p>${escapeHTML(recording.notes)}</p>
              <p>${escapeHTML(status)}${recording.source==='bosch'?' · automatic Bosch capture':''} · ${recording.sample_count} samples · ${escapeHTML(recording.entity_id)} · ${historyReading(recording.last_power_w===null?'— W':Math.round(recording.last_power_w)+' W',[recording.entity_id],{native:this.interaction?.native,demo:library.mode==='demo',label:'Recorded power'})}</p>
              ${recording.error || recording.interruption_reason?`<p class="notice">${escapeHTML(recording.error || recording.interruption_reason)}</p>`:''}
              ${recording.modifiers?`<p>Modifiers at start: ${escapeHTML(Object.entries(recording.modifiers).map(([name,value])=>name+': '+(value??'unavailable')).join(', '))}</p>`:''}</details>
              <details class="profile-delete"><summary>Delete recording…</summary><p>Permanently delete this physical recording, its samples and its contribution. This cannot be undone.</p>
              <button type="button" data-profile-command="delete" data-id="${identity}">Confirm permanent deletion</button></details></div>
              <div data-recording-editor="${identity}" ${expanded?'':'hidden'}></div></section>`;
          }).join(''):'<p class="muted">No cycles recorded yet.</p>'}</div></section>`;
      }).join('');
      const interacting = container.contains(this.root.getRootNode().activeElement) || container.querySelector('details[open]');
      if (this.recordingMarkup[machine] !== markup && (this.forceRecordings || !interacting)) {
        if (container.contains(review)) this.root.append(review); // Preserve the active form/chart across ordinary polls.
        container.innerHTML = markup;
        this.recordingMarkup[machine] = markup;
      }
    }
    if (this.reviewed && !this.reviewed.averaged) {
      const host = this.root.querySelector(`[data-recording-editor="${CSS.escape(this.reviewed.id)}"]`);
      if (host) { host.hidden=false;host.append(review); }
      else this.closeReview();
    }
    this.forceRecordings = false;
  }

  editProgram(action, form) {
    const select = form.elements.program;
    const input = form.elements.program_name;
    if (action === 'cancel') {
      this.programEdit = null;
      input.value = '';
      this.message('');
    } else {
      this.programEdit = {action, program:select.value, revision:this.library.revision};
      input.value = action === 'rename' ? this.library.programs.washing_machine[select.value] : '';
    }
    const editing = !!this.programEdit;
    form.querySelector('[data-program-selector]').hidden = editing;
    form.querySelector('[data-program-editor]').hidden = !editing;
    select.disabled = editing;
    input.disabled = !editing;
    form.querySelector('[data-profile-arm]').disabled = editing;
    if (editing) input.focus();
    else select.focus();
  }

  async saveProgram(form) {
    const {action, program, revision} = this.programEdit;
    const body = {revision, machine:'washing_machine', name:form.elements.program_name.value};
    if (action === 'rename') body.program = program;
    const result = await this.api(`profiles/program-${action}`, 'POST', body);
    this.library = result.library;
    this.advanceRevision(revision, this.library.revision);
    this.renderManualPrograms();
    form.elements.program.value = result.program.id;
    this.editProgram('cancel', form);
    this.forceRecordings = true;
    this.renderRecordings();
    this.message(action === 'create' ? 'Program added.' : 'Program name updated.');
  }

  async submit(form) {
    const values = Object.fromEntries(new FormData(form));
    const action = form.dataset.profileForm;
    if (action === 'arm' && form.dataset.machine === 'washing_machine' && this.programEdit) {
      await this.saveProgram(form);
    } else if (action === 'bosch-configure') {
      const revision = Number(form.dataset.revision);
      this.library = await this.api('profiles/bosch-configure','POST',{revision,entities:values});
      this.advanceRevision(revision,this.library.revision);
      this.message('Bosch mappings saved. Automatic collection begins when actual execution is observed.');
    } else if (action === 'bosch-select') {
      await this.api('profiles/bosch-command','POST',{command:'select',program:values.program});
      this.message('Selection submitted; awaiting appliance feedback. No start command was sent.');
    } else if (action === 'arm') {
      const recording = await this.api('profiles/arm', 'POST', {...values, machine: form.dataset.machine});
      this.library = {...this.library, now:recording.armed_at,
        recordings:[recording, ...this.library.recordings.filter(row=>row.id !== recording.id)]};
      this.libraryObservedAt = performance.now();
      this.recorderStatusUnavailable = false;
      this.renderRecorderStatus();
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
      this.message(action === 'revise' ? 'Selection updated for this recording. Original measurements and inclusion are retained.' : 'Reviewed cycle saved and added to the program average. Original recordings are retained.');
    }
    await this.refresh();
  }

  advanceRevision(previous, next) {
    if (next !== previous + 1) return;
    if (this.programEdit?.revision === previous) this.programEdit.revision = next;
    for (const form of this.root.querySelectorAll('form[data-revision]')) {
      if (Number(form.dataset.revision) === previous) form.dataset.revision = next;
    }
  }

  async command(button) {
    const command = button.dataset.profileCommand, id = button.dataset.id;
    if(command.startsWith('run-')){
      const managed=this.library.managed,program=this.root.querySelector('[data-bosch-program]').value;
      let action=command.slice(4),body={revision:managed.revision};
      if(action==='ready'){
        action=managed.run?.phase==='queued'?'edit':'ready';
        Object.assign(body,{program,deadline:this.deadlinePicker.value,accept_asap:this.readyPreview?.asap===true});
      }
      if(action==='choose')Object.assign(body,{choice:button.dataset.choice,proposal_id:button.dataset.proposal,approved:button.dataset.choice==='on_time'});
      await this.api(`profiles/run-${action}`,'POST',body);await this.refresh();
      if(action==='ready' || action==='edit')await this.previewReady();
      return;
    }
    if (command.startsWith('bosch-')) {
      const program = this.root.querySelector('[data-bosch-program]').value;
      const body = command === 'bosch-start' ? {command:'start',program} : command === 'bosch-power' ? {command:'power_on'} :
        {command:'modifier',modifier:button.dataset.modifier,enabled:button.dataset.enabled === 'true'};
      await this.api('profiles/bosch-command','POST',body);
      await this.refresh();
      this.message('Command submitted to HA. Actual execution is established by Bosch feedback.');
      return;
    }
    if (command === 'entities') {
      const result = await this.api('settings/entities');
      if (this.signal.aborted) return;
      this.root.querySelector('#profile-ha-entities').innerHTML = result.entities.map(entity=>`<option value="${escapeHTML(entity.entity_id)}">${escapeHTML(entity.name)} · ${escapeHTML(entity.state)}</option>`).join('');
      this.root.querySelector('#profile-power-entities').innerHTML = result.entities.filter(entity => entity.entity_id.startsWith('sensor.') && ['W', 'kW'].includes(entity.unit))
        .map(entity => `<option value="${escapeHTML(entity.entity_id)}">${escapeHTML(entity.name)} · ${escapeHTML(entity.state)} ${escapeHTML(entity.unit)}</option>`).join('');
      this.message('Power sensors loaded. Select a dedicated sensor for each machine.');
      return;
    }
    if (command === 'review') {
      if (this.expandedRecording===id && !this.reviewed?.averaged) { this.closeReview();this.forceRecordings=true;this.renderRecordings();return; }
      return this.review(id);
    }
    if (command === 'average') return this.reviewAverage(button.dataset.machine,button.dataset.program);
    if (command === 'preview') return this.previewSelection(button.closest('form'));
    const revision = this.library.revision;
    const result = await this.api(`profile-recordings/${id}/${command}`, 'POST', {revision,...(command === 'delete' ? {confirmed:true} : {}),...(command === 'select' ? {included:button.dataset.included !== 'false'} : {})});
    if (command === 'select' || command === 'delete') this.advanceRevision(revision, result.library_revision);
    if (command === 'finish') await this.review(id);
    if ((command === 'discard' || command === 'delete') && this.reviewed?.id===id && !this.reviewed?.averaged) this.closeReview();
    this.forceRecordings = true;
    await this.refresh();
    if ((command === 'select' || command === 'delete') && this.reviewed?.averaged) {
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
        this.reviewed?.id !== identity) return;
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
    this.closeReview();
    const generation=this.reviewGeneration;
    const profile = await this.api(`profiles/${machine}/${program}`);
    if (this.signal.aborted || generation!==this.reviewGeneration) return;
    this.reviewed = profile;
    this.expand?.(machine,true);
    clearTimeout(this.previewTimer);
    this.previewGeneration++;
    this.forceRecordings=true;this.renderRecordings();
    const panel = this.root.querySelector('[data-profile-review]');
    panel.hidden = false;
    panel.innerHTML = `<h2 data-profile-review-title>Average · ${machineName(machine)} · ${escapeHTML(this.library.programs[machine][program])}</h2>
      <p>${profile.recording_count} reviewed recording${profile.recording_count === 1 ? '' : 's'} ·
      ${escapeHTML(this.summaryText(profile.summary))}</p>
      <p class="muted">Starts are aligned without stretching time. Each complete cycle contributes zero after its selected end.
      Mean cycle duration: ${decimal(profile.summary.mean_duration_seconds/60,1)} min;
      graph extends to the longest cycle: ${decimal(profile.summary.duration_seconds/60,1)} min.</p>
      <div data-profile-graph></div>
      <p>${historyReading('Source history', (this.library.recordings || []).filter(r=>profile.recording_ids.includes(r.id)).map(r=>r.entity_id),
        {native:this.interaction?.native,demo:this.library.mode==='demo',label:'Average contributing sources'})}</p>
      <h3>Included recordings</h3><div class="actions profile-contributors">
      ${profile.recording_ids.map((identity,index) => `<span>Recording ${index+1}
      <button data-profile-command="review" data-id="${identity}">Inspect</button>
      <button data-profile-command="select" data-id="${identity}" data-included="false">Remove from average</button></span>`).join('')}
      </div>`;
    this.mountChart(profile,null,false);
    panel.scrollIntoView({block:'start'});
  }

  async review(id, revision = this.library.revision) {
    this.closeReview();
    const generation=this.reviewGeneration;
    const recording = await this.api(`profile-recordings/${id}`);
    if (this.signal.aborted || generation!==this.reviewGeneration) return;
    id=recording.id;
    this.reviewed = recording;
    this.expandedRecording=id;
    this.openPrograms ||= new Set();
    this.openPrograms.add(recording.machine+'/'+recording.program);
    this.expand?.(recording.machine,true);
    this.forceRecordings=true;this.renderRecordings();
    clearTimeout(this.previewTimer);
    this.previewGeneration++;
    const panel = this.root.querySelector('[data-profile-review]');
    const duration = recording.points.at(-1)?.seconds || 0;
    const selection = recording.summary || {start_seconds:0,
      end_seconds:recording.suggested_end_seconds ?? duration};
    const saved = recording.status === 'saved';
    const editable = (recording.status === 'review' || saved) && duration > 0;
    panel.hidden = false;
    panel.innerHTML = `<h2 data-profile-review-title>Review · ${machineName(recording.machine)} · ${escapeHTML(recording.machine==='washing_machine' ? (this.library.programs[recording.machine][recording.program] ?? recording.program) : programLabel(this.library.programs[recording.machine][recording.program] ?? recording.program))}</h2>
      <p>${escapeHTML(recording.notes)} · ${historyReading(escapeHTML(recording.entity_id || 'History'),[recording.entity_id],{native:this.interaction?.native,demo:this.library.mode==='demo',label:'Recording source'})} · ${escapeHTML(recording.status)}${recording.interruption_reason ? ' · ' + escapeHTML(recording.interruption_reason) : ''}</p>
      ${saved ? '<p class="notice">You can adjust this saved trim. Saving updates this recording in place, preserving raw measurements and its inclusion in the average.</p>' : ''}
      <div data-profile-graph></div>
      <p class="muted">Gaps are unknown; short measured peaks remain visible. Trim seconds are relative to the detected start.</p>
      ${recording.interrupted ? '<p class="error">Interrupted recording. Inspect it for diagnosis and record a complete cycle before saving a profile.</p>' : ''}
      ${editable ? `<form data-profile-trim data-profile-form="${saved ? 'revise' : 'accept'}" data-id="${id}" data-revision="${revision}" class="profile-form">
      <label>Start (seconds)<input name="start_seconds" type="number" min="0" max="${duration}" step="any" value="${selection.start_seconds}" required></label>
      <label>End (seconds)<input name="end_seconds" type="number" min="0" max="${duration}" step="any" value="${selection.end_seconds}" required></label>
      <button type="button" data-profile-command="preview">Preview selection</button><p data-profile-summary></p>
      <label class="profile-check"><input name="reviewed" type="checkbox" required>${saved ? 'I reviewed this selection as a complete cycle.' : 'I reviewed a complete cycle and want to include it in this program’s average.'}</label>
      <button type="submit">${saved ? 'Save revised trim' : 'Save and add to average'}</button></form>` : recording.summary ?
      `<p>${escapeHTML(this.summaryText(recording.summary))} · Selected ${selection.start_seconds}–${selection.end_seconds} seconds (shaded)</p>` :
      '<p>Finish the recording before saving a profile.</p>'}`;
    this.mountChart(recording,duration > 0 ? selection : null,editable);
    if (editable) this.syncTrim(panel.querySelector('form'));
    panel.scrollIntoView({block:'start'});
  }
}
