"""
NetProbe UDP Sunucusu

Kullanım:
    python src/server.py [--host HOST] [--port PORT] [--output-dir DIR]
                         [--loss-rate RATE] [--delay-ms MS]
"""

import argparse
import hashlib
import os
import socket
import sys
import time

# src/ klasörü içinden çalışırken üst dizini de import path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.protocol import unpack_data, pack_ack, verify_data_checksum
from src.logger import TransferLogger
from src.network_sim import SimulatedSocket, create_udp_socket


def md5_of_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def run_server(host: str, port: int, output_dir: str,
               loss_rate: float, delay_ms: float):
    os.makedirs(output_dir, exist_ok=True)

    sock = create_udp_socket(loss_rate=loss_rate, delay_ms=delay_ms)
    sock.bind((host, port))
    print(f"[SERVER] {host}:{port} dinleniyor | loss={loss_rate:.0%} delay={delay_ms}ms")

    while True:
        _handle_transfer(sock, output_dir)


def _handle_transfer(sock: SimulatedSocket, output_dir: str):
    """Tek bir dosya aktarımını yönetir."""
    buffer: dict[int, bytes] = {}
    total_pkts = None
    client_addr = None
    session_id = str(int(time.time() * 1000))
    logger = TransferLogger(log_dir="logs", session_id=f"server_{session_id}")
    logger.start()

    print("[SERVER] Yeni aktarım bekleniyor...")

    while True:
        try:
            raw, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[SERVER] Alım hatası: {e}")
            continue

        pkt = unpack_data(raw)
        if pkt is None:
            continue

        if client_addr is None:
            client_addr = addr
            print(f"[SERVER] İstemci bağlandı: {addr}")
        elif addr != client_addr:
            print(f"[SERVER] Bilinmeyen istemciden paket yoksayıldı: {addr}")
            continue

        seq = pkt["seq_num"]
        total_pkts = pkt["total_pkts"]

        # Checksum doğrulama
        if not verify_data_checksum(pkt):
            logger.log_checksum_error(seq)
            print(f"[SERVER] SEQ={seq} checksum hatası, yoksayıldı")
            continue

        # Duplicate tespiti
        if seq in buffer:
            logger.log_duplicate(seq)
            # Duplicate'e de ACK gönder (istemci ACK'i kaybetmiş olabilir)
            ack = pack_ack(seq)
            sock.sendto(ack, addr)
            continue

        buffer[seq] = pkt["payload"]
        logger.log_ack(seq)

        ack = pack_ack(seq)
        sock.sendto(ack, addr)

        received = len(buffer)
        print(f"[SERVER] SEQ={seq}/{total_pkts - 1} alındı ({received}/{total_pkts})")

        if total_pkts is not None and received == total_pkts:
            _assemble_and_save(buffer, total_pkts, output_dir,
                               session_id, logger, client_addr)
            return


def _assemble_and_save(buffer: dict, total_pkts: int, output_dir: str,
                       session_id: str, logger: TransferLogger, client_addr):
    data = b"".join(buffer[i] for i in range(total_pkts))
    file_hash = md5_of_bytes(data)
    out_path = os.path.join(output_dir, f"received_{session_id}.bin")
    with open(out_path, "wb") as f:
        f.write(data)

    total_bytes = len(data)
    logger.log_complete(total_bytes, file_hash)
    print(f"[SERVER] Aktarım tamamlandı!")
    print(f"[SERVER] Boyut : {total_bytes} byte")
    print(f"[SERVER] MD5   : {file_hash}")
    print(f"[SERVER] Dosya : {out_path}")


def main():
    parser = argparse.ArgumentParser(description="NetProbe UDP Sunucusu")
    parser.add_argument("--host",       default="127.0.0.1")
    parser.add_argument("--port",       type=int, default=5001)
    parser.add_argument("--output-dir", default="received_files")
    parser.add_argument("--loss-rate",  type=float, default=0.0,
                        help="Simüle edilecek paket kayıp oranı (0.0-1.0)")
    parser.add_argument("--delay-ms",   type=float, default=0.0,
                        help="Simüle edilecek gecikme (ms)")
    args = parser.parse_args()

    run_server(args.host, args.port, args.output_dir,
               args.loss_rate, args.delay_ms)


if __name__ == "__main__":
    main()
