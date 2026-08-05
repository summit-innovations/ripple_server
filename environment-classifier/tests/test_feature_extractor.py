"""
Sanity checks that each feature moves in the expected direction on signals
with known characteristics. These are not exact-value tests (the DSP math
is trusted to librosa/numpy) -- they check that the *relationships* the
classifier will rely on actually hold.
"""

from audio_analysis.feature_extractor import extract_features


def test_silence_has_near_zero_energy(silence_signal, sample_rate):
    features = extract_features(silence_signal, sample_rate)
    assert features.rms < 0.01
    assert features.peak < 0.05


def test_tone_is_highly_harmonic_and_not_flat(tone_signal, sample_rate):
    features = extract_features(tone_signal, sample_rate)
    assert features.harmonic_ratio > 0.8
    assert features.spectral_flatness < 0.2


def test_white_noise_is_flat_and_less_harmonic_than_tone(
    white_noise_signal, tone_signal, sample_rate
):
    noise_features = extract_features(white_noise_signal, sample_rate)
    tone_features = extract_features(tone_signal, sample_rate)
    assert noise_features.spectral_flatness > tone_features.spectral_flatness
    assert noise_features.harmonic_ratio < tone_features.harmonic_ratio


def test_crowded_signal_has_higher_energy_variance_than_tone(
    crowded_signal, tone_signal, sample_rate
):
    crowded_features = extract_features(crowded_signal, sample_rate)
    tone_features = extract_features(tone_signal, sample_rate)
    assert crowded_features.short_term_energy_variance > tone_features.short_term_energy_variance


def test_speech_like_signal_has_speech_band_energy(speech_like_signal, sample_rate):
    features = extract_features(speech_like_signal, sample_rate)
    assert features.mid_freq_energy_ratio > features.low_freq_energy_ratio
    assert features.mid_freq_energy_ratio > features.high_freq_energy_ratio
    assert features.speech_fraction > 0.0


def test_metadata_fields_are_correct(tone_signal, sample_rate):
    features = extract_features(tone_signal, sample_rate)
    assert features.sample_rate == sample_rate
    assert abs(features.duration_s - 2.0) < 1e-6


def test_all_features_are_finite(
    silence_signal, tone_signal, white_noise_signal, speech_like_signal, crowded_signal, sample_rate
):
    import math
    from dataclasses import asdict

    for signal in (silence_signal, tone_signal, white_noise_signal, speech_like_signal, crowded_signal):
        features = extract_features(signal, sample_rate)
        for name, value in asdict(features).items():
            if isinstance(value, float):
                assert math.isfinite(value), f"{name} is not finite: {value}"
