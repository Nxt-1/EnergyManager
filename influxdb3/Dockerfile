FROM influxdb:3.12.0-enterprise

ARG BUILD_VERSION=0.1.0
ARG BUILD_ARCH=amd64

USER root

RUN apt-get update \
    && apt-get install --no-install-recommends -y gosu jq openssl \
    && rm -rf /var/lib/apt/lists/*

COPY run.sh /run.sh
RUN chmod 0755 /run.sh

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}"

ENTRYPOINT []
CMD ["/run.sh"]
