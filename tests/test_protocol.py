import pytest
from src import protocol


def test_data_roundtrip_preserves_payload():
    payload = b"hello netprobe"
    raw = protocol.pack_data(seq_num=3, total_pkts=10, payload=payload)
    pkt = protocol.unpack_data(raw)
    assert pkt is not None
    assert pkt["seq_num"] == 3
    assert pkt["total_pkts"] == 10
    assert pkt["payload"] == payload
    assert protocol.verify_data_checksum(pkt) is True


def test_data_roundtrip_empty_payload():
    payload = b""
    raw = protocol.pack_data(seq_num=0, total_pkts=1, payload=payload)
    pkt = protocol.unpack_data(raw)
    assert pkt is not None
    assert pkt["payload"] == payload
    assert protocol.verify_data_checksum(pkt) is True


def test_data_roundtrip_large_payload():
    payload = b"x" * 4096
    raw = protocol.pack_data(seq_num=99, total_pkts=100, payload=payload)
    pkt = protocol.unpack_data(raw)
    assert pkt is not None
    assert pkt["payload"] == payload
    assert protocol.verify_data_checksum(pkt) is True


def test_unpack_data_rejects_short_buffer():
    assert protocol.unpack_data(b"\x01\x00") is None


def test_unpack_data_rejects_wrong_type():
    raw = protocol.pack_ack(5)
    assert protocol.unpack_data(raw) is None


def test_corrupted_payload_fails_checksum():
    raw = bytearray(protocol.pack_data(0, 1, b"abcdef"))
    raw[-1] ^= 0xFF
    pkt = protocol.unpack_data(bytes(raw))
    assert pkt is not None
    assert protocol.verify_data_checksum(pkt) is False


def test_ack_roundtrip():
    raw = protocol.pack_ack(42)
    ack = protocol.unpack_ack(raw)
    assert ack == {"ack_num": 42}


def test_ack_roundtrip_zero():
    assert protocol.unpack_ack(protocol.pack_ack(0)) == {"ack_num": 0}


def test_ack_rejects_corrupted_crc():
    raw = bytearray(protocol.pack_ack(42))
    raw[-1] ^= 0xFF
    assert protocol.unpack_ack(bytes(raw)) is None


def test_ack_rejects_short_buffer():
    assert protocol.unpack_ack(b"\x02\x00") is None


def test_ack_rejects_wrong_type():
    payload = b"A" * 10
    raw = protocol.pack_data(0, 1, payload)
    assert protocol.unpack_ack(raw) is None
