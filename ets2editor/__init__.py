"""Save editor for Euro Truck Simulator 2 / American Truck Simulator.

Supports the three .sii file formats used by SCS Software games:
    - SiiN  -> plain text (directly editable)
    - ScsC  -> encrypted (AES-256-CBC + zlib)
    - BSII  -> binary

The editor decrypts/decodes any of them to SiiN text, which is the format
the game can also load back.

Python port of the reference implementation Trucky/sii-decrypt-ts.
"""

from .formats import (
    Signature,
    detect_signature,
    decrypt_scsc,
    decode_to_text,
)
from .bsii import decode_bsii
from .save import SaveFile, find_profiles, QUICK_FIELDS

__all__ = [
    "Signature",
    "detect_signature",
    "decrypt_scsc",
    "decode_to_text",
    "decode_bsii",
    "SaveFile",
    "find_profiles",
    "QUICK_FIELDS",
]
