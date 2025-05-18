import sqlite3
import hashlib
from pathlib import Path
import datetime
import json
import logging
from typing import Optional

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
            total_standard_input_tokens INTEGER DEFAULT 0,
            total_cached_input_tokens INTEGER DEFAULT 0,
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
            standard_input_tokens INTEGER,      
            cached_input_tokens INTEGER,      
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
    logging.info(f"Database initialized at {db_file}")

def _calculate_pdf_hash(pdf_path: Path) -> str:
    """Calculates the SHA256 hash of a PDF file's content."""
    hasher = hashlib.sha256()
    try:
        with open(pdf_path, "rb") as f:
            while chunk := f.read(8192):  # Read in 8KB chunks
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        logging.error(f"File not found at {pdf_path} during hash calculation.")
        return "" # Or raise error
    except Exception as e:
        logging.error(f"Error calculating hash for {pdf_path}: {e}")
        return "" # Or raise error
    # Note: No database connection is used here, so nothing to close in finally block.

def add_file_mapping(pdf_path: Path, openai_file_id: str, db_path: Path = Path.cwd()):
    """Adds or updates a mapping between a PDF's hash and its OpenAI file ID."""
    pdf_hash = _calculate_pdf_hash(pdf_path)
    if not pdf_hash:
        logging.warning(f"Skipping DB add for {pdf_path.name} due to hashing error.")
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
        logging.info(f"Mapped PDF hash {pdf_hash[:8]}... for {pdf_path.name} to OpenAI ID {openai_file_id}")
    except sqlite3.Error as e:
        logging.error(f"SQLite error when adding/updating mapping for {pdf_path.name}: {e}")
    finally:
        conn.close()

def get_openai_file_id(pdf_path: Path, db_path: Path = Path.cwd()) -> str | None:
    """Retrieves an OpenAI file ID for a given PDF path by its content hash.
    Returns the OpenAI file ID if found, otherwise None.
    """
    pdf_hash = _calculate_pdf_hash(pdf_path)
    if not pdf_hash:
        logging.warning(f"Skipping DB lookup for {pdf_path.name} due to hashing error.")
        return None

    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT openai_file_id FROM {TABLE_NAME} WHERE pdf_hash = ?", (pdf_hash,))
        result = cursor.fetchone()
        if result:
            logging.debug(f"Found existing OpenAI ID {result[0]} for PDF {pdf_path.name} (hash {pdf_hash[:8]}...)")
            return result[0]
        else:
            logging.debug(f"No existing OpenAI ID found for PDF {pdf_path.name} (hash {pdf_hash[:8]}...)")
            return None
    except sqlite3.Error as e:
        logging.error(f"SQLite error when retrieving mapping for {pdf_path.name}: {e}")
        return None
    finally:
        conn.close()

