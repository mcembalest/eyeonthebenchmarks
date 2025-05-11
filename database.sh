sqlite3 eotm_file_store.sqlite \
".mode column" \
".headers on" \
"SELECT SUBSTR(pdf_hash, 1, 8) AS pdf_h, SUBSTR(openai_file_id, 1, 12) AS oai_id, original_filename AS fname, SUBSTR(upload_timestamp, 1, 16) AS uploaded FROM openai_file_map;" \
"SELECT id, SUBSTR(timestamp, 1, 16) AS created, label, SUBSTR(description, 1, 25) || '...' AS desc FROM benchmarks;" \
"SELECT id, benchmark_id, SUBSTR(file_path, LENGTH(RTRIM(file_path, REPLACE(file_path, '/', ''))) + 1) AS fname FROM benchmark_files;" \
"SELECT id, benchmark_id, SUBSTR(model_name, 1, 20) AS model, PRINTF('%.1f', latency) AS lat_s, SUBSTR(created_at, 1, 16) AS run_at, total_input_tokens AS in_tok, total_output_tokens AS out_tok, total_tokens AS tot_tok, SUBSTR(report, 1, 20) || '...' AS report_sum FROM benchmark_runs ORDER BY created_at DESC;" \
"SELECT id, benchmark_run_id AS run_id, score, PRINTF('%.1f', latency) AS lat_s, input_tokens, output_tokens, scoring_config_id AS sc_cfg_id FROM benchmark_prompts WHERE benchmark_run_id IN (SELECT id FROM benchmark_runs ORDER BY created_at DESC LIMIT 2) ORDER BY benchmark_run_id DESC, id ASC;" \
"SELECT id, name, SUBSTR(config, 1, 30) || '...' AS cfg_sum FROM scoring_configs;" \
"SELECT id, benchmark_id, SUBSTR(compared_models, 1, 25) || '...' AS models_json, SUBSTR(report, 1, 20) || '...' AS report_sum, SUBSTR(created_at, 1, 16) AS created FROM benchmark_reports ORDER BY created_at DESC;"