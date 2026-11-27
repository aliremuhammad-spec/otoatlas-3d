"""Development only: print the NRRD header of ZETA's micro-slicing volume (colour cryosection
stack) without downloading its data. Prints the header lines and a few facts.

    python colour_header.py ZETA
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "DATA_PIPELINE"))
from otopipe import fetch  # noqa: E402


def main(specimen: str) -> None:
    from remotezip import RemoteZip

    meta = fetch.record_files(fetch.OPENEAR_RECORD)[f"{specimen.upper()}.zip"]
    with RemoteZip(meta["links"]["self"], timeout=180) as rz:
        names = rz.namelist()
        print(f"{len(names)} files; microslicing-like members:")
        for n in names:
            if re.search(r"microslic|reconstruction", n, re.I):
                print("  ", n, rz.getinfo(n).file_size, rz.getinfo(n).compress_size)
        member = fetch.find_member(names, r"re:04_Reconstruction_Microslicing/[^/]*\.nrrd$")
        print("member:", member)
        with rz.open(member) as fh:
            head = b""
            while b"\n\n" not in head and len(head) < 200_000:
                chunk = fh.read(4096)
                if not chunk:
                    break
                head += chunk
    print(head.split(b"\n\n")[0].decode("latin-1"))


if __name__ == "__main__":
    main(sys.argv[1])