def save_benchmark(label: str, description: str, file_paths: list[str], model_name: str = None, db_path: Path = Path.cwd()) -> int | None:
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
        # Store model name if provided
        if model_name:
            # Create a placeholder benchmark run to store the model association
            cursor.execute(f'''
                INSERT INTO {BENCHMARK_RUNS_TABLE_NAME} 
                (benchmark_id, model_name, report, latency, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (benchmark_id, model_name, "Model association", 0.0, timestamp))
        conn.commit()
        return benchmark_id
    except sqlite3.Error as e:
        logging.error(f"SQLite error when saving benchmark: {e}")
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
        logging.error(f"SQLite error when adding file to benchmark: {e}")
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
        logging.error(f"SQLite error when loading files for benchmark {benchmark_id}: {e}")
        return []
    finally:
        conn.close()

def save_benchmark_run(benchmark_id: int, model_name: str, report: str, latency: float, total_standard_input_tokens: int, total_cached_input_tokens: int, total_output_tokens: int, total_tokens: int, db_path: Path = Path.cwd()) -> int | None:
    """Saves a benchmark run and returns its ID."""
    # Validate inputs - ensure integer values are actually integers, not None
    if benchmark_id is None or not isinstance(benchmark_id, int):
        logging.error(f"Invalid benchmark_id provided: {benchmark_id}")
        return None
        
    # Ensure token counts are valid integers, not None
    std_tokens = int(total_standard_input_tokens) if total_standard_input_tokens is not None else 0
    cached_tokens = int(total_cached_input_tokens) if total_cached_input_tokens is not None else 0
    output_tokens = int(total_output_tokens) if total_output_tokens is not None else 0
    total_token_count = int(total_tokens) if total_tokens is not None else 0
    
    # Convert latency to float if it's not None, otherwise use 0.0
    latency_val = float(latency) if latency is not None else 0.0
    
    # Serialize report if it's a dictionary, ensure it's a string otherwise
    report_json = json.dumps(report) if isinstance(report, (dict, list)) else str(report)
    
    # Get current timestamp
    created_at_ts = datetime.datetime.now().isoformat()
    
    db_file = db_path / DB_NAME
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        # Begin transaction explicitly
        conn.execute("BEGIN TRANSACTION")
        cursor = conn.cursor()
        
        # Use parameterized query for security
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_RUNS_TABLE_NAME} 
            (benchmark_id, model_name, report, latency, created_at, 
             total_standard_input_tokens, total_cached_input_tokens, 
             total_output_tokens, total_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (benchmark_id, model_name, report_json, latency_val, created_at_ts, 
              std_tokens, cached_tokens, output_tokens, total_token_count))
        
        # Get the last inserted ID (the run_id)
        run_id = cursor.lastrowid
        
        # Commit transaction
        conn.commit()
        logging.info(f"Successfully saved benchmark run with ID {run_id}")
        return run_id
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when saving benchmark run: {e}")
        # Rollback if there was an error
        if conn:
            conn.rollback()
        return None
        
    finally:
        # Always close the connection
        if conn:
            conn.close()

def save_benchmark_prompt(benchmark_run_id: int, prompt: str, answer: str, response: str, score: str, latency: float, standard_input_tokens: int, cached_input_tokens: int, output_tokens: int, scoring_config_id: int | None = None, db_path: Path = Path.cwd()) -> int | None:
    """Saves a prompt result for a benchmark run."""
    # Validate inputs
    if benchmark_run_id is None or not isinstance(benchmark_run_id, int):
        logging.error(f"Invalid benchmark_run_id provided: {benchmark_run_id}")
        return None
        
    # Ensure token counts are valid integers, not None
    std_tokens = int(standard_input_tokens) if standard_input_tokens is not None else 0
    cached_tokens = int(cached_input_tokens) if cached_input_tokens is not None else 0
    output_tokens = int(output_tokens) if output_tokens is not None else 0
    
    # Convert latency to float if it's not None, otherwise use 0.0
    latency_val = float(latency) if latency is not None else 0.0
    
    # Ensure text fields are strings, not None
    prompt_text = str(prompt) if prompt is not None else ""
    answer_text = str(answer) if answer is not None else ""
    response_text = str(response) if response is not None else ""
    score_text = str(score) if score is not None else ""
    
    db_file = db_path / DB_NAME
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        # Begin transaction explicitly
        conn.execute("BEGIN TRANSACTION")
        cursor = conn.cursor()
        
        # Use parameterized query for security
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_PROMPTS_TABLE_NAME} 
            (benchmark_run_id, prompt, answer, response, score, latency, 
             standard_input_tokens, cached_input_tokens, output_tokens, scoring_config_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (benchmark_run_id, prompt_text, answer_text, response_text, score_text, 
              latency_val, std_tokens, cached_tokens, output_tokens, scoring_config_id))
        
        # Get the last inserted ID
        prompt_id = cursor.lastrowid
        
        # Commit transaction
        conn.commit()
        logging.info(f"Successfully saved benchmark prompt {prompt_id} for run {benchmark_run_id}")
        return prompt_id
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when saving benchmark prompt: {e}")
        # Rollback if there was an error
        if conn:
            conn.rollback()
        return None
        
    finally:
        # Always close the connection
        if conn:
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
        logging.error(f"SQLite error when saving scoring config: {e}")
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
        logging.error(f"SQLite error when saving benchmark report: {e}")
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
            SELECT br.id, br.benchmark_id, b.label as benchmark_label, br.model_name, br.report, br.latency, br.created_at,
                br.total_standard_input_tokens, br.total_cached_input_tokens, br.total_output_tokens, br.total_tokens,
                GROUP_CONCAT(DISTINCT bf.file_path) as file_paths
            FROM {BENCHMARK_RUNS_TABLE_NAME} br
        JOIN {BENCHMARKS_TABLE_NAME} b ON br.benchmark_id = b.id
        LEFT JOIN benchmark_files bf ON br.benchmark_id = bf.benchmark_id
        GROUP BY br.id
        ORDER BY br.created_at DESC
        ''')
        rows = cursor.fetchall()
        for row_data in rows:
            runs.append({    
                "id": row_data[0], 
                "benchmark_id": row_data[1], 
                "benchmark_label": row_data[2], 
                "model_name": row_data[3],    
                "report": json.loads(row_data[4]) if row_data[4] else {}, 
                "latency": row_data[5], 
                "created_at": row_data[6],    
                "total_standard_input_tokens": row_data[7], 
                "total_cached_input_tokens": row_data[8], 
                "total_output_tokens": row_data[9], 
                "total_tokens": row_data[10],    
                "file_paths": row_data[11].split(',') if row_data[11] else []}
            )
            # run_dict = dict(row_data)
            # # Attempt to parse mean_score and total_items from report string for compatibility
            # # This is brittle; ideally, these would be separate columns in BENCHMARK_RUNS_TABLE_NAME
            # run_dict['mean_score'] = None
            # run_dict['total_items'] = None
            # if run_dict.get('report'):
            #     try:
            #         report_str = run_dict['report']
            #         if "Mean score:" in report_str and "Items:" in report_str:
            #             parts = report_str.split(',')
            #             for part in parts:
            #                 if "Mean score:" in part:
            #                     run_dict['mean_score'] = float(part.split(':')[1].strip())
            #                 if "Items:" in part:
            #                     run_dict['total_items'] = int(part.split(':')[1].split(',')[0].strip())
            #     except Exception:
            #         pass # Ignore parsing errors, fields will remain None
            # runs.append(run_dict)
        logging.info(f"Loaded {len(runs)} benchmark runs from DB.")
    except sqlite3.Error as e:
        logging.error(f"SQLite error when loading benchmark runs: {e}")
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
            logging.warning(f"No benchmark found with ID {benchmark_id}")
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


        # 3. Fetch all benchmark runs for this benchmark, grouped by model
        cursor.execute(f'''
            SELECT r.id AS run_id, r.model_name, r.report, r.latency, r.created_at AS run_timestamp, 
                   r.total_standard_input_tokens, r.total_cached_input_tokens, r.total_output_tokens, r.total_tokens
            FROM {BENCHMARK_RUNS_TABLE_NAME} r
            INNER JOIN (
                SELECT model_name, MAX(created_at) as max_date
                FROM {BENCHMARK_RUNS_TABLE_NAME} 
                WHERE benchmark_id = ?
                GROUP BY model_name
            ) latest ON r.model_name = latest.model_name AND r.created_at = latest.max_date
            WHERE r.benchmark_id = ?
            ORDER BY r.created_at DESC
        ''', (benchmark_id, benchmark_id))
        run_infos = cursor.fetchall()

        if run_infos:
            logging.info(f"LOAD_BENCHMARK_DETAILS: Fetched {len(run_infos)} run_infos for benchmark_id {benchmark_id}")
        else:
            logging.info(f"LOAD_BENCHMARK_DETAILS: No run_infos found for benchmark_id {benchmark_id}")

        # Process results for multiple models
        if run_infos:
            # Store all model names
            model_names = []
            model_results = []
            
            # Track the most recent run for generic details
            most_recent_run = dict(run_infos[0]) if run_infos else None
            
            # Process each run by model
            for run_info in run_infos:
                run_info_dict = dict(run_info)
                model_name = run_info_dict['model_name']
                model_names.append(model_name)
                
                # Create a result entry for this model
                model_result = {
                    'model': model_name,
                    'status': 'completed',
                    'run_id': run_info_dict['run_id'],
                    'latency': run_info_dict['latency'],
                    'report': run_info_dict['report'],
                    'duration': run_info_dict['latency'],
                    'total_standard_input_tokens': run_info_dict['total_standard_input_tokens'],
                    'total_cached_input_tokens': run_info_dict['total_cached_input_tokens'],
                    'total_output_tokens': run_info_dict['total_output_tokens'],
                    'total_tokens': run_info_dict['total_tokens']
                }
                
                # Extract mean score from report
                if isinstance(run_info_dict['report'], str):
                    try:
                        if "Mean score:" in run_info_dict['report']:
                            parts = run_info_dict['report'].split(',')
                            for part in parts:
                                if "Mean score:" in part:
                                    model_result['score'] = float(part.split(':')[1].strip())
                    except Exception as e:
                        logging.warning(f"Could not parse mean_score from report for {model_name}: {e}")
                
                model_results.append(model_result)
            
            # Use the most recent run for UI compatibility, but include all models
            if most_recent_run:
                details['models'] = model_names
                details['files'] = details.get('file_paths', [])
                details['results'] = model_results
            
            # 4. Fetch prompts for each run
            all_prompts_data = []
            prompts_by_model = {}
            
            for run_info in run_infos:
                run_info_dict = dict(run_info)
                model_name = run_info_dict['model_name']
                run_id = run_info_dict['run_id']
                
                cursor.execute(f'''
                    SELECT prompt, answer AS expected_answer, response AS model_answer, score, 
                           latency AS prompt_latency, standard_input_tokens, cached_input_tokens, output_tokens
                    FROM {BENCHMARK_PROMPTS_TABLE_NAME}
                    WHERE benchmark_run_id = ?
                    ORDER BY id ASC
                ''', (run_id,))
                prompts = cursor.fetchall()
                
                # Store the prompts with a model identifier
                processed_prompts = []
                for p in prompts:
                    prompt_dict = dict(p)
                    # Add model name to each prompt for UI reference
                    prompt_dict['model_name'] = model_name
                    prompt_dict['prompt_text'] = prompt_dict['prompt']
                    del prompt_dict['prompt']  # Remove original key after copying
                    processed_prompts.append(prompt_dict)
                
                # Store by model
                prompts_by_model[model_name] = processed_prompts
                
                # Add to the full list
                all_prompts_data.extend(processed_prompts)
            
            # Include both the combined prompt data and model-specific versions
            details['prompts_data'] = all_prompts_data
            details['prompts_by_model'] = prompts_by_model
            
            logging.debug(f"Loaded details for benchmark ID {benchmark_id} with {len(model_names)} models")
        else:
            # No runs available
            details['models'] = []
            details['results'] = []
            details['prompts_data'] = [] 
            details['prompts_by_model'] = {}
            logging.info(f"Benchmark ID {benchmark_id} has no runs.")

    except sqlite3.Error as e:
        logging.error(f"SQLite error when loading benchmark details for ID {benchmark_id}: {e}")
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
            
            # Get model names
            cursor.execute(f'''
                SELECT DISTINCT model_name FROM {BENCHMARK_RUNS_TABLE_NAME}
                WHERE benchmark_id = ?
            ''', (row['id'],))
            model_rows = cursor.fetchall()
            model_names = [m['model_name'] for m in model_rows]
            benchmark['model_names'] = model_names
            
            # Get file paths
            cursor.execute('''
                SELECT file_path FROM benchmark_files WHERE benchmark_id = ?
            ''', (row['id'],))
            file_rows = cursor.fetchall()
            benchmark['file_paths'] = [f['file_path'] for f in file_rows]
            
            # Get model results (score, latency, cost)
            model_results = {}
            for model_name in model_names:
                # Get run data for this model
                cursor.execute(f'''
                    SELECT id, latency, total_standard_input_tokens, total_cached_input_tokens, total_output_tokens, total_tokens, report
                    FROM {BENCHMARK_RUNS_TABLE_NAME}
                    WHERE benchmark_id = ? AND model_name = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (row['id'], model_name))
                run_row = cursor.fetchone()
                
                if run_row:
                    run_data = dict(run_row)
                    run_id = run_data['id']
                    
                    # Get average score from prompts
                    cursor.execute(f'''
                        SELECT AVG(CAST(score AS REAL)) as avg_score
                        FROM {BENCHMARK_PROMPTS_TABLE_NAME}
                        WHERE benchmark_run_id = ? AND score IS NOT NULL AND score != ''
                    ''', (run_id,))
                    score_row = cursor.fetchone()
                    avg_score = score_row['avg_score'] if score_row and score_row['avg_score'] is not None else 0
                    
                    # Calculate estimated cost based on tokens and model
                    # This uses the detailed token breakdown for more accurate pricing
                    standard_input_tokens = run_data['total_standard_input_tokens'] or 0
                    cached_input_tokens = run_data['total_cached_input_tokens'] or 0
                    output_tokens = run_data['total_output_tokens'] or 0
                    
                    # Cost calculation based on accurate pricing
                    cost = 0
                    # Convert tokens to millions for easier calculation with pricing
                    standard_input_tokens_m = standard_input_tokens / 1000000
                    cached_input_tokens_m = cached_input_tokens / 1000000
                    output_tokens_m = output_tokens / 1000000
                    
                    if model_name == "gpt-4o":
                        cost = (standard_input_tokens_m * 2.50) + (cached_input_tokens_m * 0.63) + (output_tokens_m * 10.00)  # Estimated cached input 1/4 price
                    elif model_name == "gpt-4o-mini":
                        cost = (standard_input_tokens_m * 0.15) + (cached_input_tokens_m * 0.04) + (output_tokens_m * 0.60)  # Estimated cached input 1/4 price
                    elif model_name == "gpt-4.1":
                        cost = (standard_input_tokens_m * 2.00) + (cached_input_tokens_m * 0.50) + (output_tokens_m * 8.00)  # Exact pricing from user
                    elif model_name == "gpt-4.1-mini":
                        cost = (standard_input_tokens_m * 0.40) + (cached_input_tokens_m * 0.10) + (output_tokens_m * 1.60)  # Exact pricing from user
                    elif model_name == "gpt-4.1-nano":
                        cost = (standard_input_tokens_m * 0.100) + (cached_input_tokens_m * 0.025) + (output_tokens_m * 0.400)  # Exact pricing from user
                    elif model_name == "o3-mini":
                        cost = (standard_input_tokens_m * 1.10) + (cached_input_tokens_m * 0.28) + (output_tokens_m * 4.40)  # Estimated cached input 1/4 price
                    elif model_name == "o4":
                        cost = (standard_input_tokens_m * 2.00) + (cached_input_tokens_m * 0.50) + (output_tokens_m * 8.00)  # Estimate based on similar models
                    elif model_name == "o4-mini":
                        cost = (standard_input_tokens_m * 1.10) + (cached_input_tokens_m * 0.28) + (output_tokens_m * 4.40)  # Estimated cached input 1/4 price
                    
                    model_results[model_name] = {
                        'score': avg_score * 100 if avg_score is not None else 'N/A',  # Convert to percentage
                        'latency': run_data['latency'] if run_data['latency'] is not None else 'N/A',
                        'cost': cost if cost is not None else 0.0,
                        'standard_input_tokens': standard_input_tokens,
                        'cached_input_tokens': cached_input_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': run_data['total_tokens'] or 0
                    }
                else:
                    model_results[model_name] = {
                        'score': 'N/A',
                        'latency': 'N/A',
                        'cost': 'N/A',
                        'standard_input_tokens': 0,
                        'cached_input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0
                    }
            
            benchmark['model_results'] = model_results
            benchmarks.append(benchmark)
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            # This can happen if the database is new and init_db hasn't run or completed yet.
            # Silently return an empty list, init_db will create tables.
            pass
        else:
            # For other operational errors, print them as they are unexpected.
            logging.error(f"SQLite operational error when loading benchmarks with models: {e}")
    except sqlite3.Error as e:
        # For other, more general SQLite errors.
        logging.error(f"SQLite error when loading benchmarks with models: {e}")
    finally:
        if conn:
            conn.close()
    return benchmarks

def find_benchmark_by_files(file_paths: list, db_path: Path = Path.cwd()) -> int | None:
    """Returns the benchmark ID for a given set of file paths, or None if not found. (Matches on first file for now)"""
    if not file_paths or len(file_paths) == 0:
        return None
        
    # Convert Path objects to strings if necessary
    first_path = str(file_paths[0]) if hasattr(file_paths[0], '__fspath__') else file_paths[0]
    
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT benchmark_id FROM benchmark_files WHERE file_path = ?
        ''', (first_path,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    except sqlite3.Error as e:
        logging.error(f"SQLite error when searching for benchmark by files: {e}")
        return None
    finally:
        conn.close()

def get_active_benchmarks():
    """Return a dictionary of active benchmarks based on recent runs.
    This is used for UI display to show which benchmarks are currently running.
    
    Returns:
        dict: Dictionary with benchmark IDs as keys and benchmark data as values
    """
    # In this implementation, we'll return an empty dictionary
    # The actual active benchmarks are tracked in AppLogic.jobs with 'unfinished' status
    # This function is called directly from the UI bridge to minimize visual disruption
    # during polling updates
    return {}

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
        logging.error(f"SQLite error when deleting benchmark {benchmark_id}: {e}")
        return False
    finally:
        conn.close()

def update_benchmark_details(benchmark_id: int, label: Optional[str] = None, description: Optional[str] = None, db_path: Path = Path.cwd()) -> bool:
    """Updates the label and/or description of a benchmark."""
    logging.info(f"Updating benchmark {benchmark_id} with label='{label}', description='{description}'")

    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    fields_to_update = []
    params = []

    # Handle both None and empty string cases
    if label is not None:
        fields_to_update.append("label = ?")
        params.append(label)
    if description is not None:
        fields_to_update.append("description = ?")
        params.append(description)

    # If no fields to update, return early
    if not fields_to_update:
        logging.info(f"No valid fields to update for benchmark {benchmark_id}")
        return False

    params.append(benchmark_id)
    
    try:
        query = f"UPDATE {BENCHMARKS_TABLE_NAME} SET {', '.join(fields_to_update)} WHERE id = ?"
        logging.info(f"Executing query: {query} with params {params}")
        cursor.execute(query, tuple(params))
        conn.commit()
        rows_affected = cursor.rowcount
        logging.info(f"Updated details for benchmark {benchmark_id}. Rows affected: {rows_affected}")
        return rows_affected > 0
    except sqlite3.Error as e:
        logging.error(f"SQLite error when updating benchmark {benchmark_id}: {e}")
        return False
    finally:
        conn.close()

def update_benchmark_model(benchmark_id: int, model_name: str, db_path: Path = Path.cwd()):
    """
    Updates a benchmark with a model name that is being used in an active run.
    This ensures the model is visible in the UI even before completion.
    
    Args:
        benchmark_id: ID of the benchmark
        model_name: Name of the model to add
        db_path: Directory containing the database
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Type validation
    if not isinstance(benchmark_id, int) or not isinstance(model_name, str):
        logging.error(f"Invalid parameter types: benchmark_id={type(benchmark_id)}, model_name={type(model_name)}")
        return False
        
    db_file = db_path / DB_NAME
    conn = None
    
    try:
        conn = sqlite3.connect(db_file)
        conn.execute("BEGIN TRANSACTION")
        cursor = conn.cursor()
        
        # First check if this benchmark exists
        cursor.execute(f"SELECT id FROM {BENCHMARKS_TABLE_NAME} WHERE id = ?", (benchmark_id,))
        if not cursor.fetchone():
            logging.warning(f"Benchmark with ID {benchmark_id} not found")
            return False
        
        # Create a new run entry with all required fields according to schema
        created_at_ts = datetime.datetime.now().isoformat()
        logging.info(f"Creating benchmark run for benchmark_id={benchmark_id}, model={model_name}")
        
        # Insert into benchmark_runs with all required fields
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_RUNS_TABLE_NAME} 
            (benchmark_id, model_name, report, latency, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (benchmark_id, model_name, "Initializing", 0.0, created_at_ts))
        
        # Get the benchmark_run_id for the newly created run
        benchmark_run_id = cursor.lastrowid
        logging.info(f"Created benchmark run with ID {benchmark_run_id}")
        
        # Insert a placeholder entry into benchmark_prompts with all required fields
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_PROMPTS_TABLE_NAME} 
            (benchmark_run_id, prompt, answer, response, score, latency)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (benchmark_run_id, "model_registration", "", "", "N/A", 0.0))
        
        # Commit transaction
        conn.commit()
        logging.info(f"Successfully registered model {model_name} for benchmark {benchmark_id}")
        return True
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Database error in update_benchmark_model: {e}")
        return False
    finally:
        if conn:
            conn.close()

# Example usage (for testing only)
if __name__ == '__main__':
    # This is a placeholder for test code
    pass