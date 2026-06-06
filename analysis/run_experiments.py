"""
NetProbe Deney Koşucusu

4 senaryoyu otomatik çalıştırır, sonuçları results/ klasörüne CSV olarak kaydeder,
ardından grafikleri üretir.

Kullanım:
    python analysis/run_experiments.py [--scenario 1|2|3|4|all]
                                       [--file TEST_DOSYASI]
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import socket
import threading
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.protocol import unpack_data, pack_ack, verify_data_checksum


RESULTS_DIR = "results"
LOGS_DIR    = "logs"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5002   # Deney için ayrı port


def md5_of_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def create_test_file(size_bytes: int, path: str):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "wb") as f:
        import random
        data = bytes(random.getrandbits(8) for _ in range(size_bytes))
        f.write(data)


def run_transfer(file_path: str, chunk_size: int = 1024,
                 timeout: float = 1.0, max_retries: int = 5,
                 loss_rate: float = 0.0, window_size: int = 1,
                 server_port: int = SERVER_PORT) -> dict:
    """
    Dahili olarak server + client çalıştırır, JSON özetini döndürür.
    """
    # Sunucuyu ayrı thread'de başlat
    server_ready = threading.Event()
    result_holder = {}

    def server_thread():
        import socket as sock_mod
        from src.network_sim import SimulatedSocket, create_udp_socket
        from src.logger import TransferLogger

        server_sock = create_udp_socket(loss_rate=loss_rate)
        server_sock.bind((SERVER_HOST, server_port))
        server_sock.settimeout(10.0)
        server_ready.set()

        buffer = {}
        total_pkts = None
        received = 0

        while True:
            try:
                raw, addr = server_sock.recvfrom(65535)
            except sock_mod.timeout:
                break
            pkt = unpack_data(raw)
            if pkt is None:
                continue
            total_pkts = pkt["total_pkts"]
            seq = pkt["seq_num"]
            if not verify_data_checksum(pkt):
                continue
            if seq not in buffer:
                buffer[seq] = pkt["payload"]
                received += 1
            ack = pack_ack(seq)
            server_sock.sendto(ack, addr)
            if total_pkts and received == total_pkts:
                break
        server_sock.close()

    srv = threading.Thread(target=server_thread, daemon=True)
    srv.start()
    server_ready.wait(timeout=3)

    # İstemciyi çalıştır
    cmd = [
        sys.executable, "src/client.py",
        "--file", file_path,
        "--host", SERVER_HOST,
        "--port", str(server_port),
        "--chunk-size", str(chunk_size),
        "--timeout", str(timeout),
        "--max-retries", str(max_retries),
        "--loss-rate", str(loss_rate),
        "--window-size", str(window_size),
    ]

    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    elapsed = time.time() - start

    srv.join(timeout=5)

    # En son oluşturulan JSON özetini bul
    import glob
    summaries = sorted(glob.glob(os.path.join(LOGS_DIR, "summary_client_*.json")))
    if summaries:
        with open(summaries[-1]) as f:
            result = json.load(f)
    else:
        result = {"elapsed_s": elapsed, "success": proc.returncode == 0}

    result["chunk_size"]      = chunk_size
    result["timeout_s"]       = timeout
    result["loss_rate"]       = loss_rate
    result["window_size"]     = window_size
    result["file_size_bytes"] = os.path.getsize(file_path)
    result["throughput_kbps"] = result.get("throughput_bps", 0) / 1024
    result["goodput_kbps"]    = result.get("goodput_bps", 0) / 1024

    return result


def save_scenario_csv(scenario_id: int, rows: list[dict], fieldnames: list[str]):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"scenario{scenario_id}_{int(time.time())}.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[EXP] Senaryo {scenario_id} kaydedildi: {path}")
    return path


def scenario1(base_file: str):
    """Paket boyutunun etkisi"""
    print("\n[EXP] === Senaryo 1: Paket Boyutu Etkisi ===")
    chunk_sizes = [256, 512, 1024, 4096]
    rows = []
    for cs in chunk_sizes:
        print(f"[EXP] chunk_size={cs}B...")
        r = run_transfer(base_file, chunk_size=cs, loss_rate=0.0)
        rows.append(r)
        time.sleep(1)
    return save_scenario_csv(1, rows,
        ["chunk_size", "elapsed_s", "throughput_kbps", "goodput_kbps",
         "retransmissions", "retx_rate", "packets_sent"])


def scenario2(base_file: str):
    """Timeout değerinin etkisi"""
    print("\n[EXP] === Senaryo 2: Timeout Etkisi ===")
    timeouts = [0.1, 0.5, 1.0, 2.0]
    rows = []
    for to in timeouts:
        print(f"[EXP] timeout={to}s, loss=5%...")
        r = run_transfer(base_file, timeout=to, loss_rate=0.05, chunk_size=1024)
        rows.append(r)
        time.sleep(1)
    return save_scenario_csv(2, rows,
        ["timeout_s", "elapsed_s", "throughput_kbps", "goodput_kbps",
         "retransmissions", "retx_rate", "timeouts"])


def scenario3(base_file: str):
    """Kayıp oranının etkisi"""
    print("\n[EXP] === Senaryo 3: Kayıp Oranı Etkisi ===")
    loss_rates = [0.0, 0.05, 0.10, 0.20]
    rows = []
    for lr in loss_rates:
        print(f"[EXP] loss_rate={lr:.0%}...")
        r = run_transfer(base_file, loss_rate=lr, chunk_size=1024, timeout=1.0)
        rows.append(r)
        time.sleep(1)
    return save_scenario_csv(3, rows,
        ["loss_rate", "elapsed_s", "throughput_kbps", "goodput_kbps",
         "retransmissions", "retx_rate", "timeouts"])


def scenario4(sizes_and_files: list[tuple[int, str]]):
    """Dosya boyutunun etkisi"""
    print("\n[EXP] === Senaryo 4: Dosya Boyutu Etkisi ===")
    rows = []
    for size_bytes, file_path in sizes_and_files:
        print(f"[EXP] file_size={size_bytes//1024}KB...")
        r = run_transfer(file_path, chunk_size=1024, loss_rate=0.0, timeout=1.0)
        rows.append(r)
        time.sleep(1)
    return save_scenario_csv(4, rows,
        ["file_size_bytes", "elapsed_s", "throughput_kbps", "goodput_kbps",
         "retransmissions", "retx_rate", "packets_sent"])


def prepare_test_files():
    sizes = {
        "10KB":  10 * 1024,
        "100KB": 100 * 1024,
        "1MB":   1024 * 1024,
        "10MB":  10 * 1024 * 1024,
    }
    os.makedirs("test_files", exist_ok=True)
    files = {}
    for label, size in sizes.items():
        path = f"test_files/test_{label}.bin"
        if not os.path.exists(path):
            print(f"[EXP] Test dosyası oluşturuluyor: {path}")
            create_test_file(size, path)
        files[label] = (size, path)
    return files


def main():
    parser = argparse.ArgumentParser(description="NetProbe Deney Koşucusu")
    parser.add_argument("--scenario", default="all",
                        choices=["1", "2", "3", "4", "all"])
    parser.add_argument("--file", default=None,
                        help="Senaryo 1-3 için test dosyası (varsayılan: 1MB)")
    args = parser.parse_args()

    files = prepare_test_files()
    base_file = args.file or files["1MB"][1]

    run_all = args.scenario == "all"

    if run_all or args.scenario == "1":
        scenario1(base_file)
    if run_all or args.scenario == "2":
        scenario2(base_file)
    if run_all or args.scenario == "3":
        scenario3(base_file)
    if run_all or args.scenario == "4":
        scenario4(list(files.values()))

    print("\n[EXP] Grafikler üretiliyor...")
    subprocess.run([sys.executable, "analysis/plot.py"],
                   cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("[EXP] Tüm deneyler tamamlandı. Sonuçlar: results/")


if __name__ == "__main__":
    main()
