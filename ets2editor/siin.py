"""Structured parser/serializer for SiiN text.

Parses the decoded save into a list of units, each with an ordered list of
fields (key, subscript, value). This is what powers the friendly Profile tab
and the "edit everything" Explorer, while staying lossless enough to round-trip.

The SCS text (SiiNunit) is line-oriented and flat (no nested braces inside a
unit), so a single-pass line parser is enough.
"""

import re

_UNIT_HEADER = re.compile(r"^\s*([A-Za-z0-9_.]+)\s*:\s*(\S+)\s*\{\s*$")
_FIELD = re.compile(r"^\s*([A-Za-z0-9_]+)(\[\d+\])?\s*:\s?(.*?)\s*$")


class Field:
    """One line inside a unit. If key is None it is a passthrough raw line."""

    __slots__ = ("key", "sub", "value", "raw")

    def __init__(self, key, sub, value, raw=None):
        self.key = key        # e.g. "money_account" or None
        self.sub = sub or ""  # e.g. "" or "[0]"
        self.value = value    # value text as-is
        self.raw = raw        # original raw line if passthrough

    @property
    def name(self):
        return "%s%s" % (self.key, self.sub) if self.key else ""

    def render(self):
        if self.key is None:
            return self.raw if self.raw is not None else ""
        return " %s%s: %s" % (self.key, self.sub, self.value)


class Unit:
    __slots__ = ("type", "name", "fields")

    def __init__(self, unit_type, name):
        self.type = unit_type
        self.name = name
        self.fields = []      # list[Field]

    def get(self, key):
        """First field value with this key (ignoring subscript)."""
        for f in self.fields:
            if f.key == key and f.sub == "":
                return f.value
        return None

    def set(self, key, value):
        for f in self.fields:
            if f.key == key and f.sub == "":
                f.value = str(value)
                return True
        return False

    def set_array(self, key, values, quote=False):
        """Replace an array field (count line + key[i] lines) with new values.

        Keeps the array at its original position; appends if it did not exist.
        """
        pos = None
        kept = []
        for f in self.fields:
            if f.key == key:
                if pos is None:
                    pos = len(kept)
                continue  # drop old count + indexed lines
            kept.append(f)
        block = [Field(key, "", str(len(values)))]
        for i, v in enumerate(values):
            val = '"%s"' % v if quote else str(v)
            block.append(Field(key, "[%d]" % i, val))
        if pos is None:
            pos = len(kept)
        kept[pos:pos] = block
        self.fields = kept
        return len(values)

    def render(self):
        out = ["%s : %s {" % (self.type, self.name)]
        out.extend(f.render() for f in self.fields)
        out.append("}")
        return "\n".join(out)


class Document:
    """A parsed SiiN document: an ordered list of units."""

    def __init__(self, units, header="SiiNunit"):
        self.units = units
        self.header = header

    # -- queries ----------------------------------------------------------
    def units_of(self, unit_type):
        return [u for u in self.units if u.type == unit_type]

    def first(self, unit_type):
        for u in self.units:
            if u.type == unit_type:
                return u
        return None

    def unit_types(self):
        seen = {}
        for u in self.units:
            seen[u.type] = seen.get(u.type, 0) + 1
        return seen

    # -- serialization ----------------------------------------------------
    def render(self):
        parts = ["%s\n{\n" % self.header]
        for u in self.units:
            parts.append(u.render())
            parts.append("\n\n")
        parts.append("}\n")
        return "".join(parts)


def parse(text):
    """Parse SiiN text into a Document."""
    lines = text.splitlines()
    units = []
    header = "SiiNunit"
    i = 0
    n = len(lines)

    # find the header line and the opening brace
    while i < n:
        stripped = lines[i].strip()
        if stripped.endswith("nit") and stripped.lower().startswith("siin"):
            header = stripped
            i += 1
            break
        i += 1
    # skip the opening "{"
    while i < n and lines[i].strip() != "{":
        i += 1
    i += 1

    current = None
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if current is None:
            if stripped == "}":
                # end of the whole document
                break
            m = _UNIT_HEADER.match(line)
            if m:
                current = Unit(m.group(1), m.group(2))
                units.append(current)
            # else: blank line between units -> ignore
        else:
            if stripped == "}":
                current = None
            else:
                fm = _FIELD.match(line)
                if fm:
                    sub = fm.group(2) or ""
                    current.fields.append(Field(fm.group(1), sub, fm.group(3)))
                else:
                    # keep unknown lines verbatim so nothing is lost
                    current.fields.append(Field(None, "", None, raw=line))
        i += 1

    return Document(units, header)
