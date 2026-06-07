"""
NetProbe UDP İstemcisi

Stop-and-Wait temel modu (window_size=1) ve Go-Back-N modu (window_size>1) desteklenir.

Kullanım:
    python src/client.py --file DOSYA [--host HOST] [--port PORT]
                         [--chunk-size BYTES] [--timeout SECS]
                         [--max-retries N] [--window-size N]
                         [--loss-rate RATE] [--delay-ms MS]
"""

import argparse
import hashlib
import os
import socket
import sys
import time
from threading import Thread, Lock, Event

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.protocol import pack_data, unpack_ack
from src.logger import TransferLogger
from src.network_sim import create_udp_socket

DEFAULT_CHUNK_SIZE  = 1024   # byte
DEFAULT_TIMEOUT     = 1.0    # saniye
DEFAULT_MAX_RETRIES = 5
DEFAULT_WINDOW_SIZE = 1      # 1 = stop-and-wait


def md5_of_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def split_file(path: str, chunk_size: int) -> list[bytes]:
    chunks = []
    with open(path, "rb") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            chunks.append(data)
    return chunks


# ---------------------------------------------------------------------------
# Stop-and-Wait (window_size = 1)
# ---------------------------------------------------------------------------

def send_stop_and_wait(sock, chunks: list[bytes], server_addr: tuple,
                       timeout: float, max_retries: int,
                       logger: TransferLogger) -> bool:
    total = len(chunks)
    sock.settimeout(timeout)

    for seq, payload in enumerate(chunks):
        pkt = pack_data(seq, total, payload)
        sent = False

        for attempt in range(1, max_retries + 2):
            if attempt == 1:
                logger.log_sent(seq, attempt=1)
            else:
                logger.log_retransmit(seq, attempt=attempt)

            sock.sendto(pkt, server_addr)

            try:
                raw, _ = sock.recvfrom(128)
                ack = unpack_ack(raw)
                if ack and ack["ack_num"] == seq:
                    logger.log_ack(seq)
                    sent = True
                    break
            except socket.timeout:
                logger.log_timeout(seq, attempt=attempt)
                # attempt == max_retries + 1 olduğunda artık deneme hakkı kalmadı
                if attempt >= max_retries + 1:
                    break

        if not sent:
            reason = f"max retries ({max_retries}) aşıldı"
            logger.log_failed(seq, reason)
            print(f"[CLIENT] HATA: SEQ={seq} gönderilemedi ({reason})")
            return False

        progress = (seq + 1) / total * 100
        print(f"\r[CLIENT] {seq + 1}/{total} paket gönderildi ({progress:.1f}%)", end="", flush=True)

    print()
    return True


# ---------------------------------------------------------------------------
# Go-Back-N (window_size > 1)
# ---------------------------------------------------------------------------

def send_go_back_n(sock, chunks: list[bytes], server_addr: tuple,
                   timeout: float, max_retries: int, window_size: int,
                   logger: TransferLogger) -> bool:
    total = len(chunks)
    sock.settimeout(timeout)

    base         = 0
    next_seq     = 0
    acked        = [False] * total
    attempts     = [0] * total
    send_times   = {}
    lock         = Lock()
    stop_event   = Event()
    failed_flag  = [False]

    def ack_receiver():
        while not stop_event.is_set():
            try:
                raw, _ = sock.recvfrom(128)
                ack = unpack_ack(raw)
                if ack is None:
                    continue
                ack_num = ack["ack_num"]
                with lock:
                    if 0 <= ack_num < total and not acked[ack_num]:
                        acked[ack_num] = True
                        logger.log_ack(ack_num)
            except socket.timeout:
                pass
            except OSError as e:
                if not stop_event.is_set():
                    print(f"[CLIENT] ACK alım hatası: {e}")
                break

    receiver = Thread(target=ack_receiver, daemon=True)
    receiver.start()

    window_start = time.time()

    while base < total and not failed_flag[0]:
        with lock:
            # Pencere içindeki paketleri gönder
            while next_seq < base + window_size and next_seq < total:
                if not acked[next_seq]:
                    pkt = pack_data(next_seq, total, chunks[next_seq])
                    attempts[next_seq] += 1
                    if attempts[next_seq] == 1:
                        logger.log_sent(next_seq, attempt=1)
                    else:
                        logger.log_retransmit(next_seq, attempt=attempts[next_seq])
                    sock.sendto(pkt, server_addr)
                    send_times[next_seq] = time.time()
                next_seq += 1

            # base'i ilerlet
            while base < total and acked[base]:
                base += 1

        time.sleep(0.001)

        # Timeout kontrolü: penceredeki paketler için
        now = time.time()
        with lock:
            for seq in range(base, min(next_seq, total)):
                if not acked[seq] and seq in send_times:
                    elapsed = now - send_times[seq]
                    if elapsed >= timeout:
                        if attempts[seq] > max_retries:
                            logger.log_failed(seq, f"max retries ({max_retries}) aşıldı")
                            print(f"\n[CLIENT] HATA: SEQ={seq} gönderilemedi")
                            failed_flag[0] = True
                            break
                        logger.log_timeout(seq, attempt=attempts[seq])
                        # Go-Back-N: base'den yeniden gönder
                        for resend_seq in range(seq, min(next_seq, total)):
                            if not acked[resend_seq]:
                                pkt = pack_data(resend_seq, total, chunks[resend_seq])
                                attempts[resend_seq] += 1
                                logger.log_retransmit(resend_seq, attempt=attempts[resend_seq])
                                sock.sendto(pkt, server_addr)
                                send_times[resend_seq] = time.time()
                        break

        progress = base / total * 100
        print(f"\r[CLIENT] {base}/{total} paket onaylandı ({progress:.1f}%)", end="", flush=True)

    stop_event.set()
    print()
    return not failed_flag[0]


