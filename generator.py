import random
from rdkit import Chem

class GeneratorAgent:
    def __init__(self, seed):
        #random seed generator
        self.rng = random.Random(seed)

    def mutate(self, mol: Chem.Mol, rng):
        #add methyl
        if rng.random() < 0.5:
            rw = Chem.RWMol(mol)
            for atom in rw.GetAtoms():
                if atom.GetAtomicNum() == 6 and atom.GetNumImplicitHs() > 0:
                    c_idx = rw.AddAtom(Chem.Atom(6))
                    rw.AddBond(atom.GetIdx(), c_idx, Chem.BondType.SINGLE)
                    try:
                        new_mol = rw.GetMol()
                        Chem.SanitizeMol(new_mol)
                        return new_mol, "add_methyl"
                    except Exception as e:
                        print("Error when mutate", e)

        #remove C
        rw = Chem.RWMol(mol)
        for atom in rw.GetAtoms():
            if atom.GetAtomicNum() == 6 and atom.GetDegree() == 1:
                rw.RemoveAtom(atom.GetIdx())
                try:
                    new_mol = rw.GetMol()
                    Chem.SanitizeMol(new_mol)
                    return new_mol, "remove methyl"
                except Exception as e:
                    print("Error when mutate", e)
    
    def generate(self, seed_smiles, n, mutation_rate = 0.2):
        seen = set()
        out = []
        invalid = 0
        dup = 0
        transform_counts = {}

        seed_mols = []
        
        #check smiles valid
        for s in seed_smiles:
            m = Chem.MolFromSmiles(s)
            if m:
                seed_mols.append(m)
        
        max_attempts = n * 20
        attempts = 0
        while len(out) < n and attempts < max_attempts:
            attempts += 1
            base = self.rng.choice(seed_mols) if seed_mols else None
            if base is None:
                break
            
            #decide number mutation apply
            steps = 2 if self.rng.random() < mutation_rate else 1

            m = Chem.Mol(base)
            chosen_transforms = []
            is_mutate = True
            for _ in range(steps):
                res = self.mutate(m, self.rng)
                if not res:
                    is_mutate = False
                    break
                m, transform = res
                chosen_transforms.append(transform)
            
            if not is_mutate:
                invalid += 1
                continue

            smi = Chem.MolToSmiles(m, canonical=True)
            if smi in seen:
                dup += 1
                continue

            seen.add(smi)
            out.append(m)
            for t in chosen_transforms:
                transform_counts[t] = transform_counts.get(t, 0) + 1
        return {
            "smiles": out,
            "stats": {
                "requested": n,
                "generated": len(out),
                "attempts": attempts,
                "invalid_or_failed_mutation": invalid,
                "duplicates": dup,
                "transform_counts": transform_counts,
            }
        }