"""
Tests for the realtime watcher's change-detection logic, using tmp_path
directories rather than /opt -- these run anywhere and don't exercise the
audio pipeline at all, just the "has something new arrived" bookkeeping.
"""

import time

from scripts.realtime_watcher import detect_new_signal, find_latest_file, fingerprint


def test_find_latest_file_returns_none_for_empty_dir(tmp_path):
    assert find_latest_file(tmp_path) is None


def test_find_latest_file_returns_most_recently_modified(tmp_path):
    older = tmp_path / "older.wav"
    newer = tmp_path / "newer.wav"
    older.write_bytes(b"a")
    time.sleep(0.01)
    newer.write_bytes(b"b")

    assert find_latest_file(tmp_path) == newer


def test_detect_new_signal_is_none_when_directory_empty(tmp_path):
    assert detect_new_signal(tmp_path, last_fingerprint=None) is None


def test_detect_new_signal_fires_on_first_file(tmp_path):
    path = tmp_path / "signal.wav"
    path.write_bytes(b"content")

    detected = detect_new_signal(tmp_path, last_fingerprint=None)

    assert detected is not None
    detected_path, fp = detected
    assert detected_path == path
    assert fp == fingerprint(path)


def test_detect_new_signal_is_none_once_fingerprint_matches(tmp_path):
    path = tmp_path / "signal.wav"
    path.write_bytes(b"content")
    fp = fingerprint(path)

    assert detect_new_signal(tmp_path, last_fingerprint=fp) is None


def test_detect_new_signal_fires_when_same_filename_overwritten(tmp_path):
    path = tmp_path / "signal.wav"
    path.write_bytes(b"content-v1")
    old_fp = fingerprint(path)

    time.sleep(0.01)
    path.write_bytes(b"content-v2-longer")

    detected = detect_new_signal(tmp_path, last_fingerprint=old_fp)

    assert detected is not None
    _, new_fp = detected
    assert new_fp != old_fp
