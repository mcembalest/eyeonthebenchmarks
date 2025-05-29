import sqlite3
import hashlib
from pathlib import Path
import datetime
import json
import logging
import csv
from typing import Optional, List, Dict, Any

DB_NAME = "eotb_file_store.sqlite"

# Table names - clean multi-provider schema
FILES_TABLE = "files"
PROVIDER_FILE_UPLOADS_TABLE = "provider_file_uploads"
PROMPT_SETS_TABLE = "prompt_sets"
PROMPT_SET_ITEMS_TABLE = "prompt_set_items"
BENCHMARKS_TABLE = "benchmarks"
BENCHMARK_FILES_TABLE = "benchmark_files"
BENCHMARK_RUNS_TABLE = "benchmark_runs"
BENCHMARK_PROMPTS_TABLE = "benchmark_prompts"
BENCHMARK_REPORTS_TABLE = "benchmark_reports"

def init_db(db_path: Path = Path.cwd()):
    """Initializes the SQLite database with a clean multi-provider, multi-file schema, focused on response collection."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Files Table - Central registry of all files we've seen
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {FILES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT UNIQUE NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size_bytes INTEGER,
            mime_type TEXT,
            created_at TEXT NOT NULL,
            csv_data TEXT  -- JSON data for CSV files
        )
    ''')
    
    # Provider File Uploads - Track which files have been uploaded to which providers
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {PROVIDER_FILE_UPLOADS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            provider_file_id TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (file_id) REFERENCES {FILES_TABLE}(id),
            UNIQUE(file_id, provider)
        )
    ''')

    # Prompt Sets Table - Reusable collections of prompts
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {PROMPT_SETS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Prompt Set Items Table - Individual prompts within a set
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {PROMPT_SET_ITEMS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_set_id INTEGER NOT NULL,
            prompt_text TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (prompt_set_id) REFERENCES {PROMPT_SETS_TABLE}(id)
        )
    ''')

    # Benchmarks Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARKS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            label TEXT,
            description TEXT,
            status TEXT DEFAULT 'in-progress',
            intended_models TEXT, -- JSON array of model names that should be run
            prompt_set_id INTEGER,
            use_web_search BOOLEAN DEFAULT 0,
            FOREIGN KEY (prompt_set_id) REFERENCES {PROMPT_SETS_TABLE}(id)
        )
    ''')
    
    # Add intended_models column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARKS_TABLE} ADD COLUMN intended_models TEXT')
        logging.info("Added intended_models column to benchmarks table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("intended_models column already exists")
        else:
            logging.warning(f"Could not add intended_models column: {e}")
    
    # Add use_web_search column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARKS_TABLE} ADD COLUMN use_web_search BOOLEAN DEFAULT 0')
        logging.info("Added use_web_search column to benchmarks table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("use_web_search column already exists")
        else:
            logging.warning(f"Could not add use_web_search column: {e}")
    
    # Benchmark Files Table - Many-to-many relationship between benchmarks and files
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARK_FILES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            FOREIGN KEY (benchmark_id) REFERENCES {BENCHMARKS_TABLE}(id),
            FOREIGN KEY (file_id) REFERENCES {FILES_TABLE}(id),
            UNIQUE(benchmark_id, file_id)
        )
    ''')

    # Benchmark Runs Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARK_RUNS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            provider TEXT NOT NULL,
            report TEXT, -- General text field for any summary, if needed later
            latency REAL,
            created_at TEXT NOT NULL,
            total_standard_input_tokens INTEGER DEFAULT 0,
            total_cached_input_tokens INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            total_input_cost REAL DEFAULT 0,
            total_cached_cost REAL DEFAULT 0,
            total_output_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            FOREIGN KEY (benchmark_id) REFERENCES {BENCHMARKS_TABLE}(id)
        )
    ''')

    # Benchmark Prompts Table - Simplified: no score, no expected answer, no scoring_config_id
    cursor.execute(f'''    
        CREATE TABLE IF NOT EXISTS {BENCHMARK_PROMPTS_TABLE} (        
            id INTEGER PRIMARY KEY AUTOINCREMENT,        
            benchmark_run_id INTEGER NOT NULL,        
            prompt TEXT,        
            response TEXT,        
            latency REAL,        
            standard_input_tokens INTEGER,      
            cached_input_tokens INTEGER,      
            output_tokens INTEGER,
            thinking_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,        
            input_cost REAL DEFAULT 0,
            cached_cost REAL DEFAULT 0,
            output_cost REAL DEFAULT 0,
            thinking_cost REAL DEFAULT 0,
            reasoning_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            web_search_used BOOLEAN DEFAULT 0,
            web_search_sources TEXT,
            truncation_info TEXT,
            status TEXT DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT,
            FOREIGN KEY (benchmark_run_id) REFERENCES {BENCHMARK_RUNS_TABLE}(id)
        )       
    ''')

    # Add thinking_tokens column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN thinking_tokens INTEGER DEFAULT 0')
        logging.info("Added thinking_tokens column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("thinking_tokens column already exists")
        else:
            logging.warning(f"Could not add thinking_tokens column: {e}")

    # Add reasoning_tokens column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN reasoning_tokens INTEGER DEFAULT 0')
        logging.info("Added reasoning_tokens column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("reasoning_tokens column already exists")
        else:
            logging.warning(f"Could not add reasoning_tokens column: {e}")

    # Add thinking_cost column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN thinking_cost REAL DEFAULT 0')
        logging.info("Added thinking_cost column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("thinking_cost column already exists")
        else:
            logging.warning(f"Could not add thinking_cost column: {e}")

    # Add reasoning_cost column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN reasoning_cost REAL DEFAULT 0')
        logging.info("Added reasoning_cost column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("reasoning_cost column already exists")
        else:
            logging.warning(f"Could not add reasoning_cost column: {e}")

    # Add web_search_used column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN web_search_used BOOLEAN DEFAULT 0')
        logging.info("Added web_search_used column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("web_search_used column already exists")
        else:
            logging.warning(f"Could not add web_search_used column: {e}")

    # Add web_search_sources column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN web_search_sources TEXT')
        logging.info("Added web_search_sources column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("web_search_sources column already exists")
        else:
            logging.warning(f"Could not add web_search_sources column: {e}")

    # Add truncation_info column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN truncation_info TEXT')
        logging.info("Added truncation_info column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("truncation_info column already exists")
        else:
            logging.warning(f"Could not add truncation_info column: {e}")

    # Add status column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN status TEXT DEFAULT \'pending\'')
        logging.info("Added status column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("status column already exists")
        else:
            logging.warning(f"Could not add status column: {e}")

    # Add started_at column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN started_at TEXT')
        logging.info("Added started_at column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("started_at column already exists")
        else:
            logging.warning(f"Could not add started_at column: {e}")

    # Add completed_at column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN completed_at TEXT')
        logging.info("Added completed_at column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("completed_at column already exists")
        else:
            logging.warning(f"Could not add completed_at column: {e}")

    # Add error_message column if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {BENCHMARK_PROMPTS_TABLE} ADD COLUMN error_message TEXT')
        logging.info("Added error_message column to benchmark_prompts table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("error_message column already exists")
        else:
            logging.warning(f"Could not add error_message column: {e}")

    # Update existing records to have proper status based on their current data
    try:
        # Mark records with responses as completed
        cursor.execute(f'''
            UPDATE {BENCHMARK_PROMPTS_TABLE} 
            SET status = 'completed', 
                completed_at = COALESCE(completed_at, datetime('now'))
            WHERE response IS NOT NULL 
            AND response != '' 
            AND status IS NULL
        ''')
        
        # Mark records that start with ERROR as failed
        cursor.execute(f'''
            UPDATE {BENCHMARK_PROMPTS_TABLE} 
            SET status = 'failed',
                error_message = COALESCE(error_message, response),
                completed_at = COALESCE(completed_at, datetime('now'))
            WHERE response LIKE 'ERROR%' 
            AND status != 'failed'
        ''')
        
        logging.info("Updated existing records with proper status values")
    except sqlite3.OperationalError as e:
        logging.warning(f"Could not update existing record statuses: {e}")

    # Add csv_data column to files table if it doesn't exist (for existing databases)
    try:
        cursor.execute(f'ALTER TABLE {FILES_TABLE} ADD COLUMN csv_data TEXT')
        logging.info("Added csv_data column to files table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logging.debug("csv_data column already exists")
        else:
            logging.warning(f"Could not add csv_data column: {e}")

    # Benchmark Reports Table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {BENCHMARK_REPORTS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL,
            compared_models TEXT, -- JSON list of model names
            report TEXT, -- Text field for qualitative comparison or notes
            created_at TEXT,
            FOREIGN KEY (benchmark_id) REFERENCES {BENCHMARKS_TABLE}(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info(f"Database initialized at {db_file} (Simplified Schema - No Scoring)")

def _calculate_file_hash(file_path: Path) -> str:
    """Calculates the SHA256 hash of a file's content."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logging.error(f"Error calculating hash for {file_path}: {e}")
        raise

