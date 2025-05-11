import sqlite3
import hashlib
from pathlib import Path
import datetime
import json

DB_NAME = "eotm_file_store.sqlite"
TABLE_NAME = "openai_file_map"
BENCHMARKS_TABLE_NAME = "benchmarks"
BENCHMARK_RUNS_TABLE_NAME = "benchmark_runs"
BENCHMARK_PROMPTS_TABLE_NAME = "benchmark_prompts"
SCORING_CONFIGS_TABLE_NAME = "scoring_configs"
BENCHMARK_REPORTS_TABLE_NAME = "benchmark_reports"

def init_db(db_path: Path = Path.cwd()):
    """Initializes the SQLite database and creates tables if they don't exist."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # OpenAI File Map Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            pdf_hash TEXT PRIMARY KEY,
            openai_file_id TEXT NOT NULL,
            local_path_at_upload TEXT,
            original_filename TEXT,
            upload_timestamp TEXT NOT NULL
        )
    ''')

    # Benchmarks Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARKS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            label TEXT,
            description TEXT
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS benchmark_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY (benchmark_id) REFERENCES {BENCHMARKS_TABLE_NAME}(id)
        )
    ''')

    # Benchmark Runs Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARK_RUNS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            report TEXT,
            latency REAL,
            created_at TEXT NOT NULL,
            total_input_tokens INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            FOREIGN KEY (benchmark_id) REFERENCES {BENCHMARKS_TABLE_NAME}(id)
        )
    ''')

    # Benchmark Prompts Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARK_PROMPTS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_run_id INTEGER NOT NULL,
            prompt TEXT,
            answer TEXT,
            response TEXT,
            score TEXT,
            latency REAL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            scoring_config_id INTEGER,
            FOREIGN KEY (benchmark_run_id) REFERENCES {BENCHMARK_RUNS_TABLE_NAME}(id),
            FOREIGN KEY (scoring_config_id) REFERENCES {SCORING_CONFIGS_TABLE_NAME}(id)
        )
    ''')

    # Scoring Configs Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {SCORING_CONFIGS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            config TEXT -- JSON or code (VBA, Python, etc.)
        )
    ''')

    # Benchmark Reports Table (for cross-model analysis)
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARK_REPORTS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL,
            compared_models TEXT, -- JSON array of model names
            report TEXT,
            created_at TEXT,
            FOREIGN KEY (benchmark_id) REFERENCES {BENCHMARKS_TABLE_NAME}(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_file}")

def _calculate_pdf_hash(pdf_path: Path) -> str:
    """Calculates the SHA256 hash of a PDF file's content."""
    hasher = hashlib.sha256()
    try:
        with open(pdf_path, "rb") as f:
            while chunk := f.read(8192):  # Read in 8KB chunks
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        print(f"Error: File not found at {pdf_path} during hash calculation.")
        return "" # Or raise error
    except Exception as e:
        print(f"Error calculating hash for {pdf_path}: {e}")
        return "" # Or raise error
    # Note: No database connection is used here, so nothing to close in finally block.

def add_file_mapping(pdf_path: Path, openai_file_id: str, db_path: Path = Path.cwd()):
    """Adds or updates a mapping between a PDF's hash and its OpenAI file ID."""
    pdf_hash = _calculate_pdf_hash(pdf_path)
    if not pdf_hash:
        print(f"Skipping DB add for {pdf_path.name} due to hashing error.")
        return

    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    
    try:
        cursor.execute(f'''
            INSERT INTO {TABLE_NAME} (pdf_hash, openai_file_id, local_path_at_upload, original_filename, upload_timestamp)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(pdf_hash) DO UPDATE SET
                openai_file_id=excluded.openai_file_id,
                local_path_at_upload=excluded.local_path_at_upload,
                original_filename=excluded.original_filename,
                upload_timestamp=excluded.upload_timestamp
        ''', (pdf_hash, openai_file_id, str(pdf_path.resolve()), pdf_path.name, timestamp))
        conn.commit()
        print(f"Mapped PDF hash {pdf_hash[:8]}... for {pdf_path.name} to OpenAI ID {openai_file_id}")
    except sqlite3.Error as e:
        print(f"SQLite error when adding/updating mapping for {pdf_path.name}: {e}")
    finally:
        conn.close()

