"""Molecules from their names, laid out in 2D by RDKit (BSD licence, the open-source cheminformatics toolkit): the "molecule"
picture (video/src/viz/chem.jsx) draws atoms and bonds from these exact structures, so a benzene ring is a ring of six
carbons with alternating double bonds, not a drawing of one. A name the table does not know is refused (never guessed), and
the diagram designer then draws the idea some other way. A SMILES string is the standard one-line way to write a structure."""
from typing import Dict, List, Optional

SMILES: Dict[str, str] = {
    "water": "O", "hydrogen": "[H][H]", "oxygen": "O=O", "nitrogen": "N#N", "carbon dioxide": "O=C=O", "carbon monoxide": "[C-]#[O+]",
    "ammonia": "N", "methane": "C", "ethane": "CC", "propane": "CCC", "butane": "CCCC", "ethene": "C=C", "ethylene": "C=C",
    "ethyne": "C#C", "acetylene": "C#C", "propene": "CC=C", "benzene": "c1ccccc1", "toluene": "Cc1ccccc1", "phenol": "Oc1ccccc1",
    "methanol": "CO", "ethanol": "CCO", "propanol": "CCCO", "isopropanol": "CC(C)O", "glycerol": "OCC(O)CO",
    "formaldehyde": "C=O", "acetaldehyde": "CC=O", "acetone": "CC(C)=O", "formic acid": "OC=O", "acetic acid": "CC(=O)O",
    "citric acid": "OC(=O)CC(O)(CC(O)=O)C(O)=O", "lactic acid": "CC(O)C(O)=O", "urea": "NC(N)=O", "glycine": "NCC(=O)O",
    "alanine": "CC(N)C(=O)O", "glucose": "OCC1OC(O)C(O)C(O)C1O", "fructose": "OCC1(O)OCC(O)C(O)C1O", "sucrose": "OCC1OC(CO)(OC2OC(CO)C(O)C(O)C2O)C(O)C1O",
    "aspirin": "CC(=O)Oc1ccccc1C(=O)O", "paracetamol": "CC(=O)Nc1ccc(O)cc1", "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "ibuprofen": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "nicotine": "CN1CCCC1c1cccnc1", "dopamine": "NCCc1ccc(O)c(O)c1",
    "serotonin": "NCCc1c[nH]c2ccc(O)cc12", "adrenaline": "CNCC(O)c1ccc(O)c(O)c1", "cholesterol": "CC(C)CCCC(C)C1CCC2C1(CCC3C2CC=C4C3(CCC(C4)O)C)C",
    "hydrogen chloride": "Cl", "hydrochloric acid": "Cl", "sulfuric acid": "OS(O)(=O)=O", "nitric acid": "O[N+]([O-])=O",
    "hydrogen peroxide": "OO", "ozone": "[O-][O+]=O", "hydrogen sulfide": "S", "sulfur dioxide": "O=S=O", "chloroform": "ClC(Cl)Cl",
    "ethyl acetate": "CCOC(C)=O", "diethyl ether": "CCOCC", "cyclohexane": "C1CCCCC1", "naphthalene": "c1ccc2ccccc2c1",
    "vitamin c": "OCC(O)C1OC(=O)C(O)=C1O", "ascorbic acid": "OCC(O)C1OC(=O)C(O)=C1O", "co2": "O=C=O", "h2o": "O", "ch4": "C", "nh3": "N",
    "o2": "O=O", "n2": "N#N", "h2": "[H][H]", "hcl": "Cl", "c6h6": "c1ccccc1",
}


def lookup(name: str) -> Optional[str]:
    """The SMILES of a molecule by its common name or formula, or None."""
    return SMILES.get(" ".join(str(name).lower().replace("-", " ").split()))


def layout(name: str) -> Optional[dict]:
    """{"atoms": [[symbol, x, y], ...], "bonds": [[i, j, order], ...]} with the coordinates centred and scaled to fit [-1, 1]
    (hydrogens on carbon are left implicit, as chemists draw them), or None when the name is unknown or RDKit is missing."""
    smi = lookup(name)
    if smi is None:
        return None
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError:
        return None
    mol = Chem.MolFromSmiles(smi)
    if mol is None or mol.GetNumAtoms() == 0:
        return None
    if mol.GetNumAtoms() == 1:
        return {"atoms": [[mol.GetAtomWithIdx(0).GetSymbol(), 0.0, 0.0]], "bonds": [], "hs": [mol.GetAtomWithIdx(0).GetTotalNumHs()]}
    AllChem.Compute2DCoords(mol)
    conf = mol.GetConformer()
    xs, ys = [conf.GetAtomPosition(i).x for i in range(mol.GetNumAtoms())], [conf.GetAtomPosition(i).y for i in range(mol.GetNumAtoms())]
    cx, cy, span = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    atoms = [[a.GetSymbol(), round((xs[i] - cx) / span * 2, 4), round(-(ys[i] - cy) / span * 2, 4)] for i, a in enumerate(mol.GetAtoms())]
    bonds: List[list] = [[b.GetBeginAtomIdx(), b.GetEndAtomIdx(), 3 if b.GetBondTypeAsDouble() == 3 else 2 if b.GetBondTypeAsDouble() in (2.0,) else 1.5 if b.GetBondTypeAsDouble() == 1.5 else 1]
                         for b in mol.GetBonds()]
    return {"atoms": atoms, "bonds": bonds, "hs": [a.GetTotalNumHs() for a in mol.GetAtoms()]}
