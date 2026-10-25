// Shared by the standalone UI and versioned HA card; installed loaders stay compatible.
export function requestError(error, path, method = 'GET') {
  const operation = `${method} ${path.split('?')[0]}`;
  const timedOut = error.name === 'TimeoutError' || error.name === 'AbortError';
  const reason = timedOut ? 'timed out after 15 seconds' : error instanceof TypeError ?
    'could not reach EnergyManager' : error.message || 'request failed';
  const interrupted = timedOut || error instanceof TypeError || error instanceof SyntaxError;
  const uncertain = method !== 'GET' && interrupted ?
    ' The action may have been applied; check its current state before retrying.' : '';
  const result = new Error(`${operation}: ${reason}.${uncertain}`, {cause: error});
  result.fields = error.fields;
  return result;
}

export class StatePoller {
  constructor(request) {
    this.request = request;
    this.state = null;
    this.failures = 0;
    this.retryAt = 0;
  }

  async poll(force = false) {
    if (!force && Date.now() < this.retryAt) return null;
    const query = new URLSearchParams({compact: '1'});
    if (this.state?.accepted?.id) query.set('plan_id', this.state.accepted.id);
    try {
      const next = await this.request(`state?${query}`);
      if (next.accepted_unchanged) {
        if (!this.state?.accepted || this.state.accepted.id !== next.accepted_plan_id)
          throw new Error('Dashboard plan cache is out of sync; reload this dashboard');
        next.accepted = this.state.accepted;
      }
      this.state = next;
      this.failures = this.retryAt = 0;
      return next;
    } catch (error) {
      this.failures++;
      this.retryAt = Date.now() + Math.min(30000, 2000 * 2 ** Math.min(this.failures - 1, 4));
      throw error;
    }
  }
}
