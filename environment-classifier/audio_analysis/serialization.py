"""
JSON serialization for analysis results.

Both the batch processor and the realtime watcher need to write results to
disk in the same shape, so that shape is defined exactly once here rather
than duplicated in each script. This module only imports feature_types and
classifier for their *types* -- it doesn't compute anything itself, so it
doesn't blur the extraction/classification boundary those modules maintain.
"""

from dataclasses import asdict

from .classifier import ClassificationResult
from .feature_types import AudioFeatures


def to_result_dict(
    features: AudioFeatures,
    result: ClassificationResult,
    source_file: str,
    processed_at: str,
) -> dict:
    """
    Build a plain, JSON-serializable dict combining extracted features,
    the classification decision, and processing metadata.

    Args:
        features: the extracted AudioFeatures for the clip.
        result: the classifier's decision for those features.
        source_file: path (or identifier) of the audio file that was analyzed.
        processed_at: ISO 8601 UTC timestamp string for when this ran.
    """
    return {
        **asdict(features),
        "environment": result.environment.value,
        "reasoning": result.reasoning,
        "source_file": source_file,
        "processed_at": processed_at,
    }
