"""
Feature extraction: raw audio -> AudioFeatures.

This module is the "signal analysis" half of the pipeline. It knows nothing
about environments or labels, and must never import classifier.py -- that
boundary is what lets new environments be added later purely by changing
classifier.py and config.py, without touching how features are computed.

All functions here are pure: given the same waveform they always produce the
same features, with no hidden state or I/O.
"""

import numpy as np
import librosa

from .config import AudioConfig, NoiseEstimationConfig, SpeechBand
from .feature_types import AudioFeatures

_cfg = AudioConfig()
_noise_cfg = NoiseEstimationConfig()
_band = SpeechBand()


def extract_features(y: np.ndarray, sr: int) -> AudioFeatures:
    """
    Compute a full AudioFeatures snapshot for a mono audio waveform.

    Args:
        y: 1-D array of audio samples, float, nominally in [-1, 1].
        sr: sample rate of `y` in Hz.

    Returns:
        An AudioFeatures instance summarizing the clip's acoustic content.

    The STFT is computed once and reused across every spectral feature to
    avoid redundant transforms -- on a 2-second clip this is a minor
    optimization, but it keeps the pattern consistent as more features are
    added.
    """
    y = np.asarray(y, dtype=np.float64)
    duration_s = len(y) / sr

    magnitude = _stft_magnitude(y)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=_cfg.N_FFT)
    frame_rms = librosa.feature.rms(S=magnitude, frame_length=_cfg.N_FFT)[0]

    rms, peak, dynamic_range, crest_factor = _energy_features(y)
    centroid, bandwidth, rolloff, flatness = _frequency_features(magnitude, sr)
    zcr = _zero_crossing_rate(y)
    energy_variance = float(np.var(frame_rms))
    harmonic_energy, percussive_energy, harmonic_ratio = _harmonic_percussive_features(y)
    noise_floor, estimated_snr = _noise_floor_and_snr(frame_rms)
    speech_fraction = _speech_fraction(magnitude, freqs, frame_rms, noise_floor)
    spectral_flux = _spectral_flux(magnitude)
    spectral_contrast_mean = float(librosa.feature.spectral_contrast(S=magnitude, sr=sr).mean())
    onset_rate = _onset_rate(y, sr, duration_s)
    low_ratio, mid_ratio, high_ratio = _band_energy_ratios(magnitude, freqs)

    return AudioFeatures(
        rms=rms,
        peak=peak,
        dynamic_range=dynamic_range,
        spectral_centroid=centroid,
        spectral_bandwidth=bandwidth,
        spectral_rolloff=rolloff,
        spectral_flatness=flatness,
        zero_crossing_rate=zcr,
        short_term_energy_variance=energy_variance,
        harmonic_energy=harmonic_energy,
        percussive_energy=percussive_energy,
        harmonic_ratio=harmonic_ratio,
        speech_fraction=speech_fraction,
        noise_floor=noise_floor,
        estimated_snr=estimated_snr,
        spectral_flux=spectral_flux,
        spectral_contrast_mean=spectral_contrast_mean,
        onset_rate=onset_rate,
        low_freq_energy_ratio=low_ratio,
        mid_freq_energy_ratio=mid_ratio,
        high_freq_energy_ratio=high_ratio,
        crest_factor=crest_factor,
        sample_rate=sr,
        duration_s=duration_s,
    )


def _stft_magnitude(y: np.ndarray) -> np.ndarray:
    """Magnitude spectrogram shared by every spectral feature below."""
    stft = librosa.stft(
        y,
        n_fft=_cfg.N_FFT,
        hop_length=_cfg.HOP_LENGTH,
        win_length=_cfg.WIN_LENGTH,
    )
    return np.abs(stft)


def _energy_features(y: np.ndarray) -> tuple[float, float, float, float]:
    """
    Overall loudness/impulsiveness summary: rms, peak, dynamic_range (dB),
    crest_factor (linear peak/rms). Computed directly on the waveform rather
    than frame-by-frame since these describe the whole clip.
    """
    rms = float(np.sqrt(np.mean(np.square(y))))
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    crest_factor = peak / (rms + _cfg.EPSILON)
    dynamic_range = 20.0 * np.log10(peak / (rms + _cfg.EPSILON) + _cfg.EPSILON)
    return rms, peak, float(dynamic_range), float(crest_factor)


def _frequency_features(magnitude: np.ndarray, sr: int) -> tuple[float, float, float, float]:
    """Mean-pooled spectral shape descriptors: centroid, bandwidth, rolloff, flatness."""
    centroid = float(librosa.feature.spectral_centroid(S=magnitude, sr=sr).mean())
    bandwidth = float(librosa.feature.spectral_bandwidth(S=magnitude, sr=sr).mean())
    rolloff = float(librosa.feature.spectral_rolloff(S=magnitude, sr=sr).mean())
    flatness = float(librosa.feature.spectral_flatness(S=magnitude).mean())
    return centroid, bandwidth, rolloff, flatness


