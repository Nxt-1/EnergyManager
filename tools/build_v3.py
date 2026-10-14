"""Build the reviewed image locally, retaining TLS verification behind a supplied proxy.

Uses the current environment's proxy and optional SSL_CERT_FILE CA via a temporary
BuildKit secret. Does not push images, change Docker networking or disable verification.
"""

import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def main():
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.setdefault("DOCKER_CONFIG", str(root / ".v3-evidence/docker"))
    command = ["docker", "build", "--build-arg", "BUILD_VERSION=3.0.0b3", "--build-arg", "BUILD_ARCH=amd64"]
    hosts = set()
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        if environment.get(variable):
            command += ["--build-arg", variable]
        if variable != "NO_PROXY" and environment.get(variable):
            host = urlsplit(environment[variable]).hostname
            if host and host not in hosts:
                hosts.add(host)
                command += ["--add-host", f"{host}:{socket.gethostbyname(host)}"]
    ca = environment.get("SSL_CERT_FILE")
    if ca and Path(ca).is_file():
        command += ["--secret", f"id=pip_ca,src={ca}"]
    command += ["--tag", "energymanager:v3-review", "energymanager"]
    subprocess.run(command, cwd=root, env=environment, check=True)


if __name__ == "__main__":
    main()
