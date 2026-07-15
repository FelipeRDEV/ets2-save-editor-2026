"""Decoder for the binary BSII format -> SiiN text.

Faithful port of Trucky/sii-decrypt-ts (bsii-decoder.ts, decoder-utils.ts,
bsii-serializer.ts). Covers the 39 data types used by the SCS games.
"""

import math
import struct

# Alphabet used by "tokens" (uint64-encoded strings), base 38.
CHAR_TABLE = list("0123456789abcdefghijklmnopqrstuvwxyz_")

# "Limited" alphabet: values that can be written unquoted in SiiN.
LIMITED_ALPHABET = set(
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
)

# --- Type codes (DataTypeIdFormat) ------------------------------------------
UTF8String = 0x01
ArrayOfUTF8String = 0x02
EncodedString = 0x03
ArrayOfEncodedString = 0x04
Single = 0x05
ArrayOfSingle = 0x06
VectorOf2Single = 0x07
ArrayOfVectorOf2Single = 0x08
VectorOf3Single = 0x09
ArrayOfVectorOf3Single = 0x0A
VectorOf3Int32 = 0x11
ArrayOfVectorOf3Int32 = 0x12
VectorOf4Single = 0x17
ArrayOfVectorOf4Single = 0x18
VectorOf8Single = 0x19
ArrayOfVectorOf8Single = 0x1A
Int32 = 0x25
ArrayOfInt32 = 0x26
UInt32 = 0x27
ArrayOfUInt32 = 0x28
Int16 = 0x29
ArrayOfInt16 = 0x2A
UInt16 = 0x2B
ArrayOfUInt16 = 0x2C
UInt32Type2 = 0x2F
Int64 = 0x31
ArrayOfInt64 = 0x32
UInt64 = 0x33
ArrayOfUInt64 = 0x34
ByteBool = 0x35
ArrayOfByteBool = 0x36
OrdinalString = 0x37
Id = 0x39
ArrayOfIdA = 0x3A
IdType2 = 0x3B
ArrayOfIdC = 0x3C
IdType3 = 0x3D
ArrayOfIdE = 0x3E

SUPPORTED_VERSIONS = (1, 2, 3)


class _Reader:
    """Sequential little-endian reader over a byte buffer."""

    __slots__ = ("buf", "pos", "size")

    def __init__(self, buf):
        self.buf = buf
        self.pos = 0
        self.size = len(buf)

    def u8(self):
        v = self.buf[self.pos]
        self.pos += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.buf, self.pos)[0]
        self.pos += 2
        return v

    def i16(self):
        v = struct.unpack_from("<h", self.buf, self.pos)[0]
        self.pos += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.buf, self.pos)[0]
        self.pos += 4
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.buf, self.pos)[0]
        self.pos += 4
        return v

    def u64(self):
        v = struct.unpack_from("<Q", self.buf, self.pos)[0]
        self.pos += 8
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.buf, self.pos)[0]
        self.pos += 8
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.buf, self.pos)[0]
        self.pos += 4
        return v

    def string(self):
        length = self.u32()
        raw = self.buf[self.pos:self.pos + length]
        self.pos += length
        return raw.decode("utf-8", errors="replace")

    def token(self):
        """uint64-encoded string (base 38)."""
        value = self.u64()
        result = ""
        while value != 0:
            char_idx = value % 38
            if char_idx < 0:
                char_idx = -char_idx
            char_idx -= 1
            value //= 38
            if 0 <= char_idx < 38:
                result += CHAR_TABLE[char_idx]
        return result

    def array(self, fn):
        return [fn() for _ in range(self.u32())]

    def ident(self):
        """ID/pointer (types 0x39/0x3B/0x3D). Returns the id string."""
        part_count = self.u8()
        if part_count == 0xFF:
            address = self.u64()
            data = address.to_bytes(8, "little")
            result_value = ""
            current = ""
            n = len(data)
            for i in range(n):
                if i % 2 == 0 and i > 0:
                    if i >= n - 2:
                        while current.startswith("0"):
                            current = current[1:]
                    if current:
                        result_value = current + "." + result_value
                    current = ""
                current = "%02x" % data[i] + current
                if i == n - 1:
                    while current.startswith("0"):
                        current = current[1:]
                    if current:
                        result_value = current + "." + result_value
            return "_nameless." + result_value[:len(result_value) - 1]
        else:
            if part_count == 0:
                return "null"
            parts = [self.token() for _ in range(part_count)]
            return ".".join(parts)

    def ordinal_list(self):
        values = {}
        for _ in range(self.u32()):
            ordinal = self.u32()
            values[ordinal] = self.string()
        return values


