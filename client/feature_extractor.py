# client/feature_extractor.py
"""
Feature Extractor Module

Transforms raw interaction events (timestamps only) into numerical features.
No content (characters, window titles) is ever accessed or stored.
All features are derived purely from timing and motion metadata.
"""

import math
from collections import deque
from dataclasses import dataclass
from typing import List, Tuple, Optional

from shared.models import (
    BaseEvent,
    KeystrokeEvent,
    MouseEvent,
    FocusEvent,
    IdleEvent,
    EventType,
)


@dataclass
class FeatureVector:
    """
    Container for all behavioral features extracted from a window of events.
    Used as input to baseline builder and anomaly detectors.
    """
    avg_typing_speed: float = 0.0      # Keystrokes per minute
    avg_idle_duration: float = 0.0     # Seconds per idle event
    focus_loss_count: int = 0          # Number of focus lost events
    avg_mouse_speed: float = 0.0       # Pixels per second
    # Additional derived fields for anomaly detection
    inter_key_interval: float = 0.0    # Average time between keystrokes (seconds)
    # Window size metadata (not a feature per se)
    window_start: float = 0.0
    window_end: float = 0.0


class FeatureExtractor:
    """
    Maintains a sliding window of interaction events and computes
    aggregate features on request.
    """

    def __init__(self, window_duration: float = 30.0):
        """
        Args:
            window_duration: Length of the sliding time window (seconds).
                             Features are computed over this lookback period.
        """
        self.window_duration = window_duration
        # Internal event buffer – sorted by timestamp, oldest first.
        # Use deque for efficient removal of expired events.
        self._event_buffer: deque[BaseEvent] = deque()

    def add_event(self, event: BaseEvent) -> None:
        """
        Insert a new event into the buffer. Events are assumed to arrive
        in roughly chronological order; if out-of-order, the buffer is
        resorted (simplified – we keep it as deque and sort on demand).
        For efficiency, we assume caller provides events in increasing time.
        """
        # Keep buffer sorted by timestamp (simple insertion sort)
        # Since events are typically added in order, we can append and then
        # rotate to correct position if needed.
        if not self._event_buffer or event.timestamp >= self._event_buffer[-1].timestamp:
            self._event_buffer.append(event)
        else:
            # Rare out-of-order – insert in correct position
            for i, e in enumerate(self._event_buffer):
                if event.timestamp < e.timestamp:
                    self._event_buffer.insert(i, event)
                    break

    def _prune_buffer(self, current_time: float) -> None:
        """
        Remove events older than window_duration from the buffer.
        """
        cutoff = current_time - self.window_duration
        while self._event_buffer and self._event_buffer[0].timestamp < cutoff:
            self._event_buffer.popleft()

    def compute_features(self, current_time: Optional[float] = None) -> FeatureVector:
        """
        Compute feature vector from events in the current sliding window.

        Args:
            current_time: Reference time for window end (default: now).

        Returns:
            FeatureVector object with computed metrics.
        """
        if current_time is None:
            current_time = self._event_buffer[-1].timestamp if self._event_buffer else 0.0

        self._prune_buffer(current_time)
        window_events = list(self._event_buffer)  # copy

        fv = FeatureVector()
        fv.window_start = current_time - self.window_duration
        fv.window_end = current_time

        # --- Keystroke features ---
        press_timestamps = []
        for ev in window_events:
            if isinstance(ev, KeystrokeEvent) and ev.type == EventType.KEY_PRESS:
                press_timestamps.append(ev.timestamp)

        if len(press_timestamps) >= 2:
            # Inter‑key interval: time between consecutive key presses
            intervals = [press_timestamps[i+1] - press_timestamps[i] for i in range(len(press_timestamps)-1)]
            fv.inter_key_interval = sum(intervals) / len(intervals)
            # Typing speed: keystrokes per minute (over entire window)
            window_len = current_time - fv.window_start
            if window_len > 0:
                fv.avg_typing_speed = (len(press_timestamps) / window_len) * 60
        else:
            fv.inter_key_interval = 0.0
            fv.avg_typing_speed = 0.0

        # --- Idle duration ---
        idle_durations = []
        for ev in window_events:
            if isinstance(ev, IdleEvent):
                idle_durations.append(ev.duration)
        if idle_durations:
            fv.avg_idle_duration = sum(idle_durations) / len(idle_durations)
        else:
            fv.avg_idle_duration = 0.0

        # --- Focus loss count ---
        focus_loss_count = 0
        for ev in window_events:
            if isinstance(ev, FocusEvent) and ev.type == EventType.FOCUS_LOST:
                focus_loss_count += 1
        fv.focus_loss_count = focus_loss_count

        # --- Mouse speed ---
        # We compute total Euclidean distance traveled divided by total time
        # that the mouse was active (time between first and last mouse event in window).
        mouse_positions = []
        for ev in window_events:
            if isinstance(ev, MouseEvent) and ev.type == EventType.MOUSE_MOVE:
                mouse_positions.append((ev.timestamp, ev.x, ev.y))

        if len(mouse_positions) >= 2:
            total_distance = 0.0
            for i in range(len(mouse_positions)-1):
                _, x1, y1 = mouse_positions[i]
                _, x2, y2 = mouse_positions[i+1]
                dx = x2 - x1
                dy = y2 - y1
                total_distance += math.sqrt(dx*dx + dy*dy)

            time_span = mouse_positions[-1][0] - mouse_positions[0][0]
            if time_span > 0:
                fv.avg_mouse_speed = total_distance / time_span
            else:
                fv.avg_mouse_speed = 0.0
        else:
            fv.avg_mouse_speed = 0.0

        return fv

    def clear(self) -> None:
        """Reset the event buffer."""
        self._event_buffer.clear()