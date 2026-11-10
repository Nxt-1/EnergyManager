const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

export function manualConfirmationGoal(state, value) {
  const view = state.ev_manual;
  if (!view) return null;
  const entered = String(value ?? '').trim();
  if (entered === '') return view.next_goal;
  const soc = Number(entered);
  return (view.goals || [view.next_goal]).find(goal => goal && goal.target_percent > soc) || view.next_goal || null;
}

export function manualSoCMarkup(state, draft) {
  const view = state.ev_manual;
  if (!view) return '';
  const reference = view.reference;
  const enabled = !!reference?.enabled;
  const expanded = draft.intent === false ? false : draft.open || enabled;
  const goal = manualConfirmationGoal(state, draft.value);
  const age = Math.floor((view.reference_age_seconds || 0) / 60);
  const ageText = age < 60 ? `${age} min` : `${Math.floor(age / 60)} h ${age % 60} min`;
  const stamp = value => new Date(value).toLocaleString('en-GB', {
    timeZone: state.policy.timezone, day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit'
  });
  const status = {active:'Confirmed goal only', completed:'Confirmed charge complete · estimated',
    goal_changed:'Goal changed · confirm again', reference_required:'New reference needed',
    unplugged:'Reference invalid after unplugging', expired:'Confirmed goal ended', recovered:'Vehicle feedback restored'};
  return `<section class="ev-manual" aria-label="Manual state of charge">
    ${state.observation?.ev_progress?.feedback_incident ? '<p role="status"><strong>Vehicle feedback needs attention</strong></p>' : ''}
    <label class="hardware-switch"><input type="checkbox" role="switch" data-ev-manual-toggle
      ${expanded ? 'checked' : ''} ${draft.busy ? 'disabled' : ''}><span class="switch-track" aria-hidden="true"></span>Manual SoC</label>
    ${enabled && draft.intent !== false ? `<p class="subtle" data-manual-reference>Entered ${Number(reference.soc_percent).toFixed(1)}% · ${esc(ageText)} ago · ${esc(status[reference.status] || reference.status)}</p>` : ''}
    ${draft.busy && draft.intent === false ? '<p role="status">Turning manual mode off…</p>' : ''}
    ${expanded && !enabled ? '<p class="subtle">Not active · enter a reference and confirm.</p>' : ''}
    ${expanded ? `<div class="ev-manual-entry">
      <label>Actual current SoC <span class="ev-manual-value"><input data-ev-manual-value type="number" inputmode="decimal" min="0" max="100" step="any" value="${esc(draft.value)}" ${draft.busy ? 'disabled' : ''}> %</span></label>
      <p data-manual-goal>${goal ? `${esc(goal.title)} · ${Number(goal.target_percent).toFixed(1)}% · ${esc(stamp(goal.deadline))}` : 'No future charging goal available.'}</p>
      <button type="button" data-ev-manual-confirm ${draft.busy || !goal ? 'disabled' : ''}>${draft.busy ? 'Confirming…' : enabled ? 'Confirm new reference' : 'Confirm reference & goal'}</button>
      ${!enabled ? '<button type="button" class="secondary" data-ev-manual-cancel>Cancel</button>' : ''}
    </div>` : ''}
    ${view.refresh ? '<p role="status">Another charge needs a new reference. Extra delivery remains paused.</p>' : ''}
    ${draft.error ? `<p class="error" role="alert">${esc(draft.error)}</p>` : ''}
  </section>`;
}

export class ManualSoC {
  constructor(root, submit, redraw) {
    this.open = false;
    this.value = '';
    this.error = null;
    this.busy = false;
    this.intent = null;
    root.addEventListener('input', event => {
      if (event.target.matches('[data-ev-manual-value]')) {
        this.value = event.target.value;
        redraw();
      }
    });
    root.addEventListener('change', async event => {
      if (!event.target.matches('[data-ev-manual-toggle]') || this.busy) return;
      this.open = event.target.checked;
      this.error = null;
      if (!this.open && this.state?.ev_manual?.reference?.enabled) await this.send({enabled:false}, submit, redraw);
      else redraw();
    });
    root.addEventListener('click', async event => {
      if (event.target.closest('[data-ev-manual-cancel]')) {
        this.open = false;
        this.value = '';
        this.error = null;
        redraw();
      }
      if (!event.target.closest('[data-ev-manual-confirm]') || this.busy) return;
      const goal = manualConfirmationGoal(this.state || {}, this.value);
      const value = this.value.trim() === '' ? NaN : Number(this.value);
      if (!Number.isFinite(value) || value < 0 || value > 100 || !goal) {
        this.error = 'Enter the actual current SoC between 0 and 100%.';
        redraw();
        return;
      }
      await this.send({enabled:true, confirmed:true, soc_percent:value, goal_id:goal.id,
        goal_revision:goal.revision, deadline:goal.deadline, target_kwh:goal.target_kwh}, submit, redraw);
    });
  }

  async send(body, submit, redraw) {
    this.busy = true;
    this.intent = body.enabled;
    this.error = null;
    redraw();
    try {
      await submit(body);
      this.value = '';
      this.open = false;
    } catch (error) {
      this.error = error.message.replace(/^(?:POST ev\/manual-soc:\s*)+/, '');
    } finally {
      this.busy = false;
      this.intent = null;
      redraw();
    }
  }
}
