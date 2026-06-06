"""
NetProbe Ağ Simülatörü

Gerçek UDP soketini sarar; loss_rate ve delay_ms parametreleriyle
yapay paket kaybı ve gecikme simüle eder.
"""

import socket
import random
import time


class SimulatedSocket:
    """
    Gerçek bir UDP socket'ini sarar.
    loss_rate: 0.0 (kayıp yok) - 1.0 (tüm paketler kaybolur)
    delay_ms:  her pakete eklenen yapay gecikme (ms)
    """

    def __init__(self, sock: socket.socket, loss_rate: float = 0.0, delay_ms: float = 0.0):
        self._sock = sock
        self.loss_rate = max(0.0, min(1.0, loss_rate))
        self.delay_ms  = max(0.0, delay_ms)

        self._dropped_send = 0
        self._dropped_recv = 0

    # Soket ayarları doğrudan gerçek sokete iletilir
    def settimeout(self, timeout):
        self._sock.settimeout(timeout)

    def bind(self, addr):
        self._sock.bind(addr)

    def close(self):
        self._sock.close()

    def getsockname(self):
        return self._sock.getsockname()

    def sendto(self, data: bytes, addr) -> int:
        if self._should_drop():
            self._dropped_send += 1
            return len(data)  # Sanki gönderilmiş gibi davran
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
        return self._sock.sendto(data, addr)

    def recvfrom(self, bufsize: int):
        data, addr = self._sock.recvfrom(bufsize)
        if self._should_drop():
            self._dropped_recv += 1
            # Alındı ama yok sayıldı; timeout beklentisi karşılanması için
            # boş veri yerine tekrar almayı dene (basit yaklaşım: timeout'a bırak)
            raise socket.timeout("simulated packet loss on receive")
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
        return data, addr

    def _should_drop(self) -> bool:
        return self.loss_rate > 0.0 and random.random() < self.loss_rate

    @property
    def stats(self) -> dict:
        return {
            "dropped_on_send": self._dropped_send,
            "dropped_on_recv": self._dropped_recv,
        }


def create_udp_socket(loss_rate: float = 0.0, delay_ms: float = 0.0) -> SimulatedSocket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return SimulatedSocket(sock, loss_rate=loss_rate, delay_ms=delay_ms)