def _read_value(r, dtype, version, ordinal_map):
    """Read a value according to its type code. Returns the Python value."""
    if dtype == UTF8String:
        return r.string()
    if dtype == ArrayOfUTF8String:
        return r.array(r.string)
    if dtype == EncodedString:
        return r.token()
    if dtype == ArrayOfEncodedString:
        return r.array(r.token)
    if dtype == Single:
        return r.f32()
    if dtype == ArrayOfSingle:
        return r.array(r.f32)
    if dtype == VectorOf2Single:
        return (r.f32(), r.f32())
    if dtype == ArrayOfVectorOf2Single:
        return r.array(lambda: (r.f32(), r.f32()))
    if dtype == VectorOf3Single:
        return (r.f32(), r.f32(), r.f32())
    if dtype == ArrayOfVectorOf3Single:
        return r.array(lambda: (r.f32(), r.f32(), r.f32()))
    if dtype == VectorOf3Int32:
        return (r.i32(), r.i32(), r.i32())
    if dtype == ArrayOfVectorOf3Int32:
        return r.array(lambda: (r.i32(), r.i32(), r.i32()))
    if dtype == VectorOf4Single:
        return (r.f32(), r.f32(), r.f32(), r.f32())
    if dtype == ArrayOfVectorOf4Single:
        return r.array(lambda: (r.f32(), r.f32(), r.f32(), r.f32()))
    if dtype == VectorOf8Single:
        return _read_vec8(r, version)
    if dtype == ArrayOfVectorOf8Single:
        return r.array(lambda: _read_vec8(r, version))
    if dtype == Int32:
        return r.i32()
    if dtype == ArrayOfInt32:
        return r.array(r.i32)
    if dtype in (UInt32, UInt32Type2):
        return r.u32()
    if dtype == ArrayOfUInt32:
        return r.array(r.u32)
    if dtype == Int16:
        return r.i16()
    if dtype == ArrayOfInt16:
        return r.array(r.i16)
    if dtype == UInt16:
        return r.u16()
    if dtype == ArrayOfUInt16:
        return r.array(r.u16)
    if dtype == Int64:
        return r.i64()
    if dtype == ArrayOfInt64:
        return r.array(r.i64)
    if dtype == UInt64:
        return r.u64()
    if dtype == ArrayOfUInt64:
        return r.array(r.u64)
    if dtype == ByteBool:
        return r.u8() != 0
    if dtype == ArrayOfByteBool:
        return r.array(lambda: r.u8() != 0)
    if dtype == OrdinalString:
        idx = r.u32()
        return ordinal_map.get(idx, "")
    if dtype in (Id, IdType2, IdType3):
        return r.ident()
    if dtype in (ArrayOfIdA, ArrayOfIdC, ArrayOfIdE):
        return r.array(r.ident)
    raise ValueError("Unknown BSII type: 0x%02x" % dtype)


def _read_vec8(r, version):
    if version == 1:
        # Version 1 uses 7 floats (the last component is implicit).
        return (r.f32(), r.f32(), r.f32(), r.f32(), r.f32(), r.f32(), 0.0)
    vals = [r.f32() for _ in range(8)]
    a, b, c, d, e, f, g, h = vals
    bias = int(math.floor(d))
    bits = (bias & 0xFFF) - 2048
    a += float(bits << 9)
    bits2 = ((bias >> 12) & 0xFFF) - 2048
    c += float(bits2 << 9)
    return (a, b, c, d, e, f, g, h)


# --- Serialization to SiiN text ---------------------------------------------

def _fmt_single(value):
    if value is None:
        return "nil"
    if (value - math.trunc(value)) != 0 or value >= 1e7:
        packed = struct.pack("<f", value)
        return "&" + "".join("%02x" % packed[i] for i in (3, 2, 1, 0))
    return str(int(math.trunc(value)))


def _is_limited(value):
    return all(ch in LIMITED_ALPHABET for ch in value)


