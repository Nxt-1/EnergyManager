FROM python:3.13-alpine3.22

ARG BUILD_VERSION=dev
ARG BUILD_ARCH=amd64

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.source="https://github.com/Nxt-1/EnergyManager" \
    org.opencontainers.image.description="Predictive home energy manager for Home Assistant"

ENV \
    ENERGY_MANAGER_VERSION="${BUILD_VERSION}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
RUN python -c "import energymanager.app, energymanager.database, energymanager.economics, energymanager.legacy_influx, energymanager.load_backtest, energymanager.load_forecast, energymanager.load_service, energymanager.milp_planner, energymanager.planner, energymanager.planner_service, energymanager.pv_forecast, energymanager.pv_service"

CMD ["python", "-m", "energymanager"]