def get_openai_file_id(pdf_path: Path, db_path: Path = Path.cwd()) -> str | None:
    """Retrieves an OpenAI file ID for a given PDF path by its content hash.
    Returns the OpenAI file ID if found, otherwise None.
    """
    pdf_hash = _calculate_pdf_hash(pdf_path)
    if not pdf_hash:
        print(f"Skipping DB lookup for {pdf_path.name} due to hashing error.")
        return None

    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT openai_file_id FROM {TABLE_NAME} WHERE pdf_hash = ?", (pdf_hash,))
        result = cursor.fetchone()
        if result:
            print(f"Found existing OpenAI ID {result[0]} for PDF {pdf_path.name} (hash {pdf_hash[:8]}...)")
            return result[0]
        else:
            print(f"No existing OpenAI ID found for PDF {pdf_path.name} (hash {pdf_hash[:8]}...)")
            return None
    except sqlite3.Error as e:
        print(f"SQLite error when retrieving mapping for {pdf_path.name}: {e}")
        return None
    finally:
        conn.close()

def save_benchmark(label: str, description: str, file_paths: list[str], db_path: Path = Path.cwd()) -> int | None:
    """Saves a new benchmark and its associated files, returns the benchmark ID."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    try:
        cursor.execute(f'''
            INSERT INTO {BENCHMARKS_TABLE_NAME} (timestamp, label, description)
            VALUES (?, ?, ?)
        ''', (timestamp, label, description))
        benchmark_id = cursor.lastrowid
        # Save files in benchmark_files table
        for file_path in file_paths:
            cursor.execute('''
                INSERT INTO benchmark_files (benchmark_id, file_path)
                VALUES (?, ?)
            ''', (benchmark_id, file_path))
        conn.commit()
        return benchmark_id
    except sqlite3.Error as e:
        print(f"SQLite error when saving benchmark: {e}")
        return None
    finally:
        conn.close()

def add_benchmark_file(benchmark_id: int, file_path: str, db_path: Path = Path.cwd()) -> int | None:
    """Adds a file to a benchmark."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO benchmark_files (benchmark_id, file_path)
            VALUES (?, ?)
        ''', (benchmark_id, file_path))
        file_id = cursor.lastrowid
        conn.commit()
        return file_id
    except sqlite3.Error as e:
        print(f"SQLite error when adding file to benchmark: {e}")
        return None
    finally:
        conn.close()

def get_benchmark_files(benchmark_id: int, db_path: Path = Path.cwd()) -> list[str]:
    """Returns a list of file paths for a given benchmark."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT file_path FROM benchmark_files WHERE benchmark_id = ?
        ''', (benchmark_id,))
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    except sqlite3.Error as e:
        print(f"SQLite error when loading files for benchmark {benchmark_id}: {e}")
        return []
    finally:
        conn.close()

def save_benchmark_run(benchmark_id: int, model_name: str, report: str, latency: float, total_input_tokens: int, total_output_tokens: int, total_tokens: int, db_path: Path = Path.cwd()) -> int | None:
    """Saves a benchmark run and returns its ID."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    created_at_ts = datetime.datetime.now().isoformat()
    try:
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_RUNS_TABLE_NAME} (benchmark_id, model_name, report, latency, created_at, total_input_tokens, total_output_tokens, total_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (benchmark_id, model_name, report, latency, created_at_ts, total_input_tokens, total_output_tokens, total_tokens))
        run_id = cursor.lastrowid
        conn.commit()
        return run_id
    except sqlite3.Error as e:
        print(f"SQLite error when saving benchmark run: {e}")
        return None
    finally:
        conn.close()

def save_benchmark_prompt(benchmark_run_id: int, prompt: str, answer: str, response: str, score: str, latency: float, input_tokens: int, output_tokens: int, scoring_config_id: int | None = None, db_path: Path = Path.cwd()) -> int | None:
    """Saves a prompt result for a benchmark run."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_PROMPTS_TABLE_NAME} (benchmark_run_id, prompt, answer, response, score, latency, input_tokens, output_tokens, scoring_config_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (benchmark_run_id, prompt, answer, response, score, latency, input_tokens, output_tokens, scoring_config_id))
        prompt_id = cursor.lastrowid
        conn.commit()
        return prompt_id
    except sqlite3.Error as e:
        print(f"SQLite error when saving benchmark prompt: {e}")
        return None
    finally:
        conn.close()

def save_scoring_config(name: str, config: str, db_path: Path = Path.cwd()) -> int | None:
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute(f'''
            INSERT INTO {SCORING_CONFIGS_TABLE_NAME} (name, config)
            VALUES (?, ?)
        ''', (name, config))
        config_id = cursor.lastrowid
        conn.commit()
        return config_id
    except sqlite3.Error as e:
        print(f"SQLite error when saving scoring config: {e}")
        return None
    finally:
        conn.close()