def _zero_crossing_rate(y: np.ndarray) -> float:
    """Mean zero-crossing rate, framed consistently with the STFT parameters."""
    zcr = librosa.feature.zero_crossing_rate(
        y, frame_length=_cfg.N_FFT, hop_length=_cfg.HOP_LENGTH
    )
    return float(zcr.mean())


def _harmonic_percussive_features(y: np.ndarray) -> tuple[float, float, float]:
    """
    Harmonic/percussive source separation via librosa HPSS, reduced to RMS
    energy of each component and their normalized ratio.
    """
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    harmonic_energy = float(np.sqrt(np.mean(np.square(y_harmonic))))
    percussive_energy = float(np.sqrt(np.mean(np.square(y_percussive))))
    harmonic_ratio = harmonic_energy / (harmonic_energy + percussive_energy + _cfg.EPSILON)
    return harmonic_energy, percussive_energy, harmonic_ratio


def _noise_floor_and_snr(frame_rms: np.ndarray) -> tuple[float, float]:
    """
    Estimate noise floor and SNR from the distribution of per-frame RMS
    values. See config.NoiseEstimationConfig for the stationarity assumption
    this relies on.
    """
    noise_floor = float(np.percentile(frame_rms, NoiseEstimationConfig().NOISE_FLOOR_PERCENTILE))
    signal_level = float(np.percentile(frame_rms, NoiseEstimationConfig().SIGNAL_PERCENTILE))
    estimated_snr = 20.0 * np.log10((signal_level + _cfg.EPSILON) / (noise_floor + _cfg.EPSILON))
    return noise_floor, float(estimated_snr)


def _speech_fraction(
    magnitude: np.ndarray, freqs: np.ndarray, frame_rms: np.ndarray, noise_floor: float
) -> float:
    """
    Voice-activity-style heuristic: a frame counts as "speech-active" if it
    is both louder than the noise floor by a margin AND has most of its
    spectral energy within the conventional speech band. This is a coarse
    DSP heuristic, not a speech classifier -- other loud, speech-band content
    (e.g. music, some clattering) can also register as active.
    """
    active_mask = frame_rms > (noise_floor * _noise_cfg.ACTIVE_FRAME_MARGIN_RATIO)

    band_mask = (freqs >= _band.LOW_HZ) & (freqs <= _band.HIGH_HZ)
    power = np.square(magnitude)
    total_energy_per_frame = power.sum(axis=0) + _cfg.EPSILON
    band_energy_per_frame = power[band_mask].sum(axis=0)
    band_fraction_per_frame = band_energy_per_frame / total_energy_per_frame
    band_dominant_mask = band_fraction_per_frame > _noise_cfg.SPEECH_BAND_ENERGY_FRACTION

    return float(np.mean(active_mask & band_dominant_mask))


def _spectral_flux(magnitude: np.ndarray) -> float:
    """
    Mean frame-to-frame change in normalized spectral shape (L2 distance
    between consecutive unit-norm magnitude spectra). Captures how much the
    spectral "shape" of the sound is shifting over time, independent of
    loudness.
    """
    norms = np.linalg.norm(magnitude, axis=0, keepdims=True) + _cfg.EPSILON
    normalized = magnitude / norms
    diffs = np.diff(normalized, axis=1)
    if diffs.shape[1] == 0:
        return 0.0
    flux_per_frame_pair = np.sqrt(np.sum(np.square(diffs), axis=0))
    return float(flux_per_frame_pair.mean())


def _onset_rate(y: np.ndarray, sr: int, duration_s: float) -> float:
    """Discrete sound events per second, via librosa onset detection."""
    onset_times = librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=_cfg.HOP_LENGTH, units="time"
    )
    if duration_s <= 0:
        return 0.0
    return float(len(onset_times) / duration_s)


def _band_energy_ratios(magnitude: np.ndarray, freqs: np.ndarray) -> tuple[float, float, float]:
    """Fraction of total spectral energy in the low / speech-band / high frequency ranges."""
    power = np.square(magnitude)
    total_energy = power.sum() + _cfg.EPSILON

    low_mask = freqs < _band.LOW_HZ
    mid_mask = (freqs >= _band.LOW_HZ) & (freqs <= _band.HIGH_HZ)
    high_mask = freqs > _band.HIGH_HZ

    low_ratio = float(power[low_mask].sum() / total_energy)
    mid_ratio = float(power[mid_mask].sum() / total_energy)
    high_ratio = float(power[high_mask].sum() / total_energy)
    return low_ratio, mid_ratio, high_ratio
