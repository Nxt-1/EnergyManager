"""Private, bounded historical evidence jobs. Never opens the operational Store."""
from __future__ import annotations

import asyncio
import json
import math
import re
import shutil
import sqlite3
import threading
import time
import uuid
import zlib
from collections import Counter
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from zipfile import ZIP_DEFLATED, ZipFile

from . import __version__
from .domain import Goal, Observation, PeakPermission, Snapshot, instant

RESERVE_BYTES = 256 * 1024 * 1024
MAX_RECORD_BYTES = 32 * 1024 * 1024
MAX_SECONDS = 1800
RETENTION_SECONDS = 86400
GAP_SECONDS = 300
MAX_COVERAGE_DAYS = 36600
MAX_DECISIONS = 100000
MAX_ARTIFACTS = 16
MAX_KINDS = 1000
MAX_OMISSIONS = 2000

# Version 1 explicitly exports only these event kinds and top-level payload fields.
OBSERVATION_FIELDS = {field.name for field in fields(Observation)} | {
    'provenance', 'ev_capacity_kwh', 'ess_capacity_kwh', 'received_at', 'source', 'units', 'quality',
    'power_w', 'value', 'entity_id', 'observed_at', 'measurement_at', 'monthly_peak_valid'}
COMMAND_FIELDS = {'at', 'plan_id', 'ev_kw', 'ess_kw', 'phases', 'current_a', 'reason', 'reasons',
                  'peak_protection', 'peak_limit_kw', 'replan', 'prepare_phase', 'generation', 'ev_current_a', 'ev_phases', 'ess_power_kw',
                  'ess_charge_kw', 'ess_discharge_kw', 'mode', 'force', 'ev_enabled'}
EVENT_FIELDS = {
    'observed': OBSERVATION_FIELDS, 'measurement': OBSERVATION_FIELDS,
    'command_intent': COMMAND_FIELDS, 'commanded_dry_run': COMMAND_FIELDS,
    'protective_command': COMMAND_FIELDS,
    'actuator_service': {'generation', 'domain', 'service', 'entity_id', 'plan_id', 'key', 'value', 'reason', 'option', 'value_kw', 'power', 'current'},
    'hardware_control': {'enabled'},
    'goal_created': {field.name for field in fields(Goal)},
    'goal_revised': {field.name for field in fields(Goal)},
    'goal_cancelled': {field.name for field in fields(Goal)},
    'goal_archived': {'goal', 'at', 'reason'},
    'approval': {field.name for field in fields(Goal)},
    'ess_approval': {field.name for field in fields(PeakPermission)},
}
for _kind in ('invalidation', 'planning_requested', 'planning_cancelled', 'planning_recovered',
              'planning_rejected', 'plan_recovery', 'deadline_fallback_activated', 'forecast_updated',
              'forecast_bias', 'power_balance_recovered', 'power_balance_settling',
              'ev_feedback_problem', 'ev_feedback_recovered', 'ev_manual_confirmed', 'ev_manual_disabled',
              'ev_incident', 'ev_diagnostics', 'actuator_error', 'protective_dispatch_error',
              'input_error', 'snapshot_error', 'solver_error', 'worker_restarted', 'forecast_error'):
    EVENT_FIELDS[_kind] = {
        'id', 'at', 'since', 'reason', 'type', 'revision', 'ev', 'ess', 'request_id', 'snapshot_id',
        'decision_id', 'plan_id', 'forecast_id', 'queued_for_planning', 'generation', 'scope',
        'status', 'started_at', 'detected_at', 'resolved_at', 'reboot_attempts', 'events',
        'reported_kwh', 'manual_kwh', 'enabled', 'quality', 'entities', 'source', 'problem',
        'active', 'remaining_kwh', 'delivered_kwh', 'target_kwh', 'deadline', 'state', 'evidence',
        'publication_errors', 'seconds', 'stage', 'summary', 'pending', 'accepted_id', 'last_attempt',
        'house_w', 'balance_w', 'difference_w', 'threshold_w', 'duration_seconds',
        'cause', 'reference_kwh', 'soc_percent', 'entered_at', 'goal', 'quantity_kwh',
        'limit_kwh', 'capacity_kwh', 'efficiency', 'counter_source', 'counter_kwh',
        'replacing_active', 'attempts', 'last_at', 'kind', 'title', 'text',
        'reboot_allowed', 'charger', 'attempted_at', 'command', 'observation', 'recovery_charger'}

