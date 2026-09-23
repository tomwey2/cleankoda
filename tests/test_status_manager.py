import unittest
from cleankoda.state import (
    SessionState,
    clear_status,
    get_session_state,
    set_status,
)


class TestStatusManager(unittest.TestCase):

    def setUp(self):
        state = get_session_state()
        state.status_slots.clear()
        state._listeners.clear()

    def test_empty_status_manager(self):
        state = SessionState()
        self.assertEqual(state.get_combined_status(), "")

    def test_set_and_get_combined_status(self):
        set_status("sandbox", "Sandbox: Startet (docker:latest)...")
        self.assertEqual(
            get_session_state().get_combined_status(),
            "Sandbox: Startet (docker:latest)...",
        )

        set_status("llm", "LLM Cold Start: Versuch 1/10 (10s gewartet)")
        self.assertEqual(
            get_session_state().get_combined_status(),
            "Sandbox: Startet (docker:latest)... | LLM Cold Start: Versuch 1/10 (10s gewartet)",
        )

    def test_clear_status(self):
        set_status("sandbox", "Sandbox active")
        set_status("tool", "Führe Tool aus: run_bash...")
        clear_status("sandbox")
        self.assertEqual(
            get_session_state().get_combined_status(),
            "Führe Tool aus: run_bash...",
        )

        clear_status("tool")
        self.assertEqual(get_session_state().get_combined_status(), "")

    def test_observer_on_change(self):
        state = get_session_state()
        notifications = 0

        def on_change_cb(st: SessionState):
            nonlocal notifications
            notifications += 1

        state.subscribe(on_change_cb)

        # Initial set triggers notification
        set_status("sandbox", "Starting")
        self.assertEqual(notifications, 1)

        # Updating slot triggers notification
        set_status("sandbox", "Ready")
        self.assertEqual(notifications, 2)

        # Clearing existing slot triggers notification
        clear_status("sandbox")
        self.assertEqual(notifications, 3)

        # Clearing non-existent slot does NOT trigger notification
        clear_status("sandbox")
        self.assertEqual(notifications, 3)


if __name__ == "__main__":
    unittest.main()

