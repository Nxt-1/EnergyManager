import {localDateTime, localInstants} from './date-time.js';

export class DiagnosticsPage {
  constructor(root, api, signal, downloadUrl = path => `./api/${path}`) {
    this.root = root;
    this.api = api;
    this.downloadUrl = downloadUrl;
    this.visible = false;
    this.busy = false;
    this.initialized = false;
    root.innerHTML = `<article class="card"><h1>Diagnostics</h1><h2>Planning dataset</h2>
      <p>Datasets contain household operation data. Keep downloaded files private.</p>
      <p>Check stored history, select a period, then prepare one ZIP. Counts do not prove continuous coverage.
      Completed files remain available for 24 hours or until you remove them.</p>
      <button data-check>Check available history</button> <a data-coverage hidden>Download coverage</a>
      <p data-status role="status"></p><p data-included></p><p data-error class="error" role="alert"></p>
      <div data-inventory></div><form data-form hidden>
      <p>Installation timezone: <strong data-zone></strong>. End is exclusive.</p>
      <label>Start<input data-start type="datetime-local" required></label><select data-start-fold aria-label="Start clock occurrence" hidden></select>
      <label>End<input data-end type="datetime-local" required></label><select data-end-fold aria-label="End clock occurrence" hidden></select>
      <button type="button" data-all>All available history</button><p data-range></p>
      <button class="primary" data-prepare>Prepare dataset</button></form>
      <p><button data-cancel hidden>Cancel</button> <a data-download hidden>Download dataset</a>
      <button data-delete hidden>Remove export artifacts</button></p><div data-retained></div><div data-warnings></div></article>`;
    this.$ = name => root.querySelector(`[data-${name}]`);
    this.$('check').onclick = () => this.perform(() => api('diagnostics/coverage', 'POST', {}));
    this.$('form').onsubmit = event => {
      event.preventDefault();
      const range = this.range();
      if (range) this.perform(() => api('diagnostics/dataset', 'POST', range));
    };
    this.$('all').onclick = () => this.setRange(true);
    for (const name of ['start', 'end']) {
      this.$(name).oninput = () => { this.exactRange = null; this.resolve(); };
      this.$(`${name}-fold`).onchange = () => this.resolve();
    }
    this.$('cancel').onclick = () => this.perform(() => api(`diagnostics/${this.job.id}/cancel`, 'POST', {}));
    this.$('delete').onclick = () => this.perform(() => api(`diagnostics/${this.job.id}/delete`, 'POST', {}));
    this.timer = setInterval(() => { if (this.visible) this.poll(); }, 1500);
    signal.addEventListener('abort', () => clearInterval(this.timer), {once: true});
  }

  setVisible(visible) {
    if (visible && !this.visible) this.poll();
    this.visible = visible;
  }

  async poll() {
    if (this.busy) return;
    await this.perform(() => this.api('diagnostics'));
  }

  async perform(operation) {
    // Serialize mutations behind an in-flight status poll; never drop a human click.
    const next = (this.pending || Promise.resolve()).then(async () => {
      this.busy = true;
      try {
        const result = await operation();
        this.$('error').textContent = '';
        this.zone = result.timezone;
        this.job = result.job;
        this.artifacts = result.artifacts || [];
        this.render();
      } catch (error) {
        this.$('error').textContent = error.message;
      } finally {
        this.busy = false;
      }
    });
    this.pending = next;
    await next;
    if (this.pending === next) this.pending = null;
  }

  setRange(all = false) {
    const first = Date.parse(this.coverage.first), last = Date.parse(this.coverage.last) + 1;
    if (!Number.isFinite(first) || !Number.isFinite(last)) return;
    const start = all ? first : Math.max(first, last - 7 * 86400000);
    this.exactRange = {start: new Date(start).toISOString(), end: new Date(last).toISOString()};
    this.$('start').value = localDateTime(start, this.zone);
    this.$('end').value = localDateTime(last, this.zone);
    this.resolve();
  }

  range() {
    if (this.exactRange) return this.exactRange;
    const range = {};
    for (const name of ['start', 'end']) {
      const options = localInstants(this.$(name).value, this.zone);
      if (!options.length) return null;
      range[name] = options.length === 1 ? options[0] : this.$(`${name}-fold`).value;
      if (!range[name]) return null;
    }
    return Date.parse(range.start) < Date.parse(range.end) ? range : null;
  }