def save_benchmark_report(benchmark_id: int, compared_models: list[str], report: str, db_path: Path = Path.cwd()) -> int | None:
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    created_at = datetime.datetime.now().isoformat()
    try:
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_REPORTS_TABLE_NAME} (benchmark_id, compared_models, report, created_at)
            VALUES (?, ?, ?, ?)
        ''', (benchmark_id, json.dumps(compared_models), report, created_at))
        report_id = cursor.lastrowid
        conn.commit()
        return report_id
    except sqlite3.Error as e:
        print(f"SQLite error when saving benchmark report: {e}")
        return None
    finally:
        conn.close()

def load_all_benchmark_runs(db_path: Path = Path.cwd()) -> list[dict]:
    """Loads all benchmark runs (summary) from the database, newest first."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row # Access columns by name
    cursor = conn.cursor()
    runs = []
    try:
        cursor.execute(f'''
            SELECT 
                b.id as benchmark_id, 
                b.timestamp as benchmark_timestamp, 
                b.label as benchmark_label,
                (SELECT file_path FROM benchmark_files bf WHERE bf.benchmark_id = b.id LIMIT 1) as pdf_path, 
                br.model_name, 
                br.report, 
                br.latency as elapsed_seconds,
                br.total_input_tokens, 
                br.total_output_tokens, 
                br.total_tokens,
                br.id as run_id,
                br.created_at as run_timestamp
            FROM {BENCHMARK_RUNS_TABLE_NAME} br
            JOIN {BENCHMARKS_TABLE_NAME} b ON br.benchmark_id = b.id
            ORDER BY br.created_at DESC
        ''')
        rows = cursor.fetchall()
        for row_data in rows:
            run_dict = dict(row_data)
            # Attempt to parse mean_score and total_items from report string for compatibility
            # This is brittle; ideally, these would be separate columns in BENCHMARK_RUNS_TABLE_NAME
            run_dict['mean_score'] = None
            run_dict['total_items'] = None
            if run_dict.get('report'):
                try:
                    report_str = run_dict['report']
                    if "Mean score:" in report_str and "Items:" in report_str:
                        parts = report_str.split(',')
                        for part in parts:
                            if "Mean score:" in part:
                                run_dict['mean_score'] = float(part.split(':')[1].strip())
                            if "Items:" in part:
                                run_dict['total_items'] = int(part.split(':')[1].split(',')[0].strip())
                except Exception:
                    pass # Ignore parsing errors, fields will remain None
            runs.append(run_dict)
        print(f"Loaded {len(runs)} benchmark runs from DB.")
    except sqlite3.Error as e:
        print(f"SQLite error when loading benchmark runs: {e}")
    finally:
        conn.close()
    return runs

def load_benchmark_details(benchmark_id: int, db_path: Path = Path.cwd()) -> dict | None:
    """Loads details for a specific benchmark, including its most recent run and that run's prompts."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    details = None
    try:
        # 1. Fetch benchmark definition
        cursor.execute(f'''
            SELECT id, timestamp, label, description
            FROM {BENCHMARKS_TABLE_NAME}
            WHERE id = ?
        ''', (benchmark_id,))
        benchmark_info = cursor.fetchone()

        if not benchmark_info:
            print(f"No benchmark found with ID {benchmark_id}")
            return None
        
        details = dict(benchmark_info)

        # 2. Fetch associated file paths
        cursor.execute('''
            SELECT file_path FROM benchmark_files WHERE benchmark_id = ?
        ''', (benchmark_id,))
        file_rows = cursor.fetchall()
        details['file_paths'] = [f['file_path'] for f in file_rows]
        # For UI compatibility, provide pdf_path as the first file if available
        details['pdf_path'] = details['file_paths'][0] if details['file_paths'] else None


        # 3. Fetch the most recent benchmark run for this benchmark
        cursor.execute(f'''
            SELECT id AS run_id, model_name, report, latency, created_at AS run_timestamp
            FROM {BENCHMARK_RUNS_TABLE_NAME}
            WHERE benchmark_id = ?
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (benchmark_id,))
        run_info = cursor.fetchone()

        if run_info:
            details.update(dict(run_info)) # Add run details to the main details dict
            details['elapsed_seconds'] = run_info['latency'] # For UI compatibility
            
            # Parse report for mean_score, total_items if possible (example)
            # This is a placeholder - actual parsing depends on report structure
            # For now, UI will show N/A if these are not directly in details
            # A better approach would be to store these explicitly in benchmark_runs if needed often
            # Or have the report be a JSON string.
            if isinstance(run_info['report'], str):
                try:
                    # Example: "Mean score: 0.85, Items: 10, Time: 5.2s"
                    if "Mean score:" in run_info['report'] and "Items:" in run_info['report']:
                        parts = run_info['report'].split(',')
                        for part in parts:
                            if "Mean score:" in part:
                                details['mean_score'] = float(part.split(':')[1].strip())
                            if "Items:" in part:
                                details['total_items'] = int(part.split(':')[1].split(',')[0].strip())
                except Exception as e:
                    print(f"Could not parse mean_score/total_items from report string: {e}")


            # 4. Fetch prompts for this specific run
            cursor.execute(f'''
                SELECT prompt, answer AS expected_answer, response AS actual_answer, score, latency AS prompt_latency, input_tokens, output_tokens
                FROM {BENCHMARK_PROMPTS_TABLE_NAME}
                WHERE benchmark_run_id = ?
                ORDER BY id ASC
            ''', (run_info['run_id'],))
            prompts = cursor.fetchall()
            # Rename 'prompt' to 'prompt_text' for UI compatibility
            details['prompts_data'] = [{'prompt_text': p['prompt'], **{k: p[k] for k in p.keys() if k != 'prompt'}} for p in prompts]
            
            print(f"Loaded details for benchmark ID {benchmark_id}, including its most recent run ID {run_info['run_id']}")
        else:
            details['prompts_data'] = [] # No runs, so no prompts
            print(f"Benchmark ID {benchmark_id} has no runs.")

    except sqlite3.Error as e:
        print(f"SQLite error when loading benchmark details for ID {benchmark_id}: {e}")
        return None # Return None on error
    finally:
        conn.close()
    return details

