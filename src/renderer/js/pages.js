/**
 * Page management and navigation
 */

class Pages {
  constructor() {
    this.currentPage = 'homeContent';
    this.benchmarksData = [];
    this.deletedBenchmarkIds = new Set();
    this.currentView = 'grid'; // 'grid' or 'table'
    this.selectedPdfPaths = []; // Changed from selectedPdfPath to array
    this.prompts = [];
    this.selectedModels = [];
    this.refreshInterval = null; // For auto-refreshing running benchmarks
    
    // Initialize prompt set properties
    this.promptSetPrompts = [];
    this.currentPromptSetId = null;
    
    // Initialize header actions for the default page immediately
    // Use requestAnimationFrame for better performance than setTimeout
    requestAnimationFrame(() => {
      this.updateHeaderActions(this.currentPage);
    });
  }

  /**
   * Navigate to a specific page
   * @param {string} pageId - Page ID to navigate to
   */
  navigateTo(pageId) {
    // Clear refresh interval when navigating away from details page
    if (this.currentPage === 'detailsContent' && pageId !== 'detailsContent') {
      if (this.refreshInterval) {
        clearInterval(this.refreshInterval);
        this.refreshInterval = null;
      }
    }

    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
      page.classList.remove('active');
    });

    // Show target page
    const targetPage = document.getElementById(pageId);
    if (targetPage) {
      targetPage.classList.add('active');
      this.currentPage = pageId;

      // Manage body classes for page-specific styling
      document.body.classList.remove('composer-active', 'details-active', 'prompt-set-active');
      if (pageId === 'composerContent') {
        document.body.classList.add('composer-active');
      } else if (pageId === 'detailsContent') {
        document.body.classList.add('details-active');
      } else if (pageId === 'promptSetContent') {
        document.body.classList.add('prompt-set-active');
      }

      // Update header actions
      this.updateHeaderActions(pageId);

      // Page-specific initialization
      switch (pageId) {
        case 'homeContent':
          this.initHomePage();
          break;
        case 'composerContent':
          this.initComposerPage();
          break;
        case 'promptSetContent':
          this.initPromptSetPage();
          break;
        case 'detailsContent':
          // Details page initialization is handled by viewBenchmarkDetails
          break;
      }
    } else {
      console.error(`Page ${pageId} not found`);
    }
  }

  /**
   * Update header actions based on current page
   * @param {string} pageId - Current page ID
   */
  updateHeaderActions(pageId) {
    const headerActions = document.getElementById('headerActions');
    
    switch (pageId) {
      case 'homeContent':
        headerActions.innerHTML = `
          <button class="btn btn-primary me-2" onclick="window.Pages.navigateTo('composerContent')">
            <i class="fas fa-plus"></i> New Benchmark
          </button>
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('promptSetContent')">
            <i class="fas fa-layer-group"></i> Prompts
          </button>
        `;
        break;
      case 'composerContent':
        headerActions.innerHTML = `
          <button class="btn btn-success me-2" id="runBenchmarkBtn">
            <i class="fas fa-play"></i> Run Benchmark
          </button>
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
        `;
        break;
      case 'promptSetContent':
        headerActions.innerHTML = `
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
        `;
        break;
      case 'detailsContent':
        headerActions.innerHTML = `
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
        `;
        break;
      default:
        headerActions.innerHTML = '';
    }
  }

  /**
   * Initialize home page
   */
  async initHomePage() {
    console.log('Pages.initHomePage called');
    try {
      await this.loadBenchmarks();
      console.log('Pages.initHomePage completed successfully');
    } catch (error) {
      console.error('Error initializing home page:', error);
      window.Components.showToast('Failed to load benchmarks', 'error');
    }
  }

  /**
   * Initialize composer page
   */
  async initComposerPage() {
    console.log('Pages.initComposerPage called');
    try {
      // Load models if not already loaded
      await this.loadModels();
      
      // Initialize with one empty prompt if none exist
      // (but don't add if prompts are already loaded, e.g., from a prompt set)
      if (this.prompts.length === 0) {
        this.addPrompt();
      }
      
      this.renderPrompts();
      
      // Add event listener for load prompt set button
      this.setupComposerEventListeners();
      
      console.log('Pages.initComposerPage completed successfully');
    } catch (error) {
      console.error('Error initializing composer page:', error);
      window.Components.showToast('Failed to load models', 'error');
    }
  }

  /**
   * Set up event listeners for composer page
   */
  setupComposerEventListeners() {
    const loadPromptSetBtn = document.getElementById('loadPromptSetBtn');
    if (loadPromptSetBtn) {
      loadPromptSetBtn.onclick = () => this.showLoadPromptSetModal();
    }
  }

  /**
   * Show modal to load a prompt set into the composer
   */
  async showLoadPromptSetModal() {
    try {
      const promptSets = await window.API.getPromptSets();
      
      if (promptSets.length === 0) {
        window.Components.showToast('No prompt sets found. Create one first!', 'info');
        return;
      }

      // Create modal content
      const modalContent = `
        <div class="modal fade" id="loadPromptSetModal" tabindex="-1">
          <div class="modal-dialog modal-lg">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Load Prompt Set</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <p class="text-muted mb-3">Select a prompt set to load into your benchmark:</p>
                <div class="list-group">
                  ${promptSets.map(ps => `
                    <button type="button" class="list-group-item list-group-item-action" data-prompt-set-id="${ps.id}">
                      <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${ps.name}</h6>
                        <small>${ps.prompt_count} prompts</small>
                      </div>
                      <p class="mb-1">${ps.description || 'No description'}</p>
                      <small>Created: ${new Date(ps.created_at).toLocaleDateString()}</small>
                    </button>
                  `).join('')}
                </div>
              </div>
            </div>
          </div>
        </div>
      `;

      // Add modal to page
      document.body.insertAdjacentHTML('beforeend', modalContent);
      const modal = new bootstrap.Modal(document.getElementById('loadPromptSetModal'));
      
      // Add click handlers
      document.querySelectorAll('[data-prompt-set-id]').forEach(btn => {
        btn.onclick = async () => {
          const promptSetId = parseInt(btn.dataset.promptSetId);
          modal.hide();
          await this.loadPromptSetIntoComposer(promptSetId);
        };
      });

      // Clean up modal when hidden
      document.getElementById('loadPromptSetModal').addEventListener('hidden.bs.modal', () => {
        document.getElementById('loadPromptSetModal').remove();
      });

      modal.show();
    } catch (error) {
      console.error('Error loading prompt sets:', error);
      window.Components.showToast('Failed to load prompt sets', 'error');
    }
  }

  /**
   * Load a prompt set into the composer
   */
  async loadPromptSetIntoComposer(promptSetId) {
    try {
      const promptSet = await window.API.getPromptSetDetails(promptSetId);
      
      // Clear existing prompts
      this.prompts = [];
      
      // Load prompts from the prompt set
      promptSet.prompts.forEach(prompt => {
        this.prompts.push({
          id: Utils.generateId(),
          text: prompt.prompt_text
        });
      });
      
      // Render the prompts
      this.renderPrompts();
      
      // Show success message
      window.Components.showToast(`Loaded ${promptSet.prompts.length} prompts from "${promptSet.name}"`, 'success');
      
    } catch (error) {
      console.error('Error loading prompt set:', error);
      window.Components.showToast('Failed to load prompt set', 'error');
    }
  }

  /**
   * Initialize details page
   */
  initDetailsPage() {
    // Details page is initialized when viewing specific benchmark
  }

  /**
   * Load benchmarks from API
   * @param {boolean} useCache - Whether to use cached data
   */
  async loadBenchmarks(useCache = true) {
    console.log('Pages.loadBenchmarks called with useCache:', useCache);
    const gridContainer = document.getElementById('benchmarksGrid');
    const tableBody = document.querySelector('#benchmarksTable tbody');

    try {
      // Only show loading state if we're forcing a refresh (not using cache)
      if (!useCache) {
        console.log('Showing loading state...');
        gridContainer.innerHTML = '';
        gridContainer.appendChild(window.Components.createSpinner('Loading benchmarks...'));
        
        tableBody.innerHTML = `
          <tr>
            <td colspan="5" class="text-center">
              <div class="d-flex justify-content-center align-items-center py-3">
                <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
                Loading benchmarks...
              </div>
            </td>
          </tr>
        `;
      }

      // Fetch benchmarks
      console.log('Fetching benchmarks from API...');
      const benchmarks = await window.API.getBenchmarks(useCache);
      console.log('Received benchmarks:', benchmarks);
      
      // Filter out deleted benchmarks
      const filteredBenchmarks = benchmarks.filter(
        benchmark => !this.deletedBenchmarkIds.has(benchmark.id)
      );
      console.log('Filtered benchmarks:', filteredBenchmarks);

      this.benchmarksData = filteredBenchmarks;
      console.log('Calling renderBenchmarks...');
      this.renderBenchmarks();
      console.log('Pages.loadBenchmarks completed successfully');

    } catch (error) {
      console.error('Error loading benchmarks:', error);
      
      // Show error state
      gridContainer.innerHTML = '';
      gridContainer.appendChild(
        window.Components.createErrorState(
          'Failed to Load Benchmarks',
          error.message,
          () => this.loadBenchmarks(false)
        )
      );

      tableBody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center text-danger py-3">
            Error: ${error.message}
          </td>
        </tr>
      `;
    }
  }

  /**
   * Render benchmarks in current view
   */
  renderBenchmarks() {
    console.log('Pages.renderBenchmarks called with', this.benchmarksData.length, 'benchmarks');
    const gridContainer = document.getElementById('benchmarksGrid');
    const tableBody = document.querySelector('#benchmarksTable tbody');

    // Clear containers
    gridContainer.innerHTML = '';
    tableBody.innerHTML = '';

    if (this.benchmarksData.length === 0) {
      console.log('No benchmarks found, showing empty state');
      // Show empty state
      gridContainer.appendChild(
        window.Components.createEmptyState(
          'No Benchmarks Found',
          'Create your first benchmark to get started!',
          'fas fa-chart-line'
        )
      );

      tableBody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center text-muted py-4">
            No benchmarks found. Create your first benchmark to get started!
          </td>
        </tr>
      `;
      console.log('Empty state rendered');
      return;
    }

    console.log('Rendering', this.benchmarksData.length, 'benchmarks');
    // Render grid view
    const gridRow = document.createElement('div');
    gridRow.className = 'row';
    
    this.benchmarksData.forEach(benchmark => {
      const card = window.Components.createBenchmarkCard(benchmark, {
        onView: (id) => this.viewBenchmarkDetails(id),
        onEdit: (benchmark) => this.editBenchmark(benchmark),
        onDelete: (id) => this.deleteBenchmark(id)
      });
      gridRow.appendChild(card);
    });
    
    gridContainer.appendChild(gridRow);

    // Render table view
    this.benchmarksData.forEach(benchmark => {
      const row = window.Components.createBenchmarkRow(benchmark, {
        onView: (id) => this.viewBenchmarkDetails(id),
        onEdit: (benchmark) => this.editBenchmark(benchmark),
        onDelete: (id) => this.deleteBenchmark(id)
      });
      tableBody.appendChild(row);
    });
    
    console.log('Benchmarks rendered successfully');
  }

  /**
   * View benchmark details
   * @param {number} benchmarkId - Benchmark ID
   */
  async viewBenchmarkDetails(benchmarkId) {
    const detailsContainer = document.getElementById('detailsContainer');
    
    try {
      // Show loading state
      detailsContainer.innerHTML = '';
      detailsContainer.appendChild(window.Components.createSpinner('Loading benchmark details...'));
      
      // Navigate to details page
      this.navigateTo('detailsContent');
      
      // Always fetch and show the standard details view (works for both running and completed)
      const details = await window.API.getBenchmarkDetails(benchmarkId);
      this.renderBenchmarkDetails(details);
      
      // If the benchmark is still running, set up auto-refresh
      const benchmarks = await window.API.getBenchmarks(true);
      const benchmark = benchmarks.find(b => b.id === benchmarkId);
      
      if (benchmark && (benchmark.status === 'running' || benchmark.status === 'in-progress')) {
        // Set up periodic refresh for running benchmarks
        this.setupAutoRefreshForRunningBenchmark(benchmarkId);
      }
      
    } catch (error) {
      console.error('Error viewing benchmark details:', error);
      
      detailsContainer.innerHTML = '';
      detailsContainer.appendChild(
        window.Components.createErrorState(
          'Failed to Load Details',
          error.message,
          () => this.viewBenchmarkDetails(benchmarkId)
        )
      );
      
      window.Components.showToast('Failed to load benchmark details', 'error');
    }
  }

  /**
   * Set up auto-refresh for running benchmarks
   * @param {number} benchmarkId - Benchmark ID
   */
  setupAutoRefreshForRunningBenchmark(benchmarkId) {
    // Clear any existing refresh interval
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
    
    // Set up auto-refresh every 3 seconds
    this.refreshInterval = setInterval(async () => {
      try {
        // Check if we're still on the details page for this benchmark
        if (this.currentPage !== 'detailsContent') {
          clearInterval(this.refreshInterval);
          return;
        }
        
        // Fetch updated details
        const details = await window.API.getBenchmarkDetails(benchmarkId);
        this.renderBenchmarkDetails(details);
        
        // Check if benchmark is complete
        const benchmarks = await window.API.getBenchmarks(true);
        const benchmark = benchmarks.find(b => b.id === benchmarkId);
        
        if (!benchmark || (benchmark.status !== 'running' && benchmark.status !== 'in-progress')) {
          // Benchmark is complete, stop auto-refresh
          clearInterval(this.refreshInterval);
          this.refreshInterval = null;
        }
        
      } catch (error) {
        console.error('Error refreshing benchmark details:', error);
        // Continue trying to refresh even if there's an error
      }
    }, 3000); // Refresh every 3 seconds
  }

  /**
   * Render benchmark details
   * @param {Object} details - Benchmark details
   */
  renderBenchmarkDetails(details) {
    const detailsContainer = document.getElementById('detailsContainer');
    
    // Calculate per-model stats for the table
    const totalRuns = details.runs ? details.runs.length : 0;
65    
    // Get the ACTUAL total number of prompts in the benchmark
    // This should be consistent across all models - use the maximum found
    let totalPromptsInBenchmark = 0;
    if (details.runs && details.runs.length > 0) {
      // Find the maximum number of prompts across all runs (should be the same for all models)
      totalPromptsInBenchmark = Math.max(...details.runs.map(run => {
        if (run.prompts && run.prompts.length > 0) {
          return run.prompts.length;
        }
        return 0;
      }), 0);
      
      // If no prompts found yet, try to get from intended models or estimate
      if (totalPromptsInBenchmark === 0) {
        // For running benchmarks where no prompts are saved yet, we might need to estimate
        // This is a fallback - ideally we'd store this info in the benchmark record
        totalPromptsInBenchmark = 0; // Will show "TBD"
      }
    }
    
    // Determine if this is a running benchmark
    const isRunning = details.status === 'running' || details.status === 'in-progress';
    
    // Deduplicate models and build per-model table data
    const uniqueModels = new Map();
    if (details.runs && details.runs.length > 0) {
      details.runs.forEach(run => {
        const modelKey = `${run.model_name}_${run.provider}`;
        if (!uniqueModels.has(modelKey)) {
          uniqueModels.set(modelKey, run);
        }
      });
    }
    
    let modelTableRows = '';
    if (uniqueModels.size > 0) {
      modelTableRows = Array.from(uniqueModels.values()).map(run => {
        const modelName = run.model_name || 'Unknown Model';
        const provider = run.provider || 'unknown';
        
        // Calculate metrics for this specific model based on completed prompts
        let modelCost = 0;
        let modelTokens = 0;
        // Latency is stored in milliseconds in the database (newer runs) or seconds (older runs)
        // Handle both cases by detecting magnitude
        let modelLatencyMs = run.latency || 0;
        // If latency is less than 1000, it's likely stored in seconds (old format)
        if (modelLatencyMs > 0 && modelLatencyMs < 1000) {
          modelLatencyMs = modelLatencyMs * 1000; // Convert to milliseconds
        }
        let completedPrompts = 0;
        let totalPromptsForThisModel = 0;
        
        if (run.prompts && run.prompts.length > 0) {
          totalPromptsForThisModel = run.prompts.length;
          run.prompts.forEach(prompt => {
            if (prompt.response && prompt.response.trim().length > 0) { // Only count completed prompts
              modelCost += prompt.total_cost || 0;
              modelTokens += (prompt.standard_input_tokens || 0) + 
                            (prompt.cached_input_tokens || 0) + 
                            (prompt.output_tokens || 0);
              completedPrompts++;
            }
          });
        }
        
        const providerColor = Utils.getProviderColor(provider);
        
        // Convert latency to minutes and seconds format
        const formatLatency = (ms) => {
          const seconds = Math.round(ms / 1000);
          const minutes = Math.floor(seconds / 60);
          const remainingSeconds = seconds % 60;
          
          if (minutes > 0) {
            return `${minutes} min ${remainingSeconds} sec`;
          } else {
            return `${remainingSeconds} sec`;
          }
        };
        
        // Determine status for this model based on actual completion state
        let statusContent = '';
        let latencyContent = '';
        let costContent = '';
        let tokensContent = '';
        
        // A model is considered complete if it has completed all its prompts OR if the benchmark is not running
        const modelIsComplete = !isRunning || (totalPromptsForThisModel > 0 && completedPrompts === totalPromptsForThisModel);
        const modelHasStarted = completedPrompts > 0 || totalPromptsForThisModel > 0;
        
        if (!modelHasStarted && isRunning) {
          // Model hasn't started yet
          statusContent = '<i class="fas fa-spinner fa-spin text-primary me-2"></i>';
          latencyContent = '<span class="text-muted">Starting...</span>';
          costContent = '<span class="text-muted">Starting...</span>';
          tokensContent = '<span class="text-muted">Starting...</span>';
        } else if (!modelIsComplete && isRunning) {
          // Model is in progress
          statusContent = '<i class="fas fa-clock text-warning me-2"></i>';
          latencyContent = `<span class="text-info">${formatLatency(modelLatencyMs)}</span> <small class="text-muted">(${completedPrompts}/${totalPromptsForThisModel})</small>`;
          costContent = `<span class="text-info">${Utils.formatCurrency(modelCost)}</span> <small class="text-muted">(partial)</small>`;
          tokensContent = `<span class="text-info">${Utils.formatNumber(modelTokens)}</span> <small class="text-muted">(partial)</small>`;
        } else if (modelIsComplete && completedPrompts > 0) {
          // Model is complete and has results
          statusContent = '<i class="fas fa-check text-success me-2"></i>';
          latencyContent = formatLatency(modelLatencyMs);
          costContent = Utils.formatCurrency(modelCost);
          tokensContent = Utils.formatNumber(modelTokens);
        } else {
          // Model has no data
          statusContent = '';
          latencyContent = '<span class="text-muted">No data</span>';
          costContent = '<span class="text-muted">No data</span>';
          tokensContent = '<span class="text-muted">No data</span>';
        }
        
        return `
          <tr>
            <td>
              <div class="d-flex align-items-center">
                ${statusContent}
                ${Utils.createProviderImage(provider, 'me-2')}
                ${Utils.createModelImage(modelName, 'me-2')}
                <strong>${Utils.sanitizeHtml(Utils.formatModelName(modelName))}</strong>
              </div>
            </td>
            <td data-sort="${modelLatencyMs}">
              ${latencyContent}
            </td>
            <td data-sort="${modelCost}">
              ${costContent}
            </td>
            <td data-sort="${modelTokens}">
              ${tokensContent}
            </td>
          </tr>
        `;
      }).join('');
    } else {
      modelTableRows = `
        <tr>
          <td colspan="4" class="text-center text-muted py-3">
            ${isRunning 
              ? '<i class="fas fa-spinner fa-spin me-2"></i>Models are starting...' 
              : 'No model results available'}
          </td>
        </tr>
      `;
    }

    // Add running indicator to the header if needed (without confusing progress fraction)
    const runningBanner = isRunning ? `
      <div class="alert alert-info d-flex align-items-center mb-4">
        <div class="spinner-border spinner-border-sm text-info me-3" role="status"></div>
        <div>
          <strong>Benchmark Running</strong> - Results will update automatically as models complete
        </div>
      </div>
    ` : '';

    detailsContainer.innerHTML = `
      <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 class="mb-1">${Utils.sanitizeHtml(details.label || `Benchmark ${details.id}`)}</h2>
          <p class="text-muted mb-0">${Utils.sanitizeHtml(details.description || 'No description provided')}</p>
        </div>
        <div class="d-flex gap-2">
          <button id="refreshDetailsBtn" class="btn btn-outline-secondary">
            <i class="fas fa-sync-alt me-1"></i>Refresh
          </button>
          ${!isRunning ? `
            <button id="exportCsvBtn" class="btn btn-success">
              <i class="fas fa-download me-1"></i>Export CSV
            </button>
          ` : ''}
        </div>
      </div>

      ${runningBanner}

      <!-- Basic Info -->
      <div class="row mb-4">
        <div class="col-md-4">
          <div class="card text-center">
            <div class="card-body">
              <h4 class="text-info mb-1">${totalPromptsInBenchmark || 'TBD'}</h4>
              <small class="text-muted">Prompts</small>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-center">
            <div class="card-body">
              <h4 class="text-dark mb-1">${Utils.formatDate(details.created_at).split(',')[0]}</h4>
              <small class="text-muted">Created</small>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-center">
            <div class="card-body">
              <h4 class="text-secondary mb-1">${details.status || 'complete'}</h4>
              <small class="text-muted">Status</small>
            </div>
          </div>
        </div>
      </div>

      <!-- Model Performance Table -->
      <div class="mb-4">
        <h4 class="mb-3">
          <i class="fas fa-chart-bar me-2"></i>Model Performance Summary
        </h4>
        <div class="table-responsive">
          <table class="table table-hover" id="modelPerformanceTable">
            <thead class="table-light">
              <tr>
                <th style="cursor: pointer;" data-sort="model">
                  Model <i class="fas fa-sort text-muted"></i>
                </th>
                <th style="cursor: pointer;" data-sort="latency">
                  Latency <i class="fas fa-sort text-muted"></i>
                </th>
                <th style="cursor: pointer;" data-sort="cost">
                  Cost <i class="fas fa-sort text-muted"></i>
                </th>
                <th style="cursor: pointer;" data-sort="tokens">
                  Tokens <i class="fas fa-sort text-muted"></i>
                </th>
              </tr>
            </thead>
            <tbody>
              ${modelTableRows}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Detailed Results -->
      <div class="results-section">
        <h4 class="mb-3">
          <i class="fas me-2"></i>Detailed Results
        </h4>
        <div id="resultsContainer">
          ${this.renderModelResults(details.runs || [])}
        </div>
      </div>
    `;

    // Add event listeners
    const refreshBtn = document.getElementById('refreshDetailsBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.viewBenchmarkDetails(details.id));
    }

    const exportBtn = document.getElementById('exportCsvBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => this.exportBenchmark(details.id));
    }

    // Add table sorting functionality (only if not running to avoid conflicts)
    if (!isRunning) {
      this.setupTableSorting();
    }
  }

  /**
   * Set up table sorting functionality
   */
  setupTableSorting() {
    const table = document.getElementById('modelPerformanceTable');
    if (!table) return;

    const headers = table.querySelectorAll('th[data-sort]');
    let currentSort = { column: null, direction: 'asc' };

    headers.forEach(header => {
      header.addEventListener('click', () => {
        const sortType = header.dataset.sort;
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        // Update sort direction
        if (currentSort.column === sortType) {
          currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
        } else {
          currentSort.column = sortType;
          currentSort.direction = 'asc';
        }

        // Update header icons
        headers.forEach(h => {
          const icon = h.querySelector('i');
          icon.className = 'fas fa-sort text-muted';
        });
        
        const currentIcon = header.querySelector('i');
        currentIcon.className = currentSort.direction === 'asc' 
          ? 'fas fa-sort-up text-primary' 
          : 'fas fa-sort-down text-primary';

        // Sort rows
        rows.sort((a, b) => {
          let aVal, bVal;

          if (sortType === 'model') {
            aVal = a.cells[0].textContent.trim().toLowerCase();
            bVal = b.cells[0].textContent.trim().toLowerCase();
          } else {
            // For numeric columns, use the data-sort attribute
            const aCell = a.cells[sortType === 'latency' ? 1 : sortType === 'cost' ? 2 : 3];
            const bCell = b.cells[sortType === 'latency' ? 1 : sortType === 'cost' ? 2 : 3];
            aVal = parseFloat(aCell.dataset.sort || 0);
            bVal = parseFloat(bCell.dataset.sort || 0);
          }

          if (currentSort.direction === 'asc') {
            return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
          } else {
            return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
          }
        });

        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
      });
    });
  }

  /**
   * Render model results
   * @param {Array} runs - Benchmark runs
   * @returns {string} HTML string
   */
  renderModelResults(runs) {
    if (!runs || runs.length === 0) {
      return '<div class="text-center text-muted py-4"><h5>No results available</h5></div>';
    }

    return runs.map(run => {
      const modelDisplayName = Utils.formatModelName(run.model_name) || 'Unknown Model';
      const provider = run.provider || 'unknown';
      const runDate = Utils.formatDate(run.run_created_at);
      
      // Calculate stats based on completed prompts only
      let runTokens = 0;
      let runCost = 0;
      let completedPrompts = 0;
      
      if (run.prompts) {
        run.prompts.forEach(prompt => {
          if (prompt.response) { // Only count completed prompts
            runTokens += (prompt.standard_input_tokens || 0) + 
                        (prompt.cached_input_tokens || 0) + 
                        (prompt.output_tokens || 0);
            runCost += prompt.total_cost || 0;
            completedPrompts++;
          }
        });
      }
      
      const providerColor = Utils.getProviderColor(provider);
      
      // Determine if this run is still in progress
      const totalPrompts = run.prompts ? run.prompts.length : 0;
      const isRunning = completedPrompts < totalPrompts && totalPrompts > 0;
      const hasResults = completedPrompts > 0;
      
      // Latency handling - support both old (seconds) and new (milliseconds) formats
      let totalLatencyMs = run.latency || 0;
      // If latency is less than 1000, it's likely stored in seconds (old format)
      if (totalLatencyMs > 0 && totalLatencyMs < 1000) {
        totalLatencyMs = totalLatencyMs * 1000; // Convert to milliseconds
      }
      
      // Convert latency to minutes and seconds format for model totals
      const formatModelLatency = (ms) => {
        const seconds = Math.round(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        
        if (minutes > 0) {
          return `${minutes} min ${remainingSeconds} sec`;
        } else {
          return `${remainingSeconds} sec`;
        }
      };
      
      // Generate prompts HTML with status indicators
      let promptsHtml = '';
      if (run.prompts && run.prompts.length > 0) {
        promptsHtml = run.prompts.map((prompt, index) => {
          const isCompleted = prompt.response && prompt.response.trim().length > 0;
          
          if (isCompleted) {
            // Individual prompt latency is stored in milliseconds in database (newer runs) or seconds (older runs)
            // Handle both cases by detecting magnitude
            let promptLatencyMs = prompt.prompt_latency || 0;
            // If latency is less than 1000, it's likely stored in seconds (old format)
            if (promptLatencyMs > 0 && promptLatencyMs < 1000) {
              promptLatencyMs = promptLatencyMs * 1000; // Convert to milliseconds
            }
            const promptLatencySeconds = promptLatencyMs / 1000;
            
            // Show completed prompt
            return `
              <div class="border rounded p-3 mb-3 bg-light">
                <div class="d-flex justify-content-between align-items-start mb-2">
                  <h6 class="mb-0 text-primary">
                    <i class="fas fa-check-circle text-success me-2"></i>
                    Prompt ${index + 1}
                  </h6>
                  <div class="d-flex gap-2">
                    <span class="badge bg-secondary">${promptLatencySeconds.toFixed(3)}s</span>
                    <span class="badge bg-info">${(prompt.standard_input_tokens || 0) + (prompt.cached_input_tokens || 0)}→${prompt.output_tokens || 0} tokens</span>
                    ${prompt.total_cost ? `<span class="badge bg-success">${Utils.formatCurrency(prompt.total_cost)}</span>` : ''}
                  </div>
                </div>
                
                <div class="mb-3">
                  <div class="fw-bold text-muted mb-1">Question:</div>
                  <div class="p-2 bg-white border rounded small">${Utils.sanitizeHtml(prompt.prompt || 'N/A')}</div>
                </div>
                
                <div>
                  <div class="fw-bold text-muted mb-1">Answer:</div>
                  <div class="p-2 bg-white border rounded small" style="white-space: pre-wrap;">${Utils.sanitizeHtml(prompt.response || 'N/A')}</div>
                </div>
              </div>
            `;
          } else {
            // Show pending/running prompt
            return `
              <div class="border rounded p-3 mb-3 bg-light opacity-75">
                <div class="d-flex justify-content-between align-items-start mb-2">
                  <h6 class="mb-0 text-muted">
                    <i class="fas fa-clock text-warning me-2"></i>
                    Prompt ${index + 1}
                  </h6>
                  <div class="d-flex gap-2">
                    <span class="badge bg-warning">Pending</span>
                  </div>
                </div>
                
                <div class="mb-3">
                  <div class="fw-bold text-muted mb-1">Question:</div>
                  <div class="p-2 bg-white border rounded small">${Utils.sanitizeHtml(prompt.prompt || 'N/A')}</div>
                </div>
                
                <div>
                  <div class="fw-bold text-muted mb-1">Answer:</div>
                  <div class="p-2 bg-white border rounded small text-muted">
                    <i class="fas fa-spinner fa-spin me-2"></i>Processing...
                  </div>
                </div>
              </div>
            `;
          }
        }).join('');
      } else {
        promptsHtml = '<div class="text-muted text-center py-4"><i class="fas fa-spinner fa-spin me-2"></i>Waiting for prompts to start...</div>';
      }

      // Determine header status and styling
      let headerClass = 'bg-primary';
      let statusText = 'Run completed';
      
      if (isRunning) {
        headerClass = 'bg-warning';
        statusText = `Running (${completedPrompts}/${totalPrompts} completed)`;
      } else if (!hasResults) {
        headerClass = 'bg-secondary';
        statusText = 'Waiting to start';
      }

      return `
        <div class="card mb-4 shadow-sm">
          <div class="card-header ${headerClass} text-white">
            <div class="d-flex justify-content-between align-items-center">
              <div class="d-flex align-items-center">
                ${Utils.createModelImage(modelDisplayName, 'me-2')}
                <div>
                  <h5 class="mb-0">${Utils.sanitizeHtml(modelDisplayName)}</h5>
                  <small class="opacity-75">${statusText}${runDate ? ` • ${runDate}` : ''}</small>
                </div>
              </div>
              <div class="d-flex gap-2 align-items-center">
                ${Utils.createProviderImage(provider, 'provider-badge')}
                ${hasResults ? `<span class="badge bg-light text-dark fs-6">${formatModelLatency(totalLatencyMs)} total</span>` : ''}
                ${isRunning ? '<i class="fas fa-spinner fa-spin"></i>' : ''}
              </div>
            </div>
          </div>
          
          <div class="card-body">
            <div class="row mb-3">
              <div class="col-md-3">
                <div class="text-center p-2 bg-light rounded">
                  <div class="h4 mb-0 text-primary">${completedPrompts}${totalPrompts > 0 ? `/${totalPrompts}` : ''}</div>
                  <small class="text-muted">Prompts ${isRunning ? 'Completed' : 'Total'}</small>
                </div>
              </div>
              <div class="col-md-3">
                <div class="text-center p-2 bg-light rounded">
                  <div class="h4 mb-0 text-info">${hasResults ? Utils.formatNumber(runTokens) : '—'}</div>
                  <small class="text-muted">Tokens${isRunning ? ' (so far)' : ''}</small>
                </div>
              </div>
              <div class="col-md-3">
                <div class="text-center p-2 bg-light rounded">
                  <div class="h4 mb-0 text-success">${hasResults ? Utils.formatCurrency(runCost) : '—'}</div>
                  <small class="text-muted">Cost${isRunning ? ' (so far)' : ''}</small>
                </div>
              </div>
              <div class="col-md-3">
                <div class="text-center p-2 bg-light rounded">
                  <div class="h4 mb-0 text-warning">${hasResults ? formatModelLatency(totalLatencyMs) : '—'}</div>
                  <small class="text-muted">Latency${isRunning ? ' (partial)' : ''}</small>
                </div>
              </div>
            </div>
            
            <div class="mt-3">
              <h6 class="text-muted mb-3">
                Detailed Results:
                ${isRunning ? `<span class="badge bg-info ms-2">${completedPrompts}/${totalPrompts} completed</span>` : ''}
              </h6>
              ${promptsHtml}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * Edit benchmark
   * @param {Object} benchmark - Benchmark data
   */
  editBenchmark(benchmark) {
    // Create edit modal using Bootstrap modal
    const modalHtml = `
      <div class="modal fade" id="editBenchmarkModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Edit Benchmark</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="mb-3">
                <label for="editBenchmarkName" class="form-label">Name</label>
                <input type="text" class="form-control" id="editBenchmarkName" 
                       value="${Utils.sanitizeHtml(benchmark.label || '')}" required>
              </div>
              <div class="mb-3">
                <label for="editBenchmarkDescription" class="form-label">Description</label>
                <textarea class="form-control" id="editBenchmarkDescription" rows="3">${Utils.sanitizeHtml(benchmark.description || '')}</textarea>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" id="saveBenchmarkBtn">Save Changes</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Remove existing modal if any
    const existingModal = document.getElementById('editBenchmarkModal');
    if (existingModal) {
      existingModal.remove();
    }

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    const modal = new bootstrap.Modal(document.getElementById('editBenchmarkModal'));
    const saveBtn = document.getElementById('saveBenchmarkBtn');
    const nameInput = document.getElementById('editBenchmarkName');
    const descInput = document.getElementById('editBenchmarkDescription');

    // Handle save
    saveBtn.addEventListener('click', async () => {
      const newName = nameInput.value.trim();
      const newDescription = descInput.value.trim();

      if (!newName) {
        window.Components.showToast('Name is required', 'error');
        return;
      }

      try {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

        await window.API.updateBenchmark(benchmark.id, newName, newDescription);
        
        window.Components.showToast('Benchmark updated successfully', 'success');
        modal.hide();
        
        // Refresh benchmarks
        await this.loadBenchmarks(false);
        
      } catch (error) {
        console.error('Error updating benchmark:', error);
        window.Components.showToast(`Failed to update benchmark: ${error.message}`, 'error');
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = 'Save Changes';
      }
    });

    // Clean up modal on hide
    document.getElementById('editBenchmarkModal').addEventListener('hidden.bs.modal', () => {
      document.getElementById('editBenchmarkModal').remove();
    });

    modal.show();
    nameInput.focus();
  }

  /**
   * Delete benchmark
   * @param {number} benchmarkId - Benchmark ID
   */
  deleteBenchmark(benchmarkId) {
    window.Components.createConfirmModal(
      'Delete Benchmark',
      'Are you sure you want to delete this benchmark? This action cannot be undone.',
      async () => {
        try {
          // Add to deleted set immediately
          this.deletedBenchmarkIds.add(benchmarkId);
          
          // Remove from UI immediately
          const card = document.querySelector(`[data-benchmark-id="${benchmarkId}"]`);
          if (card) {
            card.remove();
          }

          await window.API.deleteBenchmark(benchmarkId);
          
          window.Components.showToast('Benchmark deleted successfully', 'success');
          
          // Refresh benchmarks
          await this.loadBenchmarks(false);
          
        } catch (error) {
          console.error('Error deleting benchmark:', error);
          
          // Remove from deleted set on error
          this.deletedBenchmarkIds.delete(benchmarkId);
          
          window.Components.showToast(`Failed to delete benchmark: ${error.message}`, 'error');
          
          // Refresh to restore UI
          await this.loadBenchmarks(false);
        }
      }
    );
  }

  /**
   * Export benchmark to CSV
   * @param {number} benchmarkId - Benchmark ID
   */
  async exportBenchmark(benchmarkId) {
    const exportBtn = document.getElementById('exportCsvBtn');
    
    try {
      if (exportBtn) {
        exportBtn.disabled = true;
        exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Exporting...';
      }

      const result = await window.API.exportBenchmark(benchmarkId);
      
      if (result && result.success) {
        window.Components.showToast('CSV export completed successfully!', 'success');
      } else {
        throw new Error(result?.error || 'Export failed');
      }
      
    } catch (error) {
      console.error('Export error:', error);
      window.Components.showToast(`Export failed: ${error.message}`, 'error');
    } finally {
      if (exportBtn) {
        exportBtn.disabled = false;
        exportBtn.innerHTML = '<i class="fas fa-download me-1"></i>Export CSV';
      }
    }
  }

  /**
   * Load available models
   */
  async loadModels() {
    const modelList = document.getElementById('modelList');
    
    try {
      modelList.innerHTML = '';
      modelList.appendChild(window.Components.createSpinner('Loading models...', 'sm'));

      const models = await window.API.getModels();
      
      modelList.innerHTML = '';
      
      if (models.length === 0) {
        modelList.appendChild(
          window.Components.createEmptyState(
            'No Models Available',
            'No models could be loaded from the system.'
          )
        );
        return;
      }

      // Group models by provider
      const groupedModels = {};
      models.forEach(model => {
        if (!groupedModels[model.provider]) {
          groupedModels[model.provider] = [];
        }
        groupedModels[model.provider].push(model);
      });

      // Render models grouped by provider
      Object.keys(groupedModels).forEach(provider => {
        const providerDiv = document.createElement('div');
        providerDiv.className = 'mb-3';
        
        const providerColor = Utils.getProviderColor(provider);
        
        providerDiv.innerHTML = `
          <h6 class="text-muted mb-2">
            <span class="badge bg-${providerColor} me-2">${provider.toUpperCase()}</span>
            Models
          </h6>
        `;

        groupedModels[provider].forEach(model => {
          const isDefault = model.id === 'gpt-4o-mini';
          const checkbox = window.Components.createModelCheckbox(model, isDefault);
          providerDiv.appendChild(checkbox);
        });

        modelList.appendChild(providerDiv);
      });

    } catch (error) {
      console.error('Error loading models:', error);
      
      modelList.innerHTML = '';
      modelList.appendChild(
        window.Components.createErrorState(
          'Failed to Load Models',
          error.message,
          () => this.loadModels()
        )
      );
    }
  }

  /**
   * Add a new prompt
   */
  addPrompt(value = '') {
    const prompt = {
      id: Utils.generateId(),
      text: value
    };
    
    this.prompts.push(prompt);
    this.renderPrompts();
  }

  /**
   * Remove a prompt
   * @param {string} promptId - Prompt ID
   */
  removePrompt(promptId) {
    this.prompts = this.prompts.filter(p => p.id !== promptId);
    this.renderPrompts();
  }

  /**
   * Clear all empty prompts (prompts with no text or only whitespace)
   */
  clearEmptyPrompts() {
    const originalCount = this.prompts.length;
    this.prompts = this.prompts.filter(p => p.text && p.text.trim().length > 0);
    const removedCount = originalCount - this.prompts.length;
    
    if (removedCount > 0) {
      console.log(`Cleared ${removedCount} empty prompt(s)`);
      this.renderPrompts();
    }
  }

  /**
   * Render prompts list
   */
  renderPrompts() {
    console.log('renderPrompts called with', this.prompts.length, 'prompts');
    const promptsList = document.getElementById('promptsList');
    if (!promptsList) {
      console.error('promptsList element not found!');
      return;
    }

    promptsList.innerHTML = '';

    if (this.prompts.length === 0) {
      console.log('No prompts to render, showing empty state');
      promptsList.appendChild(
        window.Components.createEmptyState(
          'No Prompts',
          'Add prompts to test your models.',
          'fas fa-question-circle'
        )
      );
      return;
    }

    console.log('Rendering', this.prompts.length, 'prompts...');
    this.prompts.forEach((prompt, index) => {
      console.log(`Rendering prompt ${index + 1}:`, prompt.text.substring(0, 30) + '...');
      const promptElement = window.Components.createPromptInput(
        prompt.text,
        (element) => {
          this.removePrompt(prompt.id);
        }
      );

      // Update prompt text on change
      const textarea = promptElement.querySelector('.prompt-input');
      if (textarea) {
        textarea.addEventListener('input', (e) => {
          prompt.text = e.target.value;
        });
      } else {
        console.warn('No textarea found in prompt element for prompt', index + 1);
      }

      promptsList.appendChild(promptElement);
    });
    
    console.log('Finished rendering prompts. promptsList now has', promptsList.children.length, 'children');
  }

  /**
   * Toggle view between grid and table
   * @param {string} view - 'grid' or 'table'
   */
  toggleView(view) {
    this.currentView = view;
    
    const gridContainer = document.getElementById('benchmarksGrid');
    const tableContainer = document.getElementById('benchmarksTable');
    const gridBtn = document.getElementById('gridViewBtn');
    const tableBtn = document.getElementById('tableViewBtn');

    if (view === 'grid') {
      gridContainer.classList.add('active');
      tableContainer.classList.remove('active');
      gridBtn.classList.add('active');
      tableBtn.classList.remove('active');
    } else {
      gridContainer.classList.remove('active');
      tableContainer.classList.add('active');
      gridBtn.classList.remove('active');
      tableBtn.classList.add('active');
    }
  }

  /**
   * Run a new benchmark
   */
  async runBenchmark() {
    const runBtn = document.getElementById('runBenchmarkBtn');
    const nameInput = document.getElementById('benchmarkNameInput');
    const descInput = document.getElementById('benchmarkDescriptionInput');

    try {
      // Validate inputs
      const benchmarkName = nameInput.value.trim();
      if (!benchmarkName) {
        window.Components.showToast('Benchmark name is required', 'error');
        nameInput.focus();
        return;
      }

      // Get prompts
      const prompts = this.prompts
        .map(p => ({ prompt_text: p.text.trim() }))
        .filter(p => p.prompt_text);

      if (prompts.length === 0) {
        window.Components.showToast('At least one prompt is required', 'error');
        return;
      }

      // Get selected models
      const selectedModels = Array.from(
        document.querySelectorAll('#modelList input[type="checkbox"]:checked')
      ).map(cb => cb.value);

      if (selectedModels.length === 0) {
        window.Components.showToast('At least one model must be selected', 'error');
        return;
      }

      // Disable button and show loading
      if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Starting Benchmark...';
      }

      // Run benchmark
      const result = await window.API.runBenchmark({
        prompts,
        pdfPaths: this.selectedPdfPaths,
        modelNames: selectedModels,
        benchmarkName,
        benchmarkDescription: descInput.value.trim()
      });

      if (result && result.status === 'success') {
        window.Components.showToast(`Benchmark "${benchmarkName}" started successfully!`, 'success');
        
        // Navigate back to home
        this.navigateTo('homeContent');
        
        // Refresh benchmarks
        setTimeout(() => {
          this.loadBenchmarks(false);
        }, 1000);
        
      } else {
        throw new Error(result?.message || 'Failed to start benchmark');
      }

    } catch (error) {
      console.error('Error running benchmark:', error);
      window.Components.showToast(`Failed to start benchmark: ${error.message}`, 'error');
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = '<i class="fas fa-play me-2"></i>Run Benchmark';
      }
    }
  }

  /**
   * Handle progress updates
   * @param {Object} data - Progress data
   */
  handleProgress(data) {
    console.log('🔄 Pages.handleProgress called with data:', data);
    
    // Update benchmark status in the home view
    if (data.benchmark_id) {
      window.Components.updateBenchmarkStatus(data.benchmark_id, 'running');
      
      // If a model has completed, refresh the benchmark data to get updated model list
      if (data.model_name && data.status === 'complete') {
        console.log(`Model ${data.model_name} completed, refreshing benchmark data...`);
        this.refreshBenchmarkData(data.benchmark_id);
      }
    }

    // No longer using progress log - the details view auto-refreshes instead
  }

  /**
   * Refresh benchmark data for a specific benchmark
   * @param {number} benchmarkId - Benchmark ID
   */
  async refreshBenchmarkData(benchmarkId) {
    try {
      // Only refresh if we're on the home page
      if (this.currentPage !== 'homeContent') return;
      
      // Get updated benchmark data
      const benchmarks = await window.API.getBenchmarks(false); // Force refresh
      const updatedBenchmark = benchmarks.find(b => b.id === benchmarkId);
      
      if (updatedBenchmark) {
        console.log(`Updated benchmark ${benchmarkId} models:`, updatedBenchmark.model_names);
        // Update the specific benchmark card with new data
        window.Components.updateBenchmarkCard(benchmarkId, updatedBenchmark);
      }
    } catch (error) {
      console.error('Error refreshing benchmark data:', error);
    }
  }

  /**
   * Handle benchmark completion
   * @param {Object} data - Completion data
   */
  handleComplete(data) {
    console.log('Benchmark completion:', data);
    
    // Update benchmark status in the home view
    if (data.benchmark_id) {
      window.Components.updateBenchmarkStatus(data.benchmark_id, 'complete');
      
      // Refresh benchmark data to get the latest model information
      console.log('Benchmark completed, refreshing benchmark data...');
      this.refreshBenchmarkData(data.benchmark_id);
    }

    // Refresh the home page benchmark list to show updated status
    if (this.currentPage === 'homeContent') {
      this.loadBenchmarks(true); // Silent refresh
    }
  }

  /**
   * Initialize prompt set creation page
   */
  async initPromptSetPage() {
    // Show prompt sets list instead of creation form
    await this.showPromptSetsList();
  }

  /**
   * Show list of existing prompt sets
   */
  async showPromptSetsList() {
    const promptSetContent = document.getElementById('promptSetContent');
    if (!promptSetContent) return;

    try {
      const promptSets = await window.API.getPromptSets();
      
      promptSetContent.innerHTML = `
        <div class="container-fluid h-100">
          <div class="d-flex justify-content-between align-items-center mb-4">
            <h3>Prompt Sets</h3>
            <button class="btn btn-primary" id="createNewPromptSetBtn">
              <i class="fas fa-plus"></i> Create New Prompt Set
            </button>
          </div>
          
          ${promptSets.length === 0 ? `
            <div class="text-center py-5">
              <i class="fas fa-layer-group fa-3x text-muted mb-3"></i>
              <h5 class="text-muted">No Prompt Sets Yet</h5>
              <p class="text-muted">Create your first prompt set to organize your prompts</p>
              <button class="btn btn-primary" onclick="window.Pages.showPromptSetCreation()">
                <i class="fas fa-plus"></i> Create Your First Prompt Set
              </button>
            </div>
          ` : `
            <div class="row">
              ${promptSets.map(promptSet => `
                <div class="col-md-6 col-lg-4 mb-4">
                  <div class="card h-100">
                    <div class="card-body">
                      <h5 class="card-title">${promptSet.name}</h5>
                      <p class="card-text text-muted">${promptSet.description || 'No description'}</p>
                      <div class="d-flex justify-content-between align-items-center">
                        <small class="text-muted">
                          <i class="fas fa-list"></i> ${promptSet.prompt_count} prompts
                        </small>
                        <small class="text-muted">
                          ${new Date(promptSet.created_at).toLocaleDateString()}
                        </small>
                      </div>
                    </div>
                    <div class="card-footer bg-transparent">
                      <div class="btn-group w-100" role="group">
                        <button class="btn btn-outline-primary" onclick="window.Pages.editPromptSet(${promptSet.id})">
                          <i class="fas fa-eye"></i> View/Edit
                        </button>
                        <button class="btn btn-outline-success" onclick="window.Pages.usePromptSetInBenchmark(${promptSet.id})">
                          <i class="fas fa-play"></i> Use in Benchmark
                        </button>
                        <button class="btn btn-outline-danger" onclick="window.Pages.deletePromptSetFromList(${promptSet.id})">
                          <i class="fas fa-trash"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>
          `}
        </div>
      `;

      // Add event listener for create new button
      const createBtn = document.getElementById('createNewPromptSetBtn');
      if (createBtn) {
        createBtn.onclick = () => this.showPromptSetCreation();
      }

    } catch (error) {
      console.error('Error loading prompt sets:', error);
      promptSetContent.innerHTML = `
        <div class="container-fluid h-100">
          <div class="alert alert-danger">
            <h5>Error Loading Prompt Sets</h5>
            <p>${error.message}</p>
            <button class="btn btn-outline-danger" onclick="window.Pages.showPromptSetsList()">
              <i class="fas fa-sync"></i> Retry
            </button>
          </div>
        </div>
      `;
    }
  }

  /**
   * Show prompt set creation form
   */
  showPromptSetCreation() {
    const promptSetContent = document.getElementById('promptSetContent');
    if (!promptSetContent) return;

    // Show the original creation form
    promptSetContent.innerHTML = `
      <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-3 p-3">
          <h3 id="promptSetFormHeader">Create New Prompt Set</h3>
          <button class="btn btn-outline-secondary" onclick="window.Pages.showPromptSetsList()">
            <i class="fas fa-arrow-left"></i> Back to Prompt Sets
          </button>
        </div>
        
        <div class="row h-100">
          <!-- Left Panel - Prompt Set Info -->
          <div class="col-md-4 border-end bg-light h-100 d-flex flex-column">
            <div class="p-3 border-bottom">
              <h5 class="mb-3">Prompt Set Details</h5>
              
              <!-- Prompt Set Name -->
              <div class="mb-3">
                <label for="promptSetName" class="form-label">Name</label>
                <div class="input-group">
                  <input type="text" class="form-control" id="promptSetName" placeholder="Enter prompt set name">
                  <button class="btn btn-outline-secondary" type="button" id="changeNameBtn" style="display: none;">
                    <i class="fas fa-edit"></i>
                  </button>
                </div>
                <div class="form-text" id="autoNameNotice" style="display: none;">
                  <i class="fas fa-info-circle"></i> Will be auto-saved as "Prompt Set X"
                </div>
              </div>

              <!-- Prompt Set Description -->
              <div class="mb-3">
                <label for="promptSetDescription" class="form-label">Description</label>
                <textarea class="form-control" id="promptSetDescription" rows="3" placeholder="Optional description"></textarea>
              </div>

              <!-- Import Options -->
              <div class="mb-3">
                <h6>Import Options</h6>
                <button class="btn btn-outline-primary btn-sm me-2" id="promptSetImportCsvBtn">
                  <i class="fas fa-file-csv"></i> Import CSV
                </button>
                <button class="btn btn-outline-secondary btn-sm" id="loadExistingBtn">
                  <i class="fas fa-folder-open"></i> Load Existing
                </button>
              </div>

              <!-- Prompt Count -->
              <div class="mb-3">
                <small class="text-muted">
                  <i class="fas fa-list"></i> <span id="promptCount">0</span> prompts
                </small>
              </div>
            </div>

            <!-- Action Buttons -->
            <div class="mt-auto p-3 border-top">
              <button class="btn btn-success w-100 mb-2" id="savePromptSetBtn">
                <i class="fas fa-save"></i> Save Prompt Set
              </button>
              <button class="btn btn-outline-danger w-100" id="deletePromptSetBtn" style="display: none;">
                <i class="fas fa-trash"></i> Delete Prompt Set
              </button>
            </div>
          </div>

          <!-- Right Panel - Prompts List -->
          <div class="col-md-8 h-100 d-flex flex-column">
            <div class="p-3 border-bottom">
              <div class="d-flex justify-content-between align-items-center">
                <h5 class="mb-0">Prompts</h5>
                <button class="btn btn-primary btn-sm" id="promptSetAddPromptBtn">
                  <i class="fas fa-plus"></i> Add Prompt
                </button>
              </div>
            </div>

            <!-- Prompts Container -->
            <div class="flex-grow-1 p-3" id="promptsContainer" style="overflow-y: auto; min-height: 0;">
              <div id="promptSetPromptsList" style="height: auto;">
                <!-- Prompts will be added here -->
              </div>
              
              <!-- Empty State -->
              <div id="emptyPromptsState" class="text-center text-muted py-5">
                <i class="fas fa-comment-dots fa-3x mb-3"></i>
                <h6>No prompts yet</h6>
                <p>Add prompts manually or import from a CSV file</p>
                <button class="btn btn-outline-primary" id="promptSetAddFirstPromptBtn">
                  <i class="fas fa-plus"></i> Add Your First Prompt
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Reset form and set up event listeners
    this.resetPromptSetForm();
    this.setupPromptSetEventListeners();
    this.updatePromptsDisplay();
  }

  /**
   * Reset the prompt set form
   */
  resetPromptSetForm() {
    document.getElementById('promptSetName').value = '';
    document.getElementById('promptSetDescription').value = '';
    document.getElementById('promptSetPromptsList').innerHTML = '';
    document.getElementById('changeNameBtn').style.display = 'none';
    document.getElementById('autoNameNotice').style.display = 'none';
    document.getElementById('deletePromptSetBtn').style.display = 'none';
    
    // Reset save button text
    const saveBtn = document.getElementById('savePromptSetBtn');
    if (saveBtn) {
      saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Prompt Set';
    }
    
    // Reset header text
    const header = document.getElementById('promptSetFormHeader');
    if (header) {
      header.textContent = 'Create New Prompt Set';
    }
    
    // Reset current prompt set tracking
    this.currentPromptSetId = null;
    this.promptSetPrompts = [];
    
    this.updatePromptCount();
  }

  /**
   * Set up event listeners for prompt set page
   */
  setupPromptSetEventListeners() {
    // Remove any existing listeners first
    const addPromptBtn = document.getElementById('promptSetAddPromptBtn');
    const addFirstPromptBtn = document.getElementById('promptSetAddFirstPromptBtn');
    const importCsvBtn = document.getElementById('promptSetImportCsvBtn');
    const loadExistingBtn = document.getElementById('loadExistingBtn');
    const savePromptSetBtn = document.getElementById('savePromptSetBtn');
    const deletePromptSetBtn = document.getElementById('deletePromptSetBtn');
    const changeNameBtn = document.getElementById('changeNameBtn');
    const promptSetNameInput = document.getElementById('promptSetName');

    // Add prompt buttons
    if (addPromptBtn) {
      addPromptBtn.onclick = () => this.addPromptToSet();
    }
    if (addFirstPromptBtn) {
      addFirstPromptBtn.onclick = () => this.addPromptToSet();
    }
    
    // Import/Load buttons
    if (importCsvBtn) {
      importCsvBtn.onclick = () => this.importPromptsFromCsv();
    }
    if (loadExistingBtn) {
      loadExistingBtn.onclick = () => this.showLoadExistingModal();
    }
    
    // Save/Delete buttons
    if (savePromptSetBtn) {
      savePromptSetBtn.onclick = () => this.savePromptSet();
    }
    if (deletePromptSetBtn) {
      deletePromptSetBtn.onclick = () => this.deleteCurrentPromptSet();
    }
    
    // Name change button
    if (changeNameBtn) {
      changeNameBtn.onclick = () => this.showNameChangeModal();
    }
    
    // Auto-name detection
    if (promptSetNameInput) {
      promptSetNameInput.oninput = (e) => {
        const hasName = e.target.value.trim().length > 0;
        const autoNameNotice = document.getElementById('autoNameNotice');
        if (autoNameNotice) {
          autoNameNotice.style.display = hasName ? 'none' : 'block';
        }
      };
    }
  }

  /**
   * Add a new prompt to prompt set
   */
  addPromptToSet(promptText = '') {
    const promptId = Date.now(); // Temporary ID for new prompts
    const prompt = {
      id: promptId,
      prompt_text: promptText,
      order_index: this.promptSetPrompts.length,
      isNew: true
    };
    
    this.promptSetPrompts.push(prompt);
    this.updatePromptsDisplay();
    
    // Focus on the new prompt textarea
    setTimeout(() => {
      const textarea = document.querySelector(`[data-prompt-id="${promptId}"] textarea`);
      if (textarea) {
        textarea.focus();
      }
    }, 100);
  }

  /**
   * Render a single prompt item
   */
  renderPromptItem(prompt) {
    const promptsList = document.getElementById('promptSetPromptsList');
    if (!promptsList) {
      console.error('promptSetPromptsList not found!');
      return;
    }
    
    console.log('Rendering prompt:', prompt.id, 'Text:', prompt.prompt_text.substring(0, 50) + '...');
    
    // Create completely minimal element with only inline styles
    const promptDiv = document.createElement('div');
    promptDiv.setAttribute('data-prompt-id', prompt.id);
    
    // Use only inline styles to force visibility
    promptDiv.style.cssText = `
      background: #ffffff !important;
      border: 2px solid #007bff !important;
      margin: 10px 0 !important;
      padding: 15px !important;
      min-height: 150px !important;
      height: auto !important;
      width: 100% !important;
      display: block !important;
      visibility: visible !important;
      opacity: 1 !important;
      position: relative !important;
      box-sizing: border-box !important;
      font-family: Arial, sans-serif !important;
      font-size: 14px !important;
      line-height: 1.4 !important;
      color: #333 !important;
      overflow: visible !important;
    `;
    
    // Create content with inline styles
    promptDiv.innerHTML = `
      <div style="display: flex !important; justify-content: space-between !important; align-items: flex-start !important; margin-bottom: 10px !important;">
        <strong style="color: #007bff !important; font-size: 16px !important;">Prompt ${prompt.order_index + 1}</strong>
        <div style="display: flex !important; gap: 5px !important;">
          <button style="padding: 5px 10px !important; background: #f8f9fa !important; border: 1px solid #ccc !important; cursor: pointer !important;" class="move-up-btn" ${prompt.order_index === 0 ? 'disabled' : ''}>↑</button>
          <button style="padding: 5px 10px !important; background: #f8f9fa !important; border: 1px solid #ccc !important; cursor: pointer !important;" class="move-down-btn" ${prompt.order_index === this.promptSetPrompts.length - 1 ? 'disabled' : ''}>↓</button>
          <button style="padding: 5px 10px !important; background: #f8f9fa !important; border: 1px solid #ccc !important; cursor: pointer !important; color: #dc3545 !important;" class="delete-prompt-btn">🗑</button>
        </div>
      </div>
      <textarea style="
        width: 100% !important;
        min-height: 80px !important;
        height: auto !important;
        padding: 10px !important;
        border: 1px solid #ccc !important;
        border-radius: 4px !important;
        font-family: Arial, sans-serif !important;
        font-size: 14px !important;
        resize: vertical !important;
        background: #ffffff !important;
        color: #333 !important;
        display: block !important;
        box-sizing: border-box !important;
      " class="prompt-textarea" placeholder="Enter your prompt here...">${prompt.prompt_text || ''}</textarea>
    `;
    
    // Add event listeners
    const textarea = promptDiv.querySelector('.prompt-textarea');
    if (textarea) {
      textarea.oninput = (e) => {
        prompt.prompt_text = e.target.value;
      };
    }
    
    const deleteBtn = promptDiv.querySelector('.delete-prompt-btn');
    if (deleteBtn) {
      deleteBtn.onclick = () => this.deletePrompt(prompt.id);
    }
    
    const moveUpBtn = promptDiv.querySelector('.move-up-btn');
    if (moveUpBtn) {
      moveUpBtn.onclick = () => this.movePrompt(prompt.id, -1);
    }
    
    const moveDownBtn = promptDiv.querySelector('.move-down-btn');
    if (moveDownBtn) {
      moveDownBtn.onclick = () => this.movePrompt(prompt.id, 1);
    }
    
    promptsList.appendChild(promptDiv);
    console.log('Prompt appended successfully. promptsList now has', promptsList.children.length, 'children');
    
    // Force multiple layout recalculations
    promptDiv.offsetHeight;
    promptDiv.scrollIntoView({ behavior: 'instant', block: 'nearest' });
    
    // Debug: Check if element is actually visible
    setTimeout(() => {
      const computedStyle = window.getComputedStyle(promptDiv);
      const parentStyle = window.getComputedStyle(promptsList);
      console.log('DEBUG - Prompt element:', {
        id: prompt.id,
        display: computedStyle.display,
        visibility: computedStyle.visibility,
        opacity: computedStyle.opacity,
        height: computedStyle.height,
        width: computedStyle.width,
        position: computedStyle.position,
        zIndex: computedStyle.zIndex,
        parentDisplay: parentStyle.display,
        parentVisibility: parentStyle.visibility,
        parentHeight: parentStyle.height,
        parentOverflow: parentStyle.overflow,
        offsetHeight: promptDiv.offsetHeight,
        offsetWidth: promptDiv.offsetWidth,
        clientHeight: promptDiv.clientHeight,
        clientWidth: promptDiv.clientWidth,
        boundingRect: promptDiv.getBoundingClientRect()
      });
    }, 100);
  }

  /**
   * Delete a prompt
   */
  deletePrompt(promptId) {
    this.promptSetPrompts = this.promptSetPrompts.filter(p => p.id !== promptId);
    this.reorderPrompts();
    this.renderAllPrompts();
    this.updatePromptsDisplay();
  }

  /**
   * Move a prompt up or down
   */
  movePrompt(promptId, direction) {
    const currentIndex = this.promptSetPrompts.findIndex(p => p.id === promptId);
    const newIndex = currentIndex + direction;
    
    if (newIndex >= 0 && newIndex < this.promptSetPrompts.length) {
      // Swap prompts
      [this.promptSetPrompts[currentIndex], this.promptSetPrompts[newIndex]] = 
      [this.promptSetPrompts[newIndex], this.promptSetPrompts[currentIndex]];
      
      this.reorderPrompts();
      this.renderAllPrompts();
    }
  }

  /**
   * Reorder prompts and update order_index
   */
  reorderPrompts() {
    this.promptSetPrompts.forEach((prompt, index) => {
      prompt.order_index = index;
    });
  }

  /**
   * Render all prompts
   */
  renderAllPrompts() {
    const promptsList = document.getElementById('promptSetPromptsList');
    if (!promptsList) {
      return;
    }
    
    // Clear existing prompts
    promptsList.innerHTML = '';
    
    // Render all prompts
    this.promptSetPrompts.forEach((prompt, index) => {
      const promptDiv = document.createElement('div');
      promptDiv.className = 'prompt-item';
      promptDiv.setAttribute('data-prompt-id', prompt.id);
      
      promptDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-start mb-3">
          <strong class="text-primary">Prompt ${prompt.order_index + 1}</strong>
          <div class="btn-group btn-group-sm" role="group">
            <button class="btn btn-outline-secondary move-up-btn" ${prompt.order_index === 0 ? 'disabled' : ''} title="Move up">
              <i class="fas fa-arrow-up"></i>
            </button>
            <button class="btn btn-outline-secondary move-down-btn" ${prompt.order_index === this.promptSetPrompts.length - 1 ? 'disabled' : ''} title="Move down">
              <i class="fas fa-arrow-down"></i>
            </button>
            <button class="btn btn-outline-danger delete-prompt-btn" title="Delete prompt">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
        <textarea class="form-control prompt-textarea" rows="3" placeholder="Enter your prompt here..." style="resize: vertical;">${prompt.prompt_text || ''}</textarea>
      `;
      
      // Add event listeners - this is crucial for saving changes
      const textarea = promptDiv.querySelector('.prompt-textarea');
      if (textarea) {
        textarea.oninput = (e) => {
          prompt.prompt_text = e.target.value;
          console.log(`Updated prompt ${prompt.id}:`, e.target.value.substring(0, 50) + '...');
        };
      }
      
      const deleteBtn = promptDiv.querySelector('.delete-prompt-btn');
      if (deleteBtn) {
        deleteBtn.onclick = () => this.deletePrompt(prompt.id);
      }
      
      const moveUpBtn = promptDiv.querySelector('.move-up-btn');
      if (moveUpBtn) {
        moveUpBtn.onclick = () => this.movePrompt(prompt.id, -1);
      }
      
      const moveDownBtn = promptDiv.querySelector('.move-down-btn');
      if (moveDownBtn) {
        moveDownBtn.onclick = () => this.movePrompt(prompt.id, 1);
      }
      
      promptsList.appendChild(promptDiv);
    });
  }

  /**
   * Update prompts display (show/hide empty state)
   */
  updatePromptsDisplay() {
    const emptyState = document.getElementById('emptyPromptsState');
    const promptsList = document.getElementById('promptSetPromptsList');
    
    if (this.promptSetPrompts.length === 0) {
      if (emptyState) emptyState.style.display = 'block';
      if (promptsList) promptsList.style.display = 'none';
    } else {
      if (emptyState) emptyState.style.display = 'none';
      if (promptsList) promptsList.style.display = 'block';
      
      // Render all prompts
      this.renderAllPrompts();
    }
    
    this.updatePromptCount();
  }

  /**
   * Update prompt count display
   */
  updatePromptCount() {
    document.getElementById('promptCount').textContent = this.promptSetPrompts.length;
  }

  /**
   * Import prompts from CSV
   */
  async importPromptsFromCsv() {
    try {
      const filePath = await window.API.openFileDialog({
        title: 'Select CSV file',
        filters: [{ name: 'CSV Files', extensions: ['csv'] }]
      });

      if (!filePath) return;

      const csvData = await window.API.readCsv(filePath);
      
      if (!csvData || csvData.length === 0) {
        window.Components.showToast('No data found in CSV file', 'warning');
        return;
      }

      // Clear existing prompts and add CSV prompts
      this.promptSetPrompts = [];
      
      csvData.forEach((row, index) => {
        const promptText = row.prompt || row.Prompt || row.question || row.Question || Object.values(row)[0] || '';
        if (promptText.trim()) {
          this.promptSetPrompts.push({
            id: Date.now() + index,
            prompt_text: promptText.trim(),
            order_index: index,
            isNew: true
          });
        }
      });

      this.updatePromptsDisplay();
      
      // Show auto-name notice if no name is set
      const nameInput = document.getElementById('promptSetName');
      if (!nameInput.value.trim()) {
        document.getElementById('autoNameNotice').style.display = 'block';
      }

      window.Components.showToast(`Imported ${this.promptSetPrompts.length} prompts from CSV`, 'success');
    } catch (error) {
      console.error('Error importing CSV:', error);
      window.Components.showToast('Failed to import CSV file', 'error');
    }
  }

  /**
   * Show modal to load existing prompt set
   */
  async showLoadExistingModal() {
    try {
      const promptSets = await window.API.getPromptSets();
      
      if (promptSets.length === 0) {
        window.Components.showToast('No existing prompt sets found', 'info');
        return;
      }

      // Create modal content
      const modalContent = `
        <div class="modal fade" id="loadExistingModal" tabindex="-1">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">Load Existing Prompt Set</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <div class="list-group">
                  ${promptSets.map(ps => `
                    <button type="button" class="list-group-item list-group-item-action" data-prompt-set-id="${ps.id}">
                      <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${ps.name}</h6>
                        <small>${ps.prompt_count} prompts</small>
                      </div>
                      <p class="mb-1">${ps.description || 'No description'}</p>
                      <small>Created: ${new Date(ps.created_at).toLocaleDateString()}</small>
                    </button>
                  `).join('')}
                </div>
              </div>
            </div>
          </div>
        </div>
      `;

      // Add modal to page
      document.body.insertAdjacentHTML('beforeend', modalContent);
      const modal = new bootstrap.Modal(document.getElementById('loadExistingModal'));
      
      // Add click handlers
      document.querySelectorAll('[data-prompt-set-id]').forEach(btn => {
        btn.onclick = () => {
          const promptSetId = parseInt(btn.dataset.promptSetId);
          modal.hide();
          this.loadPromptSet(promptSetId);
        };
      });

      // Clean up modal when hidden
      document.getElementById('loadExistingModal').addEventListener('hidden.bs.modal', () => {
        document.getElementById('loadExistingModal').remove();
      });

      modal.show();
    } catch (error) {
      console.error('Error loading prompt sets:', error);
      window.Components.showToast('Failed to load prompt sets', 'error');
    }
  }

  /**
   * Load an existing prompt set
   */
  async loadPromptSet(promptSetId) {
    try {
      const promptSet = await window.API.getPromptSetDetails(promptSetId);
      
      // Populate form
      document.getElementById('promptSetName').value = promptSet.name;
      document.getElementById('promptSetDescription').value = promptSet.description || '';
      
      // Load prompts
      this.promptSetPrompts = promptSet.prompts.map(p => ({
        ...p,
        isNew: false
      }));
      
      // Update UI
      this.currentPromptSetId = promptSetId;
      document.getElementById('deletePromptSetBtn').style.display = 'block';
      document.getElementById('autoNameNotice').style.display = 'none';
      
      this.updatePromptsDisplay();
      
      window.Components.showToast(`Loaded prompt set: ${promptSet.name}`, 'success');
    } catch (error) {
      console.error('Error loading prompt set:', error);
      window.Components.showToast('Failed to load prompt set', 'error');
    }
  }

  /**
   * Save the current prompt set
   */
  async savePromptSet() {
    try {
      const name = document.getElementById('promptSetName').value.trim();
      const description = document.getElementById('promptSetDescription').value.trim();
      
      // Validate
      if (this.promptSetPrompts.length === 0) {
        window.Components.showToast('Please add at least one prompt', 'warning');
        return;
      }

      // Auto-generate name if needed
      let finalName = name;
      if (!finalName) {
        const nextNumber = await window.API.getNextPromptSetNumber();
        finalName = `Prompt Set ${nextNumber}`;
        document.getElementById('promptSetName').value = finalName;
      }

      // Extract just the prompt texts
      const prompts = this.promptSetPrompts.map(p => p.prompt_text.trim()).filter(text => text);

      let result;
      if (this.currentPromptSetId) {
        // Update existing
        result = await window.API.updatePromptSet(this.currentPromptSetId, {
          name: finalName,
          description,
          prompts
        });
        window.Components.showToast(`Prompt set "${finalName}" updated successfully!`, 'success');
      } else {
        // Create new
        result = await window.API.createPromptSet(finalName, description, prompts);
        this.currentPromptSetId = result.prompt_set_id;
        document.getElementById('deletePromptSetBtn').style.display = 'block';
        
        // Update UI to reflect that we're now editing an existing prompt set
        const saveBtn = document.getElementById('savePromptSetBtn');
        if (saveBtn) {
          saveBtn.innerHTML = '<i class="fas fa-save"></i> Update Prompt Set';
        }
        
        const header = document.getElementById('promptSetFormHeader');
        if (header) {
          header.textContent = `Edit Prompt Set: ${finalName}`;
        }
        
        window.Components.showToast(`Prompt set "${finalName}" created successfully!`, 'success');
      }

      document.getElementById('autoNameNotice').style.display = 'none';
      
    } catch (error) {
      console.error('Error saving prompt set:', error);
      window.Components.showToast('Failed to save prompt set', 'error');
    }
  }

  /**
   * Delete the current prompt set
   */
  async deleteCurrentPromptSet() {
    if (!this.currentPromptSetId) return;

    const confirmed = confirm('Are you sure you want to delete this prompt set? This action cannot be undone.');
    if (!confirmed) return;

    try {
      await window.API.deletePromptSet(this.currentPromptSetId);
      window.Components.showToast('Prompt set deleted successfully', 'success');
      
      // Reset form
      this.resetPromptSetForm();
      
    } catch (error) {
      console.error('Error deleting prompt set:', error);
      window.Components.showToast('Failed to delete prompt set', 'error');
    }
  }

  /**
   * Show name change modal
   */
  showNameChangeModal() {
    const currentName = document.getElementById('promptSetName').value;
    const newName = prompt('Enter new name for this prompt set:', currentName);
    
    if (newName && newName.trim() !== currentName) {
      document.getElementById('promptSetName').value = newName.trim();
      document.getElementById('autoNameNotice').style.display = 'none';
    }
  }

  /**
   * Edit an existing prompt set
   */
  async editPromptSet(promptSetId) {
    try {
      const promptSet = await window.API.getPromptSetDetails(promptSetId);
      
      // Show the creation form
      this.showPromptSetCreation();
      
      // Wait for the form to be rendered
      setTimeout(() => {
        // Populate form with existing data
        document.getElementById('promptSetName').value = promptSet.name;
        document.getElementById('promptSetDescription').value = promptSet.description || '';
        
        // Load prompts with proper structure for editing
        this.promptSetPrompts = promptSet.prompts.map((p, index) => ({
          id: Date.now() + index, // Generate unique IDs for editing
          prompt_text: p.prompt_text,
          order_index: index,
          isNew: false, // Mark as existing prompts
          original_id: p.id // Keep reference to original ID if needed
        }));
        
        // Update UI state
        this.currentPromptSetId = promptSetId;
        document.getElementById('deletePromptSetBtn').style.display = 'block';
        document.getElementById('autoNameNotice').style.display = 'none';
        
        // Update the save button text to reflect editing
        const saveBtn = document.getElementById('savePromptSetBtn');
        if (saveBtn) {
          saveBtn.innerHTML = '<i class="fas fa-save"></i> Update Prompt Set';
        }
        
        // Update the header to show we're editing
        const header = document.getElementById('promptSetFormHeader');
        if (header) {
          header.textContent = `Edit Prompt Set: ${promptSet.name}`;
        }
        
        // Render the prompts
        this.updatePromptsDisplay();
        
        // Show success message
        window.Components.showToast(`Loaded "${promptSet.name}" for editing`, 'success');
      }, 100);
      
    } catch (error) {
      console.error('Error loading prompt set:', error);
      window.Components.showToast('Failed to load prompt set', 'error');
    }
  }

  /**
   * Use a prompt set in a new benchmark
   */
  async usePromptSetInBenchmark(promptSetId) {
    try {
      console.log('usePromptSetInBenchmark called with promptSetId:', promptSetId);
      const promptSet = await window.API.getPromptSetDetails(promptSetId);
      console.log('Loaded prompt set:', promptSet);
      
      // Navigate to composer page
      this.navigateTo('composerContent');
      
      // Wait for the page to load and be fully initialized
      await new Promise(resolve => {
        const checkReady = () => {
          const promptsList = document.getElementById('promptsList');
          if (promptsList && this.currentPage === 'composerContent') {
            console.log('Composer page is ready, loading prompts...');
            resolve();
          } else {
            console.log('Waiting for composer page to be ready...');
            setTimeout(checkReady, 50);
          }
        };
        checkReady();
      });
      
      // Clear existing prompts
      this.prompts = [];
      console.log('Cleared existing prompts');
      
      // Load prompts from the prompt set
      promptSet.prompts.forEach((prompt, index) => {
        console.log(`Loading prompt ${index + 1}:`, prompt.prompt_text.substring(0, 50) + '...');
        this.prompts.push({
          id: Utils.generateId(),
          text: prompt.prompt_text
        });
      });
      
      console.log('Total prompts loaded:', this.prompts.length);
      
      // Render the prompts
      this.renderPrompts();
      console.log('Prompts rendered');
      
      // Verify prompts are actually displayed
      setTimeout(() => {
        const promptsList = document.getElementById('promptsList');
        const promptElements = promptsList ? promptsList.querySelectorAll('.prompt-input') : [];
        console.log('Verification: Found', promptElements.length, 'prompt elements in DOM');
        
        if (promptElements.length !== this.prompts.length) {
          console.warn('Mismatch: Expected', this.prompts.length, 'prompts but found', promptElements.length, 'in DOM');
          // Try rendering again
          this.renderPrompts();
        }
      }, 100);
      
      // Show success message
      window.Components.showToast(`Loaded ${promptSet.prompts.length} prompts from "${promptSet.name}"`, 'success');
      
    } catch (error) {
      console.error('Error loading prompt set for benchmark:', error);
      window.Components.showToast('Failed to load prompt set', 'error');
    }
  }

  /**
   * Delete a prompt set from the list
   */
  async deletePromptSetFromList(promptSetId) {
    const confirmed = confirm('Are you sure you want to delete this prompt set? This action cannot be undone.');
    if (!confirmed) return;

    try {
      await window.API.deletePromptSet(promptSetId);
      window.Components.showToast('Prompt set deleted successfully', 'success');
      
      // Refresh the list
      await this.showPromptSetsList();
      
    } catch (error) {
      console.error('Error deleting prompt set:', error);
      window.Components.showToast('Failed to delete prompt set', 'error');
    }
  }
}

// Create singleton instance
window.Pages = new Pages(); 