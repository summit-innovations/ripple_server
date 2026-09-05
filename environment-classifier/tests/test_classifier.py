"""
Unit tests for classifier.py rule logic, using hand-constructed AudioFeatures
objects rather than real audio -- this tests the decision boundaries in
isolation, independent of whether feature extraction produces exactly these
values for any real clip.
"""

from dataclasses import replace

from audio_analysis.classifier import Environment, classify
from audio_analysis.feature_types import AudioFeatures

_BASE = AudioFeatures(
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


def test_low_energy_is_silence():
    features = replace(_BASE, rms=0.001, peak=0.01)
    result = classify(features)
    assert result.environment == Environment.SILENCE
    assert result.reasoning


def test_harmonic_speech_band_signal_is_clear_speech():
    features = replace(
        _BASE,
        rms=0.1,
        peak=0.3,
        harmonic_ratio=0.8,
        speech_fraction=0.5,
        spectral_centroid=1200.0,
        spectral_flatness=0.15,
        onset_rate=1.5,
    )
    result = classify(features)
    assert result.environment == Environment.CLEAR_SPEECH


def test_variable_noisy_low_harmonic_signal_is_crowded_space():
    features = replace(
        _BASE,
        rms=0.15,
        peak=0.4,
        harmonic_ratio=0.3,
        short_term_energy_variance=0.002,
        spectral_flatness=0.4,
        onset_rate=5.0,
    )
    result = classify(features)
    assert result.environment == Environment.CROWDED_SPACE


def test_ambiguous_signal_falls_back_to_unknown():
    features = replace(
        _BASE,
        rms=0.1,
        peak=0.3,
        harmonic_ratio=0.5,  # too low for speech, but crowded needs more than this alone
        short_term_energy_variance=0.0001,  # too low for crowded
        spectral_flatness=0.1,
        onset_rate=1.0,
    )
    result = classify(features)
    assert result.environment == Environment.UNKNOWN


def test_silence_rule_is_checked_first():
    """Even if other fields look speech-like, near-zero energy wins."""
    features = replace(
        _BASE,
        rms=0.001,
        peak=0.01,
        harmonic_ratio=0.9,
        speech_fraction=0.9,
        spectral_flatness=0.05,
    )
    result = classify(features)
    assert result.environment == Environment.SILENCE
