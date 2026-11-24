"""Molecules from names (blogwriter/chem.py, RDKit) and the new picture families' validation in vizlib."""
import pytest

from blogwriter import chem, vizlib

rdkit = pytest.importorskip("rdkit")


def test_a_molecule_is_laid_out_from_its_real_structure():
    benzene = chem.layout("Benzene")
    assert len(benzene["atoms"]) == 6 and len(benzene["bonds"]) == 6 and all(b[2] == 1.5 for b in benzene["bonds"])
    water = chem.layout("water")
    assert [a[0] for a in water["atoms"]] == ["O"] and water["hs"] == [2]
    co2 = chem.layout("carbon dioxide")
    assert [b[2] for b in co2["bonds"]] == [2, 2]
    caffeine = chem.layout("caffeine")
    assert sorted(a[0] for a in caffeine["atoms"]).count("N") == 4 and all(-1.01 <= c <= 1.01 for a in caffeine["atoms"] for c in a[1:])
    assert chem.layout("unobtainium") is None and chem.lookup("H2O") == "O"


def test_the_designer_gets_only_pictures_it_can_draw():
    why = []
    ok = lambda t, a: True          # noqa: E731
    el = {"type": "molecule"}
    assert not vizlib.fill(el, {"name": "aspirin"}, "", ok, why) and len(el["mol"]["atoms"]) == 13
    assert vizlib.fill({"type": "molecule"}, {"name": "unobtainium"}, "", ok, [])                      # not known: refused, never guessed
    q = {"type": "qubit"}
    assert not vizlib.fill(q, {"gates": ["h", "x", "bogus", "T"], "measure": True}, "", ok, why) and q["gates"] == ["H", "X", "T"]
    assert vizlib.fill({"type": "qubit"}, {"gates": ["nope"]}, "", ok, [])
    c = {"type": "qcircuit"}
    assert not vizlib.fill(c, {"circuit": ["h0", "cx01", "cx00", "Q9"]}, "", ok, why) and c["circuit"] == ["H0", "CX01"]


def test_the_real_model_picture_gets_its_data_from_the_probe_or_is_refused(monkeypatch):
    from blogwriter import llmprobe
    ok = lambda t, a: True          # noqa: E731
    monkeypatch.setattr(llmprobe, "probe", lambda text, **k: None)
    why = []
    assert vizlib.fill({"type": "llmreal"}, {"text": "The cat sat on the"}, "", ok, why) and "llmreal" in why[-1]
    monkeypatch.setattr(llmprobe, "probe", lambda text, **k: {"tokens": ["a", "b", "c"], "layer": 1, "head": 2, "attn": [[1, 0, 0], [.5, .5, 0], [.2, .3, .5]], "next": [["x", .5]]})
    el = {"type": "llmreal"}
    assert not vizlib.fill(el, {"text": "The cat sat on the"}, "", ok, [])
    assert el["tokens"] == ["a", "b", "c"] and el["layer"] == 1 and len(el["attn"]) == 3
    assert vizlib.fill({"type": "llmreal"}, {"text": "Hi"}, "", ok, [])                # too short for a picture
