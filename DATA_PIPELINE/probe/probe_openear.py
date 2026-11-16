"""List the smallest OpenEar archive remotely and print its NRRD headers."""
import json, os, tempfile, traceback
import nrrd
import requests
from remotezip import RemoteZip

j = requests.get("https://zenodo.org/api/records/1473724", timeout=120).json()
print("title:", j["metadata"]["title"])
print("license:", json.dumps(j["metadata"].get("license")))
for f in j["files"]:
    print("file:", f["key"], f["size"], f.get("checksum"))
zf = sorted(j["files"], key=lambda x: x["size"])[0]
print("archive:", zf["key"], zf["size"])
tmp = tempfile.mkdtemp()
with RemoteZip(zf["links"]["self"]) as rz:
    infos = [i for i in rz.infolist() if not i.is_dir()]
    for i in infos:
        print("entry:", i.filename, i.file_size, i.compress_size)
    for i in infos:
        low = i.filename.lower()
        try:
            if low.endswith(".nrrd") and i.compress_size < 400e6:
                p = rz.extract(i.filename, tmp)
                print("--- nrrd", i.filename)
                for k, v in nrrd.read_header(p).items():
                    print("   ", k, "=", str(v).replace("\n", " ")[:300])
                os.remove(p)
            if low.endswith((".txt", ".md", ".json", ".csv")) and i.file_size < 200000:
                print("--- text", i.filename)
                print(rz.read(i.filename).decode("utf-8", errors="replace")[:4000])
        except Exception:
            traceback.print_exc()
