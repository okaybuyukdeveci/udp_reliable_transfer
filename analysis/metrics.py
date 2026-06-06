"""
NetProbe Performans Metrikleri

JSON özet dosyalarından veya doğrudan parametrelerden metrikleri hesaplar.
"""

import json
import os
import glob
from dataclasses import dataclass


@dataclass
class TransferMetrics:
    session_id:       str
    success:          bool
    total_bytes:      int
    elapsed_s:        float
    throughput_bps:   float   # byte/s
    goodput_bps:      float   # byte/s
    packets_sent:     int
    acks_received:    int
    timeouts:         int
    retransmissions:  int
    duplicates:       int
    failed_packets:   int
    checksum_errors:  int
    packet_loss_rate: float   # 0.0 - 1.0
    retx_rate:        float   # 0.0 - 1.0
    avg_rtt_s:        float

    @property
    def throughput_kbps(self) -> float:
        return self.throughput_bps / 1024

    @property
    def goodput_kbps(self) -> float:
        return self.goodput_bps / 1024

    @property
    def completion_time_s(self) -> float:
        return self.elapsed_s


def load_from_json(json_path: str) -> TransferMetrics:
    with open(json_path) as f:
        d = json.load(f)
    return TransferMetrics(**d)


def load_all_from_dir(log_dir: str = "logs") -> list[TransferMetrics]:
    results = []
    for path in glob.glob(os.path.join(log_dir, "summary_*.json")):
        try:
            results.append(load_from_json(path))
        except Exception as e:
            print(f"Uyarı: {path} okunamadı: {e}")
    return results


def print_metrics(m: TransferMetrics):
    print(f"\n{'='*50}")
    print(f"Oturum   : {m.session_id}")
    print(f"Başarı   : {'Evet' if m.success else 'Hayır'}")
    print(f"Boyut    : {m.total_bytes:,} byte")
    print(f"Süre     : {m.elapsed_s:.4f} s")
    print(f"Throughput : {m.throughput_kbps:.2f} KB/s")
    print(f"Goodput    : {m.goodput_kbps:.2f} KB/s")
    print(f"Gönderilen : {m.packets_sent} paket")
    print(f"ACK alındı : {m.acks_received}")
    print(f"Timeout    : {m.timeouts}")
    print(f"Retransmit : {m.retransmissions} ({m.retx_rate:.1%})")
    print(f"Kayıp oranı: {m.packet_loss_rate:.1%}")
    print(f"Ortalama RTT: {m.avg_rtt_s*1000:.2f} ms")
    print(f"{'='*50}\n")
