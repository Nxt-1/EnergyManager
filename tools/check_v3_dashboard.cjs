// DOM contracts plus optional real HTTP backend used by pytest integration.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor() { this.children = []; this.style = {}; this.value = ''; this.textContent = ''; this.disabled = false; }
  appendChild(child) { this.children.push(child); }
  replaceChildren() { this.children = []; this.textContent = ''; }
}
class Element extends Node {
  set innerHTML(value) {
    this.html = value;
    this.nodes = Object.fromEntries([...value.matchAll(/\b(data-[a-z-]+)(?=[\s>])/g)]
      .map(match => [`[${match[1]}]`, new Node()]));
    this.nodes['[data-kind]'].value = 'forbid_ev';
  }
  querySelector(key) { return this.nodes[key] || null; }
}
global.HTMLElement = Element;
global.document = {createElement: () => new Node()};
global.location = {protocol: 'https:'};
const registered = new Map();
global.customElements = {get: key => registered.get(key), define: (key, value) => registered.set(key, value)};
const source = fs.readFileSync('energymanager-dashboard/energymanager-timeline-card.js', 'utf8');
vm.runInThisContext(source.slice(source.indexOf('// V3 evidence viewer:')));
const realFetch = global.fetch;
const apiURL = process.env.V3_API_URL;
let submitted;
const fixture = {snapshot_id: 'a'.repeat(32), generated_at: '2026-10-14T00:00:00Z', disposition: 'accepted',
  evaluation: {quality: {physical_validation: 'passed', objective_eur: 2, stages: []}},
  intervals: [{period_start_local: '2026-10-14T00:00:00Z', scheduled_load_w: 1380}],
  previous_intervals: [], selections: [{kind: 'Requirement', label: '<script>unsafe</script>',
    record: {formula: 'energy / efficiency'}, start_index: 0, end_index: 1}], limitation: 'Timing causation not established'};
global.fetch = async (url, options) => {
  if (apiURL) return realFetch(apiURL + url.replace('/api/hassio_ingress/token', ''), {...options,
    headers: {...options.headers, 'X-Ingress-Path': '/api/hassio_ingress/token'}});
  let data;
  if (url.includes('/api/decisions?')) data = {decisions: [{snapshot_id: fixture.snapshot_id}], next_offset: null};
  else if (url.includes('/api/decisions/')) data = fixture;
  else if (options.method === 'POST') { submitted = JSON.parse(options.body); data = {job_id: 'job'}; }
  else data = {status: 'completed', result: {baseline: {adoption_ready: true}, alternative: {adoption_ready: true},
    economic_confidence: {conclusion: 'feasible_incumbents_only'}}};
  return {ok: true, status: 200, json: async () => data};
};
const allText = node => node.textContent + node.children.map(allText).join(' ');
(async () => {
  const Card = registered.get('energymanager-decision-details');
  const card = new Card(); card.setConfig({});
  card._hass = {callWS: async request => {
    if (request.endpoint === '/addons') return {addons: [{slug: 'local_energy_manager'}]};
    if (request.endpoint.endsWith('/info')) return {ingress_url: '/api/hassio_ingress/token'};
    assert.equal(request.endpoint, '/ingress/session'); return {session: 'authenticated-session'};
  }};
  card.build(); await card.history(0);
  assert.ok(card._decision, card.querySelector('[data-status]').textContent);
  assert.match(document.cookie, /SameSite=Strict;Secure/);
  assert.match(card.querySelector('[data-quality]').textContent, /passed/);
  assert.ok(card.querySelector('[data-selection]').children.length);
  assert.ok(!card.html.includes('<script>unsafe'));
  if (!apiURL) assert.match(allText(card.querySelector('[data-selected]')), /energy \/ efficiency/);
  await card.run();
  for (let i = 0; card._jobRunning && i < 80; i++) await new Promise(resolve => setTimeout(resolve, 100));
  card.disconnectedCallback();
  assert.match(card.querySelector('[data-job]').textContent, /completed/);
  assert.ok(card.querySelector('[data-result]').children.length);
  if (!apiURL) assert.equal(submitted.snapshot_id, fixture.snapshot_id);
  // Invalid windows never submit a diagnostic request.
  card.querySelector('[data-start]').value = '2'; card.querySelector('[data-end]').value = '1';
  await card.run(); assert.match(card.querySelector('[data-job]').textContent, /end after/);
  console.log('V3 GUI history → selection → counterfactual contracts passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