def _quote_string(value):
    if value is None:
        value = ""
    if value != "" and _is_int_str(value):
        return value
    if value == "":
        return '""'
    if " " in value:
        return '"%s"' % value
    if _is_limited(value):
        return value
    return '"%s"' % value


def _is_int_str(value):
    if not value:
        return False
    s = value[1:] if value[0] == "-" else value
    return s.isdigit()


def _serialize_segment(name, dtype, value, version):
    """Return the SiiN line(s) for a segment. Prefixed with one space."""
    # Simple scalars ------------------------------------------------------
    if dtype == UTF8String:
        return " %s: %s\n" % (name, _quote_string(value))
    if dtype == EncodedString:
        return " %s: %s\n" % (name, value if value else '""')
    if dtype == OrdinalString:
        return " %s: %s\n" % (name, value)
    if dtype in (Id, IdType2, IdType3):
        return " %s: %s\n" % (name, value)
    if dtype == Single:
        return " %s: %s\n" % (name, _fmt_single(value))
    if dtype == Int32:
        return " %s: %s\n" % (name, value if value is not None else "nil")
    if dtype in (UInt32, UInt32Type2):
        text = str(value) if value is not None and value != 4294967295 else "nil"
        return " %s: %s\n" % (name, text)
    if dtype == Int64:
        return " %s: %s\n" % (name, value if value is not None else "nil")
    if dtype == UInt64:
        return " %s: %s\n" % (name, value if value is not None else "nil")
    if dtype == UInt16:
        text = str(value) if value is not None and value != 65535 else "nil"
        return " %s: %s\n" % (name, text)
    if dtype == Int16:
        text = str(value) if value is not None and value != 32767 else "nil"
        return " %s: %s\n" % (name, text)
    if dtype == ByteBool:
        return " %s: %s\n" % (name, "true" if value else "false")
    # Vectors -------------------------------------------------------------
    if dtype == VectorOf2Single:
        a, b = value
        return " %s: (%s, %s)\n" % (name, _fmt_single(a), _fmt_single(b))
    if dtype == VectorOf3Single:
        a, b, c = value
        return " %s: (%s, %s, %s)\n" % (
            name, _fmt_single(a), _fmt_single(b), _fmt_single(c))
    if dtype == VectorOf3Int32:
        a, b, c = value
        return " %s: (%s, %s, %s)\n" % (name, a, b, c)
    if dtype == VectorOf4Single:
        a, b, c, d = value
        return " %s: (%s; %s, %s, %s)\n" % (
            name, _fmt_single(a), _fmt_single(b), _fmt_single(c), _fmt_single(d))
    if dtype == VectorOf8Single:
        return " %s: %s\n" % (name, _fmt_vec8(value, version))
    # Arrays --------------------------------------------------------------
    if dtype in _ARRAY_SCALAR:
        return _serialize_scalar_array(name, dtype, value)
    if dtype == ArrayOfUTF8String:
        out = " %s: %d\n" % (name, len(value))
        for i, v in enumerate(value):
            out += " %s[%d]: %s\n" % (name, i, _quote_string(v))
        return out
    if dtype == ArrayOfSingle:
        out = " %s: %d\n" % (name, len(value))
        for i, v in enumerate(value):
            out += " %s[%d]: %s\n" % (name, i, _fmt_single(v))
        return out
    if dtype == ArrayOfVectorOf2Single:
        out = " %s: %d\n" % (name, len(value))
        for i, (a, b) in enumerate(value):
            out += " %s[%d]: (%s, %s)\n" % (name, i, _fmt_single(a), _fmt_single(b))
        return out
    if dtype == ArrayOfVectorOf3Single:
        out = " %s: %d\n" % (name, len(value))
        for i, (a, b, c) in enumerate(value):
            out += " %s[%d]: (%s, %s, %s)\n" % (
                name, i, _fmt_single(a), _fmt_single(b), _fmt_single(c))
        return out
    if dtype == ArrayOfVectorOf3Int32:
        out = " %s: %d\n" % (name, len(value))
        for i, (a, b, c) in enumerate(value):
            out += " %s[%d]: (%s, %s, %s)\n" % (name, i, a, b, c)
        return out
    if dtype == ArrayOfVectorOf4Single:
        out = " %s: %d\n" % (name, len(value))
        for i, (a, b, c, d) in enumerate(value):
            out += " %s[%d]: (%s; %s, %s, %s)\n" % (
                name, i, _fmt_single(a), _fmt_single(b),
                _fmt_single(c), _fmt_single(d))
        return out
    if dtype == ArrayOfVectorOf8Single:
        out = " %s: %d\n" % (name, len(value))
        for i, v in enumerate(value):
            out += " %s[%d]: %s\n" % (name, i, _fmt_vec8(v, version))
        return out
    if dtype in (ArrayOfIdA, ArrayOfIdC, ArrayOfIdE):
        out = " %s: %d\n" % (name, len(value))
        for i, v in enumerate(value):
            out += " %s[%d]: %s\n" % (name, i, v)
        return out
    raise ValueError("Unknown serialization type: 0x%02x (%s)" % (dtype, name))


