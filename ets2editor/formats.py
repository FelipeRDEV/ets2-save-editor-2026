"""Format detection, ScsC decryption and the pipeline down to SiiN text."""

import struct
import zlib
import enum

from .bsii import decode_bsii

try:
    from Crypto.Cipher import AES  # pycryptodome
    _HAVE_AES = True
except ImportError:  # pragma: no cover
    _HAVE_AES = False

# Public AES-256 key used by SCS Software (identical to SII_Decrypt).
SCS_KEY = bytes([
    0x2a, 0x5f, 0xcb, 0x17, 0x91, 0xd2, 0x2f, 0xb6, 0x02, 0x45, 0xb3, 0xd8,
    0x36, 0x9e, 0xd0, 0xb2, 0xc2, 0x73, 0x71, 0x56, 0x3f, 0xbf, 0x1f, 0x3c,
    0x9e, 0xdf, 0x6b, 0x11, 0x82, 0x5a, 0x5d, 0x0a,
])


class Signature(enum.Enum):
    PLAIN = b"SiiN"        # plain text (SiiNunit)
    ENCRYPTED = b"ScsC"    # encrypted (AES + zlib)
    BINARY = b"BSII"       # binary
    THREE_NK = b"3nK\x01"  # obfuscated (not used in saves)
    UNKNOWN = b""


def detect_signature(data):
    head = data[:4]
    for sig in (Signature.PLAIN, Signature.ENCRYPTED,
                Signature.BINARY, Signature.THREE_NK):
        if head == sig.value:
            return sig
    return Signature.UNKNOWN


def decrypt_scsc(data):
    """Decrypt a ScsC buffer and return the inner bytes (SiiN or BSII)."""
    if not _HAVE_AES:
        raise RuntimeError(
            "pycryptodome is not installed. Run: pip install pycryptodome")
    if data[:4] != Signature.ENCRYPTED.value:
        raise ValueError("Not a ScsC file")
    if len(data) < 56:
        raise ValueError("Truncated ScsC header")

    iv = data[36:52]
    # data[52:56] = uncompressed size (uint32); used only for validation.
    expected_size = struct.unpack_from("<I", data, 52)[0]
    ciphertext = data[56:]
    if len(ciphertext) % 16 != 0:
        # AES-CBC requires a multiple of 16; defensively trim the remainder.
        ciphertext = ciphertext[: len(ciphertext) - (len(ciphertext) % 16)]

    cipher = AES.new(SCS_KEY, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)

    # zlib: decompressobj stops at the end of the stream and ignores padding.
    dobj = zlib.decompressobj()
    out = dobj.decompress(decrypted)
    out += dobj.flush()

    if expected_size and len(out) != expected_size:
        # Not fatal (some saves differ), but worth noting while debugging.
        pass
    return out


def decode_to_text(data):
    """Take raw .sii content and return (SiiN_text, original_format).

    original_format: 'plain' | 'encrypted+binary' | 'encrypted+plain' | 'binary'
    """
    sig = detect_signature(data)

    if sig == Signature.ENCRYPTED:
        inner = decrypt_scsc(data)
        inner_sig = detect_signature(inner)
        if inner_sig == Signature.BINARY:
            return decode_bsii(inner), "encrypted+binary"
        if inner_sig == Signature.PLAIN:
            return inner.decode("utf-8", errors="replace"), "encrypted+plain"
        raise ValueError("Unknown inner content after decryption")

    if sig == Signature.BINARY:
        return decode_bsii(data), "binary"

    if sig == Signature.PLAIN:
        return data.decode("utf-8", errors="replace"), "plain"

    if sig == Signature.THREE_NK:
        raise ValueError("3nK format is not supported (not used in saves)")

    raise ValueError("Unknown file signature: %r" % data[:4])
