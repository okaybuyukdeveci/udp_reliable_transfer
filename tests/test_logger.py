import json
import os
import pytest
from src.logger import TransferLogger


def test_summary_counts_and_rates(tmp_path):
    log = TransferLogger(log_dir=str(tmp_path), session_id="t1")
    log.start()
    log.log_sent(0)
    log.log_ack(0)
    log.log_sent(1)
    log.log_timeout(1, attempt=1)
    log.log_retransmit(1, attempt=2)
    log.log_ack(1)

    summary = log._write_summary(total_bytes=2048, elapsed=1.0, success=True)

    assert summary["packets_sent"] == 2
    assert summary["acks_received"] == 2
    assert summary["timeouts"] == 1
    assert summary["retransmissions"] == 1
    assert summary["retx_rate"] == 0.5
    assert summary["success"] is True


def test_summary_written_to_json(tmp_path):
    log = TransferLogger(log_dir=str(tmp_path), session_id="t2")
    log.start()
    log.log_sent(0)
    log.log_ack(0)
    log._write_summary(total_bytes=1024, elapsed=0.5, success=True)

    json_path = tmp_path / "summary_t2.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["packets_sent"] == 1
    assert data["acks_received"] == 1


def test_csv_written_on_complete(tmp_path):
    log = TransferLogger(log_dir=str(tmp_path), session_id="t3")
    log.start()
    log.log_sent(0)
    log.log_ack(0)
    log.log_complete(512, "abc123")

    csv_path = tmp_path / "transfer_t3.csv"
    assert csv_path.exists()
    content = csv_path.read_text()
    assert "SENT" in content
    assert "ACK_RECEIVED" in content
    assert "TRANSFER_COMPLETE" in content


def test_duplicate_count(tmp_path):
    log = TransferLogger(log_dir=str(tmp_path), session_id="t4")
    log.start()
    log.log_duplicate(0)
    log.log_duplicate(0)
    assert log.duplicate_count == 2


def test_checksum_error_count(tmp_path):
    log = TransferLogger(log_dir=str(tmp_path), session_id="t5")
    log.start()
    log.log_checksum_error(3)
    assert log.checksum_errors == 1


def test_zero_elapsed_no_division_error(tmp_path):
    log = TransferLogger(log_dir=str(tmp_path), session_id="t6")
    log.start()
    summary = log._write_summary(total_bytes=0, elapsed=0.0, success=False)
    assert summary["throughput_bps"] == 0
    assert summary["goodput_bps"] == 0
