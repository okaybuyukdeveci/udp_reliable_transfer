"""
NetProbe Uygulama Katmanı Protokolü

Veri Paketi: | type(1B) | seq_num(4B) | total_pkts(4B) | payload_len(2B) | checksum(16B MD5) | payload |
ACK Paketi:  | type(1B) | ack_num(4B) | checksum(4B CRC32) |
"""

import struct
import hashlib
import zlib

PKT_DATA = 0x01
PKT_ACK  = 0x02

DATA_HEADER_FORMAT = "!B I I H 16s"
DATA_HEADER_SIZE   = struct.calcsize(DATA_HEADER_FORMAT)  # 27 bytes

ACK_FORMAT = "!B I I"
ACK_SIZE   = struct.calcsize(ACK_FORMAT)  # 9 bytes


def _md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def pack_data(seq_num: int, total_pkts: int, payload: bytes) -> bytes:
    checksum = _md5(payload)
    header = struct.pack(
        DATA_HEADER_FORMAT,
        PKT_DATA, seq_num, total_pkts, len(payload), checksum
    )
    return header + payload


def unpack_data(raw: bytes) -> dict | None:
    if len(raw) < DATA_HEADER_SIZE:
        return None
    pkt_type, seq_num, total_pkts, payload_len, checksum = struct.unpack_from(
        DATA_HEADER_FORMAT, raw
    )
    if pkt_type != PKT_DATA:
        return None
    payload = raw[DATA_HEADER_SIZE: DATA_HEADER_SIZE + payload_len]
    if len(payload) != payload_len:
        return None
    return {
        "seq_num": seq_num,
        "total_pkts": total_pkts,
        "payload_len": payload_len,
        "checksum": checksum,
        "payload": payload,
    }


def verify_data_checksum(pkt: dict) -> bool:
    return _md5(pkt["payload"]) == pkt["checksum"]


def pack_ack(ack_num: int) -> bytes:
    body = struct.pack("!B I", PKT_ACK, ack_num)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return struct.pack(ACK_FORMAT, PKT_ACK, ack_num, crc)


def unpack_ack(raw: bytes) -> dict | None:
    if len(raw) < ACK_SIZE:
        return None
    pkt_type, ack_num, crc = struct.unpack_from(ACK_FORMAT, raw)
    if pkt_type != PKT_ACK:
        return None
    body = struct.pack("!B I", PKT_ACK, ack_num)
    if (zlib.crc32(body) & 0xFFFFFFFF) != crc:
        return None
    return {"ack_num": ack_num}