SENSITIVE_KEY = re.compile(r'(notification|raw_http|token|password|secret|authorization|credential|api.?key|cookie|raw.?payload)', re.I)
SENSITIVE_TEXT = re.compile(
    r'(https?://|Bearer\s+|Basic\s+[A-Za-z0-9+/=]{12,}|[?&](?:key|token|code)=|'
    r'(?:password|secret|token|authorization|credential|cookie|api[_ -]?key)\s*[:=]|'
    r'ya29\.[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9]+|'
    r'eyJ[A-Za-z0-9_-]{12,}\.|-----BEGIN .*PRIVATE KEY)', re.I)


def safe_content(value: Any, depth: int = 0) -> bool:
    """Fail closed on unsupported sensitive content, including legacy free-text errors."""
    if depth > 40:
        return False
    if isinstance(value, dict):
        return all(not SENSITIVE_KEY.search(key) and safe_content(item, depth + 1) for key, item in value.items())
    if isinstance(value, list):
        return all(safe_content(item, depth + 1) for item in value)
    if isinstance(value, str):
        return not SENSITIVE_TEXT.search(value)
    return value is None or isinstance(value, (bool, int)) or isinstance(value, float) and math.isfinite(value)


def timestamp(value: Any) -> float | None:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result = float(value)
            datetime.fromtimestamp(result, UTC)
        else:
            result = instant(value).timestamp()
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError, OSError, AttributeError):
        return None


