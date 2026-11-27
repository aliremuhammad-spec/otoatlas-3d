"""Development only (Phase 2B WP1): for every OpenEar specimen, list the micro-slicing colour volume
and print its NRRD header (size, spacing, space, encoding) without downloading the data.

    python colour_survey.py [SPEC ...]

Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "DATA_PIPELINE"))
from otopipe import fetch  # noqa: E402

ALL = ["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA", "ETA", "THETA"]
KEEP = ("type", "dimension", "sizes", "space", "space directions", "space origin", "encoding", "endian", "kinds")


def main(names: list[str]) -> None:
    from remotezip import RemoteZip

    files = fetch.record_files(fetch.OPENEAR_RECORD)
    for sp in names:
        print(f"=== {sp}", flush=True)
        try:
            with RemoteZip(files[f"{sp}.zip"]["links"]["self"], timeout=180) as rz:
                cand = [n for n in rz.namelist() if re.search(r"Reconstruction_Microslicing/[^/]*\.nrrd$", n)]
                other = [n for n in rz.namelist() if re.search(r"Reconstruction_Microslicing/", n) and n not in cand]
                print("members:", [(n, rz.getinfo(n).file_size >> 20, rz.getinfo(n).compress_size >> 20) for n in cand],
                      "| other files in folder:", len(other))
                for member in cand:
                    with rz.open(member) as fh:
                        head = b""
                        while b"\n\n" not in head and len(head) < 200_000:
                            chunk = fh.read(4096)
                            if not chunk:
                                break
                            head += chunk
                    for line in head.split(b"\n\n")[0].decode("latin-1").splitlines():
                        if line.split(":")[0].strip() in KEEP:
                            print("   ", line[:160])
        except Exception as e:  # keep going: one bad archive must not hide the others
            print("   FAILED", repr(e)[:200])


if __name__ == "__main__":
    main([a.upper() for a in sys.argv[1:]] or ALL)
