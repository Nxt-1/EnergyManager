"""Process entrypoint for the Energy Manager Home Assistant app."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from . import __version__
from .app import EnergyManagerApp
from .config import ConfigurationError, Settings
from .ha_client import HomeAssistantClient
from .load_service import BackgroundLoadService
from .open_meteo import OpenMeteoClient
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
        load_service = BackgroundLoadService(client)
        if settings.pv.forecast_enabled:
            async with OpenMeteoClient() as meteo_client:
                pv_service = PvForecastService(client, meteo_client)
                app = EnergyManagerApp(
                    settings,
                    client,
                    pv_forecast_service=pv_service,
                    background_load_service=load_service,
                )
                await app.run(stop_event)
        else:
            app = EnergyManagerApp(settings, client, background_load_service=load_service)
            await app.run(stop_event)

    logger.info("Energy Manager stopped")
    return 0


def main() -> None:
    """Synchronous process entrypoint."""
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
