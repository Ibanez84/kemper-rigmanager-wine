#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apply the WM_PARENTNOTIFY sign-extension fix to Soda 11.0-10's x86_64-unix/win32u.so.

Soda's win32u differs from vanilla Wine, so a vanilla-built win32u/user32 cannot be dropped
into the runner. This script patches 22 bytes in send_parent_notify() instead: it adds a
`movslq %edx,%rdx` so WM_PARENTNOTIFY's wParam is sign-extended like on Windows. Without it,
Rig Manager's editor crashes with an OverflowException.

It only touches a file whose SHA-256 matches the known Soda 11.0-10 build, and keeps a backup.

Usage: patch-soda-win32u.py <runner>/lib/wine/x86_64-unix/win32u.so
"""
import hashlib
import shutil
import sys

ORIGINAL_SHA256 = "201fe734f60cc0626ceb9da6e66090bdf2e931192f40459ab36f69be73c6d197"
PATCHED_SHA256 = "48bba9de5b1a72142cc6f0f394aecb95d0f248df73ec66140a3975e30d2ef49e"
OFFSET = 0x1647BA
OLD = bytes.fromhex("be10020000" "c1e210" "09ea" "5d" "415c" "e98400efff" "0f1f4000")
NEW = bytes.fromhex("be10020000" "c1e210" "09ea" "4863d2" "5d" "415c" "e98100efff" "90")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    data = bytearray(open(path, "rb").read())
    digest = hashlib.sha256(data).hexdigest()

    if digest == PATCHED_SHA256:
        print("Already patched, nothing to do.")
        return
    if digest != ORIGINAL_SHA256 or data[OFFSET:OFFSET + len(OLD)] != OLD:
        sys.exit("This is not the win32u.so from Soda 11.0-10; refusing to patch.")

    shutil.copy2(path, path + ".orig")
    data[OFFSET:OFFSET + len(NEW)] = NEW
    assert hashlib.sha256(data).hexdigest() == PATCHED_SHA256
    with open(path, "wb") as f:
        f.write(data)
    print(f"Patched. Original saved as {path}.orig")


if __name__ == "__main__":
    main()
