"""Write a compact description of the smallest OpenEar archive to the job summary."""
import os, re, tempfile, traceback
import nrrd
import requests
from remotezip import RemoteZip

out = open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a", encoding="utf-8")
def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    out.write(line + "\n")

KEEP = re.compile(r"^(type|dimension|sizes|space|space directions|space origin|encoding|kinds)$|"
                  r"^Segment\d+_(Name|LabelValue|Layer|Extent|Color)$")
j = requests.get("https://zenodo.org/api/records/1473724", timeout=120).json()
zf = sorted(j["files"], key=lambda x: x["size"])[0]
tmp = tempfile.mkdtemp()
say("```")
say("OPENEAR", zf["key"], zf["size"], j["metadata"].get("license"))
with RemoteZip(zf["links"]["self"]) as rz:
    infos = [i for i in rz.infolist() if not i.is_dir()]
    tiff = [i for i in infos if i.filename.lower().endswith((".tif", ".tiff", ".dcm"))]
    say("raw image files (tif/dcm):", len(tiff), sum(i.file_size for i in tiff))
    for i in infos:
        if i not in tiff:
            say("entry", i.filename, i.file_size, i.compress_size)
    for i in infos:
        if i.filename.lower().endswith(".nrrd") and i.compress_size < 400e6:
            try:
                p = rz.extract(i.filename, tmp)
                say("nrrd", i.filename)
                for k, v in nrrd.read_header(p).items():
                    if KEEP.match(k):
                        say("  ", k, "=", " ".join(str(v).split())[:160])
                os.remove(p)
            except Exception:
                say("  failed:", traceback.format_exc().splitlines()[-1])
say("```")