def _get_mime_type(file_path: Path) -> str:
    """Get MIME type based on file extension."""
    extension = file_path.suffix.lower()
    mime_types = {
        '.pdf': 'application/pdf',
        '.csv': 'text/csv',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel'
    }
    return mime_types.get(extension, 'application/octet-stream')

def parse_csv_to_json_records(file_path: Path, max_rows: int = None) -> Dict[str, Any]:
    """
    Parse CSV file into JSON records format (like pandas to_json(orient='records')).
    
    Args:
        file_path: Path to the CSV file
        max_rows: Maximum number of rows to include (None for all)
        
    Returns:
        Dict with 'records', 'total_rows', 'included_rows', 'columns'
    """
    try:
        records = []
        total_rows = 0
        
        with open(file_path, 'r', encoding='utf-8', newline='') as csvfile:
            # Detect delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            columns = reader.fieldnames or []
            
            for row_num, row in enumerate(reader):
                total_rows += 1
                
                if max_rows is None or row_num < max_rows:
                    # Clean up the row data
                    clean_row = {}
                    for key, value in row.items():
                        # Handle None keys (can happen with malformed CSV)
                        clean_key = key.strip() if key else f"column_{len(clean_row)}"
                        # Convert empty strings to None for cleaner JSON
                        clean_value = value.strip() if value and value.strip() else None
                        clean_row[clean_key] = clean_value
                    records.append(clean_row)
                
                # Stop reading if we've hit our limit
                if max_rows and row_num >= max_rows:
                    break
        
        return {
            'records': records,
            'total_rows': total_rows,
            'included_rows': len(records),
            'columns': columns
        }
        
    except Exception as e:
        logging.error(f"Error parsing CSV {file_path}: {e}")
        raise

def parse_csv_to_markdown_format(file_path: Path, max_rows: int = None) -> Dict[str, Any]:
    """
    Parse CSV file into markdown format for LLM prompts.
    
    Args:
        file_path: Path to the CSV file
        max_rows: Maximum number of rows to include (None for all)
        
    Returns:
        Dict with 'markdown_data', 'total_rows', 'included_rows', 'columns'
    """
    try:
        records = []
        total_rows = 0
        
        with open(file_path, 'r', encoding='utf-8', newline='') as csvfile:
            # Detect delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            columns = reader.fieldnames or []
            
            for row_num, row in enumerate(reader):
                total_rows += 1
                
                if max_rows is None or row_num < max_rows:
                    # Clean up the row data
                    clean_row = {}
                    for key, value in row.items():
                        # Handle None keys (can happen with malformed CSV)
                        clean_key = key.strip() if key else f"column_{len(clean_row)}"
                        # Keep empty strings as empty strings for markdown (not None)
                        clean_value = value.strip() if value else ""
                        clean_row[clean_key] = clean_value
                    records.append(clean_row)
                
                # Stop reading if we've hit our limit
                if max_rows and row_num >= max_rows:
                    break
        
        # Format records as markdown
        markdown_data = format_records_as_markdown(records)
        
        return {
            'markdown_data': markdown_data,
            'total_rows': total_rows,
            'included_rows': len(records),
            'columns': columns
        }
        
    except Exception as e:
        logging.error(f"Error parsing CSV {file_path}: {e}")
        raise

def format_records_as_markdown(records: List[Dict[str, Any]]) -> str:
    """
    Convert CSV records to markdown format.
    
    Args:
        records: List of dictionaries representing CSV rows
        
    Returns:
        String in markdown format
    """
    if not records or len(records) == 0:
        return 'No data available'

    return '\n'.join(records_entry_to_markdown(record) for record in records)

def records_entry_to_markdown(record: Dict[str, Any]) -> str:
    """
    Convert a single CSV record to markdown format.
    
    Args:
        record: Dictionary representing a single CSV row
        
    Returns:
        String in markdown format for this record
    """
    entries = []
    for key, value in record.items():
        # Include all fields, even empty ones (show as empty string)
        entries.append(f"  {key}: {value}")
    
    return f"- {chr(10).join(entries)}"

def estimate_markdown_tokens(markdown_data: str) -> int:
    """
    Estimate token count for markdown data.
    Rough approximation: 1 token ≈ 4 characters for text data.
    """
    return len(markdown_data) // 4

def estimate_json_records_tokens(records: List[Dict[str, Any]]) -> int:
    """
    Estimate token count for JSON records.
    Rough approximation: 1 token ≈ 4 characters for JSON data.
    """
    json_str = json.dumps(records, separators=(',', ':'))
    return len(json_str) // 4

def get_csv_preview(file_path: Path, preview_rows: int = 2) -> Dict[str, Any]:
    """Get a preview of CSV data for display in UI."""
    return parse_csv_to_json_records(file_path, max_rows=preview_rows)

def _register_file_with_connection(file_path: Path, cursor, conn) -> int:
    """
    Register a file using an existing database connection and cursor.
    This is used internally to avoid database locking issues.
    """
    # Calculate file hash
    file_hash = _calculate_file_hash(file_path)
    
    # Check if file already exists
    cursor.execute(f'''
        SELECT id FROM {FILES_TABLE} WHERE file_hash = ?
    ''', (file_hash,))
    
    result = cursor.fetchone()
    
    if result:
        file_id = result[0]
        logging.info(f"File {file_path.name} already registered with ID {file_id}")
        return file_id
    
    # Register new file
    file_stats = file_path.stat()
    created_at = datetime.datetime.now().isoformat()
    
    cursor.execute(f'''
        INSERT INTO {FILES_TABLE} 
        (file_hash, original_filename, file_path, file_size_bytes, mime_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (file_hash, file_path.name, str(file_path.resolve()), 
          file_stats.st_size, _get_mime_type(file_path), created_at))
    
    file_id = cursor.lastrowid
    logging.info(f"Registered new file {file_path.name} with ID {file_id}")
    return file_id

def register_file(file_path: Path, db_path: Path = Path.cwd()) -> int:
    """
    Register a file in our central file registry.
    Returns the file_id (creates new record if file hasn't been seen before).
    """
    # Calculate file hash
    file_hash = _calculate_file_hash(file_path)

    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Check if file already exists
        cursor.execute(f"SELECT id FROM {FILES_TABLE} WHERE file_hash = ?", (file_hash,))
        result = cursor.fetchone()
        
        if result:
            file_id = result[0]
            logging.info(f"File {file_path.name} already registered with ID {file_id}")
            return file_id
        
        # Register new file
        file_stats = file_path.stat()
        created_at = datetime.datetime.now().isoformat()
        mime_type = _get_mime_type(file_path)
        
        cursor.execute(f'''
            INSERT INTO {FILES_TABLE} 
            (file_hash, original_filename, file_path, file_size_bytes, mime_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (file_hash, file_path.name, str(file_path.resolve()), 
              file_stats.st_size, mime_type, created_at))
        
        file_id = cursor.lastrowid
        
        # If it's a CSV file, parse and store the data
        if mime_type == 'text/csv':
            try:
                csv_data = parse_csv_to_json_records(file_path)
                # Store CSV data as JSON in the csv_data column
                cursor.execute(f'''
                    UPDATE {FILES_TABLE} 
                    SET csv_data = ?
                    WHERE id = ?
                ''', (json.dumps(csv_data), file_id))
                logging.info(f"Stored CSV data for {file_path.name}: {csv_data['total_rows']} rows, {len(csv_data['columns'])} columns")
            except Exception as e:
                logging.warning(f"Could not parse CSV data for {file_path.name}: {e}")
        
        conn.commit()
        logging.info(f"Registered new file {file_path.name} with ID {file_id}")
        return file_id
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when registering file {file_path.name}: {e}")
        raise
    finally:
        conn.close()

def get_provider_file_id(file_id: int, provider: str, db_path: Path = Path.cwd()) -> Optional[str]:
    """
    Get the provider-specific file ID for a file that's been uploaded to a provider.
    Returns None if the file hasn't been uploaded to this provider yet.
    """
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            SELECT provider_file_id FROM {PROVIDER_FILE_UPLOADS_TABLE} 
            WHERE file_id = ? AND provider = ?
        ''', (file_id, provider))
        
        result = cursor.fetchone()
        return result[0] if result else None
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when getting provider file ID: {e}")
        return None
    finally:
        conn.close()

def register_provider_upload(file_id: int, provider: str, provider_file_id: str, db_path: Path = Path.cwd()):
    """
    Register that a file has been uploaded to a specific provider.
    """
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        uploaded_at = datetime.datetime.now().isoformat()
        
        cursor.execute(f'''
            INSERT OR REPLACE INTO {PROVIDER_FILE_UPLOADS_TABLE} 
            (file_id, provider, provider_file_id, uploaded_at)
            VALUES (?, ?, ?, ?)
        ''', (file_id, provider, provider_file_id, uploaded_at))
        
        conn.commit()
        logging.info(f"Registered upload of file {file_id} to {provider} with ID {provider_file_id}")
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when registering provider upload: {e}")
        raise
    finally:
        conn.close()

def save_benchmark(label: str, description: str, file_paths: List[str], prompt_set_id: int = None, intended_models: List[str] = None, use_web_search: bool = False, db_path: Path = Path.cwd()) -> int:
    """
    Save a new benchmark with multiple files, optional prompt set reference, and intended models.
    
    Args:
        label: User-provided name for this benchmark
        description: Optional description for this benchmark
        file_paths: List of paths to files to include in the benchmark
        prompt_set_id: Optional ID of a prompt set to associate with the benchmark
        intended_models: Optional list of model names that should be run on this benchmark
        use_web_search: Whether web search is enabled for this benchmark
        db_path: Path to the database directory
        
    Returns:
        The benchmark ID
    """
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Create benchmark record
        created_at = datetime.datetime.now().isoformat()
        intended_models_json = json.dumps(intended_models) if intended_models else None
        
        cursor.execute(f'''
            INSERT INTO {BENCHMARKS_TABLE} (created_at, label, description, prompt_set_id, intended_models, use_web_search)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (created_at, label, description, prompt_set_id, intended_models_json, 1 if use_web_search else 0))
        
        benchmark_id = cursor.lastrowid
        
        # Register all files and link them to the benchmark
        for file_path_str in file_paths:
            file_path_obj = Path(file_path_str) # Ensure it's a Path object
            
            # Register file in central registry using the same connection
            file_id = _register_file_with_connection(file_path_obj, cursor, conn)
            logging.info(f"Processing file {file_path_str} -> file_id {file_id} for benchmark {benchmark_id}")
            
            # Check if this file is already linked to this benchmark
            cursor.execute(f'''
                SELECT COUNT(*) FROM {BENCHMARK_FILES_TABLE} 
                WHERE benchmark_id = ? AND file_id = ?
            ''', (benchmark_id, file_id))
            
            existing_count = cursor.fetchone()[0]
            if existing_count > 0:
                logging.warning(f"File {file_id} already linked to benchmark {benchmark_id}, skipping")
                continue
            
            # Link file to benchmark
            cursor.execute(f'''
                INSERT INTO {BENCHMARK_FILES_TABLE} (benchmark_id, file_id)
            VALUES (?, ?)
            ''', (benchmark_id, file_id))
        
        conn.commit()
        logging.info(f"Created benchmark {benchmark_id} with {len(file_paths)} files")
        return benchmark_id
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving benchmark: {e}")
        raise
    finally:
        conn.close()

