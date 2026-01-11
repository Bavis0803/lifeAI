CREATE TABLE runs (
    id SERIAL PRIMARY KEY,
    objective TEXT NOT NULL,
    seeds TEXT[] NOT NULL,
    rounds INTEGER NOT NULL,
    candidates_per_round INTEGER NOT NULL,
    top_k INTEGER NOT NULL,
    random_seed INTEGER NOT NULL,
    filters JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    current_round INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    total_generated INTEGER DEFAULT 0,
    total_passed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0
);

CREATE TABLE plans (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    rounds INTEGER NOT NULL,
    candidates_per_round INTEGER NOT NULL,
    diversity_goal VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id)
);

CREATE TABLE molecules (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    smiles TEXT NOT NULL,
    canonical_smiles TEXT NOT NULL,
    mw DECIMAL(10, 4) NOT NULL,
    logp DECIMAL(10, 4) NOT NULL,
    hbd INTEGER NOT NULL,
    hba INTEGER NOT NULL,
    tpsa DECIMAL(10, 4) NOT NULL,
    rotb INTEGER NOT NULL,
    qed DECIMAL(10, 4) NOT NULL,
    passed BOOLEAN NOT NULL DEFAULT FALSE,
    violations INTEGER NOT NULL DEFAULT 0,
    violation_details JSONB,
    score DECIMAL(10, 4),
    rank_in_run INTEGER,
    generation_stats JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_run_canonical UNIQUE(run_id, canonical_smiles)
);

CREATE TABLE traces (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    round_number INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER
);

CREATE INDEX idx_molecules_run_id ON molecules(run_id);
CREATE INDEX idx_molecules_round_number ON molecules(run_id, round_number);
CREATE INDEX idx_molecules_passed ON molecules(run_id, passed);
CREATE INDEX idx_molecules_score ON molecules(run_id, score DESC NULLS LAST);
CREATE INDEX idx_molecules_canonical ON molecules(canonical_smiles);

CREATE INDEX idx_traces_run_id ON traces(run_id);
CREATE INDEX idx_traces_agent_type ON traces(run_id, agent_type);
CREATE INDEX idx_traces_round ON traces(run_id, round_number);

CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);

CREATE OR REPLACE VIEW run_summary AS
SELECT 
    r.id,
    r.objective,
    r.status,
    r.rounds,
    r.current_round,
    r.candidates_per_round,
    r.top_k,
    r.created_at,
    r.started_at,
    r.completed_at,
    COUNT(DISTINCT m.id) as total_molecules,
    COUNT(DISTINCT CASE WHEN m.passed THEN m.id END) as passed_molecules,
    COUNT(DISTINCT CASE WHEN NOT m.passed THEN m.id END) as failed_molecules,
    AVG(CASE WHEN m.passed THEN m.score END) as avg_passed_score,
    MAX(CASE WHEN m.passed THEN m.score END) as max_score
FROM runs r
LEFT JOIN molecules m ON r.id = m.run_id
GROUP BY r.id, r.objective, r.status, r.rounds, r.current_round, 
         r.candidates_per_round, r.top_k, r.created_at, r.started_at, r.completed_at;

CREATE OR REPLACE VIEW top_molecules_per_run AS
SELECT 
    m.*,
    r.objective,
    r.filters
FROM molecules m
JOIN runs r ON m.run_id = r.id
WHERE m.passed = TRUE 
  AND m.rank_in_run IS NOT NULL
  AND r.status = 'completed'
ORDER BY m.run_id, m.rank_in_run;
