import {GraphCursor, plotInsets} from './graph-cursor.js';

const geometry = {width:800, height:250, ...plotInsets};

export function profileRange(range, duration) {
  const maximum = Math.max(.001, duration);
  const width = Math.max(Math.min(1, maximum), Math.min(maximum, range[1] - range[0]));
  const start = Math.max(0, Math.min(maximum - width, range[0]));
  return [start, start + width];
}

export function trimBoundary(selection, boundary, seconds, duration) {
  const minimum = boundary === 'start' ? 0 : selection.start_seconds + .001;
  const maximum = boundary === 'end' ? duration : selection.end_seconds - .001;
  return {...selection, [boundary + '_seconds']: Math.max(minimum, Math.min(maximum, seconds))};
}

// Step duplicates make the shared cursor follow measured sample holds, never a ramp.
export function profileSeries(points, maximumGap = 15) {
  const result = [];
  let previous = null;
  for (const point of points) {
    const value = Number.isFinite(point.power_w) ? point.power_w : null;
    if (previous && value !== null && previous.power_w !== null &&
        point.seconds - previous.seconds <= maximumGap)
      result.push([point.seconds * 1000, previous.power_w]);
    else if (previous) result.push([point.seconds * 1000, null]);
    result.push([point.seconds * 1000, value]);
    previous = {...point, power_w:value};
  }
  return result;
}

export function profileGraph(points, maximumGap = 15, selection = null, range = null, editable = false, averaged = false) {
  const {width, height, left, right, top, bottom} = geometry;
  const duration = Math.max(.001, points.at(-1)?.seconds || 1);
  const [start, end] = range || [0, duration];
  const peak = points.reduce((maximum, point) => Math.max(maximum,point.power_w || 0),1);
  const x = seconds => left + (seconds - start) / (end - start) * (width - left - right);
  const y = value => height - bottom - value / peak * (height - top - bottom);
  let path = '', previous = null;
  for (const point of points) {
    if (point.power_w === null) { previous = null; continue; }
    const position = x(point.seconds).toFixed(2) + ',' + y(point.power_w).toFixed(2);
    if (!previous || point.seconds - previous.seconds > maximumGap) path += 'M' + position;
    else path += 'H' + x(point.seconds).toFixed(2) + 'V' + y(point.power_w).toFixed(2);
    previous = point;
  }
  const shade = selection ? `<rect data-profile-shade x="${x(selection.start_seconds)}" y="${top}"
    width="${x(selection.end_seconds)-x(selection.start_seconds)}" height="${height-top-bottom}" fill="#007ac2" opacity="0.14"/>` : '';
  const boundaries = ['start','end'];
  const handles = selection ? boundaries.map(boundary => `<g data-trim-boundary="${boundary}"
    transform="translate(${x(selection[boundary+'_seconds'])},0)" ${editable ? 'data-trim-editable' : ''} aria-hidden="true">
    <line x1="0" x2="0" y1="${top}" y2="${height-bottom}"/>
    ${editable ? `<line class="trim-hit" x1="0" x2="0" y1="${top}" y2="${height-bottom}"/>` : ''}
    </g>`).join('') : '';
  const grips = selection && editable ? boundaries.map(boundary => `<button type="button"
    class="profile-trim-handle" data-trim-handle="${boundary}" role="slider"
    aria-label="${boundary === 'start' ? 'Selection start' : 'Selection end'}"
    aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="${duration}"
    aria-valuenow="${selection[boundary+'_seconds']}">
    <span aria-hidden="true">${boundary === 'start' ? 'Start' : 'End'}</span><span aria-hidden="true">↔</span>
    </button>`).join('') : '';
  const ticks = Array.from({length:5}, (_, index) => {
    const seconds = start + (end-start) * index / 4;
    const label = end-start < 120 ? seconds.toFixed(1) + ' s' : (seconds/60).toFixed(1) + ' min';
    return `<text x="${x(seconds)}" y="${height-8}" text-anchor="${index===0?'start':index===4?'end':'middle'}">${label}</text>`;
  }).join('');
  return `<svg viewBox="0 0 ${width} ${height}" role="img"
    aria-label="${averaged ? 'Mean profile' : 'Recorded power'} in watts against elapsed time; missing readings leave gaps">
    <defs><clipPath id="profile-power-clip"><rect x="${left}" y="${top}" width="${width-left-right}" height="${height-top-bottom}"/></clipPath></defs>
    <g clip-path="url(#profile-power-clip)">${shade}
    <path d="${path}" fill="none" stroke="#007ac2" stroke-width="1.2"/></g>
    <path d="M${left},${top}V${height-bottom}H${width-right}" fill="none" stroke="currentColor" opacity="0.3"/>
    <text x="3" y="22">${Math.round(peak)} W</text>${ticks}
    <g data-trim-overlay>${handles}</g><g class="cursor-overlay"></g></svg>${grips}`;
}