def get_benchmark_files(benchmark_id: int, db_path: Path = Path.cwd()) -> List[dict]:
    """
    Get all files associated with a benchmark.
    Returns list of file info dictionaries.
    """
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            SELECT f.id, f.file_hash, f.original_filename, f.file_path, 
                   f.file_size_bytes, f.mime_type, f.created_at
            FROM {FILES_TABLE} f
            JOIN {BENCHMARK_FILES_TABLE} bf ON f.id = bf.file_id
            WHERE bf.benchmark_id = ?
        ''', (benchmark_id,))
        
        files = []
        for row in cursor.fetchall():
            files.append({
                'id': row[0],
                'file_hash': row[1],
                'original_filename': row[2],
                'file_path': row[3],
                'file_size_bytes': row[4],
                'mime_type': row[5],
                'created_at': row[6]
            })
        
        return files
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when loading files for benchmark {benchmark_id}: {e}")
        return []
    finally:
        conn.close()

def save_benchmark_run(benchmark_id: int, model_name: str, provider: str, report: Optional[str], 
                      latency: float, total_standard_input_tokens: int, 
                      total_cached_input_tokens: int, total_output_tokens: int, 
                      total_tokens: int, total_input_cost: float = 0.0,
                      total_cached_cost: float = 0.0, total_output_cost: float = 0.0,
                      total_cost: float = 0.0, db_path: Path = Path.cwd()) -> Optional[int]:
    """Save a benchmark run with provider information and cost tracking."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        created_at = datetime.datetime.now().isoformat()
        report_data = report if report else "" # Store empty string if report is None
        if isinstance(report, (dict, list)): # Ensure JSON serializable if complex
             report_data = json.dumps(report)

        cursor.execute(f'''
            INSERT INTO {BENCHMARK_RUNS_TABLE} 
            (benchmark_id, model_name, provider, report, latency, created_at, 
             total_standard_input_tokens, total_cached_input_tokens, 
             total_output_tokens, total_tokens, total_input_cost,
             total_cached_cost, total_output_cost, total_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (benchmark_id, model_name, provider, report_data, latency, created_at,
              total_standard_input_tokens or 0, total_cached_input_tokens or 0, 
              total_output_tokens or 0, total_tokens or 0, total_input_cost,
              total_cached_cost, total_output_cost, total_cost))
        
        run_id = cursor.lastrowid
        conn.commit()
        logging.info(f"Saved benchmark run {run_id} for {provider} model {model_name} (Cost: ${total_cost:.6f})")
        return run_id
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when saving benchmark run: {e}")
        return None
    finally:
        conn.close()

def save_benchmark_prompt(benchmark_run_id: int, prompt: str, response: str, 
                         latency: float, standard_input_tokens: int, 
                         cached_input_tokens: int, output_tokens: int,
                         thinking_tokens: int = 0, reasoning_tokens: int = 0,
                         input_cost: float = 0.0, cached_cost: float = 0.0,
                         output_cost: float = 0.0, thinking_cost: float = 0.0,
                         reasoning_cost: float = 0.0, total_cost: float = 0.0,
                         web_search_used: bool = False,
                         web_search_sources: str = "",
                         truncation_info: str = "",
                         db_path: Path = Path.cwd()) -> Optional[int]:
    """Save a prompt result (response, latency, tokens, costs) for a benchmark run."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Determine status based on response content
        prompt_status = 'failed' if str(response).startswith('ERROR') else 'completed'
        error_message = str(response) if prompt_status == 'failed' else None
        
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_PROMPTS_TABLE} 
            (benchmark_run_id, prompt, response, latency, 
             standard_input_tokens, cached_input_tokens, output_tokens,
             thinking_tokens, reasoning_tokens,
             input_cost, cached_cost, output_cost, thinking_cost, reasoning_cost, total_cost, 
             web_search_used, web_search_sources, truncation_info,
             status, started_at, completed_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (benchmark_run_id, str(prompt), str(response),
              float(latency) if latency is not None else 0.0, 
              int(standard_input_tokens) if standard_input_tokens is not None else 0,
              int(cached_input_tokens) if cached_input_tokens is not None else 0,
              int(output_tokens) if output_tokens is not None else 0,
              int(thinking_tokens) if thinking_tokens is not None else 0,
              int(reasoning_tokens) if reasoning_tokens is not None else 0,
              input_cost, cached_cost, output_cost, thinking_cost, reasoning_cost, total_cost, 
              1 if web_search_used else 0, web_search_sources, truncation_info,
              prompt_status, datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat(), error_message))
        
        prompt_id = cursor.lastrowid
        conn.commit()
        return prompt_id
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when saving benchmark prompt: {e}")
        return None
    finally:
        conn.close()

def save_benchmark_report(benchmark_id: int, compared_models: List[str], report: str, db_path: Path = Path.cwd()) -> Optional[int]:
    """Save a benchmark report (e.g., qualitative comparison)."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    created_at = datetime.datetime.now().isoformat()
    try:
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_REPORTS_TABLE} (benchmark_id, compared_models, report, created_at)
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

def load_all_benchmarks(db_path: Path = Path.cwd()) -> List[dict]:
    """Load all benchmarks with their associated files and models run."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    benchmarks = []
    
    try:
        cursor.execute(f"""
            SELECT id, created_at, label, description, status
            FROM {BENCHMARKS_TABLE}
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        
        for row_data in rows:
            benchmark = dict(row_data) # Convert row object to dict
            
            # Get associated files
            files_info = get_benchmark_files(benchmark['id'], db_path)
            benchmark['files'] = files_info
            benchmark['file_count'] = len(files_info)
            
            # Get model names that have run on this benchmark
            cursor.execute(f'''
                SELECT DISTINCT model_name, provider 
                FROM {BENCHMARK_RUNS_TABLE}
                WHERE benchmark_id = ?
            ''', (benchmark['id'],))
            model_rows = cursor.fetchall()
            benchmark['models'] = [{'name': mr['model_name'], 'provider': mr['provider']} for mr in model_rows]
            
            benchmarks.append(benchmark)
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower() and BENCHMARKS_TABLE in str(e).lower():
             logging.warning(f"Table {BENCHMARKS_TABLE} not found. Database might be new or uninitialized. Returning empty list.")
        else:
            logging.error(f"SQLite operational error when loading benchmarks: {e}")
    except sqlite3.Error as e:
        logging.error(f"SQLite error when loading benchmarks: {e}")
    finally:
        conn.close()
    
    return benchmarks

