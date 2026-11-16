"""Write a compact description of one Bern labyrinth specimen to the job summary."""
import io, os, sys, tempfile, zipfile
import nibabel as nib
import numpy as np
import requests

out = open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a", encoding="utf-8")
def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    out.write(line + "\n")

name = sys.argv[1] if len(sys.argv) > 1 else "F01.zip"
j = requests.get("https://zenodo.org/api/records/3355272", timeout=120).json()
f = [x for x in j["files"] if x["key"] == name][0]
z = zipfile.ZipFile(io.BytesIO(requests.get(f["links"]["self"], timeout=600).content))
tmp = tempfile.mkdtemp()
z.extractall(tmp)
say("```")
say("BERN", name, j["metadata"].get("license"))
for root, _, files in os.walk(tmp):
    for n in sorted(files):
        p = os.path.join(root, n)
        say("entry", os.path.relpath(p, tmp), os.path.getsize(p))
        if n.lower().endswith(".json"):
            say(open(p, encoding="utf-8", errors="replace").read())
        if n.lower().endswith((".nii", ".nii.gz")):
            im = nib.load(p)
            a = np.asanyarray(im.dataobj)
            u = np.unique(a)
            say(" shape", im.shape, "zooms", [round(float(v), 4) for v in im.header.get_zooms()],
                im.get_data_dtype(), "range", a.min(), a.max(), "n_unique", len(u), u[:6].tolist())
            say(" affine", np.round(im.affine, 4).tolist())
        if n.lower().endswith(".ply"):
            head = open(p, "rb").read(300).decode("latin-1").split("end_header")[0]
            say(" ply", " | ".join(head.split("\n")))
say("```")
