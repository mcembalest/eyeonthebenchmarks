#!/bin/bash

echo "=================================================================="
echo "DATABASE EXPLORER FOR eotm_file_store.sqlite"
echo "=================================================================="

sqlite3 eotm_file_store.sqlite << 'EOSQL'
.mode column
.headers on

-----------------------------------------------------------------------
SELECT '## TABLE 1: openai_file_map - PDF Files' AS 'TABLE INFO';
-----------------------------------------------------------------------

PRAGMA table_info(openai_file_map);
SELECT CASE WHEN COUNT(*) = 0 THEN '[No data in openai_file_map table]' ELSE '[DATA]' END AS note FROM openai_file_map;
SELECT pdf_hash, openai_file_id, original_filename AS fname, upload_timestamp FROM openai_file_map;

-----------------------------------------------------------------------
SELECT '## TABLE 2: benchmarks - Benchmark Definitions' AS 'TABLE INFO';
-----------------------------------------------------------------------

SELECT CASE WHEN COUNT(*) = 0 THEN '[No data in benchmarks table]' ELSE '[DATA]' END AS note FROM benchmarks;
SELECT id, timestamp, label, description FROM benchmarks;

-----------------------------------------------------------------------
SELECT '## TABLE 3: benchmark_files - Files Used In Benchmarks' AS 'TABLE INFO';
-----------------------------------------------------------------------

SELECT CASE WHEN COUNT(*) = 0 THEN '[No data in benchmark_files table]' ELSE '[DATA]' END AS note FROM benchmark_files;
SELECT id, benchmark_id, file_path FROM benchmark_files;

-----------------------------------------------------------------------
SELECT '## TABLE 4: benchmark_runs - Model Run Results' AS 'TABLE INFO';
-----------------------------------------------------------------------

SELECT CASE WHEN COUNT(*) = 0 THEN '[No data in benchmark_runs table]' ELSE '[DATA]' END AS note FROM benchmark_runs;
SELECT id, benchmark_id, model_name, latency, created_at, 
       total_standard_input_tokens, total_cached_input_tokens, 
       total_output_tokens, total_tokens, report 
FROM benchmark_runs ORDER BY created_at DESC;

-----------------------------------------------------------------------
SELECT '## TABLE 5: benchmark_prompts - Individual Prompt Results' AS 'TABLE INFO';
-----------------------------------------------------------------------

SELECT CASE 
  WHEN (SELECT COUNT(*) FROM benchmark_prompts WHERE benchmark_run_id IN (SELECT id FROM benchmark_runs ORDER BY created_at DESC LIMIT 2)) = 0 
  THEN '[No recent data in benchmark_prompts table]' 
  ELSE '[DATA]' 
END AS note;

SELECT id, benchmark_run_id, SUBSTR(prompt, 1, 30) || CASE WHEN LENGTH(prompt) > 30 THEN '...' ELSE '' END AS prompt_preview, 
       SUBSTR(answer, 1, 20) || CASE WHEN LENGTH(answer) > 20 THEN '...' ELSE '' END AS answer_preview, 
       score, latency, standard_input_tokens, cached_input_tokens, output_tokens
FROM benchmark_prompts 
WHERE benchmark_run_id IN (SELECT id FROM benchmark_runs ORDER BY created_at DESC LIMIT 2) 
ORDER BY benchmark_run_id DESC, id ASC;

-----------------------------------------------------------------------
SELECT '## TABLE 6: scoring_configs - Scoring Configurations' AS 'TABLE INFO';
-----------------------------------------------------------------------

SELECT CASE WHEN COUNT(*) = 0 THEN '[No data in scoring_configs table]' ELSE '[DATA]' END AS note FROM scoring_configs;
SELECT id, name, SUBSTR(config, 1, 50) || CASE WHEN LENGTH(config) > 50 THEN '...' ELSE '' END AS config_preview FROM scoring_configs;

-----------------------------------------------------------------------
SELECT '## TABLE 7: benchmark_reports - Comparative Reports' AS 'TABLE INFO';
-----------------------------------------------------------------------

SELECT CASE WHEN COUNT(*) = 0 THEN '[No data in benchmark_reports table]' ELSE '[DATA]' END AS note FROM benchmark_reports;
SELECT id, benchmark_id, compared_models, SUBSTR(report, 1, 30) || CASE WHEN LENGTH(report) > 30 THEN '...' ELSE '' END AS report_preview, created_at 
FROM benchmark_reports ORDER BY created_at DESC;
EOSQL

echo "=================================================================="
echo "End of Database Explorer"
echo "=================================================================="