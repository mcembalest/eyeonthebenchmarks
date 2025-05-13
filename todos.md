# EOTM Benchmark Todos

## Core Focus & Application Goals
- [HIGH PRIORITY] Ensure overall benchmark creation and deployment process is extremely frictionless, especially for non-AI users.
- [HIGH PRIORITY] Enable easy export of benchmark results to **CSV files** (for analysis and chart creation in tools like Excel).
- [ ] (Clarify) No direct application-to-Excel integration needed. Output is CSV.
- [ ] Decouple application logic from Qt (currently `[started]`)
- [ ] Implement VBA macro reception (if for Python-side execution of user-defined scoring logic, otherwise re-evaluate)
- [ ] Allow model customization (beyond predefined list)

## UI
- [ ] Display model icon next to model name consistently (including benchmark creation dropdown)

## Models
### OpenAI
- [ ] Add support for gpt4o (+mini)
- [ ] Add support for gpt4.1 (+mini, nano)
- [x] **BUG**: gpt 4.1 nano did not save results even after a successful run (FIXED)
- [ ] Add support for o3-mini
- [ ] Add support for o3
- [ ] Add support for o4-mini
- [ ] Add support for gpt-image-1 (Likely an image generation model, see "Image Generation Benchmarks")

### Google
- [ ] Add support for Gemini 2.5 Flash
- [ ] Add support for Gemini 2.5 Pro
- [ ] (Consider Gemini models for image generation if applicable)

## Cloud Providers & File Handling
### File Upload & Sync
- [x] **OpenAI**: Ensure files are sent after upload and not re-uploaded (check local DB) (currently `[done]`)
- [ ] **Google**: Implement file sending after upload (check local DB, avoid re-uploads)

### File Preprocessing (Indexes/Vector Stores)
- [ ] **OpenAI**: Preprocess files into indexes/vector stores in advance.
    - [ ] Create vector stores for all context files upon initial processing.
    - [ ] Use vector stores strategically: especially for very long documents (e.g., >N pages/tokens) where direct prompting is infeasible. Prefer full-text context for shorter documents.
- [ ] **Google**: Preprocess files into indexes/vector stores in advance (similar strategy).
    - [ ] Investigate using Google Cloud/Storage/Drive for Gemini.
    - [ ] Investigate using Vertex AI for Google models.

## Benchmarks
### Core Functionality
- [x] Save benchmarks (currently `[done]`)
- [x] Load benchmarks (currently `[done]`)
- [x] View benchmarks from load screen (currently `[done]`)
- [x] Create benchmarks from a CSV (currently `[done]`)
- [ ] **BUG**: New benchmark overwrites the last benchmark (Needs re-verification given user feedback)
- [x] **BUG**: Incorrect token count (FIXED)
- [ ] Replace 'Answer' with 'Response' in UI and data structures where appropriate (clarify if 'Expected Answer' vs 'Model Response')

### Benchmark Creation
- [HIGH PRIORITY] Streamline the process of setting up prompts and expected outputs.
- [ ] Allow loading images as part of benchmark questions (especially for multi-modal models)
- [ ] Fix pasting text into the spreadsheet component (ensure smooth data entry)
- [ ] Restrict "Open Prompts CSV" button to only the new benchmark creation page (remove from homepage for clarity)

### Benchmark Execution & Sync
- [x] Navigate to home screen after hitting 'Start'/'Run' (instead of console) (currently `[done]`)
- [ ] Implement "Sync" functionality: Rerun a benchmark to fill in only missing prompt runs (e.g., new model or new questions on existing benchmark)
- [ ] Use batch API by default for runs exceeding a certain threshold (cost/efficiency)
- [ ] Allow running multiple benchmarks concurrently in the background
- [ ] Allow running a benchmark with different models easily
- [ ] Simplify running a new model on an existing benchmark (e.g., view benchmark, see run models, click to add new model run)

### Reporting & Plotting
- [HIGH PRIORITY] Generate **CSV files** that users can easily use to make charts.
- [ ] Auto-update relevant reports and plots within the app when new runs are added (long-term)

