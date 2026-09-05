# ripple

Classical-DSP audio environment recognition, built as a foundation for
hearing-assistance research.

## Architecture

The pipeline is split into two independent stages:

1. **Feature extraction** (`audio_analysis/feature_extractor.py`) turns a
   2-second mono clip into an `AudioFeatures` object -- a comprehensive,
   interpretable snapshot of its acoustic properties (energy, spectral
   shape, harmonic/percussive balance, estimated SNR, etc). This stage has
   no concept of "environments" and never imports the classifier.
2. **Classification** (`audio_analysis/classifier.py`) consumes an
   `AudioFeatures` object and produces an `Environment` decision using
   transparent, rule-based logic. It never touches raw audio.

This split means adding a new environment (Restaurant, Classroom, Office,
Car, Outdoors, Wind, TV, Meeting, Church, Grocery Store, ...) is normally
just:
1. A new `<Name>Thresholds` block in `audio_analysis/config.py`.
2. A new rule function + branch in `audio_analysis/classifier.py`.

No pretrained audio scene classifiers are used anywhere -- only classical
signal processing via numpy/scipy/librosa/soundfile.

## Layout

```
audio_analysis/
    config.py            All tunable thresholds/paths, grouped by purpose.
    feature_types.py      AudioFeatures dataclass, documented field-by-field.
    feature_extractor.py  Audio -> AudioFeatures. Never imports classifier.py.
    classifier.py         AudioFeatures -> Environment + reasoning.
    analyzer.py            Orchestrates the two stages above.
    serialization.py       AudioFeatures + result -> JSON-safe dict.
scripts/
    demo.py                 Analyze one file, print everything.
    batch_process.py         One-shot batch run over the training set.
    realtime_watcher.py       Long-running daemon for live signals.
deploy/
    environment-realtime-watcher.service   systemd unit for the daemon.
tests/
    ...                      pytest suite using synthetic signals.
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

Analyze a single clip:
```bash
python -m scripts.demo /opt/audio-uploader/training-uploads/0.wav
```

Batch-process the training set (`/opt/audio-uploader/training-uploads/` ->
`/opt/environment-uploader/training-uploads/`, one JSON result per clip):
```bash
python -m scripts.batch_process
```

Run the realtime watcher in the foreground (watches
`/opt/audio-uploader/realtime-uploads/`, overwrites
`/opt/environment-uploader/realtime-uploads/latest.json` on each new signal;
stop with Ctrl+C):
```bash
python -m scripts.realtime_watcher
```

## Running as a service

The realtime watcher is meant to run continuously and recover from crashes
on its own, via systemd:

```bash
sudo cp deploy/environment-realtime-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now environment-realtime-watcher.service
sudo systemctl status environment-realtime-watcher.service
```

## Tests

```bash
pytest -q
```

Tests use synthetically generated signals (silence, tones, noise,
speech-like bursts) so they don't depend on any external audio files.