# ---------------------------------------------------------------------------
# Ana gönderim fonksiyonu
# ---------------------------------------------------------------------------

def send_file(file_path: str, host: str, port: int,
              chunk_size: int, timeout: float,
              max_retries: int, window_size: int,
              loss_rate: float, delay_ms: float) -> bool:

    if not os.path.isfile(file_path):
        print(f"[CLIENT] Hata: dosya bulunamadı: {file_path}")
        return False

    file_hash = md5_of_file(file_path)
    chunks    = split_file(file_path, chunk_size)
    total     = len(chunks)
    file_size = os.path.getsize(file_path)

    print(f"[CLIENT] Dosya    : {file_path}")
    print(f"[CLIENT] Boyut    : {file_size} byte")
    print(f"[CLIENT] MD5      : {file_hash}")
    print(f"[CLIENT] Paketler : {total} (chunk={chunk_size}B)")
    print(f"[CLIENT] Pencere  : {window_size} ({'Stop-and-Wait' if window_size == 1 else 'Go-Back-N'})")

    session_id = str(int(time.time() * 1000))
    logger = TransferLogger(log_dir="logs", session_id=f"client_{session_id}")
    logger.start()

    sock = create_udp_socket(loss_rate=loss_rate, delay_ms=delay_ms)
    server_addr = (host, port)

    print(f"[CLIENT] Sunucu: {host}:{port} | loss={loss_rate:.0%} delay={delay_ms}ms")

    start = time.time()
    try:
        if window_size == 1:
            success = send_stop_and_wait(sock, chunks, server_addr,
                                         timeout, max_retries, logger)
        else:
            success = send_go_back_n(sock, chunks, server_addr,
                                      timeout, max_retries, window_size, logger)
    finally:
        sock.close()

    elapsed = time.time() - start

    if success:
        logger.log_complete(file_size, file_hash)
        throughput = file_size / elapsed / 1024
        print(f"[CLIENT] Aktarım tamamlandı: {elapsed:.2f}s | {throughput:.1f} KB/s")
    else:
        logger.finalize_failed(file_size)
        print(f"[CLIENT] Aktarım BAŞARISIZ: {elapsed:.2f}s")

    print(f"[CLIENT] Log    : logs/transfer_client_{session_id}.csv")
    print(f"[CLIENT] Özet   : logs/summary_client_{session_id}.json")
    return success


def main():
    parser = argparse.ArgumentParser(description="NetProbe UDP İstemcisi")
    parser.add_argument("--file",        required=True, help="Gönderilecek dosya")
    parser.add_argument("--host",        default="127.0.0.1")
    parser.add_argument("--port",        type=int,   default=5001)
    parser.add_argument("--chunk-size",  type=int,   default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--timeout",     type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-retries", type=int,   default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--window-size", type=int,   default=DEFAULT_WINDOW_SIZE,
                        help="1=Stop-and-Wait, >1=Go-Back-N")
    parser.add_argument("--loss-rate",   type=float, default=0.0,
                        help="İstemci tarafında simüle edilecek kayıp oranı (0.0-1.0)")
    parser.add_argument("--delay-ms",    type=float, default=0.0)
    args = parser.parse_args()

    success = send_file(
        file_path=args.file,
        host=args.host,
        port=args.port,
        chunk_size=args.chunk_size,
        timeout=args.timeout,
        max_retries=args.max_retries,
        window_size=args.window_size,
        loss_rate=args.loss_rate,
        delay_ms=args.delay_ms,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
