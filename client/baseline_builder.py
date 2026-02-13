"""
Baseline Builder Module

Establishes a behavioral baseline for a user session by observing the first
N minutes of interaction. Only numerical aggregates are stored.
"""

from typing import List, Optional
from dataclasses import dataclass

# FIXED: Add this import
from client.feature_extractor import FeatureVector


@dataclass
class BaselineProfile:
    avg_typing_speed: float
    avg_idle_duration: float
    avg_focus_rate: float


class BaselineBuilder:
    def __init__(self, calibration_duration: float = 180.0):
        self.calibration_duration = calibration_duration
        self._feature_history: List[FeatureVector] = []
        self._baseline: Optional[BaselineProfile] = None
        self._calibration_start: Optional[float] = None

    def start_calibration(self, start_time: float) -> None:
        self._feature_history.clear()
        self._baseline = None
        self._calibration_start = start_time

    def update(self, features: FeatureVector, current_time: float) -> None:
        if self._baseline is not None:
            return
        if self._calibration_start is None:
            self.start_calibration(current_time)
        if current_time - self._calibration_start <= self.calibration_duration:
            self._feature_history.append(features)
        else:
            self._build_baseline()

    def _build_baseline(self) -> None:
        if not self._feature_history:
            self._baseline = BaselineProfile(
                avg_typing_speed=150.0,
                avg_idle_duration=2.0,
                avg_focus_rate=0.5
            )
            return

        total_typing_speed = 0.0
        total_idle_duration = 0.0
        total_focus_loss = 0.0
        window_count = 0

        for fv in self._feature_history:
            total_typing_speed += fv.avg_typing_speed
            total_idle_duration += fv.avg_idle_duration
            total_focus_loss += fv.focus_loss_count
            window_count += 1

        avg_typing_speed = total_typing_speed / window_count
        avg_idle_duration = total_idle_duration / window_count

        if window_count > 0:
            avg_focus_per_window = total_focus_loss / window_count
            window_duration = 30.0
            if hasattr(self._feature_history[0], 'window_end') and hasattr(self._feature_history[0], 'window_start'):
                window_duration = self._feature_history[0].window_end - self._feature_history[0].window_start
                if window_duration <= 0:
                    window_duration = 30.0
            avg_focus_rate = avg_focus_per_window * (60.0 / window_duration)
        else:
            avg_focus_rate = 0.0

        self._baseline = BaselineProfile(
            avg_typing_speed=avg_typing_speed,
            avg_idle_duration=avg_idle_duration,
            avg_focus_rate=avg_focus_rate
        )
        self._feature_history.clear()

    @property
    def baseline(self) -> Optional[BaselineProfile]:
        return self._baseline

    @property
    def is_calibrated(self) -> bool:
        return self._baseline is not None

    def reset(self) -> None:
        self._feature_history.clear()
        self._baseline = None
        self._calibration_start = None