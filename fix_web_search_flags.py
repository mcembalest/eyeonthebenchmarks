#!/usr/bin/env python3
"""
Fix web_search_used flags in existing database records.

This script corrects cases where web_search_sources exist but web_search_used is incorrectly set to 0.
This commonly happened with Claude models due to a bug in the Anthropic model handler.
"""

import sqlite3
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fix_web_search_flags(db_path: Path = Path.cwd()):
    """Fix web_search_used flags where sources exist but flag is False."""
    
    db_file = db_path / 'eotb_file_store.sqlite'
    if not db_file.exists():
        logging.error(f"Database not found: {db_file}")
        return
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Find records where web_search_used is 0 but web_search_sources is not empty
        cursor.execute("""
            SELECT bp.id, br.model_name, length(bp.web_search_sources) as sources_length
            FROM benchmark_prompts bp
            JOIN benchmark_runs br ON bp.benchmark_run_id = br.id
            WHERE bp.web_search_used = 0 
            AND bp.web_search_sources IS NOT NULL 
            AND trim(bp.web_search_sources) != ''
            AND length(bp.web_search_sources) > 10
            ORDER BY bp.id
        """)
        
        records = cursor.fetchall()
        
        if not records:
            logging.info("No records found that need fixing.")
            return
        
        logging.info(f"Found {len(records)} records that need fixing:")
        
        # Group by model for reporting
        models = {}
        for record_id, model_name, sources_length in records:
            if model_name not in models:
                models[model_name] = []
            models[model_name].append((record_id, sources_length))
        
        for model_name, model_records in models.items():
            logging.info(f"  {model_name}: {len(model_records)} records")
            for record_id, sources_length in model_records:
                logging.info(f"    ID {record_id}: {sources_length} chars of web search sources")
        
        # Ask for confirmation
        print(f"\nFound {len(records)} records with web search sources but web_search_used = 0")
        print("These will be updated to set web_search_used = 1")
        
        user_input = input("Continue with the fix? (y/N): ").strip().lower()
        if user_input != 'y':
            logging.info("Fix cancelled by user.")
            return
        
        # Update the records
        logging.info("Updating records...")
        
        record_ids = [record[0] for record in records]
        placeholders = ','.join(['?' for _ in record_ids])
        
        cursor.execute(f"""
            UPDATE benchmark_prompts 
            SET web_search_used = 1 
            WHERE id IN ({placeholders})
        """, record_ids)
        
        updated_count = cursor.rowcount
        conn.commit()
        
        logging.info(f"Successfully updated {updated_count} records.")
        
        # Verify the fix
        cursor.execute("""
            SELECT bp.id, br.model_name, bp.web_search_used, length(bp.web_search_sources) as sources_length
            FROM benchmark_prompts bp
            JOIN benchmark_runs br ON bp.benchmark_run_id = br.id
            WHERE bp.id IN ({})
        """.format(placeholders), record_ids)
        
        verification_records = cursor.fetchall()
        
        logging.info("Verification:")
        for record_id, model_name, web_search_used, sources_length in verification_records:
            logging.info(f"  ID {record_id} ({model_name}): web_search_used = {web_search_used}, sources = {sources_length} chars")
        
        print(f"\n✅ Fix completed! Updated {updated_count} records.")
        print("The web search results should now appear in the UI.")
        
    except Exception as e:
        logging.error(f"Error fixing web search flags: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    fix_web_search_flags() 