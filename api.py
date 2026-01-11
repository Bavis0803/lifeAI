from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from tasks import run_pipeline
from models import Run, Molecule, Trace
from database import SessionLocal, get_db
from sqlalchemy.orm import Session

app = FastAPI(title="LifeAI API")

class PipelineInput(BaseModel):
    objective: str
    seeds: List[str]
    rounds: int
    candidates_per_round: int
    top_k: int
    random_seed: int
    filters: Dict[str, Any]

@app.post("/api/runs")
async def create_run(input_data: PipelineInput, db: Session = Depends(get_db)):
    try:
        from models import Run
        from datetime import datetime
        
        run = Run(
            objective=input_data.objective,
            seeds=input_data.seeds,
            rounds=input_data.rounds,
            candidates_per_round=input_data.candidates_per_round,
            top_k=input_data.top_k,
            random_seed=input_data.random_seed,
            filters=input_data.filters,
            status="pending"
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        task = run_pipeline.delay(input_data.dict(), run_id=run.id)
        
        return {
            "run_id": run.id,
            "task_id": task.id,
            "status": "pending",
            "message": "Pipeline started"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/runs/{run_id}")
async def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return {
        "id": run.id,
        "objective": run.objective,
        "status": run.status,
        "rounds": run.rounds,
        "current_round": run.current_round,
        "total_generated": run.total_generated,
        "total_passed": run.total_passed,
        "total_failed": run.total_failed,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error_message": run.error_message
    }

@app.get("/api/runs/{run_id}/molecules")
async def get_run_molecules(run_id: int, passed: bool = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Molecule).filter(Molecule.run_id == run_id)
    if passed is not None:
        query = query.filter(Molecule.passed == passed)
    molecules = query.order_by(Molecule.score.desc().nulls_last()).limit(limit).all()
    
    return [
        {
            "id": m.id,
            "smiles": m.smiles,
            "canonical_smiles": m.canonical_smiles,
            "round_number": m.round_number,
            "mw": float(m.mw),
            "logp": float(m.logp),
            "hbd": m.hbd,
            "hba": m.hba,
            "tpsa": float(m.tpsa),
            "rotb": m.rotb,
            "qed": float(m.qed),
            "passed": m.passed,
            "violations": m.violations,
            "score": float(m.score) if m.score else None,
            "rank_in_run": m.rank_in_run
        }
        for m in molecules
    ]

@app.get("/api/runs/{run_id}/traces")
async def get_run_traces(run_id: int, db: Session = Depends(get_db)):
    traces = db.query(Trace).filter(Trace.run_id == run_id).order_by(Trace.started_at).all()
    
    return [
        {
            "id": t.id,
            "agent_type": t.agent_type,
            "action": t.action,
            "round_number": t.round_number,
            "status": t.status,
            "input_data": t.input_data,
            "output_data": t.output_data,
            "error_message": t.error_message,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "duration_ms": t.duration_ms
        }
        for t in traces
    ]

@app.get("/api/runs/{run_id}/results")
async def get_run_results(run_id: int, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    top_molecules = db.query(Molecule).filter(
        Molecule.run_id == run_id,
        Molecule.passed == True,
        Molecule.rank_in_run.isnot(None)
    ).order_by(Molecule.rank_in_run).all()
    
    return {
        "run_id": run.id,
        "status": run.status,
        "total_generated": run.total_generated,
        "total_passed": run.total_passed,
        "total_failed": run.total_failed,
        "top_molecules": [
            {
                "rank": m.rank_in_run,
                "canonical_smiles": m.canonical_smiles,
                "smiles": m.smiles,
                "score": float(m.score) if m.score else None,
                "qed": float(m.qed),
                "mw": float(m.mw),
                "logp": float(m.logp),
                "hbd": m.hbd,
                "hba": m.hba,
                "tpsa": float(m.tpsa),
                "rotb": m.rotb
            }
            for m in top_molecules
        ]
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

