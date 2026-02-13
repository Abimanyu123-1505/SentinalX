"""
Risk Engine Module

Combines anomaly scores from the activity shift detector into a single
risk score using a weighted formula. Applies a moving average to smooth
short-term fluctuations.
"""

from collections import deque
from typing import Deque, Optional
from client.activity_shift_detector import AnomalyScores


class RiskEngine:
    def __init__(self, smoothing_window: int = 5):
        self.smoothing_window = smoothing_window
        self._risk_history: Deque[float] = deque(maxlen=smoothing_window)
        self._last_raw_risk: float = 0.0
        self._last_smoothed_risk: float = 0.0
        self.weight_idle_burst = 0.4
        self.weight_focus_instability = 0.3
        self.weight_behavioral_drift = 0.3

    def compute_risk(self, anomaly_scores: AnomalyScores) -> float:
        # Use REAL anomaly scores from detector
        raw_risk = (
            self.weight_idle_burst * anomaly_scores.idle_burst +
            self.weight_focus_instability * anomaly_scores.focus_instability +
            self.weight_behavioral_drift * anomaly_scores.behavioral_drift
        )
        raw_risk = max(0.0, min(100.0, raw_risk))
        
        self._last_raw_risk = raw_risk
        self._risk_history.append(raw_risk)
        
        if len(self._risk_history) > 0:
            smoothed = sum(self._risk_history) / len(self._risk_history)
        else:
            smoothed = raw_risk
            
        self._last_smoothed_risk = smoothed
        return smoothed

    @property
    def current_risk(self) -> float:
        return self._last_smoothed_risk

    @property
    def raw_risk(self) -> float:
        return self._last_raw_risk

    def reset(self) -> None:
        self._risk_history.clear()
        self._last_raw_risk = 0.0
        self._last_smoothed_risk = 0.0