"""The cochlear frame, checked against two real descriptors from the Bern dataset.

Landmarks and axes below are copied from F01_DESC.json and T01_DESC.json
(Wimmer et al. 2019, doi:10.5281/zenodo.3355272, CC BY 4.0).
"""
import numpy as np
import pytest

from otopipe.frames import cochlear_frame, max_axis_disagreement

F01 = {
    "SIDE": "LEFT",
    "LANDMARKS": {
        "RW": [-11.13, -80.87, -55.05],
        "C": [-6.94, -84.35, -54.33],
        "A": [-8.68, -86.46, -53.90],
        "OW": [-10.44, -81.81, -57.64],
        "V": [-8.86, -80.34, -58.01],
    },
    "COORD": {"XAXIS": [-0.76, 0.63, -0.13], "YAXIS": [-0.00, 0.20, 0.98], "ZAXIS": [-0.65, -0.75, 0.15]},
}
T01 = {
    "SIDE": "LEFT",
    "LANDMARKS": {
        "RW": [10.11, -63.87, -197.39],
        "C": [7.79, -62.24, -192.79],
        "A": [6.09, -64.25, -192.96],
        "OW": [11.29, -65.11, -194.91],
        "V": [12.71, -64.30, -194.87],
    },
    "COORD": {"XAXIS": [0.43, -0.30, -0.85], "YAXIS": [-0.63, 0.58, -0.52], "ZAXIS": [-0.65, -0.76, -0.06]},
}


@pytest.mark.parametrize("desc", [F01, T01], ids=["F01", "T01"])
def test_frame_is_orthonormal_and_matches_the_dataset_descriptor(desc):
    frame = cochlear_frame(desc["LANDMARKS"], desc["SIDE"])
    rotation = np.stack([frame.x, frame.y, frame.z])
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-12)
    # Descriptor axes are rounded to two decimals and x is not orthogonalised there.
    assert max_axis_disagreement(frame, desc["COORD"]) < 0.06


@pytest.mark.parametrize("desc", [F01, T01], ids=["F01", "T01"])
def test_landmarks_land_where_the_definition_says(desc):
    frame = cochlear_frame(desc["LANDMARKS"], desc["SIDE"])
    lm = {k: frame.to_frame(np.asarray([v]))[0] for k, v in desc["LANDMARKS"].items()}
    assert np.allclose(lm["C"], 0, atol=1e-12)
    # Helicotrema on the +z axis; round window in the x-z plane on the +x side.
    assert lm["A"][2] > 0 and np.allclose(lm["A"][:2], 0, atol=1e-9)
    assert lm["RW"][0] > 0 and abs(lm["RW"][1]) < 1e-9


def test_right_ear_frame_mirrors_y_only():
    left = cochlear_frame(F01["LANDMARKS"], "LEFT")
    right = cochlear_frame(F01["LANDMARKS"], "RIGHT")
    assert np.allclose(left.x, right.x) and np.allclose(left.z, right.z)
    assert np.allclose(left.y, -right.y)


def test_flipped_axis_is_detected():
    frame = cochlear_frame(F01["LANDMARKS"], "RIGHT")  # wrong side on purpose
    assert max_axis_disagreement(frame, F01["COORD"]) > 1.0


def test_bad_input_is_rejected():
    with pytest.raises(ValueError):
        cochlear_frame(F01["LANDMARKS"], "BOTH")
    same = dict(F01["LANDMARKS"], A=F01["LANDMARKS"]["C"])
    with pytest.raises(ValueError):
        cochlear_frame(same, "LEFT")
