"""High-level layer: open a save, edit common fields and save it.

Write strategy: the game loads plain-text (SiiN) saves without any problem,
so we decode any format to text, edit the text and write it back as SiiN.
There is no need to re-encrypt or re-encode to BSII.
"""

import os
import re
import json
import shutil
import string
import time

from .formats import decode_to_text
from . import siin
from .gamedata import DEALER_CITIES, RECRUITMENT_CITIES

GAMES = ("Euro Truck Simulator 2", "American Truck Simulator")
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".ets2_save_editor.json")


# Quick-edit fields: (key, label, unit_type).
# money_account lives in the "bank" unit; the rest live in "economy".
QUICK_FIELDS = [
    ("money_account", "Money", "bank"),
    ("experience_points", "XP (experience)", "economy"),
    ("adr", "Skill: ADR", "economy"),
    ("long_dist", "Skill: Long distance", "economy"),
    ("heavy", "Skill: Heavy cargo", "economy"),
    ("fragile", "Skill: Fragile cargo", "economy"),
    ("urgent", "Skill: Urgent delivery", "economy"),
    ("mechanical", "Skill: High value", "economy"),
]

# Maximum point per skill (economy field -> max).
SKILL_MAX = {
    "adr": 6, "long_dist": 6, "heavy": 6,
    "fragile": 6, "urgent": 6, "mechanical": 6,
}

XP_MAX = 999_999_999
MONEY_MAX = 1_000_000_000


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except OSError:
        pass


def get_custom_dirs():
    return list(_load_config().get("custom_dirs", []))


def add_custom_dir(path):
    """Remember a user-picked folder (game folder or a 'profiles' folder)."""
    cfg = _load_config()
    dirs = cfg.setdefault("custom_dirs", [])
    path = os.path.normpath(path)
    if path not in dirs:
        dirs.append(path)
        _save_config(cfg)
    return dirs


def _windows_drives():
    for letter in string.ascii_uppercase:
        root = "%s:\\" % letter
        if os.path.exists(root):
            yield root


def _candidate_base_dirs():
    """All plausible '<...>/<Game>' folders across the system."""
    home = os.path.expanduser("~")
    docs_names = ["Documents", "Documentos"]
    roots = [home, os.path.join(home, "OneDrive")]
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive:
        roots.append(onedrive)
    # Documents/Documentos at the root of every drive (e.g. E:\Documentos\...).
    for drive in _windows_drives():
        for docs in docs_names:
            roots.append(os.path.join(drive, docs))
        roots.append(drive)  # game folder directly at the drive root

    bases = []
    seen = set()
    for root in roots:
        for game in GAMES:
            path = os.path.join(root, game)
            if path not in seen:
                seen.add(path)
                bases.append(path)
    # User-added custom folders are treated as bases too.
    for custom in get_custom_dirs():
        if custom not in seen:
            seen.add(custom)
            bases.append(custom)
    return bases


def _infer_game(path):
    low = path.lower()
    if "american" in low or "\\ats" in low or "/ats" in low:
        return "American Truck Simulator"
    return "Euro Truck Simulator 2"


def _profiles_root(base):
    """Return the 'profiles' dir for a base, or the base itself if it is one."""
    direct = os.path.join(base, "profiles")
    if os.path.isdir(direct):
        return direct
    if os.path.basename(os.path.normpath(base)).lower() == "profiles" \
            and os.path.isdir(base):
        return base
    return None


def find_profiles(base_dirs=None):
    """Locate ETS2/ATS profiles. Returns a list of dicts with their saves."""
    if base_dirs is None:
        base_dirs = _candidate_base_dirs()
    profiles = []
    seen_roots = set()
    for base in base_dirs:
        prof_root = _profiles_root(base)
        if not prof_root or prof_root in seen_roots:
            continue
        seen_roots.add(prof_root)
        # game name from the folder above 'profiles' when possible
        parent = os.path.basename(os.path.dirname(os.path.normpath(prof_root)))
        game = parent if parent in GAMES else _infer_game(prof_root)
        for prof in sorted(os.listdir(prof_root)):
            save_dir = os.path.join(prof_root, prof, "save")
            if not os.path.isdir(save_dir):
                continue
            saves = []
            for slot in sorted(os.listdir(save_dir)):
                game_sii = os.path.join(save_dir, slot, "game.sii")
                if os.path.isfile(game_sii):
                    saves.append({
                        "slot": slot,
                        "path": game_sii,
                        "label": _save_label(os.path.join(save_dir, slot)),
                    })
            if saves:
                prof_dir = os.path.join(prof_root, prof)
                avatar = os.path.join(prof_dir, "avatar.png")
                profiles.append({
                    "game": game,
                    "profile": prof,
                    "name": _decode_profile_name(prof),
                    "dir": prof_dir,
                    "avatar": avatar if os.path.isfile(avatar) else None,
                    "saves": saves,
                })
    return profiles


def _save_label(slot_dir):
    """Read the human name of a save from its info.sii, if possible."""
    info = os.path.join(slot_dir, "info.sii")
    if not os.path.isfile(info):
        return os.path.basename(slot_dir)
    try:
        with open(info, "rb") as fh:
            text, _ = decode_to_text(fh.read())
        m = re.search(r'^\s*name:\s*(.+?)\s*$', text, re.MULTILINE)
        if m:
            name = m.group(1).strip().strip('"').strip()
            if name:
                return "%s (%s)" % (name, os.path.basename(slot_dir))
    except Exception:
        pass
    return os.path.basename(slot_dir)


def _decode_profile_name(hex_name):
    """Profile folder names are the hex-encoded profile name. Try to decode."""
    try:
        return bytes.fromhex(hex_name).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return hex_name


