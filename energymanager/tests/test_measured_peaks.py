"""Synthetic measured peaks and fake mobile delivery; no installation access."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from energymanager.live_inputs import Reading
from energymanager.notifications import Notifications, NotificationTarget
from energymanager.service import Application
from energymanager.store import Store
from test_first_slice import tiny
from test_planning_attention import FakePhone


async def test_peak_episodes_survive_restart_retry_and_month_reset(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    store = Store(path)
    app = Application(store, snapshot=tiny(), demo=False)
    phone = FakePhone()
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    peaks = app.measured_peaks
    at = datetime(2026, 10, 31, 21, tzinfo=UTC)

    async def read(minutes, peak):
        peaks.observe(at + timedelta(minutes=minutes), peak)
        await peaks.deliver()

    await read(0, 1.2)  # First installation read initializes, without a retrospective alert.
    await read(1, 2.4)
    await read(2, 2.5)
    assert not phone.calls
    phone.fail = True
    await read(3, 2.6)
    await read(4, 2.7)
    assert len(store.get("measured_peak")["pending"]) == 1
    store.close()

    store = Store(path)
    app = Application(store, snapshot=tiny(), demo=False)
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    peaks = app.measured_peaks
    phone.fail = False
    await peaks.deliver()
    assert len(phone.calls) == 1 and "2.600" in phone.calls[0][2]["message"]
    await read(5, 2.8)
    await read(19, 2.9)  # Fourteen minutes after the preceding increase remains silent.
    await read(20, 2.9)  # Repeated reads do not extend the quiet period.
    await read(34, 3.0)
    assert len(phone.calls) == 2
    await read(35, 2.8)  # Transient decrease is not a billing-month reset.
    await read(36, 3.0)
    assert len(phone.calls) == 2
    await read(121, 0)  # November begins at 23:00 UTC in the installation timezone.
    await read(122, 2.4)
    await read(123, 2.7)
    assert len(phone.calls) == 3
    assert store.get("measured_peak")["month"] == "2026-11"
    await peaks.deliver()
    assert len(phone.calls) == 3
    store.close()


async def test_restored_baseline_detects_offline_rise_and_first_high_read_only_initializes(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny(), demo=False)
    phone = FakePhone()
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    at = datetime(2026, 11, 7, tzinfo=UTC)
    app.measured_peaks.observe(at, 4)
    await app.measured_peaks.deliver()
    assert not phone.calls
    restarted = Application(store, snapshot=tiny(), demo=False)
    restarted.notifications = app.notifications
    restarted.measured_peaks.observe(at + timedelta(hours=1), 4.1)
    await restarted.measured_peaks.deliver()
    assert len(phone.calls) == 1
    store.close()


async def test_independent_peak_read_survives_other_input_failure_and_does_not_wait_for_planning(tmp_path):
    store = Store(tmp_path / "synthetic.sqlite")
    app = Application(store, snapshot=tiny(), demo=False)
    phone = FakePhone()
    app.notifications = Notifications(store, phone, NotificationTarget("notify.synthetic_phone", "action"))
    at = app.now()
    app.ha = SimpleNamespace(inputs=SimpleNamespace(readings={}))
    app.status = "inputs_unavailable"
    for second, value in ((-2, "2.5"), (-1, "3"), (0, "unavailable")):
        read_at = at + timedelta(seconds=second)
        app.ha.inputs.readings["monthly_peak_kw"] = Reading.parse("sensor.synthetic_peak", {
            "state": value, "attributes": {"unit_of_measurement": "kW"}}, read_at, "kW", 30)
        app.measured_peaks.sample()
        await app.measured_peaks.deliver()
    assert len(phone.calls) == 1
    measurements = [row["body"] for row in store.events() if row["kind"] == "measurement"]
    assert len(measurements) == 3
    assert measurements[0]["monthly_peak_valid"] is False
    assert measurements[1]["monthly_peak_kw"] == 3
    assert app.accepted is None
    store.close()
