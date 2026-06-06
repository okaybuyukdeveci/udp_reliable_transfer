import json
import pytest
from analysis.metrics import TransferMetrics, load_from_json, load_all_from_dir


def _sample(**overrides):
    base = dict(
        session_id="s", success=True, total_bytes=2048, elapsed_s=1.0,
        throughput_bps=2048, goodput_bps=1024, packets_sent=2, acks_received=2,
        timeouts=0, retransmissions=0, duplicates=0, failed_packets=0,
        checksum_errors=0, packet_loss_rate=0.0, retx_rate=0.0, avg_rtt_s=0.01,
    )
    base.update(overrides)
    return base


def test_throughput_kbps():
    m = TransferMetrics(**_sample(throughput_bps=4096))
    assert m.throughput_kbps == 4.0


def test_goodput_kbps():
    m = TransferMetrics(**_sample(goodput_bps=1024))
    assert m.goodput_kbps == 1.0


def test_completion_time_equals_elapsed():
    m = TransferMetrics(**_sample(elapsed_s=3.5))
    assert m.completion_time_s == 3.5


def test_load_from_json(tmp_path):
    path = tmp_path / "summary_x.json"
    path.write_text(json.dumps(_sample()))
    m = load_from_json(str(path))
    assert m.session_id == "s"
    assert m.success is True


def test_load_all_skips_unreadable(tmp_path):
    good = tmp_path / "summary_ok.json"
    good.write_text(json.dumps(_sample()))
    (tmp_path / "summary_bad.json").write_text("{not json")
    results = load_all_from_dir(str(tmp_path))
    assert len(results) == 1
    assert results[0].session_id == "s"


def test_load_all_empty_dir(tmp_path):
    results = load_all_from_dir(str(tmp_path))
    assert results == []