def get_benchmark_details(benchmark_id: int, db_path: Path = Path.cwd()) -> Optional[dict]:
    """Get detailed information about a specific benchmark, including runs and prompts (responses only)."""
    db_file = db_path / DB_NAME
    # Use WAL mode and timeout to handle concurrent access
    conn = sqlite3.connect(db_file, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get benchmark info including progress fields
        cursor.execute(f'''
            SELECT id, created_at, label, description, status,
                   total_prompts, completed_prompts, failed_prompts, 
                   updated_at, worker_status
            FROM {BENCHMARKS_TABLE}
            WHERE id = ?
        ''', (benchmark_id,))

        benchmark_row = cursor.fetchone()
        if not benchmark_row:
            logging.warning(f"Benchmark with ID {benchmark_id} not found.")
            return None
        
        benchmark = dict(benchmark_row)
        
        # Get files
        benchmark['files'] = get_benchmark_files(benchmark_id, db_path)
        
        # Get runs including progress and status fields
        cursor.execute(f'''
            SELECT id as run_id, model_name, provider, report, latency, created_at as run_created_at,
                   total_standard_input_tokens, total_cached_input_tokens,
                   total_output_tokens, total_tokens,
                   total_input_cost, total_cached_cost, total_output_cost, total_cost,
                   status as run_status, completed_prompts as run_completed_prompts, 
                   total_prompts as run_total_prompts, last_heartbeat
            FROM {BENCHMARK_RUNS_TABLE}
            WHERE benchmark_id = ?
            ORDER BY created_at DESC
        ''', (benchmark_id,))

        runs = []
        for run_row_data in cursor.fetchall():
            run = dict(run_row_data) # Convert row to dict

            # Get prompts for this run including status fields
            cursor.execute(f'''
                SELECT id as prompt_id, prompt, response, latency as prompt_latency,
                       standard_input_tokens, cached_input_tokens, output_tokens,
                       input_cost, cached_cost, output_cost, total_cost,
                       CASE WHEN (SELECT COUNT(*) FROM pragma_table_info('{BENCHMARK_PROMPTS_TABLE}') 
                                 WHERE name='web_search_used') > 0 
                            THEN web_search_used ELSE 0 END as web_search_used,
                       CASE WHEN (SELECT COUNT(*) FROM pragma_table_info('{BENCHMARK_PROMPTS_TABLE}') 
                                 WHERE name='web_search_sources') > 0 
                            THEN web_search_sources ELSE '' END as web_search_sources,
                       status as prompt_status, started_at, completed_at, error_message
                FROM {BENCHMARK_PROMPTS_TABLE}
                WHERE benchmark_run_id = ?
                ORDER BY id
            ''', (run['run_id'],))
            
            run['prompts'] = [dict(prompt_row_data) for prompt_row_data in cursor.fetchall()] # Convert rows to dicts
            runs.append(run)
        
        benchmark['runs'] = runs
        return benchmark
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when getting benchmark details for ID {benchmark_id}: {e}")
        return None
    finally:
        conn.close()

def delete_benchmark(benchmark_id: int, db_path: Path = Path.cwd()) -> bool:
    """Delete a benchmark and all associated data (runs, prompts, files associations, reports)."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Delete prompts for all runs of this benchmark
        cursor.execute(f'''
            DELETE FROM {BENCHMARK_PROMPTS_TABLE} 
            WHERE benchmark_run_id IN (
                SELECT id FROM {BENCHMARK_RUNS_TABLE} WHERE benchmark_id = ?
            )
        ''', (benchmark_id,))
        
        # Delete runs
        cursor.execute(f'DELETE FROM {BENCHMARK_RUNS_TABLE} WHERE benchmark_id = ?', (benchmark_id,))
        
        # Delete file associations
        cursor.execute(f'DELETE FROM {BENCHMARK_FILES_TABLE} WHERE benchmark_id = ?', (benchmark_id,))
        
        # Delete reports
        cursor.execute(f'DELETE FROM {BENCHMARK_REPORTS_TABLE} WHERE benchmark_id = ?', (benchmark_id,))
        
        # Delete the benchmark itself
        cursor.execute(f'DELETE FROM {BENCHMARKS_TABLE} WHERE id = ?', (benchmark_id,))
        
        conn.commit()
        logging.info(f"Deleted benchmark {benchmark_id} and all associated data.")
        return True
        
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"SQLite error when deleting benchmark {benchmark_id}: {e}")
        return False
    finally:
        conn.close()

def update_benchmark_status(benchmark_id: int, status: str, db_path: Path = Path.cwd()) -> bool:
    """Update the status of a benchmark."""
    if status not in ['in-progress', 'complete', 'archived', 'error']: # Added more statuses
        logging.error(f"Invalid status: {status}")
        return False
    
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            UPDATE {BENCHMARKS_TABLE} SET status = ? WHERE id = ?
        ''', (status, benchmark_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        
        if success:
            logging.info(f"Updated benchmark {benchmark_id} status to {status}")
        else:
            logging.warning(f"No benchmark found with ID {benchmark_id} to update status.")
        
        return success
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when updating benchmark {benchmark_id} status: {e}")
        return False
    finally:
        conn.close()

def load_benchmark_details(benchmark_id: int, db_path: Path = Path.cwd()) -> Optional[dict]:
    """Get detailed information about a specific benchmark, including runs and prompts."""
    return get_benchmark_details(benchmark_id, db_path)

def find_benchmark_by_files(file_paths: List[str], db_path: Path = Path.cwd()) -> Optional[int]:
    """Find a benchmark that uses the exact same set of files."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Get file IDs for the provided paths
        file_ids = []
        for file_path_str in file_paths:
            file_path = Path(file_path_str)
            file_hash = _calculate_file_hash(file_path)
            
            cursor.execute(f"SELECT id FROM {FILES_TABLE} WHERE file_hash = ?", (file_hash,))
            result = cursor.fetchone()
            if result:
                file_ids.append(result[0])
            else:
                # If any file doesn't exist, no benchmark can match
                return None
        
        if not file_ids:
            return None
        
        # Find benchmarks that have exactly these files
        file_ids_str = ','.join('?' * len(file_ids))
        cursor.execute(f'''
            SELECT benchmark_id, COUNT(*) as file_count
            FROM {BENCHMARK_FILES_TABLE}
            WHERE file_id IN ({file_ids_str})
            GROUP BY benchmark_id
            HAVING file_count = ?
        ''', file_ids + [len(file_ids)])
        
        # Check if any benchmark has exactly the right number of files
        for benchmark_id, file_count in cursor.fetchall():
            # Verify this benchmark has no other files
            cursor.execute(f'''
                SELECT COUNT(*) FROM {BENCHMARK_FILES_TABLE}
                WHERE benchmark_id = ?
            ''', (benchmark_id,))
            
            total_files = cursor.fetchone()[0]
            if total_files == len(file_ids):
                return benchmark_id
        
        return None
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when finding benchmark by files: {e}")
        return None
    finally:
        conn.close()

def update_benchmark_details(benchmark_id: int, label: Optional[str] = None, 
                           description: Optional[str] = None, db_path: Path = Path.cwd()) -> bool:
    """Update the label and/or description of a benchmark."""
    if label is None and description is None:
        return False
    
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        updates = []
        params = []
        
        if label is not None:
            updates.append("label = ?")
            params.append(label)
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        params.append(benchmark_id)
        
        cursor.execute(f'''
            UPDATE {BENCHMARKS_TABLE} 
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)
        
        success = cursor.rowcount > 0
        conn.commit()
        
        if success:
            logging.info(f"Updated benchmark {benchmark_id} details")
        else:
            logging.warning(f"No benchmark found with ID {benchmark_id} to update")
        
        return success

    except sqlite3.Error as e:
        logging.error(f"SQLite error when updating benchmark {benchmark_id} details: {e}")
        return False
    finally:
        conn.close()

def load_all_benchmarks_with_models(db_path: Path = Path.cwd()) -> List[dict]:
    """Load all benchmarks with their associated files and models run."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    benchmarks = []
    
    try:
        cursor.execute(f"""
            SELECT b.id, b.created_at, b.label, b.description, b.status, b.prompt_set_id, b.intended_models,
                   ps.name as prompt_set_name, ps.description as prompt_set_description
            FROM {BENCHMARKS_TABLE} b
            LEFT JOIN {PROMPT_SETS_TABLE} ps ON b.prompt_set_id = ps.id
            ORDER BY b.created_at DESC
        """)
        rows = cursor.fetchall()
        
        for row_data in rows:
            benchmark = dict(row_data)
            
            # Get associated files
            files_info = get_benchmark_files(benchmark['id'], db_path)
            benchmark['files'] = files_info
            benchmark['file_count'] = len(files_info)
            benchmark['file_paths'] = [f['file_path'] for f in files_info]
            
            # Get model names - prefer intended_models if available, otherwise use completed models
            if benchmark.get('intended_models'):
                try:
                    intended_models = json.loads(benchmark['intended_models'])
                    benchmark['model_names'] = intended_models
                    benchmark['models'] = [{'name': model, 'provider': 'unknown'} for model in intended_models]
                except (json.JSONDecodeError, TypeError):
                    logging.warning(f"Could not parse intended_models for benchmark {benchmark['id']}")
                    # Fall back to completed models
                    cursor.execute(f'''
                        SELECT DISTINCT model_name, provider 
                        FROM {BENCHMARK_RUNS_TABLE}
                        WHERE benchmark_id = ?
                    ''', (benchmark['id'],))
                    model_rows = cursor.fetchall()
                    benchmark['models'] = [{'name': mr['model_name'], 'provider': mr['provider']} for mr in model_rows]
                    benchmark['model_names'] = [mr['model_name'] for mr in model_rows]
            else:
                # Fall back to completed models for older benchmarks
                cursor.execute(f'''
                    SELECT DISTINCT model_name, provider 
                    FROM {BENCHMARK_RUNS_TABLE}
                    WHERE benchmark_id = ?
                ''', (benchmark['id'],))
                model_rows = cursor.fetchall()
                benchmark['models'] = [{'name': mr['model_name'], 'provider': mr['provider']} for mr in model_rows]
                benchmark['model_names'] = [mr['model_name'] for mr in model_rows]
            
            # Use created_at as timestamp for consistency
            benchmark['timestamp'] = benchmark['created_at']
            
            benchmarks.append(benchmark)
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower() and BENCHMARKS_TABLE in str(e).lower():
             logging.warning(f"Table {BENCHMARKS_TABLE} not found. Database might be new or uninitialized. Returning empty list.")
        else:
            logging.error(f"SQLite operational error when loading benchmarks: {e}")
    except sqlite3.Error as e:
        logging.error(f"SQLite error when loading benchmarks: {e}")
    finally:
        conn.close()
    
    return benchmarks

def update_benchmark_model(benchmark_id: int, model_name: str, db_path: Path = Path.cwd()) -> bool:
    """Register that a model will be run on a benchmark (for UI display purposes)."""
    # This function is called to ensure models show up in the UI even before results are saved
    # We don't need to do anything special here since models are registered when runs are saved
    # But we can verify the benchmark exists
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT id FROM {BENCHMARKS_TABLE} WHERE id = ?", (benchmark_id,))
        result = cursor.fetchone()
        
        if result:
            logging.info(f"Verified benchmark {benchmark_id} exists for model {model_name}")
            return True
        else:
            logging.warning(f"Benchmark {benchmark_id} not found when registering model {model_name}")
            return False
            
    except sqlite3.Error as e:
        logging.error(f"SQLite error when updating benchmark model: {e}")
        return False
    finally:
        conn.close()

# ===== PROMPT SET MANAGEMENT FUNCTIONS =====

def create_prompt_set(name: str, description: str, prompts: List[str], db_path: Path = Path.cwd()) -> Optional[int]:
    """Create a new prompt set with the given prompts."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Create prompt set record
        created_at = datetime.datetime.now().isoformat()
        cursor.execute(f'''
            INSERT INTO {PROMPT_SETS_TABLE} (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (name, description, created_at, created_at))
        
        prompt_set_id = cursor.lastrowid
        
        # Add prompts to the set
        for i, prompt_text in enumerate(prompts):
            cursor.execute(f'''
                INSERT INTO {PROMPT_SET_ITEMS_TABLE} (prompt_set_id, prompt_text, order_index, created_at)
                VALUES (?, ?, ?, ?)
            ''', (prompt_set_id, prompt_text, i, created_at))
        
        conn.commit()
        logging.info(f"Created prompt set {prompt_set_id} '{name}' with {len(prompts)} prompts")
        return prompt_set_id
        
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"SQLite error when creating prompt set: {e}")
        return None
    finally:
        conn.close()
        
    
def get_prompt_set(prompt_set_id: int, db_path: Path = Path.cwd()) -> Optional[dict]:
    """Get a prompt set by ID with all its prompts."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get prompt set info
        cursor.execute(f'''
            SELECT id, name, description, created_at, updated_at
            FROM {PROMPT_SETS_TABLE}
            WHERE id = ?
        ''', (prompt_set_id,))
        
        prompt_set_row = cursor.fetchone()
        if not prompt_set_row:
            return None
        
        prompt_set = dict(prompt_set_row)
        
        # Get prompts for this set
        cursor.execute(f'''
            SELECT id, prompt_text, order_index
            FROM {PROMPT_SET_ITEMS_TABLE}
            WHERE prompt_set_id = ?
            ORDER BY order_index
        ''', (prompt_set_id,))
        
        prompts = [dict(row) for row in cursor.fetchall()]
        prompt_set['prompts'] = prompts
        prompt_set['prompt_count'] = len(prompts)
        
        return prompt_set
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when getting prompt set {prompt_set_id}: {e}")
        return None
    finally:
        conn.close()


def get_all_prompt_sets(db_path: Path = Path.cwd()) -> List[dict]:
    """Get all prompt sets with basic info (no individual prompts)."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            SELECT ps.id, ps.name, ps.description, ps.created_at, ps.updated_at,
                   COUNT(psi.id) as prompt_count
            FROM {PROMPT_SETS_TABLE} ps
            LEFT JOIN {PROMPT_SET_ITEMS_TABLE} psi ON ps.id = psi.prompt_set_id
            GROUP BY ps.id, ps.name, ps.description, ps.created_at, ps.updated_at
            ORDER BY ps.created_at DESC
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when getting all prompt sets: {e}")
        return []
    finally:
        conn.close()


def update_prompt_set(prompt_set_id: int, name: str = None, description: str = None, 
                     prompts: List[str] = None, db_path: Path = Path.cwd()) -> bool:
    """Update a prompt set. If prompts are provided, replaces all existing prompts."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Update prompt set metadata if provided
        if name is not None or description is not None:
            updated_at = datetime.datetime.now().isoformat()
            
            if name is not None and description is not None:
                cursor.execute(f'''
                    UPDATE {PROMPT_SETS_TABLE} 
                    SET name = ?, description = ?, updated_at = ?
                    WHERE id = ?
                ''', (name, description, updated_at, prompt_set_id))
            elif name is not None:
                cursor.execute(f'''
                    UPDATE {PROMPT_SETS_TABLE} 
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                ''', (name, updated_at, prompt_set_id))
            elif description is not None:
                cursor.execute(f'''
                    UPDATE {PROMPT_SETS_TABLE} 
                    SET description = ?, updated_at = ?
                    WHERE id = ?
                ''', (description, updated_at, prompt_set_id))
        
        # Update prompts if provided
        if prompts is not None:
            # Delete existing prompts
            cursor.execute(f'''
                DELETE FROM {PROMPT_SET_ITEMS_TABLE} WHERE prompt_set_id = ?
            ''', (prompt_set_id,))
            
            # Add new prompts
            created_at = datetime.datetime.now().isoformat()
            for i, prompt_text in enumerate(prompts):
                cursor.execute(f'''
                    INSERT INTO {PROMPT_SET_ITEMS_TABLE} (prompt_set_id, prompt_text, order_index, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (prompt_set_id, prompt_text, i, created_at))
        
        conn.commit()
        logging.info(f"Updated prompt set {prompt_set_id}")
        return True
        
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"SQLite error when updating prompt set {prompt_set_id}: {e}")
        return False
    finally:
        conn.close()


def delete_prompt_set(prompt_set_id: int, db_path: Path = Path.cwd()) -> bool:
    """Delete a prompt set and all its prompts."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Check if any benchmarks are using this prompt set
        cursor.execute(f'''
            SELECT COUNT(*) FROM {BENCHMARKS_TABLE} WHERE prompt_set_id = ?
        ''', (prompt_set_id,))
        
        benchmark_count = cursor.fetchone()[0]
        if benchmark_count > 0:
            logging.warning(f"Cannot delete prompt set {prompt_set_id}: {benchmark_count} benchmarks are using it")
            return False
        
        # Delete prompt items
        cursor.execute(f'''
            DELETE FROM {PROMPT_SET_ITEMS_TABLE} WHERE prompt_set_id = ?
        ''', (prompt_set_id,))
        
        # Delete prompt set
        cursor.execute(f'''
            DELETE FROM {PROMPT_SETS_TABLE} WHERE id = ?
        ''', (prompt_set_id,))
        
        conn.commit()
        logging.info(f"Deleted prompt set {prompt_set_id}")
        return True
        
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"SQLite error when deleting prompt set {prompt_set_id}: {e}")
        return False
    finally:
        conn.close()


