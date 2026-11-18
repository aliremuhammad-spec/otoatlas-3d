"""Download only the files the pipeline needs from Zenodo, and verify them."""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import requests

ZENODO_API = "https://zenodo.org/api/records/{record}"
OPENEAR_RECORD = 1473724
BERN_RECORD = 3355272


def _get(url: str, timeout: int, attempts: int = 4) -> requests.Response:
    """GET with retries: Zenodo answers 5xx now and then, and a deploy should not fail on one blip."""
    import time

    for attempt in range(attempts):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code < 500:
                return r
        except (requests.ConnectionError, requests.Timeout):
            if attempt == attempts - 1:
                raise
        time.sleep(10 * (attempt + 1))
    return r


def record_files(record: int) -> dict[str, dict]:
    r = _get(ZENODO_API.format(record=record), timeout=120)
    r.raise_for_status()
    return {f["key"]: f for f in r.json()["files"]}


def verify_md5(data: bytes, checksum: str) -> None:
    """Raise if `data` does not match a Zenodo checksum string such as 'md5:0123...'."""
    algo, _, expected = checksum.partition(":")
    if algo != "md5" or not expected:
        raise ValueError(f"unsupported checksum: {checksum!r}")
    actual = hashlib.md5(data).hexdigest()  # noqa: S324 - integrity check against the publisher's value
    if actual != expected:
        raise OSError(f"checksum mismatch: expected {expected}, got {actual}")


def find_member(names: list[str], suffix: str) -> str:
    """The single archive member whose path ends with `suffix`. Zero or several is an error."""
    matches = [n for n in names if n.replace("\\", "/").endswith(suffix)]
    if len(matches) != 1:
        raise LookupError(f"expected exactly one member ending with {suffix!r}, found {len(matches)}")
    return matches[0]


def fetch_bern_specimen(specimen_id: str, dest: str | Path) -> Path:
    """Download and unpack one Bern specimen archive (20 to 50 MB), checking its checksum."""
    meta = record_files(BERN_RECORD)[f"{specimen_id}.zip"]
    r = _get(meta["links"]["self"], timeout=900)
    r.raise_for_status()
    data = r.content
    verify_md5(data, meta["checksum"])
    dest = Path(dest)
    zipfile.ZipFile(io.BytesIO(data)).extractall(dest)
    return dest / specimen_id


def fetch_openear_member(specimen: str, suffix: str, dest: str | Path) -> Path:
    """Extract one file from an OpenEar archive by HTTP range requests, without downloading it whole.

    The archive checksum cannot be verified this way; the member's own CRC-32 is
    checked by the zip reader during extraction.
    """
    from remotezip import RemoteZip

    import time

    meta = record_files(OPENEAR_RECORD)[f"{specimen.upper()}.zip"]
    # Range requests to Zenodo sometimes answer 504 or stall; time out and retry.
    for attempt in range(4):
        try:
            with RemoteZip(meta["links"]["self"], timeout=180) as rz:
                member = find_member(rz.namelist(), suffix)
                return Path(rz.extract(member, str(dest)))
        except Exception as e:  # remotezip wraps every transport error in its own types
            if attempt == 3:
                raise
            print(f"retrying {specimen} after: {e}")
            time.sleep(20 * (attempt + 1))
    raise AssertionError("unreachable")
