"""Ensure an isolated Windows solver does not outlive a crashed service parent."""

from __future__ import annotations

import os
from multiprocessing import parent_process
from threading import Thread
from time import sleep


def watch_parent() -> None:
    parent = parent_process()
    if parent is None:
        return

    def monitor() -> None:
        while parent.is_alive():
            sleep(1)
        os._exit(0)  # Only this isolated worker; no actuator or database exists here.

    Thread(target=monitor, daemon=True, name="solver-parent-watch").start()
