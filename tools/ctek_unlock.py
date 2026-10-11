#!/usr/bin/env python3
"""Compute the CTEK Battery Sense unlock payload from the 16-character code.

The code is printed under the barcode on the device sticker
(format like 40149A00W0000000). The payload is MD5(fixed salt + code) and must be
written (with response) to characteristic a1d67c01-fe3f-01bf-7d49-7dbdc43b02a6
BEFORE the link is encrypted.

The ESPHome package computes this on the device; this script is for
debugging or for other platforms (nRF Connect, bleak, ...).

Usage: python3 ctek_unlock.py <16-char code>
"""
import hashlib
import sys

SALT = bytes.fromhex("e1da7195eced40e4bc16559e9de73ba4")


def unlock_payload(code: str) -> bytes:
    norm = "".join(code.split()).upper()
    if len(norm) != 16 or not norm.isascii():
        raise ValueError(f"code must be 16 ASCII characters, got {len(norm)}: {norm!r}")
    return hashlib.md5(SALT + norm.encode("ascii")).digest()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    p = unlock_payload(sys.argv[1])
    print("hex  :", p.hex().upper())
    print("yaml :", "[" + ", ".join(f"0x{b:02X}" for b in p) + "]")
