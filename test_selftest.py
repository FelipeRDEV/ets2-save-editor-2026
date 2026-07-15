"""Self-validation tests (no real save required).

- ScsC encryption round-trip (encrypt -> decrypt_scsc).
- Decoding a hand-built BSII stream.
- Field editing via regex over SiiN text.

Run:  python test_selftest.py
"""

import struct
import zlib

from Crypto.Cipher import AES

from ets2editor import decode_bsii, decode_to_text, detect_signature, SaveFile
from ets2editor.formats import SCS_KEY
from ets2editor import bsii


# --- helpers to build test data --------------------------------------------

def encode_token(s):
    value = 0
    for i, ch in enumerate(s):
        idx = bsii.CHAR_TABLE.index(ch)
        value += (idx + 1) * (38 ** i)
    return value


def build_bsii():
    out = bytearray()
    out += b"BSII"
    out += struct.pack("<I", 2)  # version 2

    # structure definition (block_type 0)
    out += struct.pack("<I", 0)          # block_type
    out += struct.pack("<B", 1)          # validity
    out += struct.pack("<I", 1)          # structure_id
    out += struct.pack("<I", len(b"economy")) + b"economy"
    # segment: UInt64 experience_points
    out += struct.pack("<I", bsii.UInt64)
    out += struct.pack("<I", len(b"experience_points")) + b"experience_points"
    # segment: Int64 some_int
    out += struct.pack("<I", bsii.Int64)
    out += struct.pack("<I", len(b"some_int")) + b"some_int"
    # segment: ByteBool active
    out += struct.pack("<I", bsii.ByteBool)
    out += struct.pack("<I", len(b"active")) + b"active"
    # segment terminator
    out += struct.pack("<I", 0)

    # data block (block_type = structure_id 1)
    out += struct.pack("<I", 1)
    # id: part_count 1, token("player")
    out += struct.pack("<B", 1)
    out += struct.pack("<Q", encode_token("player"))
    # values
    out += struct.pack("<Q", 123456)     # experience_points
    out += struct.pack("<q", -5)         # some_int
    out += struct.pack("<B", 1)          # active -> true

    # end of definitions
    out += struct.pack("<I", 0)
    out += struct.pack("<B", 0)
    return bytes(out)


def encrypt_scsc(plaintext_bytes):
    compressed = zlib.compress(plaintext_bytes, 9)
    pad = (-len(compressed)) % 16
    padded = compressed + b"\x00" * pad
    iv = bytes(range(16))
    cipher = AES.new(SCS_KEY, AES.MODE_CBC, iv)
    ct = cipher.encrypt(padded)
    header = b"ScsC" + b"\x00" * 32 + iv + struct.pack("<I", len(plaintext_bytes))
    return header + ct


# --- tests -----------------------------------------------------------------

def test_bsii():
    text = decode_bsii(build_bsii())
    assert "economy : player {" in text, text
    assert "experience_points: 123456" in text, text
    assert "some_int: -5" in text, text
    assert "active: true" in text, text
    print("[OK] BSII decode\n" + text)


def test_crypto_roundtrip():
    sample = b"SiiNunit\n{\neconomy : player {\n money_account: 999\n}\n\n}\n"
    blob = encrypt_scsc(sample)
    assert detect_signature(blob).name == "ENCRYPTED"
    text, fmt = decode_to_text(blob)
    assert fmt == "encrypted+plain", fmt
    assert "money_account: 999" in text, text
    print("[OK] ScsC round-trip (%s)" % fmt)


def test_crypto_binary_roundtrip():
    blob = encrypt_scsc(build_bsii())
    text, fmt = decode_to_text(blob)
    assert fmt == "encrypted+binary", fmt
    assert "experience_points: 123456" in text
    print("[OK] ScsC+BSII round-trip")


def test_field_edit(tmpfile="_selftest_game.sii"):
    sample = ("SiiNunit\n{\nbank : _nameless.1 {\n money_account: 1000\n}\n\n"
              "economy : player {\n experience_points: 50\n adr: 0\n}\n\n}\n")
    with open(tmpfile, "wb") as fh:
        fh.write(sample.encode("utf-8"))
    sf = SaveFile(tmpfile)
    assert sf.get_field("money_account") == "1000"
    sf.apply_quick_fields({"money_account": "9999999",
                           "experience_points": "123456", "adr": "6"})
    assert "money_account: 9999999" in sf.text
    assert "experience_points: 123456" in sf.text
    assert "adr: 6" in sf.text
    print("[OK] regex field editing")
    import os
    os.remove(tmpfile)


if __name__ == "__main__":
    test_bsii()
    test_crypto_roundtrip()
    test_crypto_binary_roundtrip()
    test_field_edit()
    print("\nALL TESTS PASSED.")
