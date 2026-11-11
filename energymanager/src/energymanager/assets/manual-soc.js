const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

export function manualConfirmationGoal(state, value) {
  const view = state.ev_manual;
  if (!view) return null;
  return (view.goals || [view.next_goal]).find(goal => goal && goal.target_percent > Number(value)) || view.next_goal || null;
}

function currentEstimate(state) {
  const reference = state.ev_manual?.reference;
  if (!reference?.enabled || !['active', 'completed'].includes(reference.status)) return '';
  const capacity = state.capabilities?.ev_capacity_kwh;
  const energy = state.observation?.ev_progress?.estimated_kwh;
  return capacity > 0 && Number.isFinite(energy) ? String(Math.round(energy / capacity * 1000) / 10) : '';
}

export function manualSoCMarkup(state, draft) {
  if (!state.ev_manual) return '';
  const enabled = !!state.ev_manual.reference?.enabled;
  const expanded = draft.intent === false ? false : draft.open || enabled;
  const value = draft.dirty || draft.busy || draft.failed ? draft.value : currentEstimate(state);
  return `<div class="ev-manual-control">
    <label class="ev-header-control"><span>Manual SoC</span><input type="checkbox" role="switch" aria-label="Manual SoC"
      data-ev-manual-toggle ${expanded ? 'checked' : ''} ${draft.busy ? 'disabled' : ''}></label>
    <label class="ev-manual-field" ${expanded ? '' : 'hidden'}><input aria-label="Manual SoC percentage"
      data-ev-manual-value type="number" inputmode="decimal" min="0" max="100" step="any" placeholder="SoC"
      value="${esc(value)}" ${draft.busy ? 'readonly' : ''} aria-describedby="ev-manual-message"> %</label>
    <span id="ev-manual-message" class="ev-manual-message ${draft.error ? 'error' : ''}"
      role="${draft.error ? 'alert' : 'status'}" ${draft.error || draft.busy ? '' : 'hidden'}>${esc(draft.error || (draft.busy ? 'Saving…' : ''))}</span>
  </div>`;
}

export class ManualSoC {
  constructor(root, submit, redraw) {
    this.root = root;
    this.submit = submit;
    this.redraw = redraw;
    this.open = false;
    this.value = '';
    this.dirty = false;
    this.failed = false;
    this.focused = false;
    this.error = null;
    this.busy = false;
    this.intent = null;
    root.addEventListener('focusin', event => {
      if (!event.target.matches('[data-ev-manual-value]')) return;
      this.focused = true;
      if (!this.dirty) this.editState = this.state;
    });
    root.addEventListener('input', event => {
      if (!event.target.matches('[data-ev-manual-value]') || this.busy) return;
      this.editState ||= this.state;
      this.value = event.target.value;
      this.dirty = true;
      this.failed = false;
      this.error = null;
      this.sync();
    });
    root.addEventListener('keydown', event => {
      if (event.key !== 'Enter' || !event.target.matches('[data-ev-manual-value]')) return;
      event.preventDefault();
      this.commit();
    });
    root.addEventListener('focusout', event => {
      if (!event.target.matches('[data-ev-manual-value]')) return;
      this.focused = false;
      if (event.relatedTarget?.matches('[data-ev-manual-toggle]')) {
        this.dirty = false;
        this.failed = false;
        return; // Turning the mode off must not first purchase a new reference.
      }
      this.commit();
    });
    root.addEventListener('change', async event => {
      if (!event.target.matches('[data-ev-manual-toggle]') || this.busy) return;
      this.open = event.target.checked;
      this.value = '';
      this.dirty = false;
      this.failed = false;
      this.editState = null;
      this.error = null;
      if (!this.open && this.state?.ev_manual?.reference?.enabled) await this.send({enabled:false});
      else this.redraw();
    });
  }

  update(state) {
    const previous = this.state?.ev_manual;
    this.state = state;
    if (previous?.reference?.enabled && !state.ev_manual?.reference?.enabled) {
      this.open = this.focused && this.dirty;
    }
    this.sync();
  }

  sync() {
    const element = this.root.querySelector?.('.ev-manual-control');
    if (!element || !this.state) return;
    const expanded = this.intent === false ? false : this.open || !!this.state.ev_manual?.reference?.enabled;
    const toggle = element.querySelector('[data-ev-manual-toggle]');
    toggle.checked = expanded;
    toggle.disabled = this.busy;
    element.querySelector('.ev-manual-field').hidden = !expanded;
    const input = element.querySelector('[data-ev-manual-value]');
    if (!this.dirty && !this.busy && !this.failed) input.value = currentEstimate(this.state);
    input.readOnly = this.busy;
    input.setAttribute('aria-invalid', this.error ? 'true' : 'false');
    const message = element.querySelector('.ev-manual-message');
    message.hidden = !this.error && !this.busy;
    message.textContent = this.error || (this.busy ? 'Saving…' : '');
    message.classList.toggle('error', !!this.error);
    message.setAttribute('role', this.error ? 'alert' : 'status');
  }

  async commit() {
    if (this.busy || !this.dirty) { this.sync(); return; }
    const state = this.editState;
    if (!state || state.ev_manual.context !== this.state.ev_manual.context) {
      this.dirty = false;
      this.failed = false;
      this.open = false;
      this.error = 'EV feedback or goal changed. Review current values and enter again.';
      this.editState = null;
      this.redraw();
      return;
    }
    const value = this.value.trim() === '' ? NaN : Number(this.value);
    const goal = manualConfirmationGoal(state, value);
    if (!Number.isFinite(value) || value < 0 || value > 100 || !goal) {
      this.error = 'Enter the actual current SoC between 0 and 100%.';
      this.sync();
      return;
    }
    // Claim the human edit before HTTP: Enter followed by blur commits once.
    // Received estimates remain display-only, including after goal completion.
    this.dirty = false;
    await this.send({enabled:true, confirmed:true, soc_percent:value, goal_id:goal.id,
      goal_revision:goal.revision, deadline:goal.deadline, target_kwh:goal.target_kwh,
      reference_context:state.ev_manual.context});
  }

  async send(body) {
    this.busy = true;
    this.intent = body.enabled;
    this.error = null;
    this.sync();
    try {
      await this.submit(body);
      this.value = '';
      this.open = false;
      this.failed = false;
      this.editState = null;
    } catch (error) {
      this.error = error.message.replace(/^(?:POST ev\/manual-soc:\s*)+/, '');
      // Show the failed draft, but another untouched blur must not retry it.
      this.dirty = false;
      this.failed = body.enabled;
    } finally {
      this.busy = false;
      this.intent = null;
      this.redraw();
    }
  }
}
