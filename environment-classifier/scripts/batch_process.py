"""
One-shot batch processor: run the pipeline over every training clip and
write one JSON result per clip.

Reads from IngestionConfig.AUDIO_TRAINING_DIR, writes to
IngestionConfig.RESULTS_TRAINING_DIR. Re-running is idempotent -- every file
is reprocessed and its result overwritten each time; there is no
skip-if-exists logic, since the training set is static and a full rerun is
cheap.

Usage:
    python -m scripts.batch_process
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from audio_analysis import analyze_file
from audio_analysis.config import IngestionConfig
from audio_analysis.serialization import to_result_dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_cfg = IngestionConfig()


def _write_json_atomic(path, payload: str) -> None:
    """Write text to `path` via a temp file + atomic rename, so readers never see a partial file."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(payload)
    os.replace(tmp_path, path)


def main() -> int:
    _cfg.RESULTS_TRAINING_DIR.mkdir(parents=True, exist_ok=True)

    source_files = sorted(_cfg.AUDIO_TRAINING_DIR.glob("*.wav"))
    if not source_files:
        logger.warning("No .wav files found in %s", _cfg.AUDIO_TRAINING_DIR)

    processed, failed = 0, 0
    for source_path in source_files:
        try:
            features, result = analyze_file(source_path)
            processed_at = datetime.now(timezone.utc).isoformat()
            payload = to_result_dict(features, result, str(source_path), processed_at)

            dest_path = _cfg.RESULTS_TRAINING_DIR / f"{source_path.stem}.json"
            _write_json_atomic(dest_path, json.dumps(payload, indent=2))

            logger.info("%s -> %s (%s)", source_path.name, dest_path.name, result.environment.value)
            processed += 1
        except Exception:
            logger.exception("Failed to process %s", source_path)
            failed += 1

    logger.info("Done: %d processed, %d failed", processed, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