export class ProfileChart {
  constructor(root, recording, selection, editable, signal, changed) {
    this.root = root;
    this.recording = recording;
    this.points = recording.points;
    this.duration = Math.max(.001, this.points.at(-1)?.seconds || 1);
    this.range = [0, this.duration];
    this.selection = selection;
    this.editable = editable;
    this.changed = changed;
    this.controller = new AbortController();
    this.parentSignal = signal;
    this.parentAbort = () => this.close();
    signal.addEventListener('abort',this.parentAbort,{once:true});
    const localSignal = this.controller.signal;
    root.innerHTML = `<div class="profile-chart-actions">
      <button type="button" data-chart-action="in" aria-label="Zoom in recording">＋</button>
      <button type="button" data-chart-action="out" aria-label="Zoom out recording">−</button>
      <button type="button" data-chart-action="all">Full recording</button>
      ${selection ? '<button type="button" data-chart-action="selection">Show selection</button>' : ''}
      </div><div class="plot profile-plot" id="profile-power"></div>
      <p class="muted">Drag the graph to pan; wheel or pinch to zoom. Tap or use arrow keys for power and timestamp.
      ${editable ? 'Drag the coloured start/end handles to trim; arrow keys move a focused handle.' : ''}</p>`;
    this.plot = root.querySelector('.profile-plot');
    // Capture handle gestures before the shared cursor can interpret them as graph panning.
    this.plot.addEventListener('pointerdown', event => this.beginTrim(event), {capture:true,signal:localSignal});
    this.plot.addEventListener('pointermove', event => this.moveTrim(event), {capture:true,signal:localSignal});
    for (const type of ['pointerup','pointercancel','lostpointercapture'])
      this.plot.addEventListener(type, event => this.endTrim(event), {capture:true,signal:localSignal});
    this.plot.addEventListener('keydown', event => this.keyTrim(event), {capture:true,signal:localSignal});
    this.plot.addEventListener('wheel', event => {
      if (this.drag) { event.preventDefault(); event.stopImmediatePropagation(); }
    }, {capture:true,passive:false,signal:localSignal});
    root.addEventListener('click', event => {
      const action = event.target.closest('[data-chart-action]')?.dataset.chartAction;
      if (!action) return;
      if (action === 'all') this.range = [0,this.duration];
      else if (action === 'selection') this.range = [this.selection.start_seconds,this.selection.end_seconds];
      else {
        const center = (this.range[0]+this.range[1])/2;
        const half = (this.range[1]-this.range[0]) * (action === 'in' ? .25 : 1);
        this.range = [center-half,center+half];
      }
      this.range = profileRange(this.range,this.duration);
      this.render();
    }, {signal:localSignal});
    this.cursor = new GraphCursor(root, at => {
      const elapsed = (at-this.origin)/1000;
      const timestamp = recording.started_at ? new Date(at).toLocaleString('en-GB', {
        timeZone:recording.timezone || 'Europe/Brussels',day:'2-digit',month:'short',
        hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'shortOffset'}) : 'Average profile';
      return timestamp + ' · ' + elapsed.toFixed(1) + ' s';
    }, {power:'#007ac2'},localSignal,{
      enabled:() => true,
      limits:() => ({minimum:Math.min(1000,this.duration*1000),maximum:this.duration*1000}),
      changed:range => { this.range = profileRange(range.map(at => (at-this.origin)/1000),this.duration); this.render(); }
    }, ['profile-power']);
    this.render();
  }

  render() {
    this.origin = this.recording.started_at ? Date.parse(this.recording.started_at) : 0;
    this.plot.innerHTML = profileGraph(this.points,this.recording.maximum_gap_seconds ?? 15,
      this.selection,this.range,this.editable,this.recording.averaged) + '<div class="cursor-values" hidden></div>';
    const high = this.points.reduce((maximum, point) => Math.max(maximum,point.power_w || 0),1);
    this.cursor.update({'profile-power':{
      start:this.origin+this.range[0]*1000,end:this.origin+this.range[1]*1000,
      width:geometry.width,height:geometry.height,low:0,high,now:this.origin,
      columns:[['observed',this.recording.averaged ? 'Mean power' : 'Recorded']],
      series:[{name:'power',step:true,observed:profileSeries(this.points,this.recording.maximum_gap_seconds ?? 15)
        .map(point => [point[0]+this.origin,...point.slice(1)]),planned:[]}]
    }});
    this.updateHandles();
  }

