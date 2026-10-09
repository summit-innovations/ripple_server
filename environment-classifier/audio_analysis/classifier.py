"""
Environment classification: AudioFeatures -> ClassificationResult.

This module is the only place that knows about environment labels. It
consumes AudioFeatures objects produced by feature_extractor.py and never the
other way around -- feature_extractor.py has no knowledge of this module.

The classifier here is intentionally simple, transparent, rule-based logic:
a short ordered chain of threshold checks, with every threshold pulled from
config.py. This is a placeholder architecture meant to be replaced or
augmented with more sophisticated logic (a learned model, a larger rule set,
per-environment scoring) later without requiring any change to how features
are computed.

Adding a new environment (Restaurant, Classroom, Office, ...) means:
  1. Add a `<Name>Thresholds` dataclass to config.py.
  2. Add a `_looks_like_<name>(features) -> bool` function here.
  3. Add a branch to `classify()`.
No change to feature_extractor.py or feature_types.py is required unless the
new environment genuinely needs a feature that doesn't exist yet.
"""

from dataclasses import dataclass
from enum import Enum

from .config import CrowdedThresholds, SilenceThresholds, SpeechThresholds
from .feature_types import AudioFeatures

_silence_cfg = SilenceThresholds()
_speech_cfg = SpeechThresholds()
_crowded_cfg = CrowdedThresholds()


class Environment(str, Enum):
    """Recognized environment labels. Extend this as new environments are added."""

    SILENCE = "silence"
    CLEAR_SPEECH = "clear_speech"
    CROWDED_SPACE = "crowded_space"


@dataclass(frozen=True)
class ClassificationResult:
    """The classifier's decision, plus a human-readable trace of why."""

    environment: Environment

    #: Explanation of which rule matched (or why nothing matched), for
    #: transparency and debugging -- this is a rule-based system specifically
    #: so its decisions can be inspected, not just trusted.
    reasoning: str


def classify(features: AudioFeatures) -> ClassificationResult:
    """
    Classify a clip's environment from its extracted features.

    Rules are checked in order and the first match wins:
      1. Silence -- near-zero energy, checked first since it short-circuits
         every other rule (a silent clip trivially fails all of them anyway,
         but checking explicitly keeps the reasoning clear).
      2. Clear Speech -- harmonic, speech-band-dominated, low-flatness audio
         with few onsets: characteristic of one clear voice.
      3. Crowded Space -- energetically variable, noise-like or event-dense,
         less purely harmonic than clean speech: characteristic of many
         overlapping sound sources.

    If none of the rules match confidently, there is no "Unknown" escape
    hatch: every clip is forced into the environment whose thresholds it
    comes closest to satisfying, via `_closest_match`.
    """
    if _looks_like_silence(features):
        return ClassificationResult(
            environment=Environment.SILENCE,
            reasoning=(
                f"rms={features.rms:.4f} <= {_silence_cfg.MAX_RMS} and "
                f"peak={features.peak:.4f} <= {_silence_cfg.MAX_PEAK}"
            ),
        )

    if _looks_like_clear_speech(features):
        return ClassificationResult(
            environment=Environment.CLEAR_SPEECH,
            reasoning=(
                f"harmonic_ratio={features.harmonic_ratio:.2f} >= "
                f"{_speech_cfg.MIN_HARMONIC_RATIO}, "
                f"speech_fraction={features.speech_fraction:.2f} >= "
                f"{_speech_cfg.MIN_SPEECH_FRACTION}, "
                f"centroid={features.spectral_centroid:.0f}Hz in "
                f"[{_speech_cfg.MIN_SPECTRAL_CENTROID_HZ:.0f}, "
                f"{_speech_cfg.MAX_SPECTRAL_CENTROID_HZ:.0f}]Hz, "
                f"flatness={features.spectral_flatness:.2f} <= "
                f"{_speech_cfg.MAX_SPECTRAL_FLATNESS}, "
                f"onset_rate={features.onset_rate:.2f}/s <= {_speech_cfg.MAX_ONSET_RATE}/s"
            ),
        )

    if _looks_like_crowded_space(features):
        return ClassificationResult(
            environment=Environment.CROWDED_SPACE,
            reasoning=(
                f"energy_variance={features.short_term_energy_variance:.5f} >= "
                f"{_crowded_cfg.MIN_ENERGY_VARIANCE}, "
                f"(flatness={features.spectral_flatness:.2f} >= "
                f"{_crowded_cfg.MIN_SPECTRAL_FLATNESS} or "
                f"onset_rate={features.onset_rate:.2f}/s >= {_crowded_cfg.MIN_ONSET_RATE}/s), "
                f"harmonic_ratio={features.harmonic_ratio:.2f} <= "
                f"{_crowded_cfg.MAX_HARMONIC_RATIO}"
            ),
        )

    return _closest_match(features)


