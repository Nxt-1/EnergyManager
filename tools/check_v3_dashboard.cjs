// Focused DOM-contract test; no browser or Home Assistant connection.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor() { this.children = []; this.dataset = {}; this.style = {}; this.value = ''; this.textContent = ''; }
  appendChild(child) { this.children.push(child); if (this.value === '' && child.value) this.value = child.value; }
  replaceChildren() { this.children = []; }
  remove() {}
}
class Element extends Node {
  set innerHTML(value) {
    this.html = value;
    this.nodes = Object.fromEntries(['[data-status]', '[data-requirement]', '[data-detail]', '[data-live]',
      'input', '[data-stages]', '[data-cmd]', 'ha-card'].map(key => [key, new Node()]));
  }
  querySelector(key) { return this.nodes[key] || null; }
}
global.HTMLElement = Element;
global.document = {createElement: () => new Node()};
const registered = new Map();
global.customElements = {get: key => registered.get(key), define: (key, value) => registered.set(key, value)};
const source = fs.readFileSync('energymanager-dashboard/energymanager-timeline-card.js', 'utf8');
vm.runInThisContext(source.slice(source.indexOf('// V3 evidence viewer:')));
(async () => {
  const Card = registered.get('energymanager-decision-details');
  assert.ok(Card);
  const card = new Card();
  card.setConfig({});
  card.hass = {states: {}};
  assert.match(card.querySelector('[data-status]').textContent, /No decision/);
  card.hass = {states: {'sensor.energy_manager_v3_decision': {attributes: {
    snapshot_id: 'a'.repeat(32), solver_status: 'feasible_time_limit',
    requirements: [{requirement_id: '<script>test</script>', hard: true, provenance: {formula: 'energy / efficiency'}}],
    stages: [{name: 'economics', status: 'Time limit reached', gap: .1}],
  }}}};
  assert.match(card.querySelector('[data-detail]').textContent, /energy \/ efficiency/);
  assert.ok(!card.html.includes('<script>'));
  const document = {snapshot_id: 'b'.repeat(32), disposition: 'accepted', snapshot: {frame: {requirements: []}},
    evaluation: {stages: [], plan: {intervals: [{scheduled_load_w: 1380, period_start_local: '2026-10-12T00:00:00Z'},
      {scheduled_load_w: 1380, period_start_local: '2026-10-12T00:15:00Z'}, {scheduled_load_w: 0}]}}};
  await card.querySelector('input').onchange({target: {files: [{size: 2000, text: async () => JSON.stringify(document)}]}});
  assert.match(card.querySelector('[data-status]').textContent, /bbbb/);
  const sessionPanel = card.querySelector('ha-card').children.at(-1);
  assert.match(sessionPanel.children.at(-1).textContent, /forbid_ev.*0 2/);
  const comparison = {snapshot_id: 'c'.repeat(32), delta: {objective_eur: 1},
    baseline: {stages: [{name: 'economics', bound: 2, gap: .1}]},
    alternative: {stages: [{name: 'economics', bound: 1, gap: .5}]},
    economic_confidence: {conclusion: 'feasible_incumbents_only'}};
  await card.querySelector('input').onchange({target: {files: [{size: 1000,
    text: async () => JSON.stringify(comparison)}]}});
  assert.match(card.querySelector('[data-stages]').textContent, /feasible_incumbents_only/);
  assert.match(card.querySelector('[data-stages]').textContent, /baseline_stages/);
  await card.querySelector('input').onchange({target: {files: [{size: 40 * 1024 * 1024}]}});
  assert.match(card.querySelector('[data-status]').textContent, /below 32 MiB/);
  console.log('V3 dashboard DOM contracts passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
