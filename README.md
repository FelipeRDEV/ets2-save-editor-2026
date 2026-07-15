# ETS2 / ATS Save Editor 2026

A save editor for **Euro Truck Simulator 2** and **American Truck Simulator**
(SCS Software), written in Python with a graphical interface (Tkinter).

It handles all three `game.sii` formats:

| Signature | Format        | What the editor does                          |
|-----------|---------------|-----------------------------------------------|
| `SiiN`    | plain text    | edits it directly                             |
| `BSII`    | binary        | decodes it to text                            |
| `ScsC`    | encrypted     | decrypts (AES-256 + zlib) and decodes it      |

Saving is done as **SiiN text**, which the game loads normally.

## Features

- Auto-detects profiles under `Documents/Euro Truck Simulator 2` and
  `.../American Truck Simulator`.
- Quick editing of: **money** (`money_account`), **XP** (`experience_points`)
  and **skills** (ADR, long distance, heavy, fragile, urgent, high value).
- Full text editor for the save (the "Text (SiiN)" tab) for any field.
- Automatic timestamped backup before saving
  (`game.sii.YYYYMMDD_HHMMSS.bak`).
- CLI tool for decrypt/decode only.

## Requirements

- Python 3.9+
- `pycryptodome` (for the encrypted `ScsC` format)

```bash
pip install -r requirements.txt
```

`tkinter` ships with the standard Python installer on Windows.

## Usage

### GUI

```bash
python -m ets2editor.gui
# or, on Windows, double-click:
run_editor.pyw
```

1. Pick a detected profile **or** click "Open file..." and choose a `game.sii`.
2. Edit fields in the **Quick edit** tab or directly in the **Text (SiiN)** tab.
3. Click **Save** (keep "Make backup" checked the first time).

### Command line

```bash
python sii_cli.py "path/to/game.sii" output.txt
```

## Important note about saving

The game accepts **plain-text** saves. To make sure it does not rewrite them
back to binary, enable the text save format in `config.cfg`:

```
uset g_save_format "2"
```

(The file lives at `Documents/Euro Truck Simulator 2/config.cfg`.)
Even without that, the game will load a text save next time — but when you
save inside the game it rewrites it in the configured format.

**Always back up your save.** The editor creates a `.bak` automatically, but
manual edits to the text can corrupt the save if the syntax breaks.

## Project layout

```
ets2editor/
  formats.py   # signature detection, ScsC decrypt, pipeline -> text
  bsii.py      # BSII binary decoder + SiiN serializer
  save.py      # SaveFile: open, edit fields, backup, save
  gui.py       # Tkinter interface
sii_cli.py     # command-line tool
run_editor.pyw # GUI shortcut
test_selftest.py  # tests without a real save
```

## Credits / references

- Encryption format and AES key: SCS modding community (`SII_Decrypt`).
- BSII decoder port based on
  [Trucky/sii-decrypt-ts](https://github.com/Trucky/sii-decrypt-ts).
- Field map inspired by
  [liptoh/ts-se-tool](https://github.com/liptoh/ts-se-tool).

## Disclaimer

Unofficial tool for editing your own saves. Not affiliated with SCS Software.
Use at your own risk.
