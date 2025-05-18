import sqlite3
from pathlib import Path

def fix_benchmark_statuses(db_path: Path = Path.cwd()):
    """Fix benchmark statuses by checking if all models have completed runs."""
    db_file = db_path / "eotm_file_store.sqlite"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get all benchmarks and their runs
    cursor.execute("""
        SELECT 
            b.id,
            b.status,
            COUNT(DISTINCT br.model_name) as model_count,
            COUNT(DISTINCT CASE WHEN bp.score IS NOT NULL THEN br.model_name END) as completed_model_count
        FROM benchmarks b
        LEFT JOIN benchmark_runs br ON b.id = br.benchmark_id
        LEFT JOIN benchmark_prompts bp ON br.id = bp.benchmark_run_id
        GROUP BY b.id
    """)
    
    benchmarks = cursor.fetchall()
    for benchmark_id, status, model_count, completed_model_count in benchmarks:
        # If the benchmark has models and all of them have completed prompts
        if model_count > 0 and model_count == completed_model_count:
            print(f"Benchmark {benchmark_id}: {model_count} models, {completed_model_count} completed")
            print(f"  Current status: {status}")
            print(f"  Setting status to: complete")
            cursor.execute("UPDATE benchmarks SET status = 'complete' WHERE id = ?", (benchmark_id,))
        else:
            print(f"Benchmark {benchmark_id}: {model_count} models, {completed_model_count} completed")
            print(f"  Current status: {status}")
            print(f"  Keeping status as: in-progress")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_benchmark_statuses()
