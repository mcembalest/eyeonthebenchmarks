# EOTM Benchmark Todos

## Cost Calculation Implementation

### Completed
- [x] Centralized `cost_calculator.py` module
- [x] Support for OpenAI and Google Gemini models
- [x] Pricing for standard and cached input tokens
- [x] Image and web search cost support
- [x] Cost estimation integrated in benchmark runs

### Remaining
- [ ] Robust error handling for API rate limits
- [ ] Caching layer for cost calculations
- [ ] Unit tests for cost calculation functions
- [ ] Support additional providers (Anthropic, etc.)

## Benchmark CSV Export

### Completed
- [x] Dynamic CSV export in `AppLogic.handle_export_benchmark_csv`
- [x] Automatic database schema discovery for prompt export
- [x] Safe directory creation when exporting to current directory

### Remaining
- [ ] Frontend integration for CSV download button
- [ ] Provide download link in Electron UI
- [ ] Unit tests for CSV export functionality

## Migration to Electron

### Completed
- [x] Node.js and Electron architecture
- [x] Main process with IPC and Python bridge
- [x] Preload script exposing secure API
- [x] Renderer process and UI components
- [x] IPC handlers and event listeners for progress updates

## Core Focus & Application Goals
- [HIGH PRIORITY] Ensure overall benchmark creation and deployment process is extremely frictionless, especially for non-AI users.
- [HIGH PRIORITY] Enable easy export of benchmark results to **CSV files** (for analysis and chart creation in tools like Excel).
- [x] Decouple application logic from Qt
- [ ] Implement VBA macro reception (if for Python-side execution of user-defined scoring logic, otherwise re-evaluate)
- [ ] Allow model customization (beyond predefined list)

## UI
- [ ] Display model icon next to model name consistently (including benchmark creation dropdown)
- [ ] Improve UI responsiveness during benchmark runs
- [ ] Add progress indicators for long operations (file uploads, benchmark runs)

## Models
### OpenAI
- [x] Add support for gpt4o (+mini) (currently `[done]`)
- [x] Add support for gpt4.1 (+mini, nano) (currently `[done]`)
- [x] **BUG**: gpt 4.1 nano did not save results even after a successful run (FIXED)
- [ ] Add support for o3-mini
- [ ] Add support for o3
- [ ] Add support for o4-mini
- [ ] Add support for gpt-image-1 (Likely an image generation model, see "Image Generation Benchmarks")

### Google
- [ ] Add support for Gemini 2.5 Flash
- [ ] Add support for Gemini 2.5 Pro
- [ ] (Consider Gemini models for image generation if applicable)
- [ ] Implement Google API client with proper authentication

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
- [x] **BUG**: Incorrect token count (FIXED - now correctly handling standard and cached tokens separately)
- [ ] Replace 'Answer' with 'Response' in UI and data structures where appropriate (clarify if 'Expected Answer' vs 'Model Response')

### Benchmark Creation
## Benchmark Execution

~~Currently, the benchmark creation process uses placeholder/filler data instead of actually running the models.~~ 

The benchmark execution now uses real OpenAI API calls with token counting and cost calculation. The following tasks represent the current state and future enhancements:

### API Integration
- [x] Integrate OpenAI models directly via `models_openai.py`
  - [x] Implement proper API key handling via environment variables
  - [x] Add token counting for OpenAI models (standard and cached tokens)
- [x] Create additional model-specific API clients for other providers
  - [x] Create dedicated Google API client for Gemini models

### Benchmark Engine
- [x] Update `run_benchmark.py` to use real API calls instead of placeholder data
  - [x] Replace the placeholder code with actual API calls to the respective model providers (OpenAI implemented)
  - [x] Implement proper error handling for API rate limits, token limits, etc.
  - [x] Add progress reporting via IPC to show real-time benchmark status
  - [x] Implement proper token counting for both standard and cached inputs
  - [x] Calculate actual costs based on model pricing

### Scoring Implementation
- [x] Implement benchmark scoring for comparing expected vs. actual answers
  - [x] Basic exact match scoring
  - [x] Partial match scoring with length-based weighting
  - [x] Word overlap detection for partial credit
  - [ ] Semantic similarity scoring using embeddings (future enhancement)
  - [ ] Custom scoring functions for specific benchmark types

### UI Improvements
- [x] Add progress tracking in logs for models being benchmarked
- [x] Display token usage and cost estimates in benchmark details
- [x] Improve the benchmark results display with detailed metrics (standard/cached tokens, costs)
- [ ] Add real-time progress visualization in the UI
- [ ] Streamline the process of setting up prompts and expected outputs
- [ ] Add template prompts for common benchmark scenarios

## Code Structure Analysis and Cleanup Plan

The repository currently contains several redundant and overlapping Python files that need to be organized and consolidated. This section outlines which files to keep, which to delete, and the recommended structure for future development.

