import {hasTextSelection} from './text-selection.js';

export const plotInsets = {left: 58, right: 16, top: 12, bottom: 32};

// Follow the displayed line, with no extrapolation or interpolation across a gap.
export function valueAt(points, at) {
  let low = 0, high = points.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (points[middle][0] <= at) low = middle + 1;
    else high = middle;
  }
  const before = points[low - 1], after = points[low];
  if (!before || before[1] === null) return null;
  if (before[0] === at) return {value: before[1], approximate: !!before[2]};
  if (!after || after[1] === null || after[0] <= before[0]) return null;
  const fraction = (at - before[0]) / (after[0] - before[0]);
  return {value: before[1] + (after[1] - before[1]) * fraction, approximate: true};
}

export function clipSeries(points, start, end) {
  const clipped = points.filter(point => point[0] >= start && point[0] <= end);
  for (const at of [start, end]) {
    if (clipped.some(point => point[0] === at)) continue;
    const reading = valueAt(points, at);
    if (reading) clipped.push([at, reading.value, reading.approximate]);
  }
  return clipped.sort((a, b) => a[0] - b[0]);
}

export class GraphCursor {
  constructor(root, formatTime, colors, signal, pan = null) {
    this.root = root;
    this.formatTime = formatTime;
    this.colors = colors;
    this.models = {};
    this.at = null;
    this.active = null;
    this.pinned = false;
    this.pan = pan;
    this.gesture = null;
    this.panFrame = null;
    for (const name of ['power', 'soc']) {
      const plot = root.querySelector(`#${name}`);
      plot.tabIndex = 0;
      plot.setAttribute('role', 'group');
      plot.setAttribute('aria-label', `${name === 'power' ? 'Power' : 'Battery state of charge'} graph. Use left/right arrows to inspect values; Escape clears the cursor.`);
      plot.addEventListener('pointermove', event => {
        if (this.movePan(event)) return;
        if (hasTextSelection(root) || event.target.closest('.cursor-values')) return;
        if (!this.pinned || event.buttons || event.pointerType === 'touch') this.point(name, event);
      }, {signal});
      plot.addEventListener('pointerdown', event => {
        if (event.button !== 0 || event.target.closest('.cursor-values') || hasTextSelection(root)) return;
        this.beginPan(name, plot, event);
        this.pinned = true;
        plot.focus({preventScroll: true});
        this.point(name, event);
      }, {signal});
      for (const type of ['pointerup', 'pointercancel', 'lostpointercapture'])
        plot.addEventListener(type, event => this.finishPan(event), {signal});
      plot.addEventListener('pointerleave', () => {
        if (hasTextSelection(root)) return;
        if (!this.pinned) { this.at = null; this.draw(); }
      }, {signal});
      plot.addEventListener('keydown', event => {
        const model = this.models[name];
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        if (!model || !['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Escape'].includes(event.key)) return;
        event.preventDefault();
        if (event.key === 'Escape') {
          this.at = null;
          this.pinned = false;
        } else {
          const step = event.shiftKey ? 60000 : (model.end - model.start) / 100;
          const base = this.at ?? Math.max(model.start, Math.min(model.end, model.now));
          this.at = event.key === 'Home' ? model.start : event.key === 'End' ? model.end :
            Math.max(model.start, Math.min(model.end, base + (event.key === 'ArrowLeft' ? -step : step)));
          this.active = name;
          this.pinned = true;
        }
        this.draw(true);
      }, {signal});
    }
    signal.addEventListener('abort', () => this.clearPan(), {once: true});
  }

  beginPan(name, plot, event) {
    const model = this.models[name];
    if (this.gesture || event.pointerType !== 'mouse' || !this.pan?.enabled() || !model) return;
    const box = plot.querySelector('svg')?.getBoundingClientRect();
    if (!box?.width) return;
    const width = box.width * (model.width - plotInsets.left - plotInsets.right) / model.width;
    this.gesture = {plot, id: event.pointerId, x: event.clientX, y: event.clientY,
      start: model.start, end: model.end, width, dragging: false, vertical: false, range: null};
    plot.setPointerCapture(event.pointerId);
    event.preventDefault();
  }

  movePan(event) {
    const gesture = this.gesture;
    if (!gesture || gesture.id !== event.pointerId) return false;
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    if (!gesture.dragging) {
      if (Math.abs(dy) > 6 && Math.abs(dy) > Math.abs(dx)) gesture.vertical = true;
      if (gesture.vertical || Math.abs(dx) <= 6) return true;
      gesture.dragging = true;
      gesture.plot.classList.add('graph-panning');
      this.at = null;
      this.pinned = false;
      this.draw();
    }
    // Use the initial range and horizontal displacement, never the freshly redrawn model.
    const shift = -dx / gesture.width * (gesture.end - gesture.start);
    gesture.range = [gesture.start + shift, gesture.end + shift];
    if (this.panFrame === null) this.panFrame = requestAnimationFrame(() => {
      this.panFrame = null;
      this.pan.changed(gesture.range, false);
    });
    return true;
  }

