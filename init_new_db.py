#!/usr/bin/env python3
"""
Initialize the new multi-provider file database schema.
This script will wipe the existing database and create a fresh one with the new schema.
"""

import os
import logging
from pathlib import Path
from file_store import init_db, DB_NAME

def main():
    """Initialize the new database schema."""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    db_path = Path.cwd()
    db_file = db_path / DB_NAME
    
    print("🗄️  Database Initialization Script")
    print("=" * 50)
    print(f"Database file: {db_file}")
    
    # Check if database exists
    if db_file.exists():
        print(f"⚠️  Existing database found at {db_file}")
        print(f"   Size: {db_file.stat().st_size / 1024:.1f} KB")
        
        response = input("\n❓ Do you want to DELETE the existing database and create a new one? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            print("🗑️  Deleting existing database...")
            db_file.unlink()
            print("✅ Existing database deleted")
        else:
            print("❌ Aborted. Existing database preserved.")
            return
    
    print("\n🏗️  Creating new database with multi-provider schema...")
    
    try:
        init_db(db_path)
        print("✅ Database initialized successfully!")
        
        print(f"\n🎉 Ready to use! Database created at: {db_file}")
        
        # Verify the new functions work
        print("\n🔍 Verifying new multi-provider functions...")
        try:
            from file_store import (
                register_file, get_provider_file_id, register_provider_upload,
                save_benchmark, get_benchmark_files, save_benchmark_run, save_benchmark_prompt,
                load_benchmark_details, find_benchmark_by_files, update_benchmark_details,
                load_all_benchmarks_with_models, update_benchmark_model, update_benchmark_status
            )
            print("  ✅ All file_store functions imported successfully")
            
            # Test loading (should return empty list for new DB)
            benchmarks = load_all_benchmarks_with_models(db_path)
            print(f"  ✅ load_all_benchmarks_with_models: {len(benchmarks)} benchmarks found")
            
            print("\n🚀 Database is ready for multi-provider benchmarking!")
            
        except ImportError as e:
            print(f"  ❌ Import error: {e}")
            return 1
        except Exception as e:
            print(f"  ❌ Verification error: {e}")
            return 1
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        logging.error(f"Database initialization failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 