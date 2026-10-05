#!/usr/bin/env python3
"""Compare row counts in a restored database with the backup's manifest.

    python3 verify_restore.py manifest.json "postgres://user:pw@localhost/restore"

Exits non-zero (failing the monthly restore-test workflow, which alerts by
email and opens a GitHub issue) if any table is missing or has a different
number of rows than when the backup was taken.
"""

from __future__ import annotations

import json
import subprocess
import sys


def count(url: str, table: str) -> int:
    out = subprocess.run(  # noqa: S603
        ["psql", url, "-At", "-c", f'SELECT count(*) FROM public."{table}"'],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


def main() -> int:
    manifest_path, url = sys.argv[1], sys.argv[2]
    manifest = json.load(open(manifest_path))  # noqa: SIM115
    expected: dict[str, int] = manifest["row_counts"]
    if not expected:
        print("manifest has no tables", file=sys.stderr)
        return 1
    problems = []
    for table, rows in sorted(expected.items()):
        try:
            got = count(url, table)
        except subprocess.CalledProcessError as exc:
            problems.append(f"{table}: missing after restore ({exc.stderr.strip()})")
            continue
        status = "ok" if got == rows else "MISMATCH"
        print(f"{status:8} {table:45} expected {rows:>9} got {got:>9}")
        if got != rows:
            problems.append(f"{table}: expected {rows} rows, got {got}")
    if problems:
        print("\nRESTORE TEST FAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    print(f"\nRestore test passed: {len(expected)} tables match ({manifest['dump_key']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