def iso(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat()


def decode_archive(value: str | bytes) -> bytes:
    if isinstance(value, str):
        data = value.encode('utf-8')
    else:
        decoder = zlib.decompressobj()
        data = decoder.decompress(value, MAX_RECORD_BYTES + 1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('Unsupported or oversized compressed archive')
    if len(data) > MAX_RECORD_BYTES:
        raise ValueError('Archive exceeds record limit')
    return data


class Diagnostics:
    """One shared background worker and compact status; disk artifacts are never API state."""

    def __init__(self, source: Path, timezone: str) -> None:
        self.source = source.resolve()
        self.root = self.source.parent / 'diagnostics-exports'
        self.timezone = timezone
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='diagnostics')
        self.future: Any = None
        self.job: dict[str, Any] | None = None
        self.downloads: Counter[str] = Counter()
        self.artifacts: dict[str, dict[str, Any]] = {}
        self.deadline = 0.0
        self.last_check = 0.0
        self.sqlite_failure: Exception | None = None

    def initialize(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.artifacts.clear()
        interrupted = False
        for path in self.root.iterdir():
            # Only completed, bounded metadata can restore an artifact. Running work
            # has no ready marker and is removed rather than resumed.
            metadata = path / 'ready.json'
            if path.is_dir() and not path.is_symlink() and re.fullmatch(r'[0-9a-f]{32}', path.name):
                try:
                    if metadata.stat().st_size > 8192:
                        raise ValueError('Invalid artifact metadata')
                    artifact = json.loads(metadata.read_text(encoding='utf-8'))
                    member = 'dataset.zip' if artifact['kind'] == 'dataset' else 'coverage.json'
                    coverage_file = path / 'coverage.json'
                    if (artifact['id'] != path.name or artifact['state'] != 'ready'
                            or artifact['kind'] not in ('dataset', 'coverage')
                            or artifact['expires_epoch'] <= time.time()
                            or (path / member).stat().st_size != artifact['bytes']
                            or coverage_file.stat().st_size > MAX_RECORD_BYTES
                            or len(self.artifacts) >= MAX_ARTIFACTS):
                        raise ValueError('Unavailable artifact')
                    coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
                    if not isinstance(coverage, dict) or coverage.get('capture', {}).get('id') != path.name:
                        raise ValueError('Invalid coverage metadata')
                    self.artifacts[path.name] = artifact
                    continue
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            interrupted = True
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        if interrupted:
            self.job = {'state': 'interrupted', 'stage': 'Interrupted by restart; prepare again'}
        elif self.artifacts:
            artifact = max(self.artifacts.values(), key=lambda item: item['created_at'])
            coverage_file = self.root / artifact['id'] / 'coverage.json'
            if coverage_file.stat().st_size <= MAX_RECORD_BYTES:
                self.job = {**artifact, 'coverage': json.loads(coverage_file.read_text(encoding='utf-8'))}

    def status(self) -> dict[str, Any]:
        with self.lock:
            return {'job': dict(self.job) if self.job else None, 'timezone': self.timezone,
                    'artifacts': [{key: value for key, value in artifact.items() if key in
                                   ('id', 'kind', 'bytes', 'start', 'end', 'expires_at')}
                                  for artifact in self.artifacts.values()]}

    def update(self, **values: Any) -> None:
        with self.lock:
            if self.job:
                self.job.update(values)

    def start(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        if kind not in ('coverage', 'dataset'):
            raise ValueError('Unknown diagnostics operation')
        start = end = None
        if kind == 'dataset':
            start, end = timestamp(body.get('start')), timestamp(body.get('end'))
            if start is None or end is None or start >= end:
                raise ValueError('Select a valid start before end, including UTC offsets')
        with self.lock:
            if self.future and not self.future.done():
                return self.status()  # Retries cannot start a competing job.
            if len(self.artifacts) >= MAX_ARTIFACTS:
                raise ValueError('Remove an earlier export before preparing another (16-artifact limit)')
            identity = uuid.uuid4().hex
            self.cancelled.clear()
            self.job = {'id': identity, 'kind': kind, 'state': 'running', 'stage': 'Preparing', 'records': 0,
                        'created_at': iso(time.time()), 'start': iso(start) if start is not None else None,
                        'end': iso(end) if end is not None else None}
            self.future = self.executor.submit(self.run, identity, kind, start, end)
            return self.status()

    def check(self, *, force: bool = False) -> None:
        if self.cancelled.is_set():
            raise InterruptedError('Cancelled')
        now = time.monotonic()
        if now > self.deadline:
            raise TimeoutError('Diagnostics exceeded the 30-minute time limit')
        if force or now - self.last_check > 0.2:
            self.last_check = now
            if shutil.disk_usage(self.root).free < RESERVE_BYTES:
                raise OSError('Diagnostics stopped to preserve the 256 MiB disk reserve')
            time.sleep(0.001)  # Yield disk/CPU between bounded batches.

    def sqlite_progress(self) -> int:
        try:
            self.check()
        except (OSError, TimeoutError) as exc:
            self.sqlite_failure = exc
            return 1
        return 0

    def expire(self) -> None:
        with self.lock:
            for identity, artifact in list(self.artifacts.items()):
                if time.time() >= artifact['expires_epoch'] and not self.downloads[identity]:
                    shutil.rmtree(self.root / identity)
                    del self.artifacts[identity]
                    if self.job and self.job.get('id') == identity:
                        self.job.update(state='expired', stage='Artifact expired; prepare again')

    def action(self, identity: str, action: str) -> dict[str, Any]:
        with self.lock:
            current = self.job and self.job.get('id') == identity
            if action == 'cancel' and current and self.job:
                if self.job['state'] == 'running':
                    self.cancelled.set()
            elif action == 'delete' and identity in self.artifacts:
                if self.downloads[identity]:
                    raise ValueError('Wait for active downloads before removal')
                shutil.rmtree(self.root / identity)
                del self.artifacts[identity]
                if current and self.job:
                    self.job.update(state='deleted', stage='Export artifacts removed')
            else:
                raise ValueError('Unknown job or action unavailable')
            return self.status()

    def acquire(self, identity: str, member: str) -> Path:
        with self.lock:
            artifact = self.artifacts.get(identity)
            if not artifact:
                raise ValueError('Artifact is unavailable; prepare again')
            if time.time() >= artifact['expires_epoch']:
                raise ValueError('Artifact expired; prepare again')
            name = {'coverage': 'coverage.json', 'dataset': 'dataset.zip'}.get(member)
            if not name or member == 'dataset' and artifact['kind'] != 'dataset':
                raise ValueError('Unknown artifact')
            self.downloads[identity] += 1
            return self.root / identity / name

    def release(self, identity: str) -> None:
        with self.lock:
            self.downloads[identity] -= 1

    def run(self, identity: str, kind: str, start: float | None, end: float | None) -> None:
        directory = self.root / identity
        self.deadline = time.monotonic() + MAX_SECONDS
        self.sqlite_failure = None
        try:
            directory.mkdir(mode=0o700)
            wal = Path(str(self.source) + '-wal')
            source_bytes = self.source.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
            required = source_bytes * 3 + RESERVE_BYTES
            if shutil.disk_usage(directory).free < required:
                raise OSError('Not enough disk headroom for snapshot, output and 256 MiB reserve')
            capture = {'id': identity, 'backup_started_at': iso(time.time())}
            self.update(stage='Capturing consistent history')
            with closing(sqlite3.connect(self.source.as_uri() + '?mode=ro', uri=True, timeout=1)) as source:
                source.execute('BEGIN')
                source.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
                with closing(sqlite3.connect(directory / 'snapshot.sqlite')) as target:
                    source.backup(target, pages=128, progress=lambda *_: self.check(), sleep=0.01)
            capture['backup_completed_at'] = iso(time.time())
            with closing(sqlite3.connect((directory / 'snapshot.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
                db.row_factory = sqlite3.Row
                db.execute('PRAGMA temp_store=FILE')
                db.execute('PRAGMA cache_size=-4096')
                db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD_BYTES)
                db.set_progress_handler(self.sqlite_progress, 10000)
                self.update(stage='Reading history')
                coverage = self.scan(db, capture, start, end, directory if kind == 'dataset' else None)
                (directory / 'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False), encoding='utf-8')
                if kind == 'dataset':
                    if not coverage['selected_records']:
                        raise ValueError('No records in the requested period; select another period')
                    self.package(directory, coverage)
            (directory / 'snapshot.sqlite').unlink()
            self.check(force=True)
            size = (directory / ('dataset.zip' if kind == 'dataset' else 'coverage.json')).stat().st_size
            with self.lock:
                self.update(state='ready', stage='Ready', bytes=size, coverage=coverage,
                            expires_epoch=time.time() + RETENTION_SECONDS,
                            expires_at=iso(time.time() + RETENTION_SECONDS))
                metadata = {key: value for key, value in (self.job or {}).items() if key != 'coverage'}
                (directory / 'ready.json').write_text(json.dumps(metadata), encoding='utf-8')
                self.artifacts[identity] = metadata
        except Exception as exc:
            shutil.rmtree(directory, ignore_errors=True)
            if isinstance(exc, sqlite3.OperationalError) and self.sqlite_failure:
                exc = self.sqlite_failure
            # Never leak a SQLite payload/secret through exception messages.
            message = str(exc) if isinstance(exc, (ValueError, OSError, TimeoutError)) and safe_content(str(exc)) else type(exc).__name__
            if isinstance(exc, sqlite3.DataError):
                message = 'Stored history record exceeds the 32 MiB SQLite read limit'
            self.update(state='cancelled' if self.cancelled.is_set() else 'failed', stage=message)

    def scan(self, db: sqlite3.Connection, capture: dict[str, str], start: float | None,
             end: float | None, directory: Path | None) -> dict[str, Any]:
        schema = list(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"))
        tables = {row['name']: [col[1] for col in db.execute('PRAGMA table_info("' + row['name'].replace('"', '""') + '")')]
                  for row in schema}
        required = {'events': {'sequence', 'at', 'kind', 'body'},
                    'decisions': {'id', 'at', 'disposition', 'digest', 'snapshot', 'result'}}
        for name, columns in required.items():
            if not columns <= set(tables.get(name, [])):
                raise ValueError('Unsupported SQLite schema: required event/decision columns absent')
        coverage: dict[str, Any] = {
            'format_version': 1, 'capture': capture, 'timezone': self.timezone,
            'database_bytes': (db.execute('PRAGMA page_count').fetchone()[0] * db.execute('PRAGMA page_size').fetchone()[0]),
            'schema_fingerprint': sha256(json.dumps([tuple(row) for row in schema]).encode()).hexdigest(),
            'tables': tables, 'excluded_tables': sorted(set(tables) - {'events', 'decisions', 'load_samples', 'background_samples'}),
            'event_kinds': {}, 'decision_dispositions': {}, 'series': {}, 'omissions': {},
            'selected_records': 0, 'first': None, 'last': None,
            'selection': {'start': iso(start) if start is not None else None, 'end': iso(end) if end is not None else None,
                          'interval': '[start,end)', 'events': 'recording time OR valid observation time; source sequence deduplicated',
                          'samples': 'own timestamp', 'decisions': 'recording time, complete original horizon',
                          'ordering': 'events by source sequence; samples by own timestamp; decisions by recording time/id'},
            'limitations': ['Stored counts do not establish continuity.', 'Overwritten state and unavailable forecast revisions are excluded.',
                            'Historical evidence does not establish complete counterfactual replay.',
                            'Producer versions are unknown unless present in original records.',
                            'Event payloads use the version-1 field allowlist; unsupported fields are reported.',
                            'Initial runtime state may be absent; current state is never substituted.',
                            'Legacy load_samples store watts but no source/quality; missing metadata is exported as null.'],
        }
        omissions: Counter[str] = Counter()
        writers: dict[str, Any] = {}
        member_stats: dict[str, dict[str, Any]] = {}
        latest: dict[str, tuple[float, int]] = {}
        total = 0

        def selected(at: float | None) -> bool:
            return at is not None and start is not None and end is not None and start <= at < end

        def inventory(at: float | None) -> None:
            if at is None:
                omissions['invalid_timestamp'] += 1
                return
            coverage['first'] = min(coverage['first'], at) if coverage['first'] is not None else at
            coverage['last'] = max(coverage['last'], at) if coverage['last'] is not None else at

        def write(name: str, record: dict[str, Any]) -> None:
            if directory:
                if name not in writers:
                    writers[name] = (directory / name).open('w', encoding='utf-8', newline='\n')
                writers[name].write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
                stats = member_stats.setdefault(name, {'records': 0, 'first': None, 'last': None})
                stats['records'] += 1
                at = timestamp(record.get('recorded_at', record.get('at')))
                if at is not None:
                    stats['first'] = min(stats['first'], at) if stats['first'] is not None else at
                    stats['last'] = max(stats['last'], at) if stats['last'] is not None else at

        def progress() -> None:
            nonlocal total
            total += 1
            if total % 256 == 0:
                self.update(records=total)
                self.check()
                if len(omissions) > MAX_OMISSIONS:
                    raise ValueError('History exceeds supported omission-category limit')

        # Series aggregation is performed in SQLite to handle late/out-of-order records without retaining them in RAM.
        db.execute('CREATE TEMP TABLE series (kind TEXT, at REAL)')
        try:
            for row in db.execute('SELECT sequence,at,kind,body FROM events ORDER BY sequence'):
                progress()
                recorded = timestamp(row['at'])
                inventory(recorded)
                kind = row['kind']
                if len(coverage['event_kinds']) >= MAX_KINDS and kind not in coverage['event_kinds']:
                    raise ValueError('History exceeds supported event-kind limit')
                count = coverage['event_kinds'].setdefault(kind, {'stored': 0, 'selected': 0, 'supported': kind in EVENT_FIELDS})
                count['stored'] += 1
                try:
                    body = json.loads(row['body'])
                    if not isinstance(body, dict):
                        raise ValueError()
                except (ValueError, TypeError):
                    omissions['invalid_event_json'] += 1
                    continue
                observed = timestamp(body.get('at')) if kind in ('measurement', 'observed') else None
                if kind in ('measurement', 'observed'):
                    if observed is None:
                        omissions['invalid_observation_timestamp'] += 1
                    else:
                        db.execute('INSERT INTO series VALUES (?,?)', (kind, observed))
                        inventory(observed)
                reasons = [name for name, at in (('recording_time', recorded), ('observation_time', observed)) if selected(at)]
                if reasons:
                    count['selected'] += 1
                    coverage['selected_records'] += 1
                if kind not in EVENT_FIELDS:
                    omissions['excluded_event_kind:' + kind] += 1
                    continue
                unknown_fields = set(body) - EVENT_FIELDS[kind]
                for key in unknown_fields:
                    omissions['unsupported_event_field:' + kind + ':' + key] += 1
                filtered = {key: value for key, value in body.items() if key in EVENT_FIELDS[kind]}
                if not safe_content(filtered):
                    omissions['sensitive_or_unsupported_event:' + kind] += 1
                    continue
                if reasons:
                    write('events.jsonl', {'sequence': row['sequence'], 'kind': kind, 'recorded_at': row['at'],
                                           'selection_reasons': reasons, 'body': filtered})
                if (start is not None and observed is not None and observed < start
                        and recorded is not None and recorded < start):
                    if kind not in latest or observed > latest[kind][0]:
                        latest[kind] = (observed, row['sequence'])
            # Only event identities are retained; boundary bodies are read again below.
            baseline = None
            if start is not None:
                baseline = db.execute("SELECT id,at FROM decisions WHERE disposition='accepted' AND julianday(at)<julianday(?) ORDER BY julianday(at) DESC,id DESC LIMIT 1", (iso(start),)).fetchone()
            baseline_at = timestamp(baseline['at']) if baseline else None
            coverage['boundary'] = {'applicable': start is not None, 'accepted_decision': baseline['id'] if baseline else None,
                                    'missing_accepted_baseline': baseline is None, 'context_events': 0,
                                    'accepted_decision_included': False,
                                    'missing_observation_context': sorted({'measurement', 'observed'} - set(latest)),
                                    'latest_context_sequences': {key: value[1] for key, value in latest.items()}}
            if start is not None:
                for row in db.execute('SELECT sequence,at,kind,body FROM events ORDER BY sequence'):
                    progress()
                    at = timestamp(row['at'])
                    context_kind = row['kind'] in EVENT_FIELDS and row['kind'] not in ('measurement', 'observed') and at is not None and at < start
                    if row['sequence'] not in {value[1] for value in latest.values()} and not (context_kind and (baseline_at is None or at is not None and at >= baseline_at)):
                        continue
                    try:
                        body = json.loads(row['body'])
                        filtered = {key: value for key, value in body.items() if key in EVENT_FIELDS[row['kind']]}
                    except (ValueError, TypeError, AttributeError, KeyError):
                        continue
                    observed_at = timestamp(body.get('at')) if row['kind'] in ('measurement', 'observed') else None
                    if selected(at) or selected(observed_at):
                        continue  # Already retained in the selected events member.
                    if safe_content(filtered):
                        write('boundary-events.jsonl', {'sequence': row['sequence'], 'kind': row['kind'],
                                                        'recorded_at': row['at'], 'body': filtered, 'selection_reasons': ['boundary_context']})
                        coverage['boundary']['context_events'] += 1
            for table, sample_columns in (('load_samples', ['at', 'power_w']), ('background_samples', ['at', 'house_w', 'meter_w', 'background_w', 'source', 'quality'])):
                if not set(sample_columns) <= set(tables.get(table, [])):
                    omissions['missing_or_unsupported_table:' + table] += 1
                    continue
                count = 0
                for row in db.execute('SELECT ' + ','.join(sample_columns) + ' FROM ' + table + ' ORDER BY at'):
                    progress()
                    at = timestamp(row['at'])
                    inventory(at)
                    count += 1
                    if at is not None:
                        db.execute('INSERT INTO series VALUES (?,?)', (table, at))
                    if selected(at):
                        coverage['selected_records'] += 1
                        record = dict(row)
                        record['units'] = 'W'
                        if table == 'load_samples':
                            record.update(source=None, quality=None)
                        if safe_content(record):
                            write(table + '.jsonl', record)
                        else:
                            omissions['sensitive_or_invalid_sample:' + table] += 1
                coverage[table] = {'stored': count}
            # Retain referenced predecessors without trusting user-controlled paths/IDs as filenames.
            needed = {baseline['id']} if baseline else set()
            exported: set[str] = set()
            for row in db.execute('SELECT id,at,disposition FROM decisions ORDER BY julianday(at),id'):
                progress()
                at = timestamp(row['at'])
                inventory(at)
                counts = coverage['decision_dispositions'].setdefault(row['disposition'], {'stored': 0, 'selected': 0})
                counts['stored'] += 1
                if selected(at):
                    counts['selected'] += 1
                    coverage['selected_records'] += 1
                    needed.add(row['id'])
                    if len(needed) > MAX_DECISIONS:
                        raise ValueError('Selected history exceeds the 100000-decision limit')
            while needed - exported:
                self.check()
                if len(needed) > MAX_DECISIONS:
                    raise ValueError('Selected history exceeds the 100000-decision limit')
                identity = min(needed - exported)
                exported.add(identity)
                row = db.execute('SELECT * FROM decisions WHERE id=?', (identity,)).fetchone()
                if not row:
                    omissions['unresolved_predecessor'] += 1
                    continue
                try:
                    snapshot = decode_archive(row['snapshot'])
                    result = decode_archive(row['result'])
                    data, result_data = json.loads(snapshot), json.loads(result)
                    if sha256(snapshot).hexdigest() != row['digest']:
                        raise ValueError('digest')
                    if not isinstance(data, dict) or not isinstance(result_data, dict) or set(data) - {field.name for field in fields(Snapshot)}:
                        raise ValueError('schema')
                    if not safe_content(data) or not safe_content(result_data):
                        raise ValueError('sensitive')
                    # Known execution/hold references; full snapshot/result are otherwise byte-preserved.
                    references = {data.get('hold_plan_id')}
                    execution = data.get('execution') or {}
                    for key in ('plan_id', 'accepted_plan_id', 'predecessor_plan_id', 'source_plan_id'):
                        references.add(execution.get(key))
                    running = execution.get('running_task') or {}
                    references.add(running.get('plan_id'))
                    needed.update(value for value in references if isinstance(value, str) and value != identity)
                except (ValueError, TypeError, zlib.error, UnicodeError, AttributeError):
                    omissions['corrupt_sensitive_or_unsupported_decision'] += 1
                    write('decision-omissions.jsonl', {'id': identity, 'reason': 'corrupt, sensitive or unsupported archive'})
                    continue
                member = 'decision-' + sha256(identity.encode()).hexdigest()
                if baseline and identity == baseline['id']:
                    coverage['boundary']['accepted_decision_included'] = True
                if directory:
                    (directory / (member + '-snapshot.json')).write_bytes(snapshot)
                    (directory / (member + '-result.json')).write_bytes(result)
                    for suffix, payload in (('snapshot', data), ('result', result_data)):
                        intervals = payload.get('intervals') or []
                        first = timestamp(intervals[0].get('start')) if intervals and isinstance(intervals[0], dict) else None
                        last = timestamp(intervals[-1].get('end')) if intervals and isinstance(intervals[-1], dict) else None
                        member_stats[member + '-' + suffix + '.json'] = {
                            'records': 1, 'first': first, 'last': last, 'timestamp_basis': 'complete stored horizon where present'}
                write('decisions.jsonl', {'id': identity, 'recorded_at': row['at'], 'disposition': row['disposition'],
                                          'digest': row['digest'], 'snapshot': member + '-snapshot.json', 'result': member + '-result.json',
                                          'selection_reasons': ['recording_time'] if selected(timestamp(row['at'])) else ['boundary_context']})
            db.execute('CREATE INDEX series_time ON series(kind,at)')
            for row in db.execute('SELECT kind,COUNT(*),MIN(at),MAX(at) FROM series GROUP BY kind'):
                kind = row[0]
                daily = [dict(day=item[0], count=item[1]) for item in db.execute("SELECT date(at,'unixepoch'),COUNT(*) FROM series WHERE kind=? GROUP BY date(at,'unixepoch') ORDER BY 1 LIMIT ?", (kind, MAX_COVERAGE_DAYS + 1))]
                if len(daily) > MAX_COVERAGE_DAYS:
                    raise ValueError('History exceeds bounded coverage day limit')
                gaps = db.execute('SELECT COUNT(*),MAX(gap) FROM (SELECT at-LAG(at) OVER (ORDER BY at) AS gap FROM series WHERE kind=?) WHERE gap>?', (kind, GAP_SECONDS)).fetchone()
                selected_count = db.execute('SELECT COUNT(*) FROM series WHERE kind=? AND at>=? AND at<?', (kind, start, end)).fetchone()[0]
                selected_daily = [dict(day=item[0], count=item[1]) for item in db.execute(
                    "SELECT date(at,'unixepoch'),COUNT(*) FROM series WHERE kind=? AND at>=? AND at<? GROUP BY date(at,'unixepoch') ORDER BY 1",
                    (kind, start, end))]
                selected_gaps = db.execute(
                    'SELECT COUNT(*),MAX(gap) FROM (SELECT at-LAG(at) OVER (ORDER BY at) AS gap FROM series WHERE kind=? AND at>=? AND at<?) WHERE gap>?',
                    (kind, start, end, GAP_SECONDS)).fetchone()
                coverage['series'][kind] = {'stored': row[1], 'first': iso(row[2]), 'last': iso(row[3]), 'daily': daily,
                                            'selected': selected_count, 'gap_count': gaps[0], 'largest_gap_seconds': gaps[1],
                                            'selected_daily': selected_daily, 'daily_timezone': 'UTC',
                                            'selected_gap_count': selected_gaps[0], 'selected_largest_gap_seconds': selected_gaps[1],
                                            'gap_threshold_seconds': GAP_SECONDS, 'timestamp_basis': 'body.at' if kind in ('measurement', 'observed') else 'sample.at'}
        finally:
            for stream in writers.values():
                stream.close()
        if directory:
            for name in ('events', 'boundary-events', 'load_samples', 'background_samples', 'decisions', 'decision-omissions'):
                (directory / (name + '.jsonl')).touch(exist_ok=True)
                member_stats.setdefault(name + '.jsonl', {'records': 0, 'first': None, 'last': None})
        coverage['member_ranges'] = {name: {**stats, 'first': iso(stats['first']) if stats['first'] is not None else None,
                                                          'last': iso(stats['last']) if stats['last'] is not None else None,
                                                          'timestamp_basis': stats.get('timestamp_basis', 'source recording time or sample own timestamp')}
                                     for name, stats in member_stats.items()}
        coverage['omissions'] = dict(omissions)
        if baseline and not coverage['boundary']['accepted_decision_included']:
            coverage['omissions']['accepted_baseline_unavailable'] = 1
        coverage['first'] = iso(coverage['first']) if coverage['first'] is not None else None
        coverage['last'] = iso(coverage['last']) if coverage['last'] is not None else None
        self.update(records=total)
        return coverage

    def package(self, directory: Path, coverage: dict[str, Any]) -> None:
        self.update(stage='Packaging')
        members = {}
        with ZipFile(directory / 'dataset.zip', 'w', compression=ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
            for path in sorted(directory.iterdir()):
                if path.suffix not in ('.json', '.jsonl'):
                    continue
                digest = sha256()
                size = count = 0
                with path.open('rb') as source, archive.open(path.name, 'w', force_zip64=True) as target:
                    while chunk := source.read(256 * 1024):
                        self.check()
                        digest.update(chunk)
                        size += len(chunk)
                        count += chunk.count(b'\n')
                        target.write(chunk)
                members[path.name] = {'range': coverage['member_ranges'].get(path.name, {'first': None, 'last': None, 'timestamp_basis': 'capture metadata; not a time series'}), 'sha256': digest.hexdigest(), 'bytes': size,
                                      'records': count if path.suffix == '.jsonl' else 1}
            zone = ZoneInfo(self.timezone)
            selection = coverage['selection']
            manifest = {'format_version': 1, 'application_version': __version__, 'timezone': self.timezone,
                        'schema_fingerprint': coverage['schema_fingerprint'], 'capture': coverage['capture'],
                        'requested_range': {**selection, 'local_start': instant(selection['start']).astimezone(zone).isoformat(),
                                            'local_end': instant(selection['end']).astimezone(zone).isoformat()},
                        'members': members, 'exclusions': coverage['excluded_tables'], 'validation_failures': coverage['omissions'],
                        'completeness_limitations': coverage['limitations'], 'boundary': coverage['boundary'],
                        'units': {'load_samples': 'W', 'background_samples': 'W', 'timestamps': 'UTC; samples Unix seconds'},
                        'event_schema': {key: sorted(value) for key, value in EVENT_FIELDS.items()}}
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
        # Only the ZIP and independent compact coverage remain after successful packaging.
        for path in directory.iterdir():
            if path.suffix == '.jsonl' or path.name.startswith('decision-'):
                path.unlink()

    async def close(self) -> None:
        self.cancelled.set()
        if self.future:
            await asyncio.wrap_future(self.future)
        self.executor.shutdown(wait=False, cancel_futures=True)
