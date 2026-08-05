"""
Demo CLI: run the full pipeline on a single audio file and print the result.

Usage:
    python -m scripts.demo path/to/clip.wav
"""

import argparse
import sys
from dataclasses import asdict

from audio_analysis import analyze_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze one audio clip and print its features + classification.")
    parser.add_argument("audio_path", help="Path to a mono audio file (any format librosa/soundfile can read)")
    args = parser.parse_args()

    features, result = analyze_file(args.audio_path)

    print(f"\n=== {args.audio_path} ===")
    print(f"\nFeatures ({features.sample_rate}Hz, {features.duration_s:.2f}s):")
    for name, value in asdict(features).items():
        if isinstance(value, float):
            print(f"  {name:28s} = {value:.6f}")
        else:
            print(f"  {name:28s} = {value}")

    print(f"\nClassification: {result.environment.value}")
    print(f"Reasoning: {result.reasoning}\n")


if __name__ == "__main__":
    sys.exit(main())
