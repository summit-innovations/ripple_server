"""Tests for the JSON result shape shared by batch_process.py and realtime_watcher.py."""

import json
from dataclasses import fields

from audio_analysis.classifier import ClassificationResult, Environment
from audio_analysis.feature_types import AudioFeatures
from audio_analysis.serialization import to_result_dict

_FEATURES = AudioFeatures(
    rms=0.1,
    peak=0.3,
    dynamic_range=10.0,
    spectral_centroid=1000.0,
    spectral_bandwidth=800.0,
    spectral_rolloff=2000.0,
    spectral_flatness=0.3,
    zero_crossing_rate=0.05,
    short_term_energy_variance=0.0005,
    harmonic_energy=0.05,
    percussive_energy=0.05,
    harmonic_ratio=0.5,
    speech_fraction=0.1,
    noise_floor=0.01,
    estimated_snr=10.0,
    spectral_flux=0.1,
    spectral_contrast_mean=20.0,
    onset_rate=2.0,
    low_freq_energy_ratio=0.3,
    mid_freq_energy_ratio=0.4,
    high_freq_energy_ratio=0.3,
    crest_factor=3.0,
    sample_rate=16000,
    duration_s=2.0,
)
_RESULT = ClassificationResult(environment=Environment.CLEAR_SPEECH, reasoning="test reasoning")


def test_result_dict_contains_all_feature_fields():
    payload = to_result_dict(_FEATURES, _RESULT, "some/file.wav", "2026-07-26T00:00:00+00:00")
    for f in fields(AudioFeatures):
        assert f.name in payload


def test_result_dict_environment_is_plain_string():
    payload = to_result_dict(_FEATURES, _RESULT, "some/file.wav", "2026-07-26T00:00:00+00:00")
    assert payload["environment"] == "clear_speech"
    assert isinstance(payload["environment"], str)


def test_result_dict_is_json_serializable():
    payload = to_result_dict(_FEATURES, _RESULT, "some/file.wav", "2026-07-26T00:00:00+00:00")
    serialized = json.dumps(payload)
    round_tripped = json.loads(serialized)
    assert round_tripped["source_file"] == "some/file.wav"
    assert round_tripped["reasoning"] == "test reasoning"
