"""
audio_analysis: classical-DSP audio environment recognition.

Public API:
    analyze_file(path) -> (AudioFeatures, ClassificationResult)
    analyze_array(y, sr) -> (AudioFeatures, ClassificationResult)

See analyzer.py for the orchestration, feature_extractor.py for how
AudioFeatures is computed, and classifier.py for how it's turned into an
Environment decision. Those two stages are intentionally decoupled -- see
their module docstrings for why.
"""

from .analyzer import analyze_array, analyze_file
from .classifier import ClassificationResult, Environment, classify
from .feature_extractor import extract_features
from .feature_types import AudioFeatures

__all__ = [
    "analyze_array",
    "analyze_file",
    "AudioFeatures",
    "ClassificationResult",
    "Environment",
    "classify",
    "extract_features",
]
