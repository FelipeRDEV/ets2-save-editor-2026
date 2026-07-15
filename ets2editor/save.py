"""High-level layer: open a save, edit common fields and save it.

Write strategy: the game loads plain-text (SiiN) saves without any problem,
so we decode any format to text, edit the text and write it back as SiiN.
There is no need to re-encrypt or re-encode to BSII.
"""

import os
import re
import shutil
import time

from .formats import decode_to_text


# Quick-edit fields: (key, label, kind).
# 'money_account' lives in the "bank" unit; the rest live in "economy".
QUICK_FIELDS = [
    ("money_account", "Money", "int"),
    ("experience_points", "XP (experience)", "int"),
    ("adr", "Skill: ADR", "int"),
    ("long_dist", "Skill: Long distance", "int"),
    ("heavy", "Skill: Heavy cargo", "int"),
    ("fragile", "Skill: Fragile cargo", "int"),
    ("urgent", "Skill: Urgent delivery", "int"),
    ("mechanical", "Skill: High value", "int"),
]


def find_profiles(base_dirs=None):
    """Locate ETS2/ATS profiles. Returns a list of dicts with their saves."""
    if base_dirs is None:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        base_dirs = [
            os.path.join(docs, "Euro Truck Simulator 2"),
            os.path.join(docs, "American Truck Simulator"),
        ]
    profiles = []
    for base in base_dirs:
        prof_root = os.path.join(base, "profiles")
        if not os.path.isdir(prof_root):
            continue
        game = os.path.basename(base)
        for prof in sorted(os.listdir(prof_root)):
            save_dir = os.path.join(prof_root, prof, "save")
            if not os.path.isdir(save_dir):
                continue
            saves = []
            for slot in sorted(os.listdir(save_dir)):
                game_sii = os.path.join(save_dir, slot, "game.sii")
                if os.path.isfile(game_sii):
                    saves.append({"slot": slot, "path": game_sii})
            if saves:
                profiles.append({
                    "game": game,
                    "profile": prof,
                    "name": _decode_profile_name(prof),
                    "saves": saves,
                })
    return profiles


def _decode_profile_name(hex_name):
    """Profile folder names are the hex-encoded profile name. Try to decode."""
    try:
        return bytes.fromhex(hex_name).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return hex_name


class SaveFile:
    """A game.sii loaded as SiiN text, with field editing."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            self.raw = fh.read()
        self.text, self.source_format = decode_to_text(self.raw)

    # -- reading fields ---------------------------------------------------
    def get_field(self, key):
        """Return the value (str) of the first 'key: value' occurrence."""
        m = re.search(r"^\s*%s:\s*(.+?)\s*$" % re.escape(key),
                      self.text, re.MULTILINE)
        return m.group(1) if m else None

    def read_quick_fields(self):
        out = {}
        for key, _label, _kind in QUICK_FIELDS:
            out[key] = self.get_field(key)
        return out

    # -- writing fields ---------------------------------------------------
    def set_field(self, key, value):
        """Replace the value of the first 'key:' occurrence. True if found."""
        pattern = re.compile(r"^(\s*%s:\s*).+?(\s*)$" % re.escape(key),
                             re.MULTILINE)
        new_text, n = pattern.subn(
            lambda m: "%s%s%s" % (m.group(1), value, m.group(2)),
            self.text, count=1)
        if n:
            self.text = new_text
        return bool(n)

    def apply_quick_fields(self, values):
        """values: dict key->new_value (str). Returns list of applied keys."""
        applied = []
        for key, val in values.items():
            if val is None or val == "":
                continue
            if self.set_field(key, str(val)):
                applied.append(key)
        return applied

    # -- saving -----------------------------------------------------------
    def backup(self):
        """Create a timestamped .bak next to the file. Returns its path."""
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bak = "%s.%s.bak" % (self.path, stamp)
        shutil.copy2(self.path, bak)
        return bak

    def save(self, make_backup=True):
        """Write the current text as SiiN. Backs up the original by default."""
        bak = self.backup() if make_backup else None
        with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.text)
        return bak

    def save_as(self, out_path):
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.text)
