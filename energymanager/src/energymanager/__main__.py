"""Process entrypoint for the Energy Manager Home Assistant app."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from . import __version__
from .actuators import ActuatorRegistry
from .app import EnergyManagerApp
from .config import ConfigurationError, Settings
from .database import EnergyManagerStore, InfluxDatabaseClient, InfluxDatabaseError
from .diagnostics import DiagnosticsPublisher
from .ha_client import HomeAssistantClient
from .legacy_influx import LegacyInfluxBackfill, LegacyInfluxClient, LegacyInfluxError
from .load_service import BackgroundLoadHistory, BackgroundLoadService
from .open_meteo import OpenMeteoClient
from .planner_service import ShadowPlannerService
from .pv_service import PvForecastService


async def async_main() -> int:
    """Start the Energy Manager daemon and wait for termination."""
    try:
        settings = Settings.load()
    except ConfigurationError as exc:
        logging.basicConfig(level=logging.ERROR, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        logging.error("Invalid Energy Manager configuration: %s", exc)
        return 2

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("energymanager")
    logger.info("Starting Energy Manager %s in hard-coded shadow mode", __version__)

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not supervisor_token:
        logger.error("SUPERVISOR_TOKEN is missing; Home Assistant API access is unavailable")
        return 2

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    async with HomeAssistantClient(supervisor_token) as client:
        if settings.database.enabled:
            assert settings.database.url is not None
            assert settings.database.token is not None
            async with InfluxDatabaseClient(
                settings.database.url,
                settings.database.database,
                settings.database.token,
            ) as database_client:
                await _run_with_database(settings, client, database_client, stop_event)
        else:
            diagnostics = DiagnosticsPublisher(client)
            await diagnostics.publish_database_status("disabled", database=settings.database.database)
            await _run_app(settings, client, stop_event, store=None, history=None)

    logger.info("Energy Manager stopped")
    return 0


async def _run_with_database(
    settings: Settings,
    client: HomeAssistantClient,
    database_client: InfluxDatabaseClient,
    stop_event: asyncio.Event,
) -> None:
    logger = logging.getLogger("energymanager")
    diagnostics = DiagnosticsPublisher(client)
    store = EnergyManagerStore(database_client)
    backfill_result = None
    backfill_error = None
    try:
        migrated_pv, migrated_load, migrated_load_forecast = await store.initialize()
        if settings.legacy_influx.backfill_enabled:
            async with LegacyInfluxClient(settings.legacy_influx) as legacy_client:
                backfill_result = await LegacyInfluxBackfill(settings, legacy_client, store).run()
        samples = await store.load_background_samples(days=35)
    except InfluxDatabaseError as exc:
        logger.error("InfluxDB persistence unavailable; continuing with local JSONL fallback: %s", exc)
        await diagnostics.publish_database_status(
            "error",
            database=settings.database.database,
            url=settings.database.url,
            error=str(exc),
        )
        await _run_app(settings, client, stop_event, store=None, history=None)
        return
    except LegacyInfluxError as exc:
        backfill_error = str(exc)
        logger.warning("Legacy InfluxDB backfill failed; continuing with existing EnergyManager history: %s", exc)
        samples = await store.load_background_samples(days=35)

    logger.info(
        "InfluxDB persistence connected: database=%s, history_samples=%d",
        store.database,
        len(samples),
    )
    await diagnostics.publish_database_status(
        "connected",
        database=store.database,
        url=settings.database.url,
        migrated_pv_rows=migrated_pv,
        migrated_load_rows=migrated_load,
        migrated_load_forecast_rows=migrated_load_forecast,
        legacy_backfill_status=backfill_result.status if backfill_result else ("error" if backfill_error else None),
        legacy_backfill_source_rows=backfill_result.source_rows if backfill_result else None,
        legacy_backfill_sources_updated=backfill_result.sources_updated if backfill_result else None,
        legacy_backfill_house_rows=backfill_result.house_rows if backfill_result else None,
        legacy_backfill_background_rows=backfill_result.background_rows if backfill_result else None,
        legacy_backfill_skipped_rows=backfill_result.skipped_rows if backfill_result else None,
        legacy_backfill_start_utc=(
            backfill_result.source_start_utc.isoformat()
            if backfill_result and backfill_result.source_start_utc
            else None
        ),
        legacy_backfill_end_utc=(
            backfill_result.source_end_utc.isoformat()
            if backfill_result and backfill_result.source_end_utc
            else None
        ),
        legacy_backfill_error=backfill_error,
    )
    history = BackgroundLoadHistory(path=None, samples=samples)
    await _run_app(settings, client, stop_event, store=store, history=history)


async def _run_app(
    settings: Settings,
    client: HomeAssistantClient,
    stop_event: asyncio.Event,
    *,
    store: EnergyManagerStore | None,
    history: BackgroundLoadHistory | None,
) -> None:
    load_service = BackgroundLoadService(client, history=history, store=store)
    if settings.pv.forecast_enabled:
        async with OpenMeteoClient() as meteo_client:
            pv_service = PvForecastService(client, meteo_client, store=store)
            planner_service = ShadowPlannerService(
                client,
                load_service,
                pv_service,
                actuator_registry=ActuatorRegistry(settings),
            )
            app = EnergyManagerApp(
                settings,
                client,
                pv_forecast_service=pv_service,
                background_load_service=load_service,
                shadow_planner_service=planner_service,
            )
            await app.run(stop_event)
        return

    planner_service = ShadowPlannerService(
        client,
        load_service,
        None,
        actuator_registry=ActuatorRegistry(settings),
    )
    app = EnergyManagerApp(
        settings,
        client,
        background_load_service=load_service,
        shadow_planner_service=planner_service,
    )
    await app.run(stop_event)


def main() -> None:
    """Synchronous process entrypoint."""
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
