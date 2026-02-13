# client/interaction_listener.py
"""
Interaction Listener Module

Captures low-level interaction metadata (timing only) without storing any
actual content (keystroke characters, window titles, etc.). This preserves
privacy by design. Only timestamps, event types, and non-identifying metrics
are recorded.

In production, this module would integrate with system event hooks
(e.g., pynput, Quartz, Xlib). For demonstration, a mock listener is provided
that generates plausible synthetic events.
"""

import threading
import time
import random
from queue import Queue, Empty
from typing import List, Optional

# Shared data models – all event structures are defined in shared/models.py
# to ensure consistency between client and server.
from shared.models import (
    BaseEvent,
    EventType,
    KeystrokeEvent,
    MouseEvent,
    FocusEvent,
    IdleEvent,
)


class InteractionListener:
    """Abstract base class for all interaction listeners."""

    def start(self) -> None:
        """Start capturing interaction events."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop capturing and release any system hooks."""
        raise NotImplementedError

    def get_events(self, timeout: float = 0.1) -> List[BaseEvent]:
        """
        Retrieve all events that have been buffered since the last call.

        Args:
            timeout: Maximum time (seconds) to wait for events.

        Returns:
            List of captured events (may be empty).
        """
        raise NotImplementedError


class MockInteractionListener(InteractionListener):
    """
    A synthetic interaction listener that generates a stream of plausible
    interaction events for testing and demonstration.

    No real system hooks are used – events are produced randomly based on
    configurable parameters. This allows the system to run on any machine
    without special permissions.
    """

    def __init__(
        self,
        mean_event_interval: float = 0.08,
        idle_probability: float = 0.15,
        focus_loss_probability: float = 0.08,
    ):
        """
        Args:
            mean_event_interval: Average time (seconds) between generated events.
            idle_probability: Probability that a generated event is an IdleEvent.
            focus_loss_probability: Probability that a generated event is a focus loss.
        """
        self.mean_event_interval = mean_event_interval
        self.idle_probability = idle_probability
        self.focus_loss_probability = focus_loss_probability

        self._queue: Queue[BaseEvent] = Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background event generation thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._generate_events, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread and clear the event queue."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        # Clear any remaining events
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break

    def _generate_events(self) -> None:
        """
        Infinite loop that produces a random sequence of events.
        Each iteration sleeps for a random interval (exponential distribution)
        and then decides which type of event to emit.
        """
        last_event_time = time.time()

        while self._running:
            # Determine how long to wait until the next "natural" event
            sleep_time = random.expovariate(1.0 / self.mean_event_interval)
            time.sleep(sleep_time)
            now = time.time()

            # --- Idle detection ---
            # If the gap since the last event is significantly larger than the
            # mean interval, treat it as an idle period and emit an IdleEvent.
            idle_duration = now - last_event_time
            if idle_duration > self.mean_event_interval * 2:
                self._queue.put(
                    IdleEvent(
                        timestamp=now,
                        type=EventType.IDLE_PERIOD,
                        duration=idle_duration,
                    )
                )
            last_event_time = now

            # --- Decide which event to generate ---
            # Idle event (already emitted above) – now decide among keyboard,
            # mouse, and focus events.

            # Idle event is a special case – we already emitted it if the gap
            # was large. For the remaining probability we generate other events.
            # But we also allow explicit idle events with shorter durations?
            # For simplicity, we only generate IdleEvent when the gap is large.
            # The other events are generated with certain probabilities.

            rand = random.random()

            if rand < self.idle_probability:
                # Explicit idle event (short idle) – emit an IdleEvent with a
                # small duration (simulates brief pauses).
                self._queue.put(
                    IdleEvent(
                        timestamp=now,
                        type=EventType.IDLE_PERIOD,
                        duration=random.uniform(0.5, 2.0),
                    )
                )
            elif rand < self.idle_probability + 0.4:
                # Keystroke event: generate a press and later a release.
                press_time = now
                release_time = press_time + random.uniform(0.05, 0.20)
                self._queue.put(
                    KeystrokeEvent(timestamp=press_time, type=EventType.KEY_PRESS)
                )
                # Schedule the release event (we put it in the queue immediately
                # with a future timestamp; the feature extractor will sort by time.)
                self._queue.put(
                    KeystrokeEvent(timestamp=release_time, type=EventType.KEY_RELEASE)
                )
            elif rand < self.idle_probability + 0.7:
                # Mouse movement
                self._queue.put(
                    MouseEvent(
                        timestamp=now,
                        type=EventType.MOUSE_MOVE,
                        x=random.randint(0, 1920),
                        y=random.randint(0, 1080),
                    )
                )
            else:
                # Focus change event
                # Emit a focus loss, and after a short interval a focus gain.
                loss_time = now
                gain_time = loss_time + random.uniform(0.5, 3.0)
                self._queue.put(
                    FocusEvent(
                        timestamp=loss_time,
                        type=EventType.FOCUS_LOST,
                        lost_focus=True,
                    )
                )
                self._queue.put(
                    FocusEvent(
                        timestamp=gain_time,
                        type=EventType.FOCUS_GAINED,
                        lost_focus=False,
                    )
                )

    def get_events(self, timeout: float = 0.1) -> List[BaseEvent]:
        """
        Collect all events that have accumulated in the internal queue.

        Args:
            timeout: Maximum time (seconds) to wait for new events.
                    Since the generator runs continuously, this method
                    returns immediately after draining the queue.

        Returns:
            List of BaseEvent objects (may be empty).
        """
        events: List[BaseEvent] = []
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                event = self._queue.get_nowait()
                events.append(event)
            except Empty:
                time.sleep(0.01)
        return events
