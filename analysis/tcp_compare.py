"""
NetProbe TCP Karşılaştırma Modülü (Bonus)

Aynı dosyayı TCP üzerinden gönderir ve UDP sonuçlarıyla karşılaştırır.

Kullanım:
    python analysis/tcp_compare.py --file DOSYA [--host HOST] [--port PORT]
"""

import argparse
import hashlib
import json
import os
import socket
import sys
import threading
import time

CHUNK_SIZE = 4096


def md5_of_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def tcp_server(host: str, port: int, output_path: str,
               ready_event: threading.Event, result: dict):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(1)
    ready_event.set()

    conn, addr = server_sock.accept()
    server_sock.close()

    data_parts = []
    start = time.time()
    while True:
        chunk = conn.recv(CHUNK_SIZE)
        if not chunk:
            break
        data_parts.append(chunk)
    elapsed = time.time() - start
    conn.close()

    full_data = b"".join(data_parts)
    with open(output_path, "wb") as f:
        f.write(full_data)

    result["elapsed_s"]       = elapsed
    result["total_bytes"]     = len(full_data)
    result["throughput_kbps"] = len(full_data) / elapsed / 1024 if elapsed > 0 else 0
    result["hash"]            = md5_of_bytes(full_data)


def tcp_client(file_path: str, host: str, port: int) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    file_size = os.path.getsize(file_path)
    start = time.time()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)
    sock.close()
    elapsed = time.time() - start

    return {
        "send_elapsed_s":  elapsed,
        "file_size_bytes": file_size,
        "throughput_kbps": file_size / elapsed / 1024 if elapsed > 0 else 0,
    }


def run_tcp_transfer(file_path: str, host: str = "127.0.0.1",
                     port: int = 5003) -> dict:
    output_path = f"received_files/tcp_received_{int(time.time())}.bin"
    os.makedirs("received_files", exist_ok=True)

    server_result: dict = {}
    ready_event = threading.Event()

    srv = threading.Thread(
        target=tcp_server,
        args=(host, port, output_path, ready_event, server_result),
        daemon=True,
    )
    srv.start()
    ready_event.wait(timeout=3)

    client_result = tcp_client(file_path, host, port)
    srv.join(timeout=10)

    file_hash = hashlib.md5(open(file_path, "rb").read()).hexdigest()
    integrity = server_result.get("hash") == file_hash

    result = {
        "protocol":           "TCP",
        "file_size_bytes":    client_result["file_size_bytes"],
        "elapsed_s":          server_result.get("elapsed_s", 0),
        "throughput_kbps":    server_result.get("throughput_kbps", 0),
        "goodput_kbps":       server_result.get("throughput_kbps", 0),  # TCP'de retx yok
        "integrity":          integrity,
        "retransmissions":    0,   # TCP stack halleder
        "retx_rate":          0.0,
    }
    return result


def compare_with_udp(udp_summary_path: str, tcp_result: dict):
    with open(udp_summary_path) as f:
        udp = json.load(f)

    print("\n" + "="*60)
    print(f"{'Metrik':<25} {'UDP':>12} {'TCP':>12}")
    print("-"*60)
    metrics = [
        ("Throughput (KB/s)",    udp.get("throughput_bps", 0)/1024, tcp_result["throughput_kbps"]),
        ("Goodput (KB/s)",       udp.get("goodput_bps", 0)/1024,    tcp_result["goodput_kbps"]),
        ("Tamamlanma (s)",       udp.get("elapsed_s", 0),           tcp_result["elapsed_s"]),
        ("Retransmission sayısı",udp.get("retransmissions", 0),     tcp_result["retransmissions"]),
        ("Retx Oranı (%)",       udp.get("retx_rate", 0)*100,       tcp_result["retx_rate"]*100),
    ]
    for label, udp_val, tcp_val in metrics:
        print(f"{label:<25} {udp_val:>12.2f} {tcp_val:>12.2f}")
    print("="*60)

    # Matplotlib ile karşılaştırma grafiği
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = ["Throughput\n(KB/s)", "Goodput\n(KB/s)", "Tamamlanma\n(s)"]
        udp_vals = [udp.get("throughput_bps", 0)/1024,
                    udp.get("goodput_bps", 0)/1024,
                    udp.get("elapsed_s", 0)]
        tcp_vals = [tcp_result["throughput_kbps"],
                    tcp_result["goodput_kbps"],
                    tcp_result["elapsed_s"]]

        x = range(len(labels))
        width = 0.35
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar([i - width/2 for i in x], udp_vals, width, label="UDP (NetProbe)", color="steelblue")
        ax.bar([i + width/2 for i in x], tcp_vals, width, label="TCP (standart)",  color="seagreen")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_title("UDP vs TCP Karşılaştırması")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        os.makedirs("results", exist_ok=True)
        path = "results/udp_vs_tcp.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[TCP] Grafik kaydedildi: {path}")
    except ImportError:
        pass


def main():
    parser = argparse.ArgumentParser(description="NetProbe TCP Karşılaştırma")
    parser.add_argument("--file",        required=True)
    parser.add_argument("--host",        default="127.0.0.1")
    parser.add_argument("--port",        type=int, default=5003)
    parser.add_argument("--udp-summary", default=None,
                        help="Karşılaştırılacak UDP özet JSON dosyası")
    args = parser.parse_args()

    print(f"[TCP] {args.file} TCP ile gönderiliyor...")
    result = run_tcp_transfer(args.file, args.host, args.port)

    print(f"[TCP] Tamamlandı: {result['elapsed_s']:.2f}s | "
          f"{result['throughput_kbps']:.1f} KB/s | "
          f"Bütünlük: {'OK' if result['integrity'] else 'HATA'}")

    if args.udp_summary:
        compare_with_udp(args.udp_summary, result)


if __name__ == "__main__":
    main()