  resolve() {
    for (const name of ['start', 'end']) {
      const options = localInstants(this.$(name).value, this.zone);
      const select = this.$(`${name}-fold`), previous = select.value;
      select.hidden = options.length < 2;
      select.replaceChildren();
      if (options.length > 1) {
        select.add(new Option('Choose clock occurrence (DST)', ''));
        for (const value of options) select.add(new Option(new Date(value).toLocaleString('en-GB', {
          timeZone: this.zone, timeZoneName: 'longOffset'}), value));
        if (options.includes(previous)) select.value = previous;
      }
    }
    const range = this.range();
    this.$('prepare').disabled = !range || this.job?.state === 'running';
    this.$('range').textContent = range ?
      `${range.start} → ${range.end} · ${((Date.parse(range.end)-Date.parse(range.start))/3600000).toFixed(3)} hours` :
      'Select a start before end. Nonexistent local times are invalid; choose an occurrence for repeated DST times.';
  }

  link(name, member) {
    const anchor = this.$(name);
    anchor.href = this.downloadUrl(`diagnostics/${this.job.id}/download/${member}`);
    anchor.download = `energymanager-${member}.${member === 'dataset' ? 'zip' : 'json'}`;
  }

  render() {
    const job = this.job;
    const running = job?.state === 'running', ready = job?.state === 'ready';
    this.$('status').textContent = job ? `${job.stage}${running ? ` · ${job.records || 0} records scanned` : ''}${ready ? ` · ${job.bytes.toLocaleString()} bytes · expires ${job.expires_at}` : ''}` : 'Check history to begin.';
    this.$('check').disabled = !!running;
    this.$('cancel').hidden = !running;
    this.$('delete').hidden = !ready;
    this.$('coverage').hidden = !ready;
    this.$('download').hidden = !(ready && job.kind === 'dataset');
    this.$('included').textContent = ready && job.kind === 'dataset' ?
      `Dataset interval: ${job.start} → ${job.end}. ${Object.values(job.coverage?.omissions || {}).reduce((a,b) => a+b,0)} omissions/validation findings; review completeness details below.` : '';
    if (ready) {
      this.link('coverage', 'coverage');
      if (job.kind === 'dataset') this.link('download', 'dataset');
    }
    if (ready && job.coverage) {
      const changed = this.coverage?.capture.id !== job.coverage.capture.id;
      this.coverage = job.coverage;
      this.$('zone').textContent = this.zone;
      this.$('form').hidden = !this.coverage.first;
      this.$('inventory').textContent = this.coverage.first ?
        `Available: ${this.coverage.first} → ${this.coverage.last}. Database: ${this.coverage.database_bytes.toLocaleString()} bytes. Capture: ${this.coverage.capture.backup_completed_at}.` : 'No dated history is available.';
      if (changed) {
        const details = document.createElement('details'), summary = document.createElement('summary'), pre = document.createElement('pre');
        summary.textContent = 'Counts, daily coverage, observed gaps and omissions';
        pre.textContent = JSON.stringify({event_kinds: this.coverage.event_kinds,
          decision_dispositions: this.coverage.decision_dispositions, series: this.coverage.series,
          omissions: this.coverage.omissions, excluded_tables: this.coverage.excluded_tables}, null, 2);
        pre.style.whiteSpace = 'pre-wrap';
        details.append(summary, pre);
        this.$('warnings').replaceChildren(details);
        const note = document.createElement('p');
        note.textContent = this.coverage.limitations.join(' ');
        this.$('warnings').prepend(note);
      }
      if (!this.initialized) {
        if (job.kind === 'dataset' && job.start && job.end) {
          this.exactRange = {start: job.start, end: job.end};
          this.$('start').value = localDateTime(job.start, this.zone);
          this.$('end').value = localDateTime(job.end, this.zone);
        } else this.setRange();
        this.initialized = true;
      }
    }
    this.$('retained').replaceChildren();
    for (const artifact of this.artifacts || []) {
      if (artifact.id === job?.id) continue;
      const row = document.createElement('p'), link = document.createElement('a'), remove = document.createElement('button');
      const member = artifact.kind === 'dataset' ? 'dataset' : 'coverage';
      link.href = this.downloadUrl(`diagnostics/${artifact.id}/download/${member}`);
      link.textContent = `Earlier ${member} · ${artifact.bytes.toLocaleString()} bytes · expires ${artifact.expires_at}`;
      link.download = `energymanager-${member}.${member === 'dataset' ? 'zip' : 'json'}`;
      remove.textContent = 'Remove';
      remove.onclick = () => this.perform(() => this.api(`diagnostics/${artifact.id}/delete`, 'POST', {}));
      row.append(link, ' ', remove);
      this.$('retained').append(row);
    }
    this.resolve();
  }
}