### Contexts for Benchmarks
- [HIGH PRIORITY] Allow flexible context configuration.
- [x] Support specific PDF as context (currently `[done]`)
- [ ] Support a directory of files as context (models to access multiple sources simultaneously)
    - [ ] Modify `engine.runner.run_benchmark` to accept a list of file paths or a directory path.
    - [ ] Update PDF pre-flight checks in `engine.runner.run_benchmark` for multiple files.
    - [ ] Adapt `engine.file_store` and `engine.models_openai.openai_upload` for lists of files / multiple OpenAI file IDs.
    - [ ] Investigate how OpenAI `responses` API handles multiple `file_id`s; update `openai_ask`.
    - [ ] UI: Allow selection of a directory or multiple files in ComposerPage.
- [ ] Support internet search as context
    - [ ] Allow configurable internet search modes (e.g., open loop/extensive research vs. quick lookup)
    - [ ] Design mechanism in `engine.runner.run_benchmark` to enable/configure internet search.
    - [ ] In `engine.models_openai`, determine strategy for internet search with `responses` API (direct instruction or pre-fetch results).
    - [ ] UI: Add options in ComposerPage to enable and configure internet search modes.
- [ ] Explore "deep research" capabilities (note: official APIs might be limited)
- [ ] UI: Clearly display PDF/context limitations (file size, page count, token limits from `runner.py`) to the user during the benchmark setup phase in `ComposerPage`.
- [ ] Consider adding an option for Optical Character Recognition (OCR) for image-based PDFs - low priority.


### Metrics
- [MAJOR TODO] Accurately Calculate and Report Cost per Candidate, incorporating KV Caching.
    - [ ] Define and store pricing tiers for different models (e.g., GPT-4.1: $2.00/$0.50/$8.00, GPT-4.1-mini: $0.40/$0.10/$1.60, GPT-4.1-nano: $0.100/$0.025/$0.400 per 1M input/cached-input/output tokens respectively).
    - [ ] Modify token processing to differentiate and record: standard input tokens, **cached input tokens**, and output tokens for each prompt run.
    - [ ] Research and implement mechanisms with the OpenAI `responses` API to:
        - [ ] Reliably trigger KV caching for repeated token prefixes.
        - [ ] Verify or get confirmation from API responses if caching was utilized (if possible).
    - [ ] Update `benchmark_prompts` table (or add new table) in `engine/file_store.py` to store detailed token breakdown (standard input, cached input, output).
    - [ ] Implement logic to calculate cost based on this detailed token breakdown and model-specific pricing.
    - [ ] Aggregate and display detailed cost breakdowns in benchmark views and CSV exports.
- [ ] Measure latency per candidate (already implemented, verify consistency)
- [ ] Measure reasoning cost accurately (re-evaluate if distinct from token costs or if it implies a different metric)

## Image Generation Benchmarks
- [HIGH PRIORITY] Enable benchmarking of image generation models.
- [ ] Integrate support for image generation models (e.g., gpt-image-1, DALL-E series, Gemini vision)
- [ ] Allow defining constraints for image generation prompts (e.g., "must include X," "must not include Y," style guidance)
- [ ] Develop/Integrate scoring mechanisms for image outputs (see Scoring section)
    - [ ] Explore system-defined image scoring (e.g., CLIP scores, aesthetic scores if available via API)
    - [ ] Explore user-provided/manual image scoring rubrics

## Scoring
### Core Functionality
- [x] Basic scoring: check for expected answer in output (currently `[done]`)
- [ ] Make scoring configurable during benchmark setup (dropdown of choices, beyond `expected in output`)
- [ ] Handle image outputs for scoring (critical for Image Generation Benchmarks)
- [ ] Allow scoring configuration via Visual Basic macros (if for Python-side execution of user-defined scoring logic)
- [ ] Allow custom scoring item by item (varied correctness logic per question)
- [ ] Implement manual user review as a scoring mechanism
    - [ ] Support blind manual review (A/B testing for subjective evaluations)