class SaveFile:
    """A game.sii loaded as a structured SiiN document, with field editing."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            self.raw = fh.read()
        self.text, self.source_format = decode_to_text(self.raw)
        self.doc = siin.parse(self.text)

    @property
    def filename(self):
        return os.path.basename(self.path)

    def is_game_save(self):
        """True if this file looks like a game.sii (has an economy/bank unit)."""
        return bool(self.doc.first("economy") or self.doc.first("bank"))

    # -- reading fields ---------------------------------------------------
    def get_field(self, key, unit_type=None):
        """Return the value of the first 'key' in the given unit type."""
        if unit_type:
            unit = self.doc.first(unit_type)
            if unit is not None:
                v = unit.get(key)
                if v is not None:
                    return v
        # fallback: search all units
        for u in self.doc.units:
            v = u.get(key)
            if v is not None:
                return v
        return None

    def read_quick_fields(self):
        """Return {key: value_or_None} for every quick field."""
        out = {}
        for key, _label, unit_type in QUICK_FIELDS:
            out[key] = self.get_field(key, unit_type)
        return out

    # -- writing fields ---------------------------------------------------
    def set_field(self, key, value, unit_type=None):
        """Set the value of 'key' in unit_type. Returns True if it existed."""
        if unit_type:
            unit = self.doc.first(unit_type)
            if unit is not None and unit.set(key, value):
                return True
        for u in self.doc.units:
            if u.set(key, value):
                return True
        return False

    def apply_quick_fields(self, values):
        """values: dict key->new_value. Returns (applied, missing) key lists."""
        unit_map = {k: ut for k, _l, ut in QUICK_FIELDS}
        applied, missing = [], []
        for key, val in values.items():
            if val is None or str(val).strip() == "":
                continue
            if self.set_field(key, str(val).strip(), unit_map.get(key)):
                applied.append(key)
            else:
                missing.append(key)
        return applied, missing

    # -- bulk / "max" operations -----------------------------------------
    def vehicles(self):
        return self.doc.units_of("vehicle")

    def repair_all(self, include_unfixable=True):
        """Set every wear field on player vehicles to 0. Returns count."""
        n = 0
        for u in self.vehicles():
            for f in u.fields:
                if f.key and "wear" in f.key:
                    if not include_unfixable and "unfixable" in f.key:
                        continue
                    if f.value != "0":
                        f.value = "0"
                        n += 1
        return n

    def refuel_all(self):
        """Fill fuel on all player vehicles. Returns count."""
        n = 0
        for u in self.vehicles():
            if u.set("fuel_relative", "1"):
                n += 1
        return n

    def max_skills(self):
        econ = self.doc.first("economy")
        n = 0
        if econ:
            for key, mx in SKILL_MAX.items():
                if econ.set(key, str(mx)):
                    n += 1
        return n

    def own_all_garages(self):
        """Set all garages to an 'owned' status. Returns (count, status)."""
        garages = self.doc.units_of("garage")
        vals = sorted({int(u.get("status"))
                       for u in garages
                       if (u.get("status") or "").isdigit()
                       and int(u.get("status")) != 0})
        target = str(vals[-1]) if vals else "6"
        n = 0
        for u in garages:
            if u.set("status", target):
                n += 1
        return n, target

    def harvest_cities(self):
        """City tokens present in this save (from company unit names)."""
        cities = set()
        for u in self.doc.units_of("company"):
            if "." in u.name:
                cities.add(u.name.rsplit(".", 1)[-1])
        return cities

    def unlock_map(self):
        """Visit all cities and unlock every dealer/agency this install has.

        City list comes from the save itself; dealer/agency cities are the
        intersection with the known dealer/agency lists, so only valid tokens
        for the player's DLCs are written. Returns a summary dict.
        """
        econ = self.doc.first("economy")
        if econ is None:
            return {"cities": 0, "dealers": 0, "recruitments": 0}
        cities = sorted(self.harvest_cities())
        dealers = [c for c in cities if c in DEALER_CITIES]
        recruits = [c for c in cities if c in RECRUITMENT_CITIES]
        econ.set_array("visited_cities", cities)
        econ.set_array("visited_cities_count", [1] * len(cities))
        econ.set_array("unlocked_dealers", dealers)
        econ.set_array("unlocked_recruitments", recruits)
        if cities:
            econ.set("last_visited_city", cities[0])
        return {"cities": len(cities), "dealers": len(dealers),
                "recruitments": len(recruits)}

    def set_money(self, value):
        return self.set_field("money_account", str(value), "bank")

    def set_xp(self, value):
        return self.set_field("experience_points", str(value), "economy")

    def god_mode(self):
        """Money+XP+skills to max, repair & refuel all, own all garages."""
        report = {}
        report["money"] = self.set_money(MONEY_MAX)
        report["xp"] = self.set_xp(XP_MAX)
        report["skills"] = self.max_skills()
        report["repaired_fields"] = self.repair_all()
        report["refueled"] = self.refuel_all()
        report["garages"], report["garage_status"] = self.own_all_garages()
        report["map"] = self.unlock_map()
        return report

    def sync_text_from_doc(self):
        self.text = self.doc.render()
        return self.text

    def reparse_text(self, text):
        """Replace the document by re-parsing edited text (raw tab)."""
        self.text = text
        self.doc = siin.parse(text)

    # -- saving -----------------------------------------------------------
    def backup(self):
        """Create a timestamped .bak next to the file. Returns its path."""
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bak = "%s.%s.bak" % (self.path, stamp)
        shutil.copy2(self.path, bak)
        return bak

    def save(self, make_backup=True):
        """Serialize the document and write it as SiiN. Backs up by default."""
        bak = self.backup() if make_backup else None
        text = self.doc.render()
        with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        self.text = text
        return bak

    def save_as(self, out_path):
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.doc.render())