def get_next_prompt_set_number(db_path: Path = Path.cwd()) -> int:
    """Get the next available prompt set number for auto-naming."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Find existing prompt sets with names like "Prompt Set N"
        cursor.execute(f'''
            SELECT name FROM {PROMPT_SETS_TABLE} 
            WHERE name LIKE 'Prompt Set %'
        ''')
        
        existing_numbers = []
        for (name,) in cursor.fetchall():
            try:
                # Extract number from "Prompt Set N"
                if name.startswith('Prompt Set '):
                    number_str = name[11:]  # Remove "Prompt Set "
                    if number_str.isdigit():
                        existing_numbers.append(int(number_str))
            except (ValueError, IndexError):
                continue
        
        # Find the smallest unused number starting from 1
        next_number = 1
        while next_number in existing_numbers:
            next_number += 1
        
        return next_number
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when getting next prompt set number: {e}")
        return 1
    finally:
        conn.close()

def update_benchmark_run(run_id: int, latency: float = None, 
                        total_standard_input_tokens: int = None,
                        total_cached_input_tokens: int = None, 
                        total_output_tokens: int = None,
                        total_tokens: int = None, total_input_cost: float = None,
                        total_cached_cost: float = None, total_output_cost: float = None,
                        total_cost: float = None, report: str = None,
                        db_path: Path = Path.cwd()) -> bool:
    """Update an existing benchmark run with final totals and report."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Build dynamic update query based on provided parameters
        update_fields = []
        update_values = []
        
        if latency is not None:
            update_fields.append("latency = ?")
            update_values.append(latency)
        if total_standard_input_tokens is not None:
            update_fields.append("total_standard_input_tokens = ?")
            update_values.append(total_standard_input_tokens)
        if total_cached_input_tokens is not None:
            update_fields.append("total_cached_input_tokens = ?")
            update_values.append(total_cached_input_tokens)
        if total_output_tokens is not None:
            update_fields.append("total_output_tokens = ?")
            update_values.append(total_output_tokens)
        if total_tokens is not None:
            update_fields.append("total_tokens = ?")
            update_values.append(total_tokens)
        if total_input_cost is not None:
            update_fields.append("total_input_cost = ?")
            update_values.append(total_input_cost)
        if total_cached_cost is not None:
            update_fields.append("total_cached_cost = ?")
            update_values.append(total_cached_cost)
        if total_output_cost is not None:
            update_fields.append("total_output_cost = ?")
            update_values.append(total_output_cost)
        if total_cost is not None:
            update_fields.append("total_cost = ?")
            update_values.append(total_cost)
        if report is not None:
            update_fields.append("report = ?")
            update_values.append(report)
        
        if not update_fields:
            logging.warning("No fields provided to update for benchmark run")
            return False
        
        # Add the run_id to the end of values for the WHERE clause
        update_values.append(run_id)
        
        query = f'''
            UPDATE {BENCHMARK_RUNS_TABLE} 
            SET {", ".join(update_fields)}
            WHERE id = ?
        '''
        
        cursor.execute(query, update_values)
        
        if cursor.rowcount == 0:
            logging.warning(f"No benchmark run found with ID {run_id}")
            return False
        
        conn.commit()
        logging.info(f"Updated benchmark run {run_id} with {len(update_fields)} fields")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when updating benchmark run {run_id}: {e}")
        return False
    finally:
        conn.close()

