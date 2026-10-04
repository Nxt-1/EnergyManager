#!/usr/bin/env bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"
BASE_DIR="/data/influxdb3"
DATA_DIR="${BASE_DIR}/data"
PLUGIN_DIR="${BASE_DIR}/plugins"
SECRET_DIR="${BASE_DIR}/secrets"
SESSION_SECRET_FILE="${SECRET_DIR}/webui-session-secret"
JWT_PRIVATE_KEY_FILE="${SECRET_DIR}/jwt-private-key.pem"

if [[ ! -f "${OPTIONS_FILE}" ]]; then
    echo "ERROR: Home Assistant options file is missing."
    exit 1
fi

LICENSE_EMAIL="$(jq -r '.license_email // empty' "${OPTIONS_FILE}")"
if [[ -z "${LICENSE_EMAIL}" ]]; then
    echo "ERROR: Configure the At-Home license email before starting the app."
    exit 1
fi

mkdir -p "${DATA_DIR}" "${PLUGIN_DIR}" "${SECRET_DIR}"

if [[ ! -s "${SESSION_SECRET_FILE}" ]]; then
    openssl rand -base64 32 > "${SESSION_SECRET_FILE}"
    chmod 0600 "${SESSION_SECRET_FILE}"
fi

if [[ ! -s "${JWT_PRIVATE_KEY_FILE}" ]]; then
    openssl genrsa -traditional -out "${JWT_PRIVATE_KEY_FILE}" 2048
    chmod 0600 "${JWT_PRIVATE_KEY_FILE}"
fi

chown -R 1500:1500 "${BASE_DIR}"

WEBUI_SESSION_SECRET="$(cat "${SESSION_SECRET_FILE}")"
JWT_PRIVATE_KEY="$(cat "${JWT_PRIVATE_KEY_FILE}")"

export INFLUXDB3_LICENSE_EMAIL="${LICENSE_EMAIL}"
export INFLUXDB3_LICENSE_TYPE="home"
export INFLUXDB3_NUM_CORES="2"
export INFLUXDB3_LOG_FILTER="info"

echo "Starting InfluxDB 3 Enterprise 3.12.0"
echo "Storage: persistent Home Assistant /data volume"
echo "CPU limit: 2 cores (At-Home license)"
echo "Explorer UI: enabled on port 8181"
echo "Authentication: username/password setup enabled"

exec gosu influxdb3:influxdb3 \
    influxdb3 serve \
    --node-id="ha-node" \
    --cluster-id="energy-manager-cluster" \
    --object-store="file" \
    --data-dir="${DATA_DIR}" \
    --plugin-dir="${PLUGIN_DIR}" \
    --mode="all,webui" \
    --webui-session-secret="${WEBUI_SESSION_SECRET}" \
    --user-auth-type="basic" \
    --jwt-key-id="ha-influxdb3" \
    --jwt-private-key="${JWT_PRIVATE_KEY}"
