"""
Top-level orchestration: load audio -> extract features -> classify.

This is the only module in the package allowed to import both
feature_extractor and classifier. Keeping that coupling in a single thin
module is what preserves the extraction/classification boundary everywhere
else -- neither of those two modules ever needs to know the other exists.
"""

from pathlib import Path

import librosa
import numpy as np

from .classifier import ClassificationResult, classify
from .config import AudioConfig
from .feature_extractor import extract_features
from .feature_types import AudioFeatures

_cfg = AudioConfig()


def analyze_file(path: str | Path) -> tuple[AudioFeatures, ClassificationResult]:
    """
    Load an audio file from disk, resample it to the pipeline's standard
    sample rate, and run the full extract-then-classify pipeline on it.
    """
    y, sr = librosa.load(str(path), sr=_cfg.SAMPLE_RATE, mono=True)
    return analyze_array(y, sr)


def analyze_array(y: np.ndarray, sr: int) -> tuple[AudioFeatures, ClassificationResult]:
    """Run the full extract-then-classify pipeline on an in-memory waveform."""
    features = extract_features(y, sr)
    result = classify(features)
    return features, result
