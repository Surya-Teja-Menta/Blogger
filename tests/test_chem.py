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