_ARRAY_SCALAR = {
    ArrayOfInt32, ArrayOfUInt32, ArrayOfUInt16, ArrayOfInt16,
    ArrayOfInt64, ArrayOfUInt64, ArrayOfEncodedString,
}


def _serialize_scalar_array(name, dtype, value):
    out = " %s: %d\n" % (name, len(value))
    for i, v in enumerate(value):
        out += " %s[%d]: %s\n" % (name, i, v)
    return out


def _serialize_bool_array(name, value):
    out = " %s: %d\n" % (name, len(value))
    for i, v in enumerate(value):
        out += " %s[%d]: %s\n" % (name, i, "true" if v else "false")
    return out


def _fmt_vec8(v, version):
    a, b, c, d, e, f, g = v[:7]
    if version == 1:
        return "(%s, %s, %s) (%s; %s, %s, %s)" % (
            _fmt_single(a), _fmt_single(b), _fmt_single(c),
            _fmt_single(d), _fmt_single(e), _fmt_single(f), _fmt_single(g))
    h = v[7]
    return "(%s, %s, %s) (%s; %s, %s, %s)" % (
        _fmt_single(a), _fmt_single(b), _fmt_single(c),
        _fmt_single(e), _fmt_single(f), _fmt_single(g), _fmt_single(h))


def decode_bsii(data):
    """Decode BSII bytes (starting with 'BSII') and return SiiN text (str)."""
    r = _Reader(data)
    r.u32()  # signature 'BSII'
    version = r.u32()
    if version not in SUPPORTED_VERSIONS:
        raise ValueError("Unsupported BSII version: %d" % version)

    structures = {}          # structureId -> {"name", "segments"}
    ordinal_lists = {}       # structureId -> {ordinal: str}
    decoded = []             # data blocks: (name, id, [(seg_name, type, value)])

    while r.pos < r.size:
        block_type = r.u32()
        if block_type == 0:
            valid = r.u8() != 0
            if not valid:
                # end-of-definitions marker
                continue
            structure_id = r.u32()
            name = r.string()
            segments = []
            while True:
                seg_type = r.u32()
                if seg_type == 0:
                    break
                seg_name = r.string()
                if seg_type == OrdinalString:
                    omap = r.ordinal_list()
                    ordinal_lists.setdefault(structure_id, omap)
                segments.append((seg_name, seg_type))
            if structure_id not in structures:
                structures[structure_id] = {"name": name, "segments": segments}
        else:
            struct_def = structures.get(block_type)
            if struct_def is None:
                continue
            omap = ordinal_lists.get(block_type, {})
            block_id = r.ident()
            values = []
            for seg_name, seg_type in struct_def["segments"]:
                val = _read_value(r, seg_type, version, omap)
                values.append((seg_name, seg_type, val))
            decoded.append((struct_def["name"], block_id, values))

    return _serialize(decoded, version)


def _serialize(decoded, version):
    parts = ["SiiNunit\n{\n"]
    for name, block_id, values in decoded:
        if not name or not block_id:
            continue
        parts.append("%s : %s {\n" % (name, block_id))
        for seg_name, seg_type, val in values:
            if seg_type == 0:
                continue
            if seg_type == ArrayOfByteBool:
                parts.append(_serialize_bool_array(seg_name, val))
            else:
                parts.append(_serialize_segment(seg_name, seg_type, val, version))
        parts.append("}\n\n")
    parts.append("}\n")
    return "".join(parts)
