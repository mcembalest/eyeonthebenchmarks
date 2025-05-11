
CREATE TABLE IF NOT EXISTS benchmark_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    FOREIGN KEY (benchmark_id) REFERENCES benchmarks(id)
);


CREATE TABLE IF NOT EXISTS benchmark_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    report TEXT,           -- Flexible narrative or JSON report
    latency REAL,          -- Formerly elapsed_seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (benchmark_id) REFERENCES benchmarks(id)
);


CREATE TABLE IF NOT EXISTS benchmark_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    prompt TEXT,
    answer TEXT,
    response TEXT,
    score TEXT,         -- Now a string for flexibility
    latency REAL,
    tokens INTEGER,
    scoring_config_id INTEGER,
    FOREIGN KEY (run_id) REFERENCES benchmark_runs(id),
    FOREIGN KEY (scoring_config_id) REFERENCES scoring_configs(id)
);

CREATE TABLE IF NOT EXISTS scoring_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL, -- Store config as JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS benchmark_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_id INTEGER NOT NULL,
    report TEXT, -- Narrative or JSON summary comparing models
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (benchmark_id) REFERENCES benchmarks(id)
);