  setSelection(selection) {
    this.selection = selection;
    this.updateHandles();
  }

  updateHandles() {
    if (!this.selection) return;
    const {width,left,right} = geometry;
    const x = seconds => left+(seconds-this.range[0])/(this.range[1]-this.range[0])*(width-left-right);
    const shade = this.plot.querySelector('[data-profile-shade]');
    shade?.setAttribute('x',x(this.selection.start_seconds));
    shade?.setAttribute('width',x(this.selection.end_seconds)-x(this.selection.start_seconds));
    for (const boundary of ['start','end']) {
      const line = this.plot.querySelector('[data-trim-boundary="'+boundary+'"]');
      const handle = this.plot.querySelector('[data-trim-handle="'+boundary+'"]');
      const seconds = this.selection[boundary+'_seconds'], position = x(seconds);
      const outside = position < left-1e-6 || position > width-right+1e-6;
      line.style.display = outside ? 'none' : '';
      line.setAttribute('transform','translate('+position+',0)');
      if (!handle) continue;
      handle.style.display = outside ? 'none' : '';
      handle.style.left = (position/width*100)+'%';
      handle.setAttribute('aria-valuenow',seconds);
      handle.setAttribute('aria-valuetext',seconds.toFixed(3)+' seconds');
      handle.setAttribute('aria-valuemin',boundary === 'start' ? 0 : this.selection.start_seconds+.001);
      handle.setAttribute('aria-valuemax',boundary === 'end' ? this.duration : this.selection.end_seconds-.001);
      handle.title = 'Drag '+boundary+' · '+seconds.toFixed(3)+' seconds';
    }
  }

  trimTarget(target) {
    const element = target.closest('[data-trim-handle],[data-trim-boundary]');
    return element?.dataset.trimHandle || element?.dataset.trimBoundary;
  }

  beginTrim(event) {
    if (this.drag) { event.preventDefault(); event.stopImmediatePropagation(); return; }
    const boundary = this.trimTarget(event.target);
    if (!this.editable || !boundary || event.button !== 0) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    this.cursor.cancelNavigation();
    this.cursor.at = null;
    this.cursor.pinned = false;
    this.cursor.draw();
    this.drag = {boundary,id:event.pointerId};
    this.plot.setPointerCapture(event.pointerId);
    this.plot.querySelector('[data-trim-handle="'+boundary+'"]').focus({preventScroll:true});
    this.moveTrim(event);
  }

  moveTrim(event) {
    if (!this.drag) {
      if (this.editable && this.trimTarget(event.target)) {
        event.stopImmediatePropagation();
        this.cursor.at = null;
        this.cursor.pinned = false;
        this.cursor.draw();
      }
      return;
    }
    if (this.drag.id !== event.pointerId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const box = this.plot.querySelector('svg').getBoundingClientRect();
    const pixel = (event.clientX-box.left)/box.width*geometry.width;
    const seconds = this.range[0]+(pixel-geometry.left)/(geometry.width-geometry.left-geometry.right)*
      (this.range[1]-this.range[0]);
    this.setSelection(trimBoundary(this.selection,this.drag.boundary,Math.round(seconds*1000)/1000,this.duration));
    this.changed(this.selection,false);
  }

  endTrim(event) {
    if (!this.drag || this.drag.id !== event.pointerId) return;
    event.stopImmediatePropagation();
    if (event.type === 'pointerup') this.moveTrim(event);
    const id = this.drag.id;
    this.drag = null;
    if (this.plot.hasPointerCapture(id)) this.plot.releasePointerCapture(id);
    this.changed(this.selection,true);
  }

  keyTrim(event) {
    const handle = event.target.closest('[data-trim-handle]');
    if (!this.editable || !handle || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const boundary = handle.dataset.trimHandle, current = this.selection[boundary+'_seconds'];
    const seconds = event.key === 'Home' ? 0 : event.key === 'End' ? this.duration :
      current+(event.key === 'ArrowLeft' ? -1 : 1)*(event.shiftKey ? 10 : 1);
    this.setSelection(trimBoundary(this.selection,boundary,seconds,this.duration));
    this.changed(this.selection,true);
  }

  close() {
    const id = this.drag?.id;
    this.drag = null;
    if (id !== undefined && this.plot.hasPointerCapture(id)) this.plot.releasePointerCapture(id);
    this.controller.abort();
    this.parentSignal.removeEventListener('abort',this.parentAbort);
  }
}