### Key Files to Keep

| File | Purpose | Status |
|------|---------|--------|
| `file_store.py` | Core database functionality | KEEP - Central database management module |
| `models_openai.py` | OpenAI API integration | KEEP - Primary API client for OpenAI models |
| `exporter.py` | CSV export functionality | KEEP - Handles benchmark data export |
| `run_benchmark.py` | Electron UI bridge for running benchmarks | KEEP - Recently updated to use real models |
| `list_benchmarks.py` | Electron UI bridge for listing benchmarks | KEEP - Required for Electron integration |
| `get_benchmark_details.py` | Electron UI bridge for benchmark details | KEEP - Required for Electron integration |
| `export_benchmark.py` | Electron UI bridge for CSV export | KEEP - Implements exporter integration |

### Files to Deprecate/Remove

| File | Reason | Replacement |
|------|--------|-------------|
| `old_qt (archived)/runner.py` | Redundant with `run_benchmark.py` | Use `run_benchmark.py` for benchmark execution (moved to archived folder) |
| `app.py` | Qt-specific application logic | Useful parts incorporated into Electron bridge scripts |
| `old_qt (archived)/*` | Legacy Qt UI files | Already replaced by Electron interface |
| `test_script.py` | Likely just for testing | Remove if not needed for automated tests |

### Implementation Plan

1. **Consolidate Core Functionality**
   - [x] Verify all needed functionality from `/runner.py` is in `run_benchmark.py`
   - [x] Ensure `file_store.py` is used consistently across all scripts instead of direct SQL queries
   - [x] Extract any useful logic from `app.py` into the appropriate bridge scripts

2. **Improve API Integration**
   - [x] Implement proper API clients for OpenAI models
   - [x] Implement API clients for Google models
   - [ ] Implement API clients for additional model providers (Anthropic, etc.)
   - [x] Add token counting and cost calculation for OpenAI models
   - [x] Add token counting and cost calculation for Google models
   - [x] Implement caching mechanism to avoid redundant API calls (using file hash for OpenAI)

3. **Standardize Error Handling and Logging**
   - [x] Implement consistent logging across all bridge scripts
   - [x] Add proper error handling with detailed error messages for troubleshooting
   - [x] Update log file paths to use relative paths instead of hardcoded absolute paths

### CSV Export Functionality
- [x] Implement CSV export functionality for benchmark results
- [ ] Add option to export raw response data for further analysis
- [ ] Ensure proper formatting of token counts and costs in CSV exports
- [ ] Add header information with benchmark metadata

### Additional Features
- [ ] Allow loading images as part of benchmark questions (especially for multi-modal models)
- [ ] Fix pasting text into the spreadsheet component (ensure smooth data entry)
- [ ] Restrict "Open Prompts CSV" button to only the new benchmark creation page (remove from homepage for clarity)
- [ ] **BUG**: Creating new benchmarks does not work correctly - investigate and fix
- [ ] **BUG**: Ensure new benchmarks are properly saved to the database with correct IDs

### Benchmark Execution & Sync
- [x] Navigate to home screen after hitting 'Start'/'Run' (instead of console) (currently `[done]`)
- [ ] Implement "Sync" functionality: Rerun a benchmark to fill in only missing prompt runs (e.g., new model or new questions on existing benchmark)
- [ ] Use batch API by default for runs exceeding a certain threshold (cost/efficiency)
- [ ] Allow running multiple benchmarks concurrently in the background
- [ ] Allow running a benchmark with different models easily
- [ ] Simplify running a new model on an existing benchmark (e.g., view benchmark, see run models, click to add new model run)

### Reporting & Plotting
- [HIGH PRIORITY] Generate **CSV files** that users can easily use to make charts.
- [ ] Implement exporter.py to generate detailed CSV exports with all metrics
- [ ] Auto-update relevant reports and plots within the app when new runs are added (long-term)
- [ ] Add custom report templates for different analysis needs

### Contexts for Benchmarks
- [HIGH PRIORITY] Allow flexible context configuration.
- [x] Support specific PDF as context (currently `[done]`)
- [ ] Support a directory of files as context (models to access multiple sources simultaneously)
    - [ ] Modify `runner.run_benchmark` to accept a list of file paths or a directory path.
    - [ ] Update PDF pre-flight checks in `runner.run_benchmark` for multiple files.
    - [ ] Adapt `file_store` and `models_openai.openai_upload` for lists of files / multiple OpenAI file IDs.
    - [ ] Investigate how OpenAI `responses` API handles multiple `file_id`s; update `openai_ask`.
    - [ ] UI: Allow selection of a directory or multiple files in ComposerPage.