# ===== FILE MANAGEMENT FUNCTIONS =====

def get_all_files(db_path: Path = Path.cwd()) -> List[dict]:
    """Get all registered files."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            SELECT id, file_hash, original_filename, file_path, 
                   file_size_bytes, mime_type, created_at, csv_data
            FROM {FILES_TABLE}
            ORDER BY created_at DESC
        ''')
        
        files = []
        for row in cursor.fetchall():
            file_dict = dict(row)
            
            # Parse CSV data if available
            if file_dict.get('csv_data'):
                try:
                    csv_data = json.loads(file_dict['csv_data'])
                    file_dict['csv_rows'] = csv_data.get('total_rows', 0)
                    file_dict['csv_columns'] = len(csv_data.get('columns', []))
                except json.JSONDecodeError:
                    file_dict['csv_rows'] = 0
                    file_dict['csv_columns'] = 0
            else:
                file_dict['csv_rows'] = 0
                file_dict['csv_columns'] = 0
            
            # Check if file still exists on disk
            file_dict['exists_on_disk'] = Path(file_dict['file_path']).exists()
            files.append(file_dict)
        
        return files
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when getting all files: {e}")
        return []
    finally:
        conn.close()

def get_file_details(file_id: int, db_path: Path = Path.cwd()) -> Optional[dict]:
    """Get detailed information about a specific file."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            SELECT id, file_hash, original_filename, file_path, 
                   file_size_bytes, mime_type, created_at, csv_data
            FROM {FILES_TABLE}
            WHERE id = ?
        ''', (file_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        file_dict = dict(row)
        
        # Parse CSV data if available
        if file_dict.get('csv_data'):
            try:
                file_dict['csv_data'] = json.loads(file_dict['csv_data'])
            except json.JSONDecodeError:
                logging.warning(f"Could not parse CSV data for file {file_id}")
                file_dict['csv_data'] = None
        
        # Check if file still exists on disk
        file_dict['exists_on_disk'] = Path(file_dict['file_path']).exists()
        
        # Get provider uploads for this file
        cursor.execute(f'''
            SELECT provider, provider_file_id, uploaded_at
            FROM {PROVIDER_FILE_UPLOADS_TABLE}
            WHERE file_id = ?
        ''', (file_id,))
        
        uploads = []
        for upload_row in cursor.fetchall():
            uploads.append({
                'provider': upload_row[0],
                'provider_file_id': upload_row[1],
                'uploaded_at': upload_row[2]
            })
        
        file_dict['provider_uploads'] = uploads
        
        # Get benchmarks that use this file
        cursor.execute(f'''
            SELECT b.id, b.label, b.created_at
            FROM {BENCHMARKS_TABLE} b
            JOIN {BENCHMARK_FILES_TABLE} bf ON b.id = bf.benchmark_id
            WHERE bf.file_id = ?
            ORDER BY b.created_at DESC
        ''', (file_id,))
        
        benchmarks = []
        for benchmark_row in cursor.fetchall():
            benchmarks.append({
                'id': benchmark_row[0],
                'label': benchmark_row[1],
                'created_at': benchmark_row[2]
            })
        
        file_dict['used_in_benchmarks'] = benchmarks
        
        return file_dict
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when getting file details {file_id}: {e}")
        return None
    finally:
        conn.close()

def delete_file(file_id: int, db_path: Path = Path.cwd()) -> bool:
    """Delete a file from the system."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Check if any benchmarks are using this file
        cursor.execute(f'''
            SELECT COUNT(*) FROM {BENCHMARK_FILES_TABLE} WHERE file_id = ?
        ''', (file_id,))
        
        benchmark_count = cursor.fetchone()[0]
        if benchmark_count > 0:
            logging.warning(f"Cannot delete file {file_id}: {benchmark_count} benchmarks are using it")
            return False
        
        # Delete provider uploads
        cursor.execute(f'''
            DELETE FROM {PROVIDER_FILE_UPLOADS_TABLE} WHERE file_id = ?
        ''', (file_id,))
        
        # Delete file record
        cursor.execute(f'''
            DELETE FROM {FILES_TABLE} WHERE id = ?
        ''', (file_id,))
        
        conn.commit()
        logging.info(f"Deleted file {file_id}")
        return True
        
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"SQLite error when deleting file {file_id}: {e}")
        return False
    finally:
        conn.close()

# ============================================================================
# Atomic benchmark progress tracking functions
# ============================================================================

def update_benchmark_progress(benchmark_id: int, db_path: Path = Path.cwd()) -> bool:
    """
    Atomically update benchmark progress counters based on completed prompts.
    This should be called after each prompt completion.
    """
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Start transaction for atomic update
        cursor.execute("BEGIN EXCLUSIVE")
        
        # Count total expected prompts (models × prompts)
        cursor.execute(f'''
            SELECT COUNT(DISTINCT br.id) as model_count,
                   COUNT(DISTINCT psi.id) as prompt_count
            FROM {BENCHMARK_RUNS_TABLE} br
            JOIN {BENCHMARKS_TABLE} b ON br.benchmark_id = b.id
            LEFT JOIN {PROMPT_SET_ITEMS_TABLE} psi ON b.prompt_set_id = psi.prompt_set_id
            WHERE b.id = ?
        ''', (benchmark_id,))
        
        row = cursor.fetchone()
        model_count = row[0] or 0
        prompt_count = row[1] or 0
        total_prompts = model_count * prompt_count if prompt_count > 0 else 0
        
        # Count completed prompts
        cursor.execute(f'''
            SELECT COUNT(*) 
            FROM {BENCHMARK_PROMPTS_TABLE} bp
            JOIN {BENCHMARK_RUNS_TABLE} br ON bp.benchmark_run_id = br.id
            WHERE br.benchmark_id = ? AND bp.status = 'completed'
        ''', (benchmark_id,))
        
        completed_prompts = cursor.fetchone()[0] or 0
        
        # Count failed prompts
        cursor.execute(f'''
            SELECT COUNT(*) 
            FROM {BENCHMARK_PROMPTS_TABLE} bp
            JOIN {BENCHMARK_RUNS_TABLE} br ON bp.benchmark_run_id = br.id
            WHERE br.benchmark_id = ? AND bp.status = 'failed'
        ''', (benchmark_id,))
        
        failed_prompts = cursor.fetchone()[0] or 0
        
        # Determine overall status
        if completed_prompts + failed_prompts >= total_prompts and total_prompts > 0:
            status = 'completed' if failed_prompts == 0 else 'completed_with_errors'
        elif completed_prompts > 0 or failed_prompts > 0:
            status = 'in_progress'
        else:
            status = 'pending'
        
        # Update benchmark with atomic operation
        cursor.execute(f'''
            UPDATE {BENCHMARKS_TABLE}
            SET total_prompts = ?,
                completed_prompts = ?,
                failed_prompts = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
        ''', (total_prompts, completed_prompts, failed_prompts, 
              status, datetime.datetime.now().isoformat(), benchmark_id))
        
        # Update individual benchmark_run progress
        cursor.execute(f'''
            UPDATE {BENCHMARK_RUNS_TABLE} br
            SET completed_prompts = (
                    SELECT COUNT(*)
                    FROM {BENCHMARK_PROMPTS_TABLE} bp
                    WHERE bp.benchmark_run_id = br.id AND bp.status = 'completed'
                ),
                total_prompts = (
                    SELECT COUNT(*)
                    FROM {BENCHMARK_PROMPTS_TABLE} bp
                    WHERE bp.benchmark_run_id = br.id
                ),
                status = CASE
                    WHEN (
                        SELECT COUNT(*)
                        FROM {BENCHMARK_PROMPTS_TABLE} bp
                        WHERE bp.benchmark_run_id = br.id AND bp.status = 'completed'
                    ) >= (
                        SELECT COUNT(*)
                        FROM {BENCHMARK_PROMPTS_TABLE} bp
                        WHERE bp.benchmark_run_id = br.id
                    ) AND (
                        SELECT COUNT(*)
                        FROM {BENCHMARK_PROMPTS_TABLE} bp
                        WHERE bp.benchmark_run_id = br.id
                    ) > 0 THEN 'completed'
                    WHEN (
                        SELECT COUNT(*)
                        FROM {BENCHMARK_PROMPTS_TABLE} bp
                        WHERE bp.benchmark_run_id = br.id AND bp.status IN ('completed', 'failed')
                    ) > 0 THEN 'in_progress'
                    ELSE 'pending'
                END
            WHERE br.benchmark_id = ?
        ''', (benchmark_id,))
        
        cursor.execute("COMMIT")
        return True
        
    except sqlite3.Error as e:
        cursor.execute("ROLLBACK")
        logging.error(f"Failed to update benchmark progress: {e}")
        return False
    finally:
        conn.close()

def save_benchmark_prompt_atomic(benchmark_run_id: int, prompt: str, response: str, 
                                latency: float, standard_input_tokens: int, 
                                cached_input_tokens: int, output_tokens: int,
                                thinking_tokens: int = 0, reasoning_tokens: int = 0,
                                input_cost: float = 0.0, cached_cost: float = 0.0,
                                output_cost: float = 0.0, thinking_cost: float = 0.0,
                                reasoning_cost: float = 0.0, total_cost: float = 0.0,
                                web_search_used: bool = False,
                                web_search_sources: str = "",
                                truncation_info: str = "",
                                db_path: Path = Path.cwd()) -> Optional[int]:
    """
    Save a prompt result atomically with progress tracking.
    This replaces save_benchmark_prompt for better consistency.
    """
    db_file = db_path / DB_NAME
    # Use WAL mode and timeout to handle concurrent access
    conn = sqlite3.connect(db_file, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cursor = conn.cursor()
    
    try:
        # Start transaction
        cursor.execute("BEGIN EXCLUSIVE")
        
        # Get benchmark_id from the run
        cursor.execute(f'''
            SELECT benchmark_id FROM {BENCHMARK_RUNS_TABLE} WHERE id = ?
        ''', (benchmark_run_id,))
        
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Benchmark run {benchmark_run_id} not found")
        
        benchmark_id = result[0]
        
        # Determine status based on response content
        prompt_status = 'failed' if str(response).startswith('ERROR') else 'completed'
        error_message = str(response) if prompt_status == 'failed' else None
        
        # Insert the prompt with status tracking
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_PROMPTS_TABLE} 
            (benchmark_run_id, prompt, response, latency, 
             standard_input_tokens, cached_input_tokens, output_tokens,
             thinking_tokens, reasoning_tokens,
             input_cost, cached_cost, output_cost, thinking_cost, reasoning_cost, total_cost, 
             web_search_used, web_search_sources, truncation_info,
             status, started_at, completed_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (benchmark_run_id, str(prompt), str(response),
              float(latency) if latency is not None else 0.0, 
              int(standard_input_tokens) if standard_input_tokens is not None else 0,
              int(cached_input_tokens) if cached_input_tokens is not None else 0,
              int(output_tokens) if output_tokens is not None else 0,
              int(thinking_tokens) if thinking_tokens is not None else 0,
              int(reasoning_tokens) if reasoning_tokens is not None else 0,
              input_cost, cached_cost, output_cost, thinking_cost, reasoning_cost, total_cost, 
              1 if web_search_used else 0, web_search_sources, truncation_info,
              prompt_status, datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat(), error_message))
        
        prompt_id = cursor.lastrowid
        
        # Update benchmark progress manually within this transaction
        # Count total expected prompts (models × prompts)
        cursor.execute(f'''
            SELECT COUNT(DISTINCT br.id) as model_count,
                   COUNT(DISTINCT psi.id) as prompt_count
            FROM {BENCHMARK_RUNS_TABLE} br
            JOIN {BENCHMARKS_TABLE} b ON br.benchmark_id = b.id
            LEFT JOIN {PROMPT_SET_ITEMS_TABLE} psi ON b.prompt_set_id = psi.prompt_set_id
            WHERE b.id = ?
        ''', (benchmark_id,))
        
        row = cursor.fetchone()
        model_count = row[0] or 0
        prompt_count = row[1] or 0
        total_prompts = model_count * prompt_count if prompt_count > 0 else 0
        
        # Count completed prompts
        cursor.execute(f'''
            SELECT COUNT(*) 
            FROM {BENCHMARK_PROMPTS_TABLE} bp
            JOIN {BENCHMARK_RUNS_TABLE} br ON bp.benchmark_run_id = br.id
            WHERE br.benchmark_id = ? AND bp.status = 'completed'
        ''', (benchmark_id,))
        
        completed_prompts = cursor.fetchone()[0] or 0
        
        # Count failed prompts
        cursor.execute(f'''
            SELECT COUNT(*) 
            FROM {BENCHMARK_PROMPTS_TABLE} bp
            JOIN {BENCHMARK_RUNS_TABLE} br ON bp.benchmark_run_id = br.id
            WHERE br.benchmark_id = ? AND bp.status = 'failed'
        ''', (benchmark_id,))
        
        failed_prompts = cursor.fetchone()[0] or 0
        
        # Determine overall status
        if completed_prompts + failed_prompts >= total_prompts and total_prompts > 0:
            status = 'completed' if failed_prompts == 0 else 'completed_with_errors'
        elif completed_prompts > 0 or failed_prompts > 0:
            status = 'in_progress'
        else:
            status = 'pending'
        
        # Update benchmark with atomic operation
        cursor.execute(f'''
            UPDATE {BENCHMARKS_TABLE}
            SET total_prompts = ?,
                completed_prompts = ?,
                failed_prompts = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
        ''', (total_prompts, completed_prompts, failed_prompts, 
              status, datetime.datetime.now().isoformat(), benchmark_id))
        
        cursor.execute("COMMIT")
        return prompt_id
        
    except sqlite3.Error as e:
        try:
            cursor.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # Transaction might not be active
        logging.error(f"SQLite error when saving benchmark prompt atomically: {e}")
        return None
    finally:
        conn.close()

def update_worker_heartbeat(benchmark_run_id: int, db_path: Path = Path.cwd()) -> bool:
    """Update the last heartbeat timestamp for a benchmark run."""
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f'''
            UPDATE {BENCHMARK_RUNS_TABLE}
            SET last_heartbeat = ?
            WHERE id = ?
        ''', (datetime.datetime.now().isoformat(), benchmark_run_id))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except sqlite3.Error as e:
        logging.error(f"Failed to update worker heartbeat: {e}")
        return False
    finally:
        conn.close()

def mark_prompt_failed(benchmark_run_id: int, prompt: str, error_message: str, 
                      db_path: Path = Path.cwd()) -> bool:
    """Mark a prompt as failed with an error message."""
    db_file = db_path / DB_NAME
    # Use WAL mode and timeout to handle concurrent access
    conn = sqlite3.connect(db_file, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN EXCLUSIVE")
        
        # Insert failed prompt
        cursor.execute(f'''
            INSERT INTO {BENCHMARK_PROMPTS_TABLE} 
            (benchmark_run_id, prompt, response, status, error_message, 
             started_at, completed_at, latency)
            VALUES (?, ?, '', 'failed', ?, ?, ?, 0)
        ''', (benchmark_run_id, prompt, error_message, 
              datetime.datetime.now().isoformat(), 
              datetime.datetime.now().isoformat()))
        
        # Get benchmark_id and update progress
        cursor.execute(f'''
            SELECT benchmark_id FROM {BENCHMARK_RUNS_TABLE} WHERE id = ?
        ''', (benchmark_run_id,))
        
        result = cursor.fetchone()
        if result:
            benchmark_id = result[0]
            
            # Update benchmark progress manually within this transaction
            # Count completed and failed prompts
            cursor.execute(f'''
                SELECT COUNT(*) 
                FROM {BENCHMARK_PROMPTS_TABLE} bp
                JOIN {BENCHMARK_RUNS_TABLE} br ON bp.benchmark_run_id = br.id
                WHERE br.benchmark_id = ? AND bp.status = 'completed'
            ''', (benchmark_id,))
            
            completed_prompts = cursor.fetchone()[0] or 0
            
            cursor.execute(f'''
                SELECT COUNT(*) 
                FROM {BENCHMARK_PROMPTS_TABLE} bp
                JOIN {BENCHMARK_RUNS_TABLE} br ON bp.benchmark_run_id = br.id
                WHERE br.benchmark_id = ? AND bp.status = 'failed'
            ''', (benchmark_id,))
            
            failed_prompts = cursor.fetchone()[0] or 0
            
            # Update benchmark counters
            cursor.execute(f'''
                UPDATE {BENCHMARKS_TABLE}
                SET completed_prompts = ?,
                    failed_prompts = ?,
                    updated_at = ?
                WHERE id = ?
            ''', (completed_prompts, failed_prompts, 
                  datetime.datetime.now().isoformat(), benchmark_id))
        
        cursor.execute("COMMIT")
        return True
        
    except sqlite3.Error as e:
        try:
            cursor.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # Transaction might not be active
        logging.error(f"Failed to mark prompt as failed: {e}")
        return False
    finally:
        conn.close()

def get_benchmark_sync_status(benchmark_id: int, db_path: Path = Path.cwd()) -> Dict[str, Any]:
    """
    Analyze a benchmark to determine what prompts need to be synced/rerun.
    
    Returns:
        Dict with sync analysis including missing, failed, and pending prompts
    """
    db_file = db_path / DB_NAME
    conn = sqlite3.connect(db_file, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get benchmark info including prompt set
        cursor.execute(f'''
            SELECT b.id, b.label, b.prompt_set_id, b.intended_models
            FROM {BENCHMARKS_TABLE} b
            WHERE b.id = ?
        ''', (benchmark_id,))
        
        benchmark_row = cursor.fetchone()
        if not benchmark_row:
            return {"error": f"Benchmark {benchmark_id} not found"}
        
        benchmark = dict(benchmark_row)
        
        # Get expected prompts from prompt set
        expected_prompts = []
        if benchmark['prompt_set_id']:
            cursor.execute(f'''
                SELECT prompt_text, order_index
                FROM {PROMPT_SET_ITEMS_TABLE}
                WHERE prompt_set_id = ?
                ORDER BY order_index
            ''', (benchmark['prompt_set_id'],))
            
            expected_prompts = [dict(row) for row in cursor.fetchall()]
        else:
            # For benchmarks without prompt sets, derive expected prompts from existing runs
            # Get all unique prompts that have been used in this benchmark
            cursor.execute(f'''
                SELECT DISTINCT bp.prompt
                FROM {BENCHMARK_PROMPTS_TABLE} bp
                JOIN {BENCHMARK_RUNS_TABLE} br ON bp.benchmark_run_id = br.id
                WHERE br.benchmark_id = ?
                ORDER BY bp.id
            ''', (benchmark_id,))
            
            prompt_rows = cursor.fetchall()
            expected_prompts = [
                {"prompt_text": row[0], "order_index": i} 
                for i, row in enumerate(prompt_rows)
            ]
        
        # Get intended models
        intended_models = []
        if benchmark['intended_models']:
            try:
                intended_models = json.loads(benchmark['intended_models'])
            except (json.JSONDecodeError, TypeError):
                intended_models = []
        
        # Get existing runs for this benchmark
        cursor.execute(f'''
            SELECT id as run_id, model_name, provider
            FROM {BENCHMARK_RUNS_TABLE}
            WHERE benchmark_id = ?
        ''', (benchmark_id,))
        
        all_runs = [dict(row) for row in cursor.fetchall()]
        
        sync_analysis = {
            "benchmark_id": benchmark_id,
            "benchmark_label": benchmark['label'],
            "expected_prompts": len(expected_prompts),
            "intended_models": intended_models,
            "existing_runs": [f"{run['model_name']}_{run['provider']}" for run in all_runs],
            "models_needing_sync": [],
            "total_prompts_to_sync": 0,
            "sync_needed": False
        }
        
        # For each intended model, check what prompts need syncing
        for model_name in intended_models:
            # Find ALL runs for this model
            model_runs = [run for run in all_runs if run['model_name'] == model_name]
            
            if not model_runs:
                # No run exists for this model - all prompts need to be created
                sync_analysis["models_needing_sync"].append({
                    "model_name": model_name,
                    "run_id": None,
                    "missing_prompts": len(expected_prompts),
                    "failed_prompts": 0,
                    "pending_prompts": 0,
                    "prompts_to_sync": expected_prompts,
                    "reason": "No run exists for this model"
                })
                sync_analysis["total_prompts_to_sync"] += len(expected_prompts)
                sync_analysis["sync_needed"] = True
                continue
            
            # Track prompts that need syncing (deduplicated by prompt text)
            prompts_needing_sync = {}  # prompt_text -> prompt_info
            
            # Check what prompts need syncing for this model
            for expected_prompt in expected_prompts:
                prompt_text = expected_prompt['prompt_text']
                
                # Check if this prompt was completed successfully in ANY run
                completed_successfully = False
                latest_failed_info = None
                latest_pending_info = None
                available_run_id = None
                
                for model_run in model_runs:
                    available_run_id = model_run['run_id']  # Track any available run ID
                    
                    # Get existing prompts for this specific run
                    cursor.execute(f'''
                        SELECT prompt, status, error_message, response
                        FROM {BENCHMARK_PROMPTS_TABLE}
                        WHERE benchmark_run_id = ? AND prompt = ?
                    ''', (model_run['run_id'], prompt_text))
                    
                    existing_prompt = cursor.fetchone()
                    
                    if existing_prompt:
                        existing_prompt = dict(existing_prompt)
                        
                        if existing_prompt['status'] == 'completed' and existing_prompt['response'] and not existing_prompt['response'].startswith('ERROR'):
                            # Found a successful completion - no need to sync this prompt
                            completed_successfully = True
                            break
                        elif existing_prompt['status'] == 'failed' or (existing_prompt['response'] and existing_prompt['response'].startswith('ERROR')):
                            # Track the latest failed attempt
                            latest_failed_info = {
                                "prompt_text": prompt_text,
                                "order_index": expected_prompt['order_index'],
                                "reason": "failed",
                                "status": existing_prompt['status'],
                                "error_message": existing_prompt['error_message'],
                                "response": existing_prompt['response'][:100] + "..." if len(existing_prompt['response']) > 100 else existing_prompt['response'],
                                "run_id": model_run['run_id']
                            }
                        elif existing_prompt['status'] in ['pending', 'in_progress']:
                            # Track the latest pending attempt
                            latest_pending_info = {
                                "prompt_text": prompt_text,
                                "order_index": expected_prompt['order_index'],
                                "reason": "pending",
                                "status": existing_prompt['status'],
                                "run_id": model_run['run_id']
                            }
                
                # If not completed successfully, add to sync list
                if not completed_successfully:
                    if latest_failed_info:
                        prompts_needing_sync[prompt_text] = latest_failed_info
                    elif latest_pending_info:
                        prompts_needing_sync[prompt_text] = latest_pending_info
                    else:
                        # Missing prompt - doesn't exist in any run
                        prompts_needing_sync[prompt_text] = {
                            "prompt_text": prompt_text,
                            "order_index": expected_prompt['order_index'],
                            "reason": "missing",
                            "status": None,
                            "run_id": available_run_id
                        }
            
            if prompts_needing_sync:
                # Count by reason
                missing_count = sum(1 for p in prompts_needing_sync.values() if p['reason'] == 'missing')
                failed_count = sum(1 for p in prompts_needing_sync.values() if p['reason'] == 'failed')
                pending_count = sum(1 for p in prompts_needing_sync.values() if p['reason'] == 'pending')
                
                sync_analysis["models_needing_sync"].append({
                    "model_name": model_name,
                    "run_id": model_runs[0]['run_id'],  # Use first run for compatibility
                    "missing_prompts": missing_count,
                    "failed_prompts": failed_count,
                    "pending_prompts": pending_count,
                    "prompts_to_sync": list(prompts_needing_sync.values()),
                    "reason": f"{missing_count} missing, {failed_count} failed, {pending_count} pending across {len(model_runs)} runs"
                })
                sync_analysis["total_prompts_to_sync"] += len(prompts_needing_sync)
                sync_analysis["sync_needed"] = True
        
        return sync_analysis
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error when analyzing benchmark sync status: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

def needs_sync(benchmark_id: int, db_path: Path = Path.cwd()) -> bool:
    """
    Quick check if a benchmark needs syncing.
    
    Returns:
        True if the benchmark has missing, failed, or pending prompts
    """
    sync_status = get_benchmark_sync_status(benchmark_id, db_path)
    return sync_status.get("sync_needed", False)