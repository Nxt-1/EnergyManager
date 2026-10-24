import {
  localDateTime,
  localInstants
} from './date-time.js';
import {
  powerText
} from './display.js';

const hour = 3600000;
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [char]));
const number = value => value === null || value === undefined ? '—' : Number(value).toFixed(1);

function nextDate(date) {
  return new Date(Date.parse(date + 'T12:00:00Z') + 24 * hour).toISOString().slice(0, 10);
}

function dayStart(date, zone) {
  // Some zones move their clocks at midnight; begin at the first real local hour.
  for (let h = 0; h < 24; h++) {
    const instant = localInstants(`${date}T${String(h).padStart(2, '0')}:00`, zone)[0];
    if (instant) return Date.parse(instant);
  }
  return null;
}

// Local midnight boundaries preserve 23/25-hour days and repeated clock hours.
export function scheduleDays(start, end, zone) {
  const days = [];
  let date = localDateTime(start, zone).slice(0, 10);
  while (true) {
    const tomorrow = nextDate(date);
    const left = dayStart(date, zone);
    if (left === null) {
      date = tomorrow;
      continue;
    }
    let following = tomorrow;
    while (dayStart(following, zone) === null) following = nextDate(following);
    const right = dayStart(following, zone);
    if (left >= end) break;
    days.push({
      date,
      start: left,
      end: right
    });
    date = tomorrow;
  }
  return days;
}

export function eventsOnDay(events, day, start, end) {
  const left = Math.max(day.start, start),
    right = Math.min(day.end, end);
  return events.filter(event => event.end > event.start ?
      event.start < right && event.end > left : event.start >= left && event.start < right)
    .map(event => ({
      ...event,
      left: Math.max(left, event.start),
      right: Math.min(right, event.end)
    }))
    .sort((a, b) => a.left - b.left || a.type.localeCompare(b.type));
}

export function evSchedule(state) {
  const start = Date.parse(state.now),
    end = start + 168 * hour;
  const plan = state.accepted;
  const current = !!plan && state.ev_plan_valid === true && plan.revision === state.revision &&
    Date.parse(plan.intervals.at(-1)?.end) > start;
  const goals = state.schedule_goals.map(goal => ({
    ...(current ? plan.goals.find(item => item.id === goal.id && item.revision === goal.revision) : {}),
    ...goal
  }));
  const events = [];
  for (const goal of goals) {
    const departure = Date.parse(goal.deadline);
    events.push({
      type: goal.kind,
      start: departure,
      end: departure,
      title: goal.title,
      goal
    });
    if (goal.kind !== 'trip') continue;
    const returned = goal.return_at ? Date.parse(goal.return_at) : end;
    events.push({
      type: 'away',
      start: departure,
      end: returned,
      title: goal.title,
      goal
    });
    if (goal.return_at) events.push({
      type: 'return',
      start: returned,
      end: returned,
      title: 'Expected return · ' + goal.title,
      goal
    });
  }
  for (const session of current ? plan.sessions : []) {
    if (session.resource !== 'ev') continue;
    events.push({
      type: 'charge',
      start: Date.parse(session.start),
      end: Date.parse(session.end),
      title: 'Planned charging',
      session
    });
  }
  return {
    start,
    end,
    current,
    goals,
    events,
    days: scheduleDays(start, end, state.policy.timezone)
  };
}

function goalStatus(goal) {
  if (goal.status === 'unknown_return_state') return 'Return SoC unknown';
  if (goal.shortfall_kwh > 0.001) return `${number(goal.shortfall_kwh)} kWh shortfall`;
  if (goal.status === 'scheduled') return 'Scheduled';
  return 'Awaiting plan';
}

