import sqlite3
import hashlib
from pathlib import Path
import datetime

DB_NAME = "eotm_file_store.sqlite"
TABLE_NAME = "openai_file_map"
BENCHMARKS_TABLE_NAME = "benchmarks"
BENCHMARK_PROMPTS_TABLE_NAME = "benchmark_prompts"

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
            pdf_path TEXT NOT NULL,
            pdf_hash TEXT,
            model_name TEXT,
            mean_score REAL,
            total_items INTEGER,
            elapsed_seconds REAL,
            total_prompt_tokens INTEGER,
            total_completion_tokens INTEGER,
            total_tokens INTEGER
        )
    ''')

    # Benchmark Prompts Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARK_PROMPTS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL,
            prompt_text TEXT,
            expected_answer TEXT,
            actual_answer TEXT,
            score REAL,
            prompt_length_chars INTEGER,
            latency_ms INTEGER,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
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

def save_benchmark_run(pdf_path: Path, result_dict: dict, db_path: Path = Path.cwd()) -> int | None:
    """Saves a benchmark run and its associated prompts to the database.
    Returns the ID of the saved benchmark run, or None if an error occurs.
    """
    pdf_hash = _calculate_pdf_hash(pdf_path)
    if not pdf_hash:
        print(f"Skipping benchmark save for {pdf_path.name} due to hashing error.")
        # Allow saving even if hash fails for some reason, pdf_path is still useful
        # return None 

    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    run_timestamp = datetime.datetime.now().isoformat()

    try:
        cursor.execute(f'''
            INSERT INTO {BENCHMARKS_TABLE_NAME} 
            (timestamp, pdf_path, pdf_hash, model_name, mean_score, total_items, elapsed_seconds, total_prompt_tokens, total_completion_tokens, total_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_timestamp,
            str(pdf_path.resolve()),
            pdf_hash,
            result_dict.get('model_name', 'unknown'),
            result_dict.get('mean_score'),
            result_dict.get('items'),
            result_dict.get('elapsed_s'),
            result_dict.get('total_prompt_tokens'),
            result_dict.get('total_completion_tokens'),
            result_dict.get('total_tokens')
        ))
        benchmark_id = cursor.lastrowid
        conn.commit()

        if benchmark_id and 'prompts_data' in result_dict:
            prompts_to_save = []
            for p_data in result_dict['prompts_data']:
                prompts_to_save.append((
                    benchmark_id,
                    p_data.get('prompt_text'),
                    p_data.get('expected_answer'),
                    p_data.get('actual_answer'),
                    p_data.get('score'),
                    p_data.get('prompt_length_chars'),
                    p_data.get('latency_ms'),
                    p_data.get('prompt_tokens'),
                    p_data.get('completion_tokens')
                ))
            
            if prompts_to_save:
                cursor.executemany(f'''
                    INSERT INTO {BENCHMARK_PROMPTS_TABLE_NAME}
                    (benchmark_id, prompt_text, expected_answer, actual_answer, score, prompt_length_chars, latency_ms, prompt_tokens, completion_tokens)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', prompts_to_save)
                conn.commit()
        
        print(f"Saved benchmark run ID {benchmark_id} for PDF {pdf_path.name}")
        return benchmark_id
    except sqlite3.Error as e:
        print(f"SQLite error when saving benchmark run for {pdf_path.name}: {e}")
        conn.rollback() # Rollback in case of error during prompts insertion
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
            SELECT id, timestamp, pdf_path, model_name, mean_score, total_items, elapsed_seconds,
                   total_prompt_tokens, total_completion_tokens, total_tokens
            FROM {BENCHMARKS_TABLE_NAME}
            ORDER BY timestamp DESC
        ''')
        rows = cursor.fetchall()
        for row in rows:
            runs.append(dict(row))
        print(f"Loaded {len(runs)} benchmark runs from DB.")
    except sqlite3.Error as e:
        print(f"SQLite error when loading benchmark runs: {e}")
    finally:
        conn.close()
    return runs

def load_benchmark_details(benchmark_id: int, db_path: Path = Path.cwd()) -> dict | None:
    """Loads full details for a specific benchmark run, including all prompts."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    details = None
    try:
        cursor.execute(f'''
            SELECT id, timestamp, pdf_path, model_name, mean_score, total_items, elapsed_seconds,
                   total_prompt_tokens, total_completion_tokens, total_tokens
            FROM {BENCHMARKS_TABLE_NAME}
            WHERE id = ?
        ''', (benchmark_id,))
        run_info = cursor.fetchone()

        if run_info:
            details = dict(run_info)
            cursor.execute(f'''
                SELECT prompt_text, expected_answer, actual_answer, score,
                       prompt_length_chars, latency_ms, prompt_tokens, completion_tokens
                FROM {BENCHMARK_PROMPTS_TABLE_NAME}
                WHERE benchmark_id = ?
                ORDER BY id ASC
            ''', (benchmark_id,))
            prompts = cursor.fetchall()
            details['prompts_data'] = [dict(p) for p in prompts]
            print(f"Loaded details for benchmark ID {benchmark_id}")
        else:
            print(f"No benchmark found with ID {benchmark_id}")

    except sqlite3.Error as e:
        print(f"SQLite error when loading benchmark details for ID {benchmark_id}: {e}")
    finally:
        conn.close()
    return details

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
        'total_prompt_tokens': 100,
        'total_completion_tokens': 200,
        'total_tokens': 300,
        'prompts_data': [
            {'prompt_text': "P1", 'expected_answer': "E1", 'actual_answer': "A1", 'score': 1.0, 'prompt_length_chars': 10, 'latency_ms': 50, 'prompt_tokens': 20, 'completion_tokens': 40},
            {'prompt_text': "P2", 'expected_answer': "E2", 'actual_answer': "A2", 'score': 0.7, 'prompt_length_chars': 8, 'latency_ms': 30, 'prompt_tokens': 15, 'completion_tokens': 25}
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