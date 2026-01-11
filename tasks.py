from celery_app import celery_app
from planner import PlannerAgent
from generator import GeneratorAgent
from rank import RankAgent
from models import Run, Plan, Molecule, Trace
from database import SessionLocal, init_db
from datetime import datetime
from rdkit import Chem
import time
import traceback

init_db()

def create_trace(db, run_id, agent_type, action, input_data=None, output_data=None, 
                round_number=None, status="success", error_message=None, duration_ms=None):
    try:
        trace = Trace(
            run_id=run_id,
            agent_type=agent_type,
            action=action,
            input_data=input_data,
            output_data=output_data,
            round_number=round_number,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms
        )
        db.add(trace)
        db.commit()
        return trace
    except Exception as e:
        db.rollback()
        raise

@celery_app.task(bind=True, name="tasks.run_pipeline")
def run_pipeline(self, run_input, run_id=None):
    db = SessionLocal()
    try:
        if run_id:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                raise ValueError(f"Run with id {run_id} not found")
            run.status = "running"
            run.started_at = datetime.utcnow()
        else:
            run = Run(
                objective=run_input["objective"],
                seeds=run_input["seeds"],
                rounds=run_input["rounds"],
                candidates_per_round=run_input["candidates_per_round"],
                top_k=run_input["top_k"],
                random_seed=run_input["random_seed"],
                filters=run_input["filters"],
                status="running",
                started_at=datetime.utcnow()
            )
            db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

        planner = PlannerAgent()
        generator = GeneratorAgent(seed=run_input["random_seed"])
        ranker = RankAgent()

        start_time = time.time()
        plan = planner.plan(run_input)
        duration_ms = int((time.time() - start_time) * 1000)

        create_trace(
            db=db,
            run_id=run_id,
            agent_type="planner",
            action="plan",
            input_data=run_input,
            output_data=plan,
            status="success",
            duration_ms=duration_ms
        )

        plan_db = Plan(
            run_id=run_id,
            rounds=plan["rounds"],
            candidates_per_round=plan["candicates_per_round"],
            diversity_goal=plan.get("diversity_goal")
        )
        db.add(plan_db)
        db.commit()

        all_passed_molecules = {}

        for round_num in range(1, run_input["rounds"] + 1):
            run.current_round = round_num
            db.commit()

            start_time = time.time()
            smiles_list = generator.generate(run_input["seeds"], run_input["candidates_per_round"])
            duration_ms = int((time.time() - start_time) * 1000)

            create_trace(
                db=db,
                run_id=run_id,
                agent_type="generator",
                action="generate",
                input_data={"seeds": run_input["seeds"], "n": run_input["candidates_per_round"]},
                output_data=smiles_list["stats"],
                round_number=round_num,
                status="success",
                duration_ms=duration_ms
            )

            start_time = time.time()
            canonical_list = ranker.extract_metric(smiles_list['smiles'])
            duration_ms = int((time.time() - start_time) * 1000)

            create_trace(
                db=db,
                run_id=run_id,
                agent_type="ranker",
                action="extract_metric",
                input_data={"count": len(smiles_list['smiles'])},
                output_data={"canonical_count": len(canonical_list)},
                round_number=round_num,
                status="success",
                duration_ms=duration_ms
            )

            start_time = time.time()
            smi_pass, smi_fail = ranker.screening(canonical_list, run_input["filters"])
            duration_ms = int((time.time() - start_time) * 1000)

            create_trace(
                db=db,
                run_id=run_id,
                agent_type="ranker",
                action="screening",
                input_data={"canonical_count": len(canonical_list), "filters": run_input["filters"]},
                output_data={"passed": len(smi_pass), "failed": len(smi_fail)},
                round_number=round_num,
                status="success",
                duration_ms=duration_ms
            )

            for canonical, metrics in canonical_list.items():
                existing_molecule = db.query(Molecule).filter(
                    Molecule.run_id == run_id,
                    Molecule.canonical_smiles == canonical
                ).first()

                if existing_molecule:
                    if canonical in smi_pass and canonical not in all_passed_molecules:
                        all_passed_molecules[canonical] = smi_pass[canonical]
                    continue

                mol_obj = None
                for mol in smiles_list['smiles']:
                    if Chem.MolToSmiles(mol, canonical=True) == canonical:
                        mol_obj = mol
                        break

                if mol_obj is None:
                    continue

                molecule = Molecule(
                    run_id=run_id,
                    round_number=round_num,
                    smiles=Chem.MolToSmiles(mol_obj),
                    canonical_smiles=canonical,
                    mw=metrics["mw"],
                    logp=metrics["logp"],
                    hbd=metrics["hbd"],
                    hba=metrics["hba"],
                    tpsa=metrics["tpsa"],
                    rotb=metrics["rotb"],
                    qed=metrics["qed"],
                    generation_stats=smiles_list["stats"]
                )

                if canonical in smi_pass:
                    molecule.passed = True
                    molecule.score = smi_pass[canonical]
                    molecule.violations = 0
                    molecule.violation_details = None
                    all_passed_molecules[canonical] = smi_pass[canonical]
                    run.total_passed += 1
                else:
                    molecule.passed = False
                    molecule.score = None
                    violation_details = smi_fail.get(canonical, {})
                    molecule.violations = len(violation_details)
                    molecule.violation_details = violation_details if violation_details else None
                    run.total_failed += 1

                run.total_generated += 1
                db.add(molecule)

            try:
                db.commit()
            except Exception as e:
                db.rollback()
                raise

        start_time = time.time()
        top_score = ranker.get_top_score(all_passed_molecules)
        duration_ms = int((time.time() - start_time) * 1000)

        create_trace(
            db=db,
            run_id=run_id,
            agent_type="ranker",
            action="get_top_score",
            input_data={"passed_count": len(all_passed_molecules)},
            output_data={"top_count": len(top_score)},
            status="success",
            duration_ms=duration_ms
        )

        rank = 1
        for canonical, score in top_score.items():
            molecule = db.query(Molecule).filter(
                Molecule.run_id == run_id,
                Molecule.canonical_smiles == canonical
            ).first()
            if molecule:
                molecule.rank_in_run = rank
                rank += 1

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()

        return {
            "run_id": run_id,
            "status": "completed",
            "top_molecules": top_score,
            "total_generated": run.total_generated,
            "total_passed": run.total_passed,
            "total_failed": run.total_failed
        }

    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        try:
            if run_id:
                db.rollback()
                run = db.query(Run).filter(Run.id == run_id).first()
                if run:
                    run.status = "failed"
                    run.error_message = error_msg
                    run.completed_at = datetime.utcnow()
                    db.commit()

                create_trace(
                    db=db,
                    run_id=run_id,
                    agent_type="system",
                    action="error",
                    input_data=None,
                    output_data=None,
                    status="error",
                    error_message=error_trace,
                    duration_ms=None
                )
        except Exception as inner_e:
            db.rollback()
        finally:
            db.close()
        
        raise Exception(f"Pipeline failed: {error_msg}")

    finally:
        db.close()