export class EVSchedulePage {
  constructor(root, actions) {
    this.root = root;
    this.selectedDate = null;
    root.addEventListener('click', async event => {
      const button = event.target.closest('button');
      if (!button) return;
      try {
        if (button.dataset.evDay) {
          this.selectedDate = button.dataset.evDay;
          this.render(this.state);
          this.root.querySelector(`[data-ev-day="${this.selectedDate}"]`).focus();
          if (window.matchMedia('(max-width:1100px)').matches)
            this.root.querySelector('.ev-agenda').scrollIntoView({
              block: 'nearest',
              behavior: 'smooth'
            });
        }
        if (button.dataset.evAdd) actions.add(button.dataset.evAdd);
        if (button.dataset.evGoal) actions.goal(button.dataset.evGoal);
        if (button.dataset.evSession) actions.session(button.dataset.evSession);
        if (button.dataset.evEdit) actions.edit(button.dataset.evEdit);
        if (button.dataset.evRemove) await actions.remove(button.dataset.evRemove);
        if (button.dataset.evSettings) actions.settings();
        if (button.dataset.evReplan) await actions.replan();
        if (button.dataset.evToday) {
          this.selectedDate = null;
          this.render(this.state);
          this.root.querySelector('[data-ev-today]').focus();
        }
      } catch (error) {
        this.error = error.message;
        this.root.querySelector('.ev-message').textContent = error.message;
      }
    });
  }

