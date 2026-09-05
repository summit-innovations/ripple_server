"""
Long-running realtime watcher daemon.

Watches IngestionConfig.AUDIO_REALTIME_DIR forever for a new or changed
audio file, and whenever one is detected, runs the analysis pipeline and
atomically overwrites a single "latest result" JSON file in
IngestionConfig.RESULTS_REALTIME_DIR.

Designed to run under systemd (see deploy/environment-realtime-watcher.service)
with Restart=always, which handles the "process died outright" case. This
script's own responsibility is to survive routine problems -- a bad/partial
audio file, a transient read error -- without dying, since a single
malformed file should never take the whole daemon down.

Usage:
    python -m scripts.realtime_watcher
Stops cleanly on SIGINT/SIGTERM.
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from audio_analysis import analyze_file
from audio_analysis.config import IngestionConfig
from audio_analysis.serialization import to_result_dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_cfg = IngestionConfig()

# (filename, mtime_ns, size) -- cheap enough to stat every poll, specific
# enough to catch both "new file appeared" and "existing file overwritten".
Fingerprint = tuple[str, int, int]


def find_latest_file(directory: Path) -> Path | None:
    """Return the most recently modified regular file in `directory`, or None if empty."""
    candidates = [p for p in directory.iterdir() if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime_ns)


def fingerprint(path: Path) -> Fingerprint:
    """A cheap identity for a file's current content: name + mtime + size."""
    stat = path.stat()
    return (path.name, stat.st_mtime_ns, stat.st_size)


def detect_new_signal(
    directory: Path, last_fingerprint: Fingerprint | None
) -> tuple[Path, Fingerprint] | None:
    """
    Check `directory` for a signal that hasn't been processed yet.

    Returns (path, fingerprint) if the most recently modified file's
    fingerprint differs from `last_fingerprint` (covers both a brand new
    filename and an existing filename overwritten with new content), or None
    if there's nothing new to process.
    """
    latest = find_latest_file(directory)
    if latest is None:
        return None
    fp = fingerprint(latest)
    if fp == last_fingerprint:
        return None
    return latest, fp


def write_result_atomic(directory: Path, filename: str, payload: dict) -> None:
    """Write `payload` as JSON to directory/filename via temp file + atomic rename."""
    directory.mkdir(parents=True, exist_ok=True)
    dest_path = directory / filename
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2))
    os.replace(tmp_path, dest_path)


class _ShutdownRequested(Exception):
    """Raised from the signal handler to unwind the poll loop cleanly."""


def _install_signal_handlers() -> None:
    def _handler(signum, _frame):
        logger.info("Received signal %s, shutting down.", signal.Signals(signum).name)
        raise _ShutdownRequested()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def run() -> None:
    """Poll forever until SIGTERM/SIGINT, processing each newly detected signal."""
    _install_signal_handlers()
    last_fingerprint: Fingerprint | None = None
    logger.info("Watching %s (poll interval %.2fs)", _cfg.AUDIO_REALTIME_DIR, _cfg.POLL_INTERVAL_S)

    while True:
        try:
            detected = detect_new_signal(_cfg.AUDIO_REALTIME_DIR, last_fingerprint)
            if detected is not None:
                path, fp = detected
                features, result = analyze_file(path)
                processed_at = datetime.now(timezone.utc).isoformat()
                payload = to_result_dict(features, result, str(path), processed_at)
                write_result_atomic(_cfg.RESULTS_REALTIME_DIR, _cfg.REALTIME_RESULT_FILENAME, payload)
                last_fingerprint = fp
                logger.info("Processed %s -> %s", path.name, result.environment.value)
        except _ShutdownRequested:
            break
        except Exception:
            # A single bad file or transient error must not kill the daemon --
            # systemd's Restart=always is the backstop for a fatal crash, but
            # routine problems should just be logged and skipped.
            logger.exception("Error while processing realtime signal; continuing.")

        try:
            time.sleep(_cfg.POLL_INTERVAL_S)
        except _ShutdownRequested:
            break

    logger.info("Stopped.")


if __name__ == "__main__":
    run()
    sys.exit(0)
