import pytest
from src.network_sim import SimulatedSocket, create_udp_socket


def test_loss_rate_clamped_above_one():
    s = create_udp_socket(loss_rate=5.0)
    assert s.loss_rate == 1.0


def test_loss_rate_clamped_below_zero():
    s = create_udp_socket(loss_rate=-1.0)
    assert s.loss_rate == 0.0


def test_delay_ms_clamped_non_negative():
    s = create_udp_socket(delay_ms=-10.0)
    assert s.delay_ms == 0.0


def test_no_drop_when_loss_rate_zero():
    s = create_udp_socket(loss_rate=0.0)
    # loss_rate=0 hiçbir zaman düşürmemeli
    for _ in range(100):
        assert s._should_drop() is False


def test_always_drop_when_loss_rate_one():
    s = create_udp_socket(loss_rate=1.0)
    for _ in range(100):
        assert s._should_drop() is True


def test_stats_initial_zero():
    s = create_udp_socket()
    assert s.stats == {"dropped_on_send": 0, "dropped_on_recv": 0}
