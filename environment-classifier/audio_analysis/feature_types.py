"""
Data types produced by the feature extraction stage.

AudioFeatures is the contract between feature_extractor.py and classifier.py.
It is intentionally a flat, frozen, plain-data structure: adding a new field
here (and computing it in feature_extractor.py) is how the pipeline grows
richer over time, while classifier.py simply gains access to a new signal it
can use in its rules without either module needing to know about the other's
internals.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioFeatures:
    """
    A comprehensive, interpretable snapshot of a 2-second audio clip's
    acoustic characteristics, computed with classical DSP (no learned
    models). Every field is a scalar summary (typically mean-pooled across
    STFT frames) so the object is cheap to log, store, and reason about.
    """

    # ---- Energy -----------------------------------------------------------

    #: Root-mean-square amplitude of the waveform (0-1 float scale for
    #: normalized audio). The primary measure of overall loudness; used to
    #: distinguish silence from any active sound.
    rms: float

    #: Maximum absolute sample value in the clip. Captures the loudest
    #: instant even if the rest of the clip is quiet -- useful for detecting
    #: sharp transients (a door slam, a single clap) that RMS alone would
    #: average away.
    peak: float

    #: Ratio between peak and RMS, in dB (20*log10(peak/rms)). A large
    #: dynamic range indicates a mostly-quiet clip punctuated by loud
    #: moments (e.g. occasional clatter); a small one indicates a
    #: consistently loud or consistently quiet clip.
    dynamic_range: float

    # ---- Frequency (spectral shape) ----------------------------------------

    #: Center of mass of the spectrum in Hz. Roughly tracks perceived
    #: "brightness" -- low for rumbling/bassy environments (traffic, HVAC,
    #: car cabins), higher for bright/sibilant ones (wind, clattering
    #: dishes).
    spectral_centroid: float

    #: Spread of the spectrum around its centroid, in Hz. Narrow bandwidth
    #: suggests a tonal/focused sound source (a single voice, a hum); wide
    #: bandwidth suggests broadband content (noise, many overlapping
    #: sources).
    spectral_bandwidth: float

    #: Frequency below which a fixed fraction (typically 85%) of spectral
    #: energy is contained, in Hz. A complementary brightness measure to
    #: centroid that is less sensitive to isolated high-frequency outliers.
    spectral_rolloff: float

    #: Ratio of the geometric mean to the arithmetic mean of the spectrum,
    #: in [0, 1]. Near 1.0 for noise-like/flat spectra (white noise, crowd
    #: babble); near 0.0 for tonal/peaky spectra (a single voice, a hum).
    #: One of the most useful single features for separating "noisy" from
    #: "tonal" environments.
    spectral_flatness: float

    # ---- Temporal -----------------------------------------------------------

    #: Rate at which the waveform crosses zero amplitude, normalized to
    #: crossings/sample. Higher for noisy/fricative-heavy or high-frequency
    #: content, lower for smooth, low-frequency, or tonal signals.
    zero_crossing_rate: float

    #: Variance of short-term (frame-level) energy across the clip. Low for
    #: a steady, consistent sound (a hum, continuous traffic noise); high for
    #: a clip with bursts of activity separated by quieter moments (a crowd
    #: with intermittent chatter, dishes clinking).
    short_term_energy_variance: float

    # ---- Harmonic / Percussive (HPSS) --------------------------------------

    #: RMS energy of the harmonic (tonal) component extracted by
    #: librosa's harmonic-percussive source separation. High for sustained,
    #: pitched content -- voices, music, hums.
    harmonic_energy: float

    #: RMS energy of the percussive (transient) component from the same
    #: separation. High for sharp, broadband events -- clatter, footsteps,
    #: clicks, consonant bursts.
    percussive_energy: float

    #: harmonic_energy / (harmonic_energy + percussive_energy). A
    #: normalized [0, 1] summary of how "tonal vs. transient-dominated" the
    #: clip is, independent of overall loudness.
    harmonic_ratio: float

    # ---- Speech / noise estimation (classical DSP heuristics) --------------
    # These are *estimates* based on framed-energy statistics, not outputs of
    # a trained speech detector. They assume the background noise level is
    # roughly stationary within the 2-second clip -- see
    # config.NoiseEstimationConfig for the exact assumptions and knobs.

    #: Estimated fraction of frames (in [0, 1]) that contain active,
    #: speech-band signal above the estimated noise floor. A voice-activity-
    #: style heuristic, not a speech/non-speech classifier -- clattering
    #: dishes or music in the speech band can also register as "active".
    speech_fraction: float

    #: Estimated background noise level (RMS scale), taken as a low
    #: percentile of the short-term energy envelope. Approximates "how loud
    #: is it during the quietest moments of this clip".
    noise_floor: float

    #: Estimated signal-to-noise ratio in dB, computed as
    #: 20*log10(signal_level / noise_floor) where signal_level is a high
    #: percentile of the short-term energy envelope. Higher values suggest a
    #: clean, isolated sound source; lower values suggest a noisy or
    #: uniformly busy environment where "signal" and "noise" are hard to
    #: tell apart.
    estimated_snr: float

    # ---- Additional interpretable features ---------------------------------

    #: Mean frame-to-frame spectral change (L2 distance between consecutive
    #: normalized magnitude spectra). Low for a stable, unchanging sound
    #: (a steady hum); high for a clip whose spectral content keeps shifting
    #: (multiple people talking over each other, varied background events).
    spectral_flux: float

    #: Mean spectral contrast across frequency bands (peak-to-valley energy
    #: difference per band, from librosa.feature.spectral_contrast). High
    #: contrast suggests a clear tonal structure standing out against a
    #: quieter background (a distinct voice); low contrast suggests a more
    #: uniformly filled spectrum (dense noise/chatter).
    spectral_contrast_mean: float

    #: Detected onsets per second (via librosa onset detection). Counts
    #: discrete sound *events* -- individual words/syllables, footsteps,
    #: clinks -- as opposed to continuous steady-state noise. Very useful
    #: for telling a bursty environment (crowd, kitchen) from a droning one
    #: (highway, HVAC).
    onset_rate: float

    #: Fraction of total spectral energy below SpeechBand.LOW_HZ (~300Hz).
    #: High for rumble-heavy environments: HVAC, traffic, car cabins, wind
    #: buffeting.
    low_freq_energy_ratio: float

    #: Fraction of total spectral energy within the speech band
    #: (~300-3400Hz). High when speech-range content dominates the clip.
    mid_freq_energy_ratio: float

    #: Fraction of total spectral energy above SpeechBand.HIGH_HZ (~3400Hz).
    #: High for sibilant/hissy content: wind noise, clattering dishes,
    #: consonant-heavy or noisy high-frequency texture.
    high_freq_energy_ratio: float

    #: Peak amplitude divided by RMS amplitude (linear ratio, not dB).
    #: A direct measure of impulsiveness/"peakiness" -- high for a signal
    #: dominated by sharp transients (clinking dishes against a quiet
    #: background), low for a signal that's uniformly loud or uniformly
    #: quiet throughout.
    crest_factor: float

    # ---- Provenance ---------------------------------------------------------

    #: Sample rate (Hz) the features above were computed at. Recorded
    #: alongside the features themselves so downstream consumers (and
    #: serialized JSON output) are self-describing.
    sample_rate: int

    #: Duration of the analyzed clip in seconds.
    duration_s: float
