"""Tests for StopWatch utility."""

import logging
from time import sleep
from unittest.mock import MagicMock

from app.infrastructure.observability.stopwatch import StopWatch


class TestLapTiming:
    def test_lap_records_duration_ms(self) -> None:
        sw = StopWatch()
        with sw.lap("step_a"):
            sleep(0.01)
        assert "step_a" in sw.laps
        assert sw.laps["step_a"] >= 5  # at least ~10ms, allow jitter

    def test_multiple_laps(self) -> None:
        sw = StopWatch()
        with sw.lap("a"):
            sleep(0.01)
        with sw.lap("b"):
            sleep(0.01)
        assert set(sw.laps.keys()) == {"a", "b"}

    def test_laps_returns_copy(self) -> None:
        sw = StopWatch()
        with sw.lap("x"):
            pass
        laps = sw.laps
        laps["injected"] = 999
        assert "injected" not in sw.laps


class TestTotalMs:
    def test_total_ms_increases(self) -> None:
        sw = StopWatch()
        sleep(0.01)
        assert sw.total_ms >= 5


class TestSetExtras:
    def test_set_stores_extras(self) -> None:
        sw = StopWatch()
        sw.set(doc_id="abc", count=3)
        # Extras are only visible in log output; verify via auto-log test below


class TestAutoLogging:
    def test_logs_on_exit_with_logger(self) -> None:
        mock_logger = MagicMock(spec=logging.Logger)
        with StopWatch("my_label", mock_logger) as sw:
            with sw.lap("step1"):
                pass
            sw.set(key="val")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "my_label"
        extra = call_args[1]["extra"]
        assert "total_ms" in extra
        assert "step1_ms" in extra
        assert extra["key"] == "val"

    def test_no_log_without_logger(self) -> None:
        # Should not raise
        with StopWatch("label") as sw:
            with sw.lap("a"):
                pass
        # No logger -> no call, just verify no exception

    def test_extra_keys_do_not_collide_with_laps(self) -> None:
        mock_logger = MagicMock(spec=logging.Logger)
        with StopWatch("op", mock_logger) as sw:
            with sw.lap("fetch"):
                pass
            sw.set(fetch_count=5)

        extra = mock_logger.info.call_args[1]["extra"]
        assert "fetch_ms" in extra
        assert extra["fetch_count"] == 5


class TestManualMode:
    def test_without_context_manager(self) -> None:
        sw = StopWatch()
        with sw.lap("work"):
            sleep(0.01)
        assert sw.laps["work"] >= 5
        assert sw.total_ms >= 5