  render(state) {
    const scroller = this.root.querySelector('.ev-calendar-scroll');
    const scrollLeft = scroller?.scrollLeft || 0;
    const focused = this.root.contains(document.activeElement) ? document.activeElement : null;
    const focusAttribute = focused?.getAttributeNames().find(name => name.startsWith('data-ev-'));
    const focusValue = focusAttribute ? focused.getAttribute(focusAttribute) : null;
    const matchingButtons = focusAttribute ? [...this.root.querySelectorAll(`[${focusAttribute}]`)]
      .filter(button => button.getAttribute(focusAttribute) === focusValue) : [];
    const focusIndex = matchingButtons.indexOf(focused);
    this.state = state;
    const schedule = evSchedule(state);
    const zone = state.policy.timezone;
    const clock = instant => {
      const repeated = localInstants(localDateTime(instant, zone), zone).length > 1;
      return new Date(instant).toLocaleTimeString('en-GB', {
        timeZone: zone,
        hour: '2-digit',
        minute: '2-digit',
        ...(repeated ? {
          timeZoneName: 'shortOffset'
        } : {})
      });
    };
    const dateLabel = date => new Date(date + 'T12:00:00Z').toLocaleDateString('en-GB', {
      timeZone: 'UTC',
      weekday: 'short',
      day: 'numeric',
      month: 'short'
    });
    const stamp = instant => `${dateLabel(localDateTime(instant, zone).slice(0, 10))}, ${clock(instant)}`;
    const target = goal => goal.kind === 'trip' ?
      Math.min(100, (goal.distance_km + state.policy.arrival_reserve_km) *
        state.policy.consumption_kwh_per_100km / state.capabilities.ev_capacity_kwh) : goal.target_soc_percent;
    const action = event => event.session ? `data-ev-session="${esc(event.session.id)}"` :
      `data-ev-goal="${esc(event.goal.id)}"`;
    const editActions = event => ['trip', 'manual'].includes(event.type) ||
      event.type === 'away' && event.start < event.left ?
      `<div class="actions"><button data-ev-edit="${esc(event.goal.id)}">Edit</button><button data-ev-remove="${esc(event.goal.id)}">Remove</button></div>` : '';
    const description = event => {
      if (event.type === 'charge') return `${number(event.session.energy_kwh)} kWh to battery · whole session`;
      if (event.type === 'away') return event.goal.return_at ?
        `Expected away until ${stamp(event.end)}` : 'Return unknown · away until measured reconnection';
      if (event.type === 'return') return 'Expected availability · return SoC follows the plan or measured reconnection';
      return `${number(target(event.goal))}% ${event.type === 'trip' ? 'departure target' : 'minimum SoC'} · ${goalStatus(event.goal)}`;
    };
    if (!schedule.days.some(day => day.date === this.selectedDate)) this.selectedDate = schedule.days[0].date;
    const selectedDay = schedule.days.find(day => day.date === this.selectedDate);
    const selectedEvents = eventsOnDay(schedule.events, selectedDay, schedule.start, schedule.end);
    const nextGoal = schedule.goals.filter(goal => Date.parse(goal.deadline) >= schedule.start)
      .sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline))[0];
    const reading = state.live_inputs?.cards.ev;
    const age = (schedule.start - Date.parse(state.observation.at)) / 1000;
    const known = state.observation.ev_state_known !== false &&
      (state.demo || state.observation.quality === 'measured' && age >= -5 && age <= state.policy.measurement_max_age_seconds);
    const soc = !state.demo && state.live_inputs ? reading?.value :
      known ? state.observation.ev_kwh / state.capabilities.ev_capacity_kwh * 100 : null;
    const connection = !state.demo && state.live_inputs ? reading?.label || 'Waiting for live input' :
      known ? state.observation.connected ? 'Connected' : 'Away / disconnected' : 'Waiting for live input';
    const charging = schedule.events.filter(event => event.type === 'charge' && event.end > schedule.start);
    const calendar = schedule.days.map(day => {
      const events = eventsOnDay(schedule.events, day, schedule.start, schedule.end);
      const position = instant => (instant - day.start) / (day.end - day.start) * 100;
      const lane = (types, label) => {
        // Stack overlapping items, including nearby deadline markers, instead of hiding them.
        const rows = [];
        const buttons = events.filter(event => types.includes(event.type)).map(event => {
          const point = event.start === event.end;
          const left = position(event.left);
          const width = point ? 6 : position(event.right) - left;
          const boxLeft = point ? left - width / 2 : left;
          let row = rows.findIndex(right => right + 0.4 <= boxLeft);
          if (row === -1) row = rows.length;
          rows[row] = boxLeft + width;
          const title = `${event.title} · ${stamp(event.start)} · ${description(event)}`;
          const text = point ? event.type === 'trip' ? '↗' : `${Math.round(target(event.goal))}%` :
            event.type === 'charge' ? width > 6 ? 'Charging' : '' : event.goal.return_at ? 'Away' : 'Away → ?';
          return `<button class="ev-event ev-${event.type} ${point ? 'ev-point' : ''}" ${action(event)} style="left:${left}%;width:${width}%;top:${row * 28}px" title="${esc(title)}" aria-label="${esc(title)}">${esc(text)}</button>`;
        }).join('');
        return `<div class="ev-lane"><small>${label}</small><div class="ev-track" style="height:${Math.max(1, rows.length) * 28}px">${buttons}</div></div>`;
      };
      const ticks = [0, 6, 12, 18].map(h => {
        const at = localInstants(`${day.date}T${String(h).padStart(2, '0')}:00`, zone)[0];
        if (!at) return '';
        return `<span style="left:${position(Date.parse(at))}%">${String(h).padStart(2, '0')}</span>`;
      }).join('') + '<span style="left:100%">24</span>';
      const now = schedule.start >= day.start && schedule.start < day.end ?
        `<div class="ev-current"><i class="ev-now" style="left:${position(schedule.start)}%" title="Now"></i></div>` : '';
      return `<section class="ev-day ${day.date === this.selectedDate ? 'ev-selected' : ''}">
        <button class="ev-date" data-ev-day="${day.date}" aria-pressed="${day.date === this.selectedDate}">${dateLabel(day.date)}<small>${(day.end - day.start) / hour !== 24 ? `${(day.end - day.start) / hour}-hour day` : day.date === schedule.days[0].date ? 'Today' : 'View day'}</small></button>
        <div class="ev-day-tracks"><div class="ev-hours">${ticks}</div>${lane(['away'], 'Away')}${lane(['charge'], 'Charge')}${lane(['trip', 'manual', 'daily'], 'Targets')}${now}</div></section>`;
    }).join('');
    const agenda = selectedEvents.map(event => `<section class="ev-agenda-item ev-${event.type}">
      <small>${event.start < selectedDay.start ? 'Continues · ' : ''}${clock(event.left)}${event.end > event.start ? ` — ${event.end >= selectedDay.end ? '24:00' : clock(event.right)}` : ''}${event.end > selectedDay.end ? ' · continues' : ''}</small>
      <button class="ev-agenda-title" ${action(event)}>${esc(event.title)}</button><p>${esc(description(event))}</p>
      ${event.goal && ['trip', 'manual', 'daily'].includes(event.type) ? `<p>${event.goal.planned_kwh === undefined || event.goal.planned_kwh === null ? '' : `${number(event.goal.planned_kwh / state.capabilities.ev_capacity_kwh * 100)}% planned at deadline · `}${event.type === 'trip' ? `${number(event.goal.distance_km)} km total · ${state.policy.arrival_reserve_km} km arrival reserve` : 'No journey or battery withdrawal assumed'}</p>${event.goal.external_charging_required ? '<p class="error">Charging away must be arranged. Return SoC is unknown.</p>' : ''}${event.type === 'daily' ? '<button data-ev-settings="true">Daily readiness settings</button>' : ''}` : ''}${editActions(event)}
    </section>`).join('');
    this.root.innerHTML = `<div class="notice">${esc(state.provenance)} · ${state.demo ? 'SYNTHETIC demonstration' : 'Configured inputs'}</div>
      <section class="page-heading"><div><h1>EV schedule</h1><p class="muted">${stamp(schedule.start)} — ${stamp(schedule.end)} · ${esc(zone)}</p></div>
      <div class="actions"><button data-ev-add="trip" class="primary">＋ Journey</button><button data-ev-add="manual">＋ SoC goal</button></div></section>
      <div class="ev-summary"><article class="live-item"><span class="muted">Current EV SoC</span><strong class="ev-soc">${number(soc)}%</strong><small>${esc(connection)}</small>${(reading?.issues || []).map(issue => `<small class="error">${esc(powerText(issue))}</small>`).join('')}</article>
      <article class="live-item"><span class="muted">Next requirement</span><strong>${nextGoal ? `${number(target(nextGoal))}%` : '—'}</strong><small>${nextGoal ? `${esc(nextGoal.title)} · ${stamp(nextGoal.deadline)}` : 'No upcoming requirements'}</small></article>
      <article class="live-item"><span class="muted">Planned EV charging</span><strong>${schedule.current ? charging.length : '—'} <small>sessions</small></strong><small>${charging[0] ? `Next ${stamp(Math.max(schedule.start, charging[0].start))}` : schedule.current ? 'No charging selected' : 'Awaiting a current validated plan'}</small></article></div>
      <p class="ev-message error" role="alert">${esc(this.error || '')}</p>
      <p class="status-line" role="status">${schedule.current ? 'Charging and deadline outcomes are forecasts from the accepted plan.' : 'Charging and deadline outcomes will appear after a current plan is accepted. Entered journeys and requirements remain visible.'}${state.status === 'planning' ? ' Recalculating…' : ''}${state.error ? ` <span class="error">${esc(powerText(state.error))}</span>` : ''}</p>
      <div class="ev-layout"><article class="card ev-calendar"><div class="card-heading"><div><h2>Seven-day calendar</h2><p class="subtle">Expected away · planned charging · minimum SoC / ↗ departure</p></div><button data-ev-today="true">Today</button></div>
      <div class="ev-calendar-scroll" tabindex="0" aria-label="Seven-day EV calendar; scroll horizontally for all hours"><div class="ev-calendar-days">${calendar}</div></div>
      <p class="subtle">Only the next 168 hours are shown. Away periods come from entered journeys. An unknown return stays away; no routine driving or charging away is assumed.</p></article>
      <aside class="card ev-agenda"><h2>${dateLabel(selectedDay.date)}</h2>${agenda || '<p class="empty">No journeys, requirements or planned charging in this part of the day.</p>'}<div class="actions"><button data-ev-replan="true">Recalculate</button></div><p class="subtle">Charging uses the shared EV/ESS plan. Open an item for details.</p></aside></div>`;
    if (focusAttribute)[...this.root.querySelectorAll(`[${focusAttribute}]`)]
      .filter(button => button.getAttribute(focusAttribute) === focusValue)[focusIndex]?.focus({
        preventScroll: true
      });
    if (scroller && focused === scroller) this.root.querySelector('.ev-calendar-scroll').focus({
      preventScroll: true
    });
    this.root.querySelector('.ev-calendar-scroll').scrollLeft = scrollLeft;
  }
}
