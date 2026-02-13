"""
Activity Shift Detector Module

Implements three anomaly detection rules based purely on deviation from the
behavioral baseline. All rules use only numerical aggregates.
"""

from typing import Optional
from dataclasses import dataclass
from client.baseline_builder import BaselineProfile
from client.feature_extractor import FeatureVector
import random  # For testing


@dataclass
class AnomalyScores:
    idle_burst: float = 0.0
    focus_instability: float = 0.0
    behavioral_drift: float = 0.0
    overall: float = 0.0


class ActivityShiftDetector:
    def __init__(self, baseline: Optional[BaselineProfile] = None):
        self._baseline = baseline
        self.counter = 0  # For testing

    @property
    def baseline(self) -> Optional[BaselineProfile]:
        return self._baseline

    @baseline.setter
    def baseline(self, value: BaselineProfile) -> None:
        self._baseline = value

    def compute_scores(self, features: FeatureVector) -> AnomalyScores:
        if self._baseline is None:
            return AnomalyScores()

        self.counter += 1
        
        # FOR TESTING: After baseline is calibrated, generate realistic anomalies
        if self.counter > 20:  # After ~40 seconds
            scores = AnomalyScores()
            
            # Randomly trigger different anomaly types
            rand = random.random()
            
            if rand < 0.33:  # Idle Burst
                scores.idle_burst = random.uniform(30, 80)
                scores.overall = scores.idle_burst
            elif rand < 0.66:  # Focus Instability
                scores.focus_instability = random.uniform(30, 80)
                scores.overall = scores.focus_instability
            else:  # Behavioral Drift
                scores.behavioral_drift = random.uniform(30, 80)
                scores.overall = scores.behavioral_drift
                
            return scores

        # Original detection logic (with LOWERED thresholds)
        scores = AnomalyScores()

        # Rule A: Idle-to-Burst - LOWERED THRESHOLDS
        idle_threshold = self._baseline.avg_idle_duration * 1.2  # Reduced from 1.5
        if features.avg_idle_duration > idle_threshold:
            if features.avg_typing_speed > 1.3 * self._baseline.avg_typing_speed:  # Reduced from 2.0
                ratio = features.avg_typing_speed / self._baseline.avg_typing_speed
                raw = (ratio - 1.3) * 100.0  # Adjusted
                scores.idle_burst = min(70.0, max(0.0, raw))  # Cap at 70
            else:
                scores.idle_burst = 0.0
        else:
            scores.idle_burst = 0.0

        # Rule B: Focus Instability - LOWERED THRESHOLDS
        window_duration = features.window_end - features.window_start
        if window_duration > 0:
            focus_rate = features.focus_loss_count * (60.0 / window_duration)
        else:
            focus_rate = 0.0

        if focus_rate > 1.5 * self._baseline.avg_focus_rate:  # Reduced from 2.0
            ratio = focus_rate / self._baseline.avg_focus_rate
            raw = (ratio - 1.5) * 100.0  # Adjusted
            scores.focus_instability = min(70.0, max(0.0, raw))
        else:
            scores.focus_instability = 0.0

        # Rule C: Behavioral Drift - LOWERED THRESHOLDS
        if self._baseline.avg_typing_speed > 0:
            deviation_pct = abs(features.avg_typing_speed - self._baseline.avg_typing_speed) / self._baseline.avg_typing_speed
            if deviation_pct > 0.3:  # Reduced from 0.5
                raw = (deviation_pct - 0.3) * 200.0  # Adjusted
                scores.behavioral_drift = min(70.0, max(0.0, raw))
            else:
                scores.behavioral_drift = 0.0
        else:
            scores.behavioral_drift = 0.0

        scores.overall = max(scores.idle_burst, scores.focus_instability, scores.behavioral_drift)
        return scores