- [ ] Support internet search as context
    - [ ] Allow configurable internet search modes (e.g., open loop/extensive research vs. quick lookup)
    - [ ] Design mechanism in `runner.run_benchmark` to enable/configure internet search.
    - [ ] In `models_openai`, determine strategy for internet search with `responses` API (direct instruction or pre-fetch results).
    - [ ] UI: Add options in ComposerPage to enable and configure internet search modes.
- [ ] Explore "deep research" capabilities (note: official APIs might be limited)
- [ ] UI: Clearly display PDF/context limitations (file size, page count, token limits from `runner.py`) to the user during the benchmark setup phase in `ComposerPage`.
- [ ] Consider adding an option for Optical Character Recognition (OCR) for image-based PDFs - low priority.

### Metrics
## Cost Calculation and Reporting

### Core Functionality
- [x] Define database schema to store standard input tokens and cached input tokens separately
- [x] Update runner.py to track and return standard_input_tokens, cached_input_tokens, and output_tokens separately
- [x] Define and store pricing tiers for different models
- [x] Modify token processing to differentiate and record token types
- [x] Implement cost calculation based on token breakdown and model-specific pricing
- [x] Add cost breakdown to benchmark results

### Model Support
- [x] OpenAI models with proper token tracking
- [x] Google models with proper token tracking
- [x] Image generation model (GPT-Image-1)

### UI/Reporting
- [x] Add cost information to benchmark results
- [ ] Add detailed cost breakdowns in benchmark views
- [ ] Include cost breakdowns in CSV exports
- [ ] Add cost visualization to dashboard

### Future Enhancements
- [ ] Add support for more granular cost tracking
- [ ] Implement cost forecasting
- [ ] Add budget tracking and alerts
- [x] Measure latency per candidate (implemented - each prompt result includes latency_ms)
- [ ] Measure reasoning cost accurately (re-evaluate if distinct from token costs or if it implies a different metric)

## Image Generation Benchmarks

### Core Features
- [x] Support for GPT-Image-1
- [x] Cost calculation for image generation
- [x] Support for different image sizes and qualities
- [x] Integration with benchmark runner

### Future Enhancements
- [ ] Add more image generation models
- [ ] Implement image quality metrics
- [ ] Add support for image editing workflows
- [HIGH PRIORITY] Enable benchmarking of image generation models.
- [ ] Integrate support for image generation models
- [ ] Allow defining constraints for image generation prompts (e.g., "must include X," "must not include Y," style guidance)
- [ ] Develop/Integrate scoring mechanisms for image outputs (see Scoring section)
    - [ ] Explore system-defined image scoring (e.g., CLIP scores, aesthetic scores if available via API)
    - [ ] Explore user-provided/manual image scoring rubrics
- [ ] Implement image storage and retrieval in the database

## Scoring
### Core Functionality
- [x] Basic scoring: check for expected answer in output (currently `[done]` - implemented in simple_score function in runner.py)
- [ ] Make scoring configurable during benchmark setup (dropdown of choices, beyond `expected in output`)
- [ ] Handle image outputs for scoring (critical for Image Generation Benchmarks)
- [ ] Allow scoring configuration via Visual Basic macros (if for Python-side execution of user-defined scoring logic)
- [ ] Allow custom scoring item by item (varied correctness logic per question)
- [ ] Implement manual user review as a scoring mechanism
    - [ ] Support blind manual review (A/B testing for subjective evaluations)
- [ ] Add semantic similarity scoring option (not just substring matching)

## Architecture & Performance Improvements
- [x] Implement UI bridge pattern for better separation of concerns (implemented in ui_bridge.py)
- [ ] Optimize file handling for large PDFs (streaming approach instead of loading entire content)
- [ ] Add comprehensive error handling and recovery mechanisms
- [ ] Implement caching layer for frequently accessed data
- [ ] Add automated testing for core functionality
- [ ] Improve multithreading to prevent UI freezing during operations

## Database & Data Access Improvements
- [x] Fixed the database path in scripts to correctly point to eotm_file_store.sqlite
- [x] Implemented correct handling of schema with standard_input_tokens and cached_input_tokens stored separately
- [x] Created load_benchmarks.sh script that runs list_benchmarks.py and saves output to benchmark_data.json
- [x] Modified the Electron app to read benchmark data from JSON file instead of executing Python each time
- [x] Updated get_benchmark_details.py to use the correct database schema and relationships
- [ ] **CRITICAL BUG**: Fix ID mismatch between benchmarks table (IDs 6, 7) and benchmark_runs table (IDs 8, 9 with foreign keys 6, 7)
- [ ] Update get_benchmark_details.py to distinguish between benchmark IDs and run IDs
- [ ] Ensure benchmark_data.json is properly regenerated when new benchmarks are created
- [ ] Investigate issues with creating new benchmarks and ensure they're saved correctly
- [ ] Add more robust error handling and debugging information in Python-Electron bridge
- [ ] Consider implementing a proper API layer between Python and Electron for better integration