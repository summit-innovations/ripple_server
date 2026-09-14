"""
Synthetic signal fixtures shared across the test suite.

Using synthetic signals (rather than the project's real mic recordings)
keeps the test suite self-contained and independent of any external
filesystem paths, while still exercising every feature/rule with signals
that have known, designed-in characteristics.
"""

import numpy as np
import pytest

SR = 16000
DURATION_S = 2.0


def _time_axis(sr: int = SR, duration: float = DURATION_S) -> np.ndarray:
    return np.linspace(0, duration, int(sr * duration), endpoint=False)


@pytest.fixture
def sample_rate() -> int:
    return SR


@pytest.fixture
def silence_signal() -> np.ndarray:
    """Near-zero amplitude signal with a touch of simulated mic self-noise."""
    rng = np.random.default_rng(0)
    return (rng.normal(scale=1e-4, size=int(SR * DURATION_S))).astype(np.float64)


@pytest.fixture
def tone_signal() -> np.ndarray:
    """A single steady 440Hz sine tone: maximally harmonic, minimally flat."""
    t = _time_axis()
    return (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float64)


@pytest.fixture
def white_noise_signal() -> np.ndarray:
    """Broadband white noise: maximally flat, minimally harmonic."""
    rng = np.random.default_rng(1)
    return (0.3 * rng.standard_normal(int(SR * DURATION_S))).astype(np.float64)


@pytest.fixture
def speech_like_signal() -> np.ndarray:
    """
    A synthetic "clear speech" stand-in: a harmonic stack in the voice range
    (fundamental + 3 overtones) gated by a slow syllable-like amplitude
    envelope, so it has speech-band harmonic energy, a few discrete
    "syllable" onsets, and periods of near-silence between them -- without
    depending on any real recorded voice.
    """
    t = _time_axis()
    fundamental = 150.0
    harmonics = sum(
        (1.0 / n) * np.sin(2 * np.pi * fundamental * n * t) for n in (1, 2, 3, 4)
    )
    harmonics /= np.max(np.abs(harmonics))

    # Raised-cosine syllable envelope: ~3 "words" over the 2s clip, separated
    # by brief gaps, mimicking speech's bursty activity pattern.
    envelope = np.zeros_like(t)
    syllable_starts = [0.1, 0.6, 1.1, 1.6]
    syllable_len = 0.35
    for start in syllable_starts:
        mask = (t >= start) & (t < start + syllable_len)
        local_t = (t[mask] - start) / syllable_len
        envelope[mask] = 0.5 * (1 - np.cos(2 * np.pi * local_t))

    signal = 0.6 * harmonics * envelope
    return signal.astype(np.float64)


@pytest.fixture
def crowded_signal() -> np.ndarray:
    """
    A synthetic "crowded space" stand-in: several unsynchronized tones
    (many overlapping "voices") plus random impulsive noise bursts
    ("clatter"), with a randomly varying amplitude envelope -- producing
    high energy variance, a dense spectrum, and a high onset rate, without
    being dominated by any single harmonic source.
    """
    rng = np.random.default_rng(2)
    t = _time_axis()
    n = len(t)

    voices = sum(
        0.15 * np.sin(2 * np.pi * freq * t + phase)
        for freq, phase in [(180, 0.3), (240, 1.7), (310, 2.9), (420, 0.6)]
    )

    clatter = np.zeros(n)
    n_bursts = 25
    burst_len = int(0.01 * SR)
    for _ in range(n_bursts):
        start = rng.integers(0, n - burst_len)
        clatter[start : start + burst_len] += rng.standard_normal(burst_len) * 0.4

    # Slowly varying loudness so short-term energy variance is high.
    slow_mod = 0.5 + 0.5 * np.sin(2 * np.pi * 1.5 * t + rng.uniform(0, np.pi))

    signal = (voices + clatter) * slow_mod
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = 0.8 * signal / peak
    return signal.astype(np.float64)