def load_all_benchmarks_with_models(db_path: Path = Path.cwd()) -> list[dict]:
    """Loads all benchmarks, each with a list of associated model names and files."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    benchmarks = []
    try:
        cursor.execute(f'''
            SELECT id, timestamp, label, description
            FROM {BENCHMARKS_TABLE_NAME}
            ORDER BY timestamp DESC
        ''')
        rows = cursor.fetchall()
        for row in rows:
            benchmark = dict(row)
            cursor.execute(f'''
                SELECT DISTINCT model_name FROM {BENCHMARK_RUNS_TABLE_NAME}
                WHERE benchmark_id = ?
            ''', (row['id'],))
            model_rows = cursor.fetchall()
            model_names = [m['model_name'] for m in model_rows]
            benchmark['model_names'] = model_names
            cursor.execute('''
                SELECT file_path FROM benchmark_files WHERE benchmark_id = ?
            ''', (row['id'],))
            file_rows = cursor.fetchall()
            benchmark['file_paths'] = [f['file_path'] for f in file_rows]
            benchmarks.append(benchmark)
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            # This can happen if the database is new and init_db hasn't run or completed yet.
            # Silently return an empty list, init_db will create tables.
            pass
        else:
            # For other operational errors, print them as they are unexpected.
            print(f"SQLite operational error when loading benchmarks with models: {e}")
    except sqlite3.Error as e:
        # For other, more general SQLite errors.
        print(f"SQLite error when loading benchmarks with models: {e}")
    finally:
        if conn:
            conn.close()
    return benchmarks

def find_benchmark_by_files(file_paths: list[str], db_path: Path = Path.cwd()) -> int | None:
    """Returns the benchmark ID for a given set of file paths, or None if not found. (Matches on first file for now)"""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT benchmark_id FROM benchmark_files WHERE file_path = ?
        ''', (file_paths[0],))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    except sqlite3.Error as e:
        print(f"SQLite error when searching for benchmark by files: {e}")
        return None
    finally:
        conn.close()

def delete_benchmark(benchmark_id: int, db_path: Path = Path.cwd()) -> bool:
    """Deletes a benchmark and all associated files, runs, and prompts."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        # Delete prompts
        cursor.execute(f'''DELETE FROM benchmark_prompts WHERE benchmark_run_id IN (SELECT id FROM benchmark_runs WHERE benchmark_id = ?)''', (benchmark_id,))
        # Delete runs
        cursor.execute(f'''DELETE FROM benchmark_runs WHERE benchmark_id = ?''', (benchmark_id,))
        # Delete files
        cursor.execute(f'''DELETE FROM benchmark_files WHERE benchmark_id = ?''', (benchmark_id,))
        # Delete the benchmark
        cursor.execute(f'''DELETE FROM benchmarks WHERE id = ?''', (benchmark_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"SQLite error when deleting benchmark {benchmark_id}: {e}")
        return False
    finally:
        conn.close()

# Example usage (optional, for testing)
if __name__ == '__main__':
    # Create a dummy files directory and a dummy PDF for testing
    test_files_dir = Path.cwd() / "test_files_for_store"
    test_files_dir.mkdir(exist_ok=True)
    dummy_pdf_path = test_files_dir / "dummy.pdf"
    with open(dummy_pdf_path, "wb") as f:
        f.write(b"This is some dummy PDF content.")

    db_storage_path = Path.cwd() # Or specify a different directory like app data folder

    init_db(db_storage_path)
    
    # Test adding a new mapping
    print("\n--- Test Add ---")
    test_openai_id = "file-dummy123"
    add_file_mapping(dummy_pdf_path, test_openai_id, db_storage_path)
    
    # Test retrieving the mapping
    print("\n--- Test Retrieve ---")
    retrieved_id = get_openai_file_id(dummy_pdf_path, db_storage_path)
    assert retrieved_id == test_openai_id, f"Expected {test_openai_id}, got {retrieved_id}"
    
    # Test retrieving a non-existent mapping
    print("\n--- Test Retrieve Non-existent ---")
    non_existent_pdf = test_files_dir / "non_existent.pdf"
    with open(non_existent_pdf, "wb") as f: # Create another dummy file
        f.write(b"Other content.")
    retrieved_id_none = get_openai_file_id(non_existent_pdf, db_storage_path)
    assert retrieved_id_none is None, f"Expected None, got {retrieved_id_none}"

    # Modify the content of the first PDF and check if it's treated as new
    print("\n--- Test Content Change ---")
    with open(dummy_pdf_path, "wb") as f:
        f.write(b"This is MODIFIED dummy PDF content.")
    retrieved_id_after_mod = get_openai_file_id(dummy_pdf_path, db_storage_path)
    assert retrieved_id_after_mod is None, "Expected None after content modification, but found old ID."
    
    new_openai_id = "file-dummy456"
    add_file_mapping(dummy_pdf_path, new_openai_id, db_storage_path)
    retrieved_new_id = get_openai_file_id(dummy_pdf_path, db_storage_path)
    assert retrieved_new_id == new_openai_id, "Failed to map new ID after content modification."

    print("\n--- Test Benchmark Save and Load ---")
    # Create a dummy result dict
    dummy_result = {
        'model_name': 'test_model_v1',
        'mean_score': 0.85,
        'items': 2,
        'elapsed_s': 12.34,
        'total_input_tokens': 100,
        'total_output_tokens': 200,
        'total_tokens': 300,
        'prompts_data': [
            {'prompt_text': "P1", 'expected_answer': "E1", 'actual_answer': "A1", 'score': 1.0, 'prompt_length_chars': 10, 'latency_ms': 50, 'input_tokens': 20, 'output_tokens': 40},
            {'prompt_text': "P2", 'expected_answer': "E2", 'actual_answer': "A2", 'score': 0.7, 'prompt_length_chars': 8, 'latency_ms': 30, 'input_tokens': 15, 'output_tokens': 25}
        ]
    }
    saved_run_id = save_benchmark_run(dummy_pdf_path, dummy_result, db_storage_path)
    assert saved_run_id is not None, "Failed to save benchmark run."

    all_runs = load_all_benchmark_runs(db_storage_path)
    assert len(all_runs) > 0, "Failed to load benchmark runs."
    print(f"Found runs: {all_runs}")

    if saved_run_id:
        run_details = load_benchmark_details(saved_run_id, db_storage_path)
        assert run_details is not None, "Failed to load benchmark details."
        assert len(run_details.get('prompts_data', [])) == 2, "Incorrect number of prompts loaded."
        print(f"Details for run {saved_run_id}: {run_details}")

    print("\nAll file_store tests passed (if no assertion errors).")
    
    # Clean up dummy files
    # dummy_pdf_path.unlink()
    # non_existent_pdf.unlink()
    # test_files_dir.rmdir()
    # (Path(db_storage_path) / DB_NAME).unlink() # Optionally delete the test DB 