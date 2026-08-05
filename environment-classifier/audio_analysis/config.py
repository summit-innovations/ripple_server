"""
Central configuration for the audio analysis pipeline.

This module is the single place where tunable numbers live. Feature extraction
code and classifier code should never contain inline magic numbers -- they
should import the relevant section from here. This keeps two kinds of future
work cheap:

  * Retuning an existing environment's detection accuracy -> edit a threshold
    here, nothing else.
  * Adding a brand new environment -> add a new *Thresholds class here and a
    matching branch in classifier.py. feature_extractor.py never changes.

Grouped into small dataclasses (rather than one flat namespace) so each
environment's tuning knobs are easy to find and reason about independently.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioConfig:
    """Signal-processing parameters shared by every feature computation."""

    #: Fixed sample rate the whole pipeline standardizes on. Determined by
    #: inspecting the project's actual microphone recordings (all captured at
    #: 16 kHz mono). Any input clip is resampled to this rate on load so every
    #: downstream feature is comparable regardless of the source file's native
    #: rate.
    SAMPLE_RATE: int = 16000

    #: Expected clip length. Not strictly enforced everywhere, but used to
    #: size framing windows sensibly for a "2 seconds of context" clip.
    CLIP_DURATION_S: float = 2.0

    #: STFT window size in samples. 1024 samples @ 16kHz = 64ms, a reasonable
    #: balance of frequency resolution vs. time resolution for room/ambient
    #: acoustic analysis (as opposed to e.g. pitch-tracking, which would want
    #: a longer window).
    N_FFT: int = 1024

    #: STFT hop size in samples (256 = 75% overlap at N_FFT=1024). Smaller
    #: hops give smoother frame-to-frame features at higher compute cost.
    HOP_LENGTH: int = 256

    #: Analysis window length passed to librosa.stft; kept equal to N_FFT.
    WIN_LENGTH: int = 1024

    #: Frame size (in samples) used for short-term energy framing (e.g.
    #: short_term_energy_variance, noise floor estimation). 480 samples @
    #: 16kHz = 30ms, a standard short-term analysis window for speech/audio.
    SHORT_TERM_FRAME_LENGTH: int = 480

    #: Hop size for the short-term energy framing above (240 samples = 50%
    #: overlap).
    SHORT_TERM_HOP_LENGTH: int = 240

    #: Small constant added before divisions/logs to avoid division-by-zero
    #: and log(0) on digital silence.
    EPSILON: float = 1e-10


@dataclass(frozen=True)
class SpeechBand:
    """Frequency band conventionally associated with speech intelligibility."""

    #: Lower edge of the speech band in Hz. Below this is mostly room rumble,
    #: HVAC, traffic, and other low-frequency noise rather than voice content.
    LOW_HZ: float = 300.0

    #: Upper edge of the speech band in Hz. Most speech energy and
    #: intelligibility-critical content sits below this; above it is mostly
    #: sibilance, clatter, and other high-frequency texture.
    HIGH_HZ: float = 3400.0


@dataclass(frozen=True)
class NoiseEstimationConfig:
    """
    Parameters for the non-ML speech/noise heuristics in feature_extractor.py.

    Assumption underlying all of these: within a single 2-second clip, the
    background noise level is roughly stationary (it doesn't ramp up or down
    dramatically), so a low percentile of the short-term energy envelope is a
    reasonable proxy for "the quiet parts" and a high percentile is a
    reasonable proxy for "the loud/active parts". This is a coarse heuristic,
    not a statistically rigorous noise model -- documented here so future
    readers know its limits.
    """

    #: Percentile of the short-term energy envelope used to estimate the
    #: noise floor (the quietest recurring level in the clip).
    NOISE_FLOOR_PERCENTILE: float = 10.0

    #: Percentile of the short-term energy envelope used to estimate the
    #: "signal" level for SNR purposes.
    SIGNAL_PERCENTILE: float = 90.0

    #: A frame counts as "active" (above the noise floor) for speech_fraction
    #: purposes once its energy exceeds noise_floor * this multiplicative
    #: margin. Expressed as a ratio rather than an additive dB offset to
    #: behave consistently across quiet and loud recordings.
    ACTIVE_FRAME_MARGIN_RATIO: float = 2.0

    #: A frame counts as "speech-band-dominated" once more than this fraction
    #: of its spectral energy falls within SpeechBand [LOW_HZ, HIGH_HZ].
    #: Combined with the activity gate above to estimate speech_fraction.
    SPEECH_BAND_ENERGY_FRACTION: float = 0.5


@dataclass(frozen=True)
class SilenceThresholds:
    """Thresholds for recognizing a clip as containing essentially no sound."""

    #: RMS amplitude (0-1 float scale) below which a clip is considered
    #: silent. Chosen well above digital-zero to also catch mic self-noise
    #: and very faint room tone.
    MAX_RMS: float = 0.01

    #: Peak amplitude below which a clip is considered silent, as a backstop
    #: in case a single loud transient pushes RMS up while the clip is
    #: otherwise silent (rare, but cheap to guard against).
    MAX_PEAK: float = 0.05


@dataclass(frozen=True)
class SpeechThresholds:
    """Thresholds for recognizing a clip as clear, single-voice speech."""

    #: Minimum harmonic/(harmonic+percussive) ratio. Clean voiced speech is
    #: dominated by harmonic (tonal) content from vocal fold vibration.
    MIN_HARMONIC_RATIO: float = 0.55

    #: Minimum fraction of frames classified as speech-active (see
    #: NoiseEstimationConfig). Clear speech should occupy a meaningful
    #: portion of the clip, not just a brief blip.
    MIN_SPEECH_FRACTION: float = 0.25

    #: Spectral centroid range (Hz) typical of voiced speech energy. Too low
    #: suggests low-frequency rumble/hum; too high suggests hiss/sibilance-
    #: dominated or non-speech content.
    MIN_SPECTRAL_CENTROID_HZ: float = 300.0
    MAX_SPECTRAL_CENTROID_HZ: float = 3500.0

    #: Maximum spectral flatness. Speech has strong formant structure (peaky
    #: spectrum), so flatness (noise-like uniformity) should be low.
    MAX_SPECTRAL_FLATNESS: float = 0.35

    #: Maximum onset rate (onsets/sec). Clean single-voice speech has fewer,
    #: smoother transitions than a crowd of overlapping talkers or clatter.
    MAX_ONSET_RATE: float = 4.0


@dataclass(frozen=True)
class CrowdedThresholds:
    """Thresholds for recognizing a clip as a busy, multi-source space."""

    #: Minimum short-term energy variance. Crowded spaces (overlapping
    #: talkers, clattering dishes, movement) fluctuate in loudness far more
    #: than a single steady voice or ambient hum.
    MIN_ENERGY_VARIANCE: float = 0.0008

    #: Minimum spectral flatness OR minimum onset rate (checked as an "or")
    #: -- crowded spaces tend to be either noise-like (many overlapping
    #: voices blur into broadband noise) or event-dense (frequent clatter/
    #: chatter onsets), not necessarily both at once.
    MIN_SPECTRAL_FLATNESS: float = 0.25
    MIN_ONSET_RATE: float = 3.0

    #: Maximum harmonic ratio. A crowded space's mixture of many overlapping,
    #: uncorrelated sound sources is less purely harmonic than one clear
    #: voice.
    MAX_HARMONIC_RATIO: float = 0.6


@dataclass(frozen=True)
class IngestionConfig:
    """
    Filesystem wiring for the batch and realtime deployment scripts.

    Kept separate from the DSP tuning knobs above: these are deployment/
    environment paths, not signal-processing parameters, and are the ones
    most likely to need overriding per-machine.
    """

    #: Source directory of static, pre-recorded training clips (raw audio).
    AUDIO_TRAINING_DIR: Path = Path("/srv/projects/ripple_server/audio-uploader/training-uploads")

    #: Source directory that some external process drops/overwrites live
    #: audio clips into. This project only watches it -- it does not write
    #: here.
    AUDIO_REALTIME_DIR: Path = Path("/srv/projects/ripple_server/audio-uploader/realtime-uploads")

    #: Destination directory for one JSON result file per training clip.
    RESULTS_TRAINING_DIR: Path = Path("/srv/projects/ripple_server/environment-uploader/training-uploads")

    #: Destination directory for the realtime daemon's single "latest result"
    #: file.
    RESULTS_REALTIME_DIR: Path = Path("/srv/projects/ripple_server/environment-uploader/realtime-uploads")

    #: Filename of the realtime daemon's single result file, overwritten in
    #: place on every newly detected signal.
    REALTIME_RESULT_FILENAME: str = "latest.json"

    #: How often (seconds) the realtime daemon polls AUDIO_REALTIME_DIR for a
    #: new or changed file. Lower = more responsive to new signals, at the
    #: cost of more filesystem checks while idle; 0.5s is responsive enough
    #: for a 2-second-clip cadence without being wasteful.
    POLL_INTERVAL_S: float = 0.5
