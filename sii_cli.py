"""Command-line tool: decode a .sii file to SiiN text.

Usage:
    python sii_cli.py input.sii [output.txt]

If no output is given, prints to stdout.
"""

import sys

from ets2editor import decode_to_text


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    with open(argv[1], "rb") as fh:
        data = fh.read()
    text, fmt = decode_to_text(data)
    sys.stderr.write("Original format: %s\n" % fmt)
    if len(argv) >= 3:
        with open(argv[2], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        sys.stderr.write("Written to: %s\n" % argv[2])
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