def _looks_like_silence(features: AudioFeatures) -> bool:
    """True if the clip has essentially no acoustic energy."""
    return features.rms <= _silence_cfg.MAX_RMS and features.peak <= _silence_cfg.MAX_PEAK


def _looks_like_clear_speech(features: AudioFeatures) -> bool:
    """True if the clip looks like one clear voice: harmonic, speech-band, low-flatness, few onsets."""
    return (
        features.harmonic_ratio >= _speech_cfg.MIN_HARMONIC_RATIO
        and features.speech_fraction >= _speech_cfg.MIN_SPEECH_FRACTION
        and _speech_cfg.MIN_SPECTRAL_CENTROID_HZ
        <= features.spectral_centroid
        <= _speech_cfg.MAX_SPECTRAL_CENTROID_HZ
        and features.spectral_flatness <= _speech_cfg.MAX_SPECTRAL_FLATNESS
        and features.onset_rate <= _speech_cfg.MAX_ONSET_RATE
    )


def _looks_like_crowded_space(features: AudioFeatures) -> bool:
    """True if the clip looks like a busy, multi-source space: variable, noisy/event-dense, less harmonic."""
    noisy_or_bursty = (
        features.spectral_flatness >= _crowded_cfg.MIN_SPECTRAL_FLATNESS
        or features.onset_rate >= _crowded_cfg.MIN_ONSET_RATE
    )
    return (
        features.short_term_energy_variance >= _crowded_cfg.MIN_ENERGY_VARIANCE
        and noisy_or_bursty
        and features.harmonic_ratio <= _crowded_cfg.MAX_HARMONIC_RATIO
    )


def _undershoot(value: float, min_threshold: float) -> float:
    """How far `value` falls below a `>=` threshold, as a fraction of the threshold. 0 if satisfied."""
    if value >= min_threshold:
        return 0.0
    return (min_threshold - value) / max(abs(min_threshold), 1e-10)


def _overshoot(value: float, max_threshold: float) -> float:
    """How far `value` rises above a `<=` threshold, as a fraction of the threshold. 0 if satisfied."""
    if value <= max_threshold:
        return 0.0
    return (value - max_threshold) / max(abs(max_threshold), 1e-10)


def _silence_distance(features: AudioFeatures) -> float:
    """Total normalized violation of the silence thresholds; 0 means the rule is satisfied."""
    return _overshoot(features.rms, _silence_cfg.MAX_RMS) + _overshoot(
        features.peak, _silence_cfg.MAX_PEAK
    )


def _clear_speech_distance(features: AudioFeatures) -> float:
    """Total normalized violation of the clear-speech thresholds; 0 means the rule is satisfied."""
    return (
        _undershoot(features.harmonic_ratio, _speech_cfg.MIN_HARMONIC_RATIO)
        + _undershoot(features.speech_fraction, _speech_cfg.MIN_SPEECH_FRACTION)
        + _undershoot(features.spectral_centroid, _speech_cfg.MIN_SPECTRAL_CENTROID_HZ)
        + _overshoot(features.spectral_centroid, _speech_cfg.MAX_SPECTRAL_CENTROID_HZ)
        + _overshoot(features.spectral_flatness, _speech_cfg.MAX_SPECTRAL_FLATNESS)
        + _overshoot(features.onset_rate, _speech_cfg.MAX_ONSET_RATE)
    )


def _crowded_space_distance(features: AudioFeatures) -> float:
    """Total normalized violation of the crowded-space thresholds; 0 means the rule is satisfied."""
    noisy_or_bursty_violation = min(
        _undershoot(features.spectral_flatness, _crowded_cfg.MIN_SPECTRAL_FLATNESS),
        _undershoot(features.onset_rate, _crowded_cfg.MIN_ONSET_RATE),
    )
    return (
        _undershoot(features.short_term_energy_variance, _crowded_cfg.MIN_ENERGY_VARIANCE)
        + noisy_or_bursty_violation
        + _overshoot(features.harmonic_ratio, _crowded_cfg.MAX_HARMONIC_RATIO)
    )


def _closest_match(features: AudioFeatures) -> ClassificationResult:
    """
    Fallback for a clip that satisfied none of the rules above.

    Scores each environment by how far (as a normalized, summed fraction
    over its own thresholds) the clip's features are from satisfying that
    rule, and returns the environment with the smallest total violation --
    i.e. whichever rule the clip came closest to matching. Ties keep the
    same silence > clear speech > crowded space priority used above.
    """
    candidates = (
        (Environment.SILENCE, _silence_distance(features)),
        (Environment.CLEAR_SPEECH, _clear_speech_distance(features)),
        (Environment.CROWDED_SPACE, _crowded_space_distance(features)),
    )
    environment, distance = min(candidates, key=lambda candidate: candidate[1])
    return ClassificationResult(
        environment=environment,
        reasoning=(
            f"No rule matched confidently; falling back to the closest match "
            f"({environment.value}, total normalized threshold violation={distance:.3f})."
        ),
    )
