const activeStates = new Set(['requested', 'restarting', 'calculating', 'checking', 'waiting']);

function stageLabel(stage = '') {
  if (/continuity|steady_grid|operational_polish/.test(stage)) return 'Smoothing charging';
  if (/minimum_necessary/.test(stage)) return 'Checking energy';
  if (/exceptional|replacement|health_constrained/.test(stage)) return 'Checking solar';
  if (/normal_ceiling|peak_precharge/.test(stage)) return 'Optimizing energy';
  if (/required|permission/.test(stage)) return 'Finding a plan';
  if (/rolling_window/.test(stage)) return 'Refining plan';
  return 'Preparing';
}

export function planningActivityModel(activity = {}, now = Date.now()) {
  const busy = activeStates.has(activity.state);
  const finished = Date.parse(activity.finished_at);
  const recent = Number.isFinite(finished) && now - finished < 6000;
  let label = {requested: 'Starting', restarting: 'Restarting', checking: 'Validating',
    waiting: 'Waiting for inputs', ready: 'Plan updated', error: 'Calculation failed'}[activity.state];
  if (activity.state === 'calculating') label = stageLabel(activity.stage);
  const elapsed = Math.max(0, Math.floor(Number(activity.elapsed_seconds) || 0));
  return {busy, visible: busy || activity.state === 'error' || recent, label: label || '',
    elapsed: `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`,
    tone: activity.state === 'ready' ? 'ready' : activity.state === 'error' ? 'error' : 'busy'};
}

export class PlanningActivity {
  constructor(root, button, request, locked = () => false, extraButtons = () => []) {
    this.root = root;
    this.button = button;
    this.request = request;
    this.locked = locked;
    this.extraButtons = extraButtons;
    this.activity = {};
    this.receivedAt = Date.now();
    this.minimumRequestedAt = -Infinity;
    this.requesting = false;
    this.error = null;
    this.label = root.querySelector('[data-planning-label]');
    this.elapsed = root.querySelector('[data-planning-time]');
    this.track = root.querySelector('[role="progressbar"]');
    this.timer = setInterval(() => this.render(), 1000);
  }

  update(state) {
    const activity = state.planning_activity || {};
    // A state fetch started before the POST must not erase its acknowledgement.
    const requestedAt = Date.parse(activity.requested_at);
    if (this.minimumRequestedAt !== -Infinity &&
        (!Number.isFinite(requestedAt) || requestedAt < this.minimumRequestedAt)) return;
    if (this.error && activity.request_id !== this.activity.request_id) this.error = null;
    this.activity = activity;
    this.receivedAt = Date.now();
    this.render();
  }

  async recalculate() {
    if (this.requesting) return null;
    this.error = null;
    this.requesting = true;
    this.render(true);
    try {
      const result = await this.request();
      if (result.planning_activity) {
        this.activity = result.planning_activity;
        this.minimumRequestedAt = Date.parse(this.activity.requested_at);
        this.receivedAt = Date.now();
      }
      return result;
    } catch (error) {
      this.error = error.message || 'Recalculation request failed';
      throw error;
    } finally {
      this.requesting = false;
      this.render(true);
    }
  }

  render(force = false) {
    if (this.disposed || !force && this.locked()) return;
    const activity = {...this.activity};
    if (activeStates.has(activity.state) && activity.started_at)
      activity.elapsed_seconds = (Number(activity.elapsed_seconds) || 0) + (Date.now() - this.receivedAt) / 1000;
    const model = planningActivityModel(activity);
    const busy = this.requesting || model.busy;
    let label = model.label;
    if (this.requesting) label = model.busy ? 'Restarting' : 'Starting';
    if (this.error) label = 'Request failed';
    this.root.hidden = !this.error && !this.requesting && !model.visible;
    this.root.dataset.state = this.error ? 'error' : this.requesting ? 'busy' : model.tone;
    this.label.textContent = label;
    this.elapsed.textContent = busy && activity.started_at ? model.elapsed : '';
    this.root.title = this.error || (model.busy ? 'Calculation in progress; the bar does not represent a completion percentage.' : label);
    this.track.setAttribute('aria-valuetext', label);
    for (const button of [this.button, ...this.extraButtons()]) {
      button.disabled = this.requesting;
      button.classList.toggle('calculating', busy);
      button.classList.toggle('request-error', Boolean(this.error));
      button.setAttribute('aria-busy', String(busy));
      button.title = model.busy ? 'Cancel the current calculation and start again with current inputs' : 'Calculate a fresh plan';
      const action = model.busy ? 'Restart calculation' : 'Recalculate';
      button.querySelector('[data-recalculate-label]').textContent = this.requesting ? `${label}…` : action;
    }
  }

  dispose() {
    this.disposed = true;
    clearInterval(this.timer);
  }
}
