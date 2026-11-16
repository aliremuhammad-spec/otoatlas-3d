"""Print licence, file list and the full contents of one Bern labyrinth specimen."""
import io, json, os, tempfile, zipfile
import nibabel as nib
import numpy as np
import requests

j = requests.get("https://zenodo.org/api/records/3355272", timeout=120).json()
print("title:", j["metadata"]["title"])
print("license:", json.dumps(j["metadata"].get("license")))
for f in j["files"]:
    print("file:", f["key"], f["size"], f.get("checksum"))
f = sorted(j["files"], key=lambda x: x["key"])[0]
z = zipfile.ZipFile(io.BytesIO(requests.get(f["links"]["self"], timeout=600).content))
tmp = tempfile.mkdtemp()
z.extractall(tmp)
for root, _, files in os.walk(tmp):
    for n in sorted(files):
        p = os.path.join(root, n)
        rel = os.path.relpath(p, tmp)
        print("entry:", rel, os.path.getsize(p))
        low = n.lower()
        if low.endswith(".json"):
            print(open(p, encoding="utf-8", errors="replace").read()[:6000])
        if low.endswith((".nii", ".nii.gz")):
            im = nib.load(p)
            a = np.asanyarray(im.dataobj)
            u = np.unique(a)
            print(" shape", im.shape, "zooms", [round(float(x), 5) for x in im.header.get_zooms()],
                  str(im.get_data_dtype()), "min", a.min(), "max", a.max(), "n_unique", len(u), u[:8].tolist())
            print(" affine", np.round(im.affine, 5).tolist())
        if low.endswith(".ply"):
            head = open(p, "rb").read(400).decode("latin-1")
            print(" ply", head.split("end_header")[0].replace("\n", " | "))