  finishPan(event) {
    const gesture = this.gesture;
    if (!gesture || gesture.id !== event.pointerId) return;
    if (gesture.dragging && event.type === 'pointerup') this.movePan(event);
    const range = gesture.range;
    this.clearPan();
    if (range) this.pan.changed(range, true);
  }

  clearPan() {
    if (this.panFrame !== null) cancelAnimationFrame(this.panFrame);
    this.panFrame = null;
    const gesture = this.gesture;
    this.gesture = null;
    if (!gesture) return;
    gesture.plot.classList.remove('graph-panning');
    if (gesture.plot.hasPointerCapture(gesture.id)) gesture.plot.releasePointerCapture(gesture.id);
  }

  point(name, event) {
    const model = this.models[name];
    const svg = this.root.querySelector(`#${name} svg`);
    if (!model || !svg) return;
    const box = svg.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width * model.width;
    const fraction = Math.max(0, Math.min(1, (x - plotInsets.left) /
      (model.width - plotInsets.left - plotInsets.right)));
    this.at = model.start + fraction * (model.end - model.start);
    this.active = name;
    this.draw();
  }

  update(models) {
    this.models = models;
    for (const name of ['power', 'soc']) {
      const plot = this.root.querySelector(`#${name}`), enabled = !!this.pan?.enabled();
      plot.classList.toggle('graph-pannable', enabled);
      plot.setAttribute('aria-label', `${name === 'power' ? 'Power' : 'Battery state of charge'} graph. ${enabled ? 'Drag left or right to scroll in time. ' : ''}Use left/right arrows to inspect values; Escape clears the cursor.`);
    }
    const model = models.power;
    if (this.at !== null && (this.at < model.start || this.at > model.end)) {
      this.at = null;
      this.pinned = false;
    }
    this.draw();
  }

  draw(announce = false) {
    for (const [name, model] of Object.entries(this.models)) {
      const plot = this.root.querySelector(`#${name}`);
      const overlay = plot.querySelector('.cursor-overlay');
      const tooltip = plot.querySelector('.cursor-values');
      if (!overlay || !tooltip) continue;
      overlay.replaceChildren();
      tooltip.hidden = this.at === null || this.active !== name;
      if (this.at === null) continue;
      const {left, right, top, bottom} = plotInsets;
      const x = left + (this.at - model.start) / (model.end - model.start) * (model.width - left - right);
      const y = value => model.height - bottom - (value - model.low) /
        (model.high - model.low) * (model.height - top - bottom);
      const svg = (tag, attributes) => {
        const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
        for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
        overlay.append(element);
      };
      svg('line', {x1: x, x2: x, y1: top, y2: model.height - bottom, class: 'cursor-line'});
      const table = document.createElement('table');
      const heading = table.createTHead().insertRow();
      for (const label of ['', 'Actual', 'Planned']) {
        const cell = document.createElement('th'); cell.textContent = label; heading.append(cell);
      }
      for (const series of model.series) {
        const row = table.insertRow();
        const label = row.insertCell();
        label.textContent = series.name === 'ev' || series.name === 'ess' ? series.name.toUpperCase() :
          series.name[0].toUpperCase() + series.name.slice(1);
        label.style.color = this.colors[series.name];
        for (const kind of ['observed', 'planned']) {
          const reading = valueAt(series[kind], this.at);
          row.insertCell().textContent = reading ? `${reading.approximate ? '≈' : ''}${
            reading.value.toFixed(name === 'soc' ? 1 : 0)} ${name === 'soc' ? '%' : 'W'}` : '—';
          if (reading) svg('circle', {cx: x, cy: y(reading.value), r: 3.5,
            fill: kind === 'observed' ? this.colors[series.name] : 'var(--surface)',
            stroke: this.colors[series.name], 'stroke-width': 1.5});
        }
      }
      tooltip.replaceChildren();
      tooltip.title = 'Values follow the plotted lines. ≈ indicates interpolation; — means no value in this period.';
      const time = document.createElement('strong');
      time.textContent = this.formatTime(this.at);
      tooltip.append(time, table);
      tooltip.setAttribute('aria-live', announce ? 'polite' : 'off');
      tooltip.style.left = `${Math.max(0, Math.min(model.width - tooltip.offsetWidth,
        x > model.width / 2 ? x - tooltip.offsetWidth - 12 : x + 12))}px`;
    }
  }
}
