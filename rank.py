from rdkit.Chem import Descriptors, QED
from rdkit import Chem

class RankAgent:
    def extract_metric(self, out):
        canonical_smiles = dict()
        for smiles in out:
            canonical = Chem.MolToSmiles(smiles, canonical=True)
            if canonical in canonical_smiles:
                continue
            props = {
                "mw": float(Descriptors.MolWt(smiles)),
                "logp": float(Descriptors.MolLogP(smiles)),
                "hbd": int(Descriptors.NumHDonors(smiles)),
                "hba": int(Descriptors.NumHAcceptors(smiles)),
                "tpsa": float(Descriptors.TPSA(smiles)),
                "rotb": int(Descriptors.NumRotatableBonds(smiles)),
                "qed": float(QED.qed(smiles)),
            }
            canonical_smiles[canonical] = props
        return canonical_smiles

    def screening(self, canonicals, filters):
        smi_pass = {}
        smi_fail = {}
        violations = 0
        detail = {}

        def check(key, value, limit):
            nonlocal violations
            if value > limit:
                violations += 1
                label = f"{key.upper()} too high"
                detail[label] = round(value, 2)

        for canonical, metrics in canonicals.items():
            check("mw", metrics["mw"], filters["mw"])
            check("logp", metrics["logp"], filters["logp"])
            check("hbd", metrics["hbd"], filters["hbd"])
            check("hba", metrics["hba"], filters["hba"])
            check("tpsa", metrics["tpsa"], filters["tpsa"])
            passed = violations <= filters["max_violations"]
            if passed:
                score = self.score_module(metrics['qed'], violations)
                smi_pass[canonical] = score
            else:
                smi_fail[canonical] = detail


            violations = 0
        return smi_pass, smi_fail


    def score_module(self, qued, violiations):
        score = qued - (0.1 * violiations)
        return float(score)
    
    def get_top_score(self, smiles):
        return dict(sorted(smiles.items(), key=lambda item: item[1], reverse=True)[:5])