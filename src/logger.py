"""
NetProbe Olay Kayıt Sistemi

Olayları hem CSV hem JSON formatında kaydeder.
Özet istatistikleri de üretir.
"""

import csv
import json
import time
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


EVENT_SENT             = "SENT"
EVENT_ACK_RECEIVED     = "ACK_RECEIVED"
EVENT_TIMEOUT          = "TIMEOUT"
EVENT_RETRANSMIT       = "RETRANSMIT"
EVENT_DUPLICATE        = "DUPLICATE"
EVENT_TRANSFER_COMPLETE = "TRANSFER_COMPLETE"
EVENT_TRANSFER_FAILED  = "TRANSFER_FAILED"
EVENT_CHECKSUM_ERROR   = "CHECKSUM_ERROR"


@dataclass
class LogEntry:
    timestamp: float
    event: str
    seq_num: Optional[int] = None
    attempt: Optional[int] = None
    note: Optional[str] = None


class TransferLogger:
    def __init__(self, log_dir: str = "logs", session_id: Optional[str] = None):
        os.makedirs(log_dir, exist_ok=True)
        if session_id is None:
            session_id = str(int(time.time()))
        self.session_id = session_id
        self.csv_path = os.path.join(log_dir, f"transfer_{session_id}.csv")
        self.json_path = os.path.join(log_dir, f"summary_{session_id}.json")

        self._entries: list[LogEntry] = []
        self._start_time: Optional[float] = None

        # Sayaçlar
        self.sent_count       = 0
        self.ack_count        = 0
        self.timeout_count    = 0
        self.retransmit_count = 0
        self.duplicate_count  = 0
        self.failed_count     = 0
        self.checksum_errors  = 0

        # RTT takibi: seq_num -> gönderim zamanı
        self._send_times: dict[int, float] = {}
        self._rtts: list[float] = []

    # --- Olay kayıt metodları ---

    def start(self):
        self._start_time = time.time()

    def log_sent(self, seq_num: int, attempt: int = 1):
        self.sent_count += 1
        self._send_times[seq_num] = time.time()
        self._log(EVENT_SENT, seq_num=seq_num, attempt=attempt)

    def log_ack(self, seq_num: int):
        self.ack_count += 1
        if seq_num in self._send_times:
            rtt = time.time() - self._send_times.pop(seq_num)
            self._rtts.append(rtt)
        self._log(EVENT_ACK_RECEIVED, seq_num=seq_num)

    def log_timeout(self, seq_num: int, attempt: int):
        self.timeout_count += 1
        self._log(EVENT_TIMEOUT, seq_num=seq_num, attempt=attempt)

    def log_retransmit(self, seq_num: int, attempt: int):
        self.retransmit_count += 1
        self._log(EVENT_RETRANSMIT, seq_num=seq_num, attempt=attempt)

    def log_duplicate(self, seq_num: int):
        self.duplicate_count += 1
        self._log(EVENT_DUPLICATE, seq_num=seq_num)

    def log_checksum_error(self, seq_num: int):
        self.checksum_errors += 1
        self._log(EVENT_CHECKSUM_ERROR, seq_num=seq_num)

    def log_complete(self, total_bytes: int, file_hash: str):
        elapsed = time.time() - self._start_time if self._start_time else 0
        self._log(EVENT_TRANSFER_COMPLETE,
                  note=f"bytes={total_bytes} hash={file_hash} elapsed={elapsed:.4f}s")
        self._flush_csv()
        self._write_summary(total_bytes, elapsed, success=True)

    def log_failed(self, seq_num: int, reason: str):
        self.failed_count += 1
        self._log(EVENT_TRANSFER_FAILED, seq_num=seq_num, note=reason)

    def finalize_failed(self, total_bytes_attempted: int):
        elapsed = time.time() - self._start_time if self._start_time else 0
        self._flush_csv()
        self._write_summary(total_bytes_attempted, elapsed, success=False)

    # --- Dahili ---

    def _log(self, event: str, seq_num=None, attempt=None, note=None):
        entry = LogEntry(
            timestamp=time.time(),
            event=event,
            seq_num=seq_num,
            attempt=attempt,
            note=note,
        )
        self._entries.append(entry)

    def _flush_csv(self):
        with open(self.csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "event", "seq_num", "attempt", "note"]
            )
            writer.writeheader()
            for e in self._entries:
                writer.writerow(asdict(e))

    def _write_summary(self, total_bytes: int, elapsed: float, success: bool):
        avg_rtt = sum(self._rtts) / len(self._rtts) if self._rtts else 0
        throughput = total_bytes / elapsed if elapsed > 0 else 0
        # Goodput: toplam gönderim sayısı (ilk + retransmit) üzerinden overhead oranı
        total_transmissions = self.sent_count + self.retransmit_count
        overhead_ratio = self.retransmit_count / total_transmissions if total_transmissions > 0 else 0
        goodput = max(0.0, throughput * (1 - overhead_ratio))
        total_sent = self.sent_count
        # Kayıp oranı: ACK alınamayan paket oranı; negatif olmayacak şekilde sınırlandırılır
        loss_rate = max(0.0,
            (total_sent - self.ack_count) / total_sent if total_sent > 0 else 0
        )
        retx_rate = self.retransmit_count / total_sent if total_sent > 0 else 0

        summary = {
            "session_id":       self.session_id,
            "success":          success,
            "total_bytes":      total_bytes,
            "elapsed_s":        round(elapsed, 4),
            "throughput_bps":   round(throughput, 2),
            "goodput_bps":      round(goodput, 2),
            "packets_sent":     self.sent_count,
            "acks_received":    self.ack_count,
            "timeouts":         self.timeout_count,
            "retransmissions":  self.retransmit_count,
            "duplicates":       self.duplicate_count,
            "failed_packets":   self.failed_count,
            "checksum_errors":  self.checksum_errors,
            "packet_loss_rate": round(loss_rate, 4),
            "retx_rate":        round(retx_rate, 4),
            "avg_rtt_s":        round(avg_rtt, 6),
        }
        with open(self.json_path, "w") as f:
            json.dump(summary, f, indent=2)
        return summary

    def get_summary(self) -> dict:
        elapsed = (time.time() - self._start_time) if self._start_time else 0
        return self._write_summary(0, elapsed, success=False)
