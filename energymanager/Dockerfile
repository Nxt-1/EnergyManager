FROM python:3.13-slim
ARG BUILD_VERSION=4.0.4
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.source="https://github.com/Nxt-1/EnergyManager" \
      org.opencontainers.image.description="EnergyManager 4 joint EV/ESS planning and control"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps .
CMD ["python", "-m", "energymanager", "--addon", "--ingress", "--port", "8099", "--data", "/data/energymanager-v4.sqlite3"]
