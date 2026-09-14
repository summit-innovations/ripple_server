"""
End-to-end smoke tests: synthetic waveform in, expected Environment out,
exercising the full extract -> classify pipeline together.
"""

import soundfile as sf

from audio_analysis.analyzer import analyze_array, analyze_file
from audio_analysis.classifier import Environment


def test_silence_signal_classifies_as_silence(silence_signal, sample_rate):
    _features, result = analyze_array(silence_signal, sample_rate)
    assert result.environment == Environment.SILENCE


def test_speech_like_signal_classifies_as_clear_speech(speech_like_signal, sample_rate):
    _features, result = analyze_array(speech_like_signal, sample_rate)
    assert result.environment == Environment.CLEAR_SPEECH


def test_crowded_signal_classifies_as_crowded_space(crowded_signal, sample_rate):
    _features, result = analyze_array(crowded_signal, sample_rate)
    assert result.environment == Environment.CROWDED_SPACE


def test_analyze_file_loads_and_resamples(tmp_path, tone_signal, sample_rate):
    """analyze_file should load from disk and produce the same kind of result as analyze_array."""
    wav_path = tmp_path / "tone.wav"
    sf.write(wav_path, tone_signal, sample_rate)

    features, result = analyze_file(wav_path)

    assert features.sample_rate == sample_rate
    assert result.environment is not None
