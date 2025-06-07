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
    this.resultsTableZoom = 1.0; // For zoom functionality in results table
    
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
        case 'filesContent':
          this.initFilesPage();
          break;
        case 'settingsContent':
          // Settings page initialization is handled by the Settings class
          if (window.Settings) {
            window.Settings.loadSettings();
          }
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
    
    // Always include the Settings button
    const settingsButton = `
      <button id="settingsBtn" class="btn btn-outline-light" onclick="window.Pages.navigateTo('settingsContent')">
        <i class="fas fa-cog me-1"></i>Settings
      </button>
    `;
    
    switch (pageId) {
      case 'homeContent':
        headerActions.innerHTML = `
          ${settingsButton}
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('promptSetContent')">
            <i class="fas fa-layer-group"></i> Prompts
          </button>
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('filesContent')">
            <i class="fas fa-file"></i> Files
          </button>
          <button class="btn btn-success border-2 ms-3" onclick="window.Pages.navigateTo('composerContent')" style="border-width: 2px !important; font-weight: 600; box-shadow: 0 2px 4px rgba(7, 234, 255, 0.3);">
            <i class="fas fa-plus"></i> New Benchmark
          </button>
        `;
        break;
      case 'composerContent':
        headerActions.innerHTML = `
          ${settingsButton}
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
          <button class="btn btn-success me-2 ms-3 border-2" id="runBenchmarkBtn" style="border-width: 2px !important; font-weight: 600;">
            <i class="fas fa-play"></i> Run Benchmark
          </button>
        `;
        break;
      case 'promptSetContent':
        headerActions.innerHTML = `
          ${settingsButton}
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
        `;
        break;
      case 'filesContent':
        headerActions.innerHTML = `
          ${settingsButton}
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
        `;
        break;
      case 'detailsContent':
        headerActions.innerHTML = `
          ${settingsButton}
          <button class="btn btn-outline-info me-2" onclick="window.Pages.forceRefresh()">
            <i class="fas fa-sync-alt"></i> Refresh
          </button>
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
        `;
        break;
      case 'settingsContent':
        headerActions.innerHTML = `
          ${settingsButton}
          <button class="btn btn-outline-light" onclick="window.Pages.navigateTo('homeContent')">
            <i class="fas fa-home"></i> Back to Home
          </button>
        `;
        break;
      default:
        headerActions.innerHTML = settingsButton;
    }
  }

  /**
   * Initialize home page
   */
  async initHomePage() {
    console.log('Pages.initHomePage called');
    try {
      // Use fresh data on initial load to ensure we get the latest benchmarks
      await this.loadBenchmarks(false, 0);
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
      
      // Initialize web search toggle
      this.setupWebSearchToggle();
      
      console.log('Pages.initComposerPage completed successfully');
    } catch (error) {
      console.error('Error initializing composer page:', error);
      window.Components.showToast('Failed to load models', 'error');
    }
  }

  /**
   * Set up web search toggle functionality
   */
  setupWebSearchToggle() {
    const webSearchToggle = document.getElementById('webSearchToggle');
    const webSearchOptions = document.getElementById('webSearchOptions');
    const webSearchAllPromptsToggle = document.getElementById('webSearchAllPromptsToggle');
    const webSearchPromptControls = document.getElementById('webSearchPromptControls');
    
    if (!webSearchToggle) return;
    
    // When main toggle changes
    webSearchToggle.addEventListener('change', (e) => {
      if (e.target.checked) {
        webSearchOptions.classList.remove('d-none');
      } else {
        webSearchOptions.classList.add('d-none');
      }
    });
    
    // When "all prompts" toggle changes
    if (webSearchAllPromptsToggle) {
      webSearchAllPromptsToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
          webSearchPromptControls.classList.add('d-none');
        } else {
          this.renderWebSearchPromptControls();
          webSearchPromptControls.classList.remove('d-none');
        }
      });
    }
  }
  
  /**
   * Render individual web search controls for each prompt
   */
  renderWebSearchPromptControls() {
    const container = document.getElementById('webSearchPromptControls');
    if (!container) return;
    
    container.innerHTML = '';
    
    this.prompts.forEach((prompt, index) => {
      const promptPreview = prompt.text.substring(0, 30) + (prompt.text.length > 30 ? '...' : '');
      
      const control = document.createElement('div');
      control.className = 'form-check';
      control.innerHTML = `
        <input class="form-check-input web-search-prompt-toggle" type="checkbox" 
               id="webSearchPrompt${index}" data-prompt-index="${index}" checked>
        <label class="form-check-label" for="webSearchPrompt${index}">
          Prompt ${index + 1}: <span class="text-muted small">${promptPreview}</span>
        </label>
      `;
      
      container.appendChild(control);
    });
  }

  /**
   * Set up event listeners for composer page
   */
  setupComposerEventListeners() {
    const loadPromptSetBtn = document.getElementById('loadPromptSetBtn');
    if (loadPromptSetBtn) {
      loadPromptSetBtn.onclick = () => this.showLoadPromptSetModal();
    }
    
    // Set up select all models toggle
    this.setupSelectAllModelsToggle();
  }
  
  /**
   * Set up the select all models toggle functionality
   */
  setupSelectAllModelsToggle() {
    const selectAllToggle = document.getElementById('selectAllModelsToggle');
    if (!selectAllToggle) return;
    
    selectAllToggle.addEventListener('change', (e) => {
      const isChecked = e.target.checked;
      const modelCheckboxes = document.querySelectorAll('#modelList input[type="checkbox"]');
      
      // Use requestAnimationFrame to ensure DOM updates are applied synchronously
      requestAnimationFrame(() => {
        modelCheckboxes.forEach(checkbox => {
          checkbox.checked = isChecked;
          
          // Trigger change event to update PDF display if needed
          checkbox.dispatchEvent(new Event('change'));
        });
        
        // Show a quick toast to confirm the action
        const count = modelCheckboxes.length;
        const action = isChecked ? 'selected' : 'deselected';
        window.Components.showToast(`${count} models ${action}`, 'info', 2000);
      });
    });
    
    // Also update the toggle state when individual checkboxes change
    const updateToggleState = () => {
      const modelCheckboxes = document.querySelectorAll('#modelList input[type="checkbox"]');
      const checkedBoxes = document.querySelectorAll('#modelList input[type="checkbox"]:checked');
      
      if (checkedBoxes.length === 0) {
        // No models selected
        selectAllToggle.checked = false;
        selectAllToggle.indeterminate = false;
      } else if (checkedBoxes.length === modelCheckboxes.length) {
        // All models selected
        selectAllToggle.checked = true;
        selectAllToggle.indeterminate = false;
      } else {
        // Some models selected
        selectAllToggle.checked = false;
        selectAllToggle.indeterminate = true;
      }
    };
    
    // Set up listeners on individual model checkboxes (needs to be done after models load)
    const setupIndividualCheckboxListeners = () => {
      const modelCheckboxes = document.querySelectorAll('#modelList input[type="checkbox"]');
      modelCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateToggleState);
      });
      
      // Update initial state
      updateToggleState();
    };
    
    // If models are already loaded, set up listeners immediately
    const modelCheckboxes = document.querySelectorAll('#modelList input[type="checkbox"]');
    if (modelCheckboxes.length > 0) {
      setupIndividualCheckboxListeners();
    } else {
      // Otherwise, wait for models to load with a MutationObserver
      const modelList = document.getElementById('modelList');
      if (modelList) {
        const observer = new MutationObserver((mutations) => {
          mutations.forEach((mutation) => {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
              const checkboxes = modelList.querySelectorAll('input[type="checkbox"]');
              if (checkboxes.length > 0) {
                setupIndividualCheckboxListeners();
                observer.disconnect(); // Stop observing once we've set up the listeners
              }
            }
          });
        });
        
        observer.observe(modelList, { childList: true, subtree: true });
      }
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
   * @param {number} retryCount - Current retry attempt
   */
  async loadBenchmarks(useCache = true, retryCount = 0) {
    console.log('Pages.loadBenchmarks called with useCache:', useCache, 'retryCount:', retryCount);
    const gridContainer = document.getElementById('benchmarksGrid');
    const tableBody = document.querySelector('#benchmarksTable tbody');

    try {
      // Only show loading state if we're forcing a refresh (not using cache) or on first load
      if (!useCache || retryCount === 0) {
        console.log('Showing loading state...');
        gridContainer.innerHTML = '';
        
        if (retryCount > 0) {
          gridContainer.appendChild(window.Components.createSpinner(`Connecting to backend (attempt ${retryCount + 1})...`));
        } else {
          gridContainer.appendChild(window.Components.createSpinner('Loading benchmarks...'));
        }
        
        tableBody.innerHTML = `
          <tr>
            <td colspan="5" class="text-center">
              <div class="d-flex justify-content-center align-items-center py-3">
                <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
                ${retryCount > 0 ? `Connecting to backend (attempt ${retryCount + 1})...` : 'Loading benchmarks...'}
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
      
      // Check if this is a connection error and we should retry
      const isConnectionError = error.message.includes('ECONNREFUSED') || 
                               error.message.includes('Failed to load benchmarks') ||
                               error.message.includes('connect');
      
      if (isConnectionError && retryCount < 5) {
        console.log(`Connection failed, retrying in ${2 ** retryCount} seconds... (attempt ${retryCount + 1}/5)`);
        
        // Show retry countdown in UI
        gridContainer.innerHTML = '';
        gridContainer.appendChild(
          window.Components.createSpinner(`Backend not ready. Retrying in ${2 ** retryCount} seconds... (${retryCount + 1}/5)`)
        );
        
        tableBody.innerHTML = `
          <tr>
            <td colspan="5" class="text-center text-warning py-3">
              <div class="d-flex justify-content-center align-items-center">
                <div class="spinner-border spinner-border-sm text-warning me-2" role="status"></div>
                Backend not ready. Retrying in ${2 ** retryCount} seconds... (${retryCount + 1}/5)
              </div>
            </td>
          </tr>
        `;
        
        // Clear cache and retry with exponential backoff
        window.API.clearCache('benchmarks');
        setTimeout(() => {
          this.loadBenchmarks(false, retryCount + 1);
        }, (2 ** retryCount) * 1000);
        
        return;
      }
      
      // Show error state after max retries or non-connection error
      gridContainer.innerHTML = '';
      gridContainer.appendChild(
        window.Components.createErrorState(
          isConnectionError ? 'Backend Connection Failed' : 'Failed to Load Benchmarks',
          isConnectionError ? 'Unable to connect to backend after multiple attempts. Please check if the backend is running.' : error.message,
          () => this.loadBenchmarks(false)
        )
      );

      tableBody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center text-danger py-3">
            Error: ${isConnectionError ? 'Backend connection failed' : error.message}
            <br>
            <button class="btn btn-outline-primary btn-sm mt-2" onclick="window.Pages.loadBenchmarks(false)">
              <i class="fas fa-redo me-1"></i>Retry
            </button>
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
    // Reconcile benchmark statuses before rendering
    const reconciledBenchmarks = this.benchmarksData.map(benchmark => this.reconcileBenchmarkStatus(benchmark));
    
    // Render grid view
    const gridRow = document.createElement('div');
    gridRow.className = 'row';
    
    reconciledBenchmarks.forEach(benchmark => {
      const card = window.Components.createBenchmarkCard(benchmark, {
        onView: (id) => this.viewBenchmarkDetails(id),
        onEdit: (benchmark) => this.editBenchmark(benchmark),
        onDelete: (id) => this.deleteBenchmark(id)
      });
      gridRow.appendChild(card);
    });
    
    gridContainer.appendChild(gridRow);

    // Render table view
    reconciledBenchmarks.forEach(benchmark => {
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
   * Reconcile benchmark status based on completion data
   * @param {Object} benchmark - Benchmark data
   * @returns {Object} Benchmark with reconciled status
   */
  reconcileBenchmarkStatus(benchmark) {
    // Create a copy to avoid mutating original data
    const reconciledBenchmark = { ...benchmark };
    
    // Only reconcile if we have the necessary data and they are valid numbers
    const completedPrompts = benchmark.completed_prompts || 0;
    const totalPrompts = benchmark.total_prompts || 0;
    const currentStatus = benchmark.status;
    
    if (totalPrompts > 0 && completedPrompts !== undefined) {
      const isActuallyComplete = completedPrompts >= totalPrompts;
      
      // If the data shows completion but status says in_progress, update it
      if (isActuallyComplete && (currentStatus === 'in_progress' || currentStatus === 'in-progress' || currentStatus === 'running')) {
        console.log(`Reconciling benchmark ${benchmark.id}: ${completedPrompts}/${totalPrompts} complete, updating status from ${currentStatus} to completed`);
        reconciledBenchmark.status = 'completed';
        
        // Clear cache since we found a status mismatch
        window.API.clearCache('benchmarks');
      }
    } else {
      // If we don't have completion data, we can't reconcile - just log for debugging
      console.log(`Cannot reconcile benchmark ${benchmark.id}: missing completion data (completed: ${completedPrompts}, total: ${totalPrompts})`);
    }
    
    return reconciledBenchmark;
  }

  /**
   * View benchmark details
   * @param {number} benchmarkId - Benchmark ID
   */
  async viewBenchmarkDetails(benchmarkId) {
    const detailsContainer = document.getElementById('detailsContainer');
    
    try {
      // Store current benchmark ID for refresh tracking
      this.currentBenchmarkId = benchmarkId;
      
      // Show loading state
      detailsContainer.innerHTML = '';
      detailsContainer.appendChild(window.Components.createSpinner('Loading benchmark details...'));
      
      // Navigate to details page
      this.navigateTo('detailsContent');
      
      // Always fetch and show the standard details view (works for both running and completed)
      const details = await window.API.getBenchmarkDetails(benchmarkId);
      const renderedStatus = this.renderBenchmarkDetails(details);
      
      // If the benchmark is still running (based on reconciled status), set up auto-refresh
      if (renderedStatus && renderedStatus.isRunning) {
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
    
    // WebSocket real-time updates have replaced polling
    // The benchmark will be updated instantly via WebSocket events
    // Keeping polling as a fallback for now, but with longer interval
    this.refreshInterval = setInterval(async () => {
      try {
        // Check if we're still on the details page for this benchmark
        if (this.currentPage !== 'detailsContent') {
          clearInterval(this.refreshInterval);
          return;
        }
        
        // Fetch updated details as fallback
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
    }, 10000); // Reduced frequency to 10 seconds as WebSocket provides real-time updates
  }

  /**
   * Refresh the current benchmark (called by WebSocket events)
   */
  async refreshBenchmark() {
    if (this.currentBenchmarkId) {
      console.log('Refreshing benchmark via WebSocket event:', this.currentBenchmarkId);
      try {
        const details = await window.API.getBenchmarkDetails(this.currentBenchmarkId);
        if (details) {
          this.renderBenchmarkDetails(details);
        }
      } catch (error) {
        console.error('Error refreshing benchmark:', error);
      }
    }
  }

  /**
   * Render benchmark details
   * @param {Object} details - Benchmark details
   */
  renderBenchmarkDetails(details) {
    const detailsContainer = document.getElementById('detailsContainer');

    // Get the total number of prompts from the database progress fields
    let totalPromptsInBenchmark = details.total_prompts || 0;
    let completedPromptsInBenchmark = details.completed_prompts || 0;
    let failedPromptsInBenchmark = details.failed_prompts || 0;
    
    // Calculate better progress metrics based on user's request
    // Count unique prompts and models
    const uniquePromptsSet = new Set();
    const uniqueModelsSet = new Set();
    const promptCompletionByModel = new Map(); // prompt_text -> Set of completed models
    const modelCompletionByPrompt = new Map(); // model_key -> Set of completed prompts
    
    if (details.runs && details.runs.length > 0) {
      details.runs.forEach(run => {
        const modelKey = `${run.model_name}_${run.provider}`;
        uniqueModelsSet.add(modelKey);
        
        if (run.prompts && run.prompts.length > 0) {
          run.prompts.forEach(prompt => {
            if (prompt.prompt) {
              uniquePromptsSet.add(prompt.prompt);
              
              // Track which models completed each prompt
              if (!promptCompletionByModel.has(prompt.prompt)) {
                promptCompletionByModel.set(prompt.prompt, new Set());
              }
              
              // Track which prompts each model completed  
              if (!modelCompletionByPrompt.has(modelKey)) {
                modelCompletionByPrompt.set(modelKey, new Set());
              }
              
              // Check if this prompt has a valid response (completed)
              const hasValidResponse = prompt.response && 
                                     prompt.response.trim().length > 0 && 
                                     !prompt.response.startsWith('ERROR');
              
              if (hasValidResponse) {
                promptCompletionByModel.get(prompt.prompt).add(modelKey);
                modelCompletionByPrompt.get(modelKey).add(prompt.prompt);
              }
            }
          });
        }
      });
    }
    
    // Calculate prompts that are complete across ALL models (no errors)
    const totalUniquePrompts = uniquePromptsSet.size;
    const totalUniqueModels = uniqueModelsSet.size;
    
    let fullyCompletedPrompts = 0;
    promptCompletionByModel.forEach((completedModels, promptText) => {
      if (completedModels.size === totalUniqueModels) {
        fullyCompletedPrompts++;
      }
    });
    
    // Calculate models that completed ALL prompts (no errors)
    let fullyCompletedModels = 0;
    modelCompletionByPrompt.forEach((completedPrompts, modelKey) => {
      if (completedPrompts.size === totalUniquePrompts) {
        fullyCompletedModels++;
      }
    });
    
    // If progress fields are not available, fall back to calculating from runs
    if (totalPromptsInBenchmark === 0 && details.runs && details.runs.length > 0) {
      // Calculate total prompts as models × prompts per model
      totalPromptsInBenchmark = totalUniqueModels * totalUniquePrompts;
    }
    
    // Determine actual completion status based on data, not just stored status
    const totalExpectedPrompts = totalUniqueModels * totalUniquePrompts;
    const actuallyComplete = totalExpectedPrompts > 0 && 
                            fullyCompletedPrompts === totalUniquePrompts && 
                            fullyCompletedModels === totalUniqueModels;
    
    // If the data shows completion but status says in_progress, update our local status
    let actualStatus = details.status;
    if (actuallyComplete && (actualStatus === 'in_progress' || actualStatus === 'in-progress' || actualStatus === 'running')) {
      console.log(`Benchmark ${details.id} appears complete but status is ${actualStatus}. Updating to completed.`);
      actualStatus = 'completed';
      
      // Update the cached benchmark list to reflect the new status
      window.API.clearCache('benchmarks');
    }
    
    // Determine if this is a running benchmark based on the reconciled status
    const isRunning = actualStatus === 'running' || actualStatus === 'in-progress' || actualStatus === 'in_progress';
    
    // Deduplicate models and build per-model table data
    const uniqueModels = new Map();
    if (details.runs && details.runs.length > 0) {
      details.runs.forEach(run => {
        const modelKey = `${run.model_name}_${run.provider}`;
        if (!uniqueModels.has(modelKey)) {
          // Initialize with first run
          uniqueModels.set(modelKey, {
            ...run,
            aggregated_cost: 0,
            aggregated_tokens: 0,
            aggregated_latency: 0,
            aggregated_completed_prompts: 0,
            aggregated_total_prompts: 0,
            all_runs: []
          });
        }
        
        // Add this run to the aggregation
        const aggregatedRun = uniqueModels.get(modelKey);
        aggregatedRun.all_runs.push(run);
        
        // Aggregate run-level totals (from database) - more reliable than prompt-level calculation
        if (run.total_cost) {
          aggregatedRun.aggregated_cost += run.total_cost;
        }
        if (run.total_standard_input_tokens || run.total_cached_input_tokens || run.total_output_tokens) {
          aggregatedRun.aggregated_tokens += (run.total_standard_input_tokens || 0) + 
                                            (run.total_cached_input_tokens || 0) + 
                                            (run.total_output_tokens || 0);
        }
        if (run.latency) {
          aggregatedRun.aggregated_latency += run.latency;
        }
      });
      
      // After collecting all runs, deduplicate prompts for each model
      uniqueModels.forEach((aggregatedRun, modelKey) => {
        const allPrompts = new Set(); // Track unique prompts by text
        const completedPrompts = new Set(); // Track completed prompts by text
        
        // Collect all unique prompts across all runs for this model
        aggregatedRun.all_runs.forEach(runData => {
          if (runData.prompts && runData.prompts.length > 0) {
            runData.prompts.forEach(prompt => {
              if (prompt.prompt) {
                allPrompts.add(prompt.prompt);
                if (prompt.response && prompt.response.trim().length > 0) {
                  completedPrompts.add(prompt.prompt);
                }
              }
            });
          }
        });
        
        // Set the deduplicated counts
        aggregatedRun.aggregated_total_prompts = allPrompts.size;
        aggregatedRun.aggregated_completed_prompts = completedPrompts.size;
      });
    }
    
    let modelTableRows = '';
    if (uniqueModels.size > 0) {
      modelTableRows = Array.from(uniqueModels.values()).map(aggregatedRun => {
        const modelName = aggregatedRun.model_name || 'Unknown Model';
        const provider = aggregatedRun.provider || 'unknown';
        
        // Calculate metrics for this specific model based on completed prompts
        let modelCost = aggregatedRun.aggregated_cost;
        let modelTokens = aggregatedRun.aggregated_tokens;
        // Latency is stored in milliseconds in the database (newer runs) or seconds (older runs)
        // Handle both cases by detecting magnitude
        let modelLatencyMs = aggregatedRun.aggregated_latency;
        // If latency is less than 1000, it's likely stored in seconds (old format)
        if (modelLatencyMs > 0 && modelLatencyMs < 1000) {
          modelLatencyMs = modelLatencyMs * 1000; // Convert to milliseconds
        }
        
        // If run.latency is 0 or missing, calculate it from individual prompt latencies
        if (modelLatencyMs === 0 && aggregatedRun.all_runs.length > 0) {
          aggregatedRun.all_runs.forEach(run => {
            if (run.prompts && run.prompts.length > 0) {
              run.prompts.forEach(prompt => {
                if (prompt.response && prompt.response.trim().length > 0) { // Only count completed prompts
                  let promptLatencyMs = prompt.prompt_latency || 0;
                  // Handle both milliseconds and seconds format for prompt latency
                  if (promptLatencyMs > 0 && promptLatencyMs < 1000) {
                    promptLatencyMs = promptLatencyMs * 1000; // Convert to milliseconds
                  }
                  modelLatencyMs += promptLatencyMs;
                }
              });
            }
          });
        }
        
        let completedPrompts = aggregatedRun.aggregated_completed_prompts;
        let totalPromptsForThisModel = aggregatedRun.aggregated_total_prompts;
        
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
        
        // Determine status for this model based on database status fields
        let statusContent = '';
        let latencyContent = '';
        let costContent = '';
        let tokensContent = '';
        
        // Use the run_status field from database if available, otherwise fall back to old logic
        const runStatus = aggregatedRun.all_runs[0].run_status || '';
        const runCompletedPrompts = aggregatedRun.all_runs[0].run_completed_prompts || completedPrompts;
        const runTotalPrompts = aggregatedRun.all_runs[0].run_total_prompts || totalPromptsForThisModel;
        
        // A model is considered complete based on the status field
        const modelIsComplete = runStatus === 'completed' || 
                               (!isRunning && completedPrompts > 0) ||
                               (runTotalPrompts > 0 && runCompletedPrompts >= runTotalPrompts);
        const modelHasStarted = runStatus === 'in_progress' || runStatus === 'completed' || 
                               completedPrompts > 0 || totalPromptsForThisModel > 0;
        
        if (!modelHasStarted && isRunning) {
          // Model hasn't started yet
          statusContent = '<i class="fas fa-spinner fa-spin text-primary me-2"></i>';
          latencyContent = '<span class="text-muted">Starting...</span>';
          costContent = '<span class="text-muted">Starting...</span>';
          tokensContent = '<span class="text-muted">Starting...</span>';
        } else if (!modelIsComplete && isRunning) {
          // Model is in progress
          statusContent = '<i class="fas fa-clock text-warning me-2"></i>';
          latencyContent = `<span class="text-info">${formatLatency(modelLatencyMs)}</span> <small class="text-muted">(${runCompletedPrompts}/${runTotalPrompts || 'TBD'})</small>`;
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

    // Add running indicator to the header if needed with actual progress
    const runningBanner = isRunning ? `
      <div class="alert alert-info d-flex align-items-center mb-4">
        <div class="spinner-border spinner-border-sm text-info me-3" role="status"></div>
        <div class="flex-grow-1">
          <strong>Benchmark Running</strong> - Results will update automatically as models complete
          <div class="small mt-1">
            <strong>Prompts complete:</strong> ${fullyCompletedPrompts}/${totalUniquePrompts} 
            <span class="mx-2">•</span>
            <strong>Models complete:</strong> ${fullyCompletedModels}/${totalUniqueModels}
            ${failedPromptsInBenchmark > 0 ? `<span class="text-danger mx-2">(${failedPromptsInBenchmark} total failures)</span>` : ''}
          </div>
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
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h4 class="text-primary mb-1">${fullyCompletedPrompts}/${totalUniquePrompts}</h4>
              <small class="text-muted">Prompts Complete</small>
              ${isRunning && totalUniquePrompts > 0 ? `
                <div class="progress mt-2" style="height: 5px;">
                  <div class="progress-bar bg-primary" role="progressbar" 
                       style="width: ${(fullyCompletedPrompts / totalUniquePrompts) * 100}%">
                  </div>
                </div>
              ` : ''}
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h4 class="text-success mb-1">${fullyCompletedModels}/${totalUniqueModels}</h4>
              <small class="text-muted">Models Complete</small>
              ${isRunning && totalUniqueModels > 0 ? `
                <div class="progress mt-2" style="height: 5px;">
                  <div class="progress-bar bg-success" role="progressbar" 
                       style="width: ${(fullyCompletedModels / totalUniqueModels) * 100}%">
                  </div>
                </div>
              ` : ''}
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h4 class="text-dark mb-1">${Utils.formatDate(details.created_at).split(',')[0]}</h4>
              <small class="text-muted">Created</small>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h4 class="text-secondary mb-1">${actualStatus || 'complete'}</h4>
              <small class="text-muted">Status</small>
            </div>
          </div>
        </div>
      </div>

      <!-- Model Performance Summary -->
      <div class="mb-4">
        <h4 class="mb-3">
          <i class="fas fa-chart-bar me-2"></i>Model Performance Summary
        </h4>
        <div class="row">
          <!-- Chart Panel -->
          <div class="col-md-6">
            <div class="card h-100">
              <div class="card-header">
                <h6 class="mb-0">Latency vs Cost</h6>
              </div>
              <div class="card-body">
                <canvas id="modelPerformanceChart" width="400" height="300"></canvas>
              </div>
            </div>
          </div>
          <!-- Table Panel -->
          <div class="col-md-6">
            <div class="card h-100">
              <div class="card-header">
                <h6 class="mb-0">Performance Metrics</h6>
              </div>
              <div class="card-body p-0">
                <div class="table-responsive">
                  <table class="table table-hover mb-0" id="modelPerformanceTable">
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
            </div>
          </div>
        </div>
      </div>

      <!-- Detailed Results -->
      <div class="results-section">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h4 class="mb-0">
            <i class="fas me-2"></i>Results
          </h4>
          <div class="d-flex gap-2 align-items-center">
            ${!isRunning && details.runs && details.runs.length > 0 ? `
              <button class="btn btn-warning" id="syncBenchmarkBtn" data-benchmark-id="${details.id}">
                <i class="fas fa-sync-alt me-1"></i>Sync Missing/Failed
              </button>
            ` : ''}
            <div class="btn-group" role="group" aria-label="Results view">
              <input type="radio" class="btn-check" name="resultsView" id="readAllView" autocomplete="off" checked>
              <label class="btn btn-outline-primary" for="readAllView">
                <i class="fas fa-list me-1"></i>Read All Results
              </label>
              
              <input type="radio" class="btn-check" name="resultsView" id="tableView" autocomplete="off">
              <label class="btn btn-outline-primary" for="tableView">
                <i class="fas fa-table me-1"></i>Results Table
              </label>
            </div>
          </div>
        </div>
        
        <!-- Read All Results View -->
        <div id="readAllResultsContainer" style="max-height: 70vh; overflow-y: auto; padding-bottom: 2rem;">
          ${this.renderModelResults(details.runs || [])}
        </div>
        
        <!-- Results Table View -->
        <div id="resultsTableContainer" style="display: none; max-height: 70vh; overflow-y: auto; padding-bottom: 2rem;">
          ${this.renderResultsTable(details.runs || [])}
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

    const syncBtn = document.getElementById('syncBenchmarkBtn');
    if (syncBtn) {
      syncBtn.addEventListener('click', () => this.syncBenchmark(details.id));
    }

    // Add view switching event listeners
    const readAllViewBtn = document.getElementById('readAllView');
    const tableViewBtn = document.getElementById('tableView');
    const readAllContainer = document.getElementById('readAllResultsContainer');
    const tableContainer = document.getElementById('resultsTableContainer');

    if (readAllViewBtn && tableViewBtn && readAllContainer && tableContainer) {
      readAllViewBtn.addEventListener('change', () => {
        if (readAllViewBtn.checked) {
          // Clean up any modal issues before switching views
          this.cleanupModals();
          readAllContainer.style.display = 'block';
          tableContainer.style.display = 'none';
        }
      });

      tableViewBtn.addEventListener('change', () => {
        if (tableViewBtn.checked) {
          // Clean up any modal issues before switching views
          this.cleanupModals();
          readAllContainer.style.display = 'none';
          tableContainer.style.display = 'block';
          // Re-setup table interactivity after switching to table view
          setTimeout(() => {
            this.setupResultsTableInteractivity();
          }, 100);
        }
      });
    }

    // Create model performance chart
    this.createModelPerformanceChart(uniqueModels);

    // Add table sorting functionality (only if not running to avoid conflicts)
    if (!isRunning) {
      this.setupTableSorting();
    }

    // Set up results table interactivity if it exists
    setTimeout(() => {
      this.setupResultsTableInteractivity();
    }, 100);
    
    // Return status information for the caller
    return {
      isRunning,
      actualStatus,
      originalStatus: details.status,
      actuallyComplete
    };
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
   * Set up results table interactivity (click handlers, zoom, pan)
   */
  setupResultsTableInteractivity() {
    const tableWrapper = document.getElementById('resultsTableWrapper');
    const table = document.getElementById('resultsTable');
    
    if (!tableWrapper || !table) return;

    // Set up click handlers for response cells using event delegation
    tableWrapper.addEventListener('click', (e) => {
      const cell = e.target.closest('.response-cell');
      if (cell) {
        const promptText = cell.getAttribute('data-prompt-text');
        const responseText = cell.getAttribute('data-response-text');
        const promptId = cell.getAttribute('data-prompt-id');
        const modalTitle = cell.getAttribute('data-modal-title');
        
        if (promptText && responseText) {
          this.showResponseModal(promptText, responseText, modalTitle, promptId);
        }
      }
    });

    // Set up zoom with mouse wheel
    tableWrapper.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoomResultsTable(delta);
      }
    });

    // Set up panning functionality
    let isDragging = false;
    let startX, startY, scrollLeft, scrollTop;

    tableWrapper.addEventListener('mousedown', (e) => {
      if (e.target.closest('.response-cell, th, button')) return; // Don't interfere with clicks
      
      isDragging = true;
      tableWrapper.style.cursor = 'grabbing';
      startX = e.pageX - tableWrapper.offsetLeft;
      startY = e.pageY - tableWrapper.offsetTop;
      scrollLeft = tableWrapper.scrollLeft;
      scrollTop = tableWrapper.scrollTop;
    });

    tableWrapper.addEventListener('mouseleave', () => {
      isDragging = false;
      tableWrapper.style.cursor = 'grab';
    });

    tableWrapper.addEventListener('mouseup', () => {
      isDragging = false;
      tableWrapper.style.cursor = 'grab';
    });

    tableWrapper.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      e.preventDefault();
      const x = e.pageX - tableWrapper.offsetLeft;
      const y = e.pageY - tableWrapper.offsetTop;
      const walkX = (x - startX) * 2;
      const walkY = (y - startY) * 2;
      tableWrapper.scrollLeft = scrollLeft - walkX;
      tableWrapper.scrollTop = scrollTop - walkY;
    });

    // Initialize zoom level
    if (!this.resultsTableZoom) {
      this.resultsTableZoom = 1.0;
    }
  }

  /**
   * Zoom the results table
   * @param {number} factor - Zoom factor (1.0 = 100%, 1.1 = 110%, 0.9 = 90%)
   */
  zoomResultsTable(factor) {
    const table = document.getElementById('resultsTable');
    if (!table) return;

    if (factor === 1.0) {
      // Reset zoom
      this.resultsTableZoom = 1.0;
    } else {
      // Apply zoom factor
      this.resultsTableZoom = Math.max(0.5, Math.min(3.0, this.resultsTableZoom * factor));
    }

    table.style.transform = `scale(${this.resultsTableZoom})`;
    
    // Update zoom display in button
    const resetBtn = document.querySelector('.btn-group button[title="Reset Zoom"]');
    if (resetBtn) {
      resetBtn.textContent = `${Math.round(this.resultsTableZoom * 100)}%`;
    }
  }

  /**
   * Create model performance chart showing latency vs cost
   * @param {Map} uniqueModels - Map of unique model data
   */
  createModelPerformanceChart(uniqueModels) {
    const chartCanvas = document.getElementById('modelPerformanceChart');
    if (!chartCanvas || !uniqueModels || uniqueModels.size === 0) return;

    // Destroy existing chart if it exists
    if (this.modelChart) {
      this.modelChart.destroy();
    }

    // Provider color mapping
    const providerColors = {
      'openai': '#28a745',      // Green
      'google': '#007bff',      // Blue  
      'anthropic': '#ffc107',   // Yellow
      'unknown': '#6c757d'      // Gray for unknown providers
    };

    // Group models by provider for datasets
    const providerDatasets = {};
    
    Array.from(uniqueModels.values()).forEach((model) => {
      // Only include completed models with valid data
      if (model.aggregated_completed_prompts > 0) {
        let latencyMs = model.aggregated_latency;
        // Handle latency conversion (same logic as table)
        if (latencyMs > 0 && latencyMs < 1000) {
          latencyMs = latencyMs * 1000;
        }
        
        // Convert to seconds for chart display
        const latencySeconds = latencyMs / 1000;
        const cost = model.aggregated_cost;
        
        if (latencySeconds > 0 && cost > 0) {
          const provider = (model.provider || 'unknown').toLowerCase();
          
          if (!providerDatasets[provider]) {
            providerDatasets[provider] = {
              label: provider.charAt(0).toUpperCase() + provider.slice(1),
              data: [],
              backgroundColor: providerColors[provider] || providerColors['unknown'],
              borderColor: providerColors[provider] || providerColors['unknown'],
              borderWidth: 2,
              pointRadius: 8,
              pointHoverRadius: 10
            };
          }
          
          providerDatasets[provider].data.push({
            x: latencySeconds,
            y: cost,
            modelName: model.model_name || 'Unknown Model',
            provider: provider
          });
        }
      }
    });

    if (Object.keys(providerDatasets).length === 0) {
      // Show message if no data available
      const ctx = chartCanvas.getContext('2d');
      ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
      ctx.fillStyle = '#6c757d';
      ctx.font = '14px Arial';
      ctx.textAlign = 'center';
      ctx.fillText('No completed models to display', chartCanvas.width / 2, chartCanvas.height / 2);
      return;
    }

    // Create chart
    const ctx = chartCanvas.getContext('2d');
    
    // Debug Chart.js availability
    console.log('Chart.js availability check:', {
      chartDefined: typeof Chart !== 'undefined',
      windowChart: window.Chart,
      globalChart: globalThis.Chart,
      documentReadyState: document.readyState
    });
    
    // Expose the error instead of hiding it
    if (typeof Chart === 'undefined') {
      console.error('CRITICAL: Chart.js library is not loaded when trying to create chart');
      console.error('Available globals:', Object.keys(window).filter(key => key.toLowerCase().includes('chart')));
      throw new Error('Chart.js library is not available. This indicates a CDN loading failure or timing issue.');
    }
    
    this.modelChart = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: Object.values(providerDatasets)
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              usePointStyle: true,
              padding: 15,
              font: {
                size: 12
              }
            }
          },
          tooltip: {
            callbacks: {
              title: () => '',
              label: (context) => {
                const point = context.parsed;
                const dataPoint = context.dataset.data[context.dataIndex];
                return [
                  `Model: ${dataPoint.modelName}`,
                  `Provider: ${dataPoint.provider.charAt(0).toUpperCase() + dataPoint.provider.slice(1)}`,
                  `Latency: ${point.x.toFixed(1)}s`,
                  `Cost: $${point.y.toFixed(4)}`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Latency (seconds)',
              font: {
                size: 12,
                weight: 'bold'
              }
            },
            type: 'linear',
            position: 'bottom'
          },
          y: {
            title: {
              display: true,
              text: 'Cost ($)',
              font: {
                size: 12,
                weight: 'bold'
              }
            },
            type: 'linear'
          }
        }
      }
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

    // Deduplicate runs by model name and provider (same logic as summary table)
    const uniqueModels = new Map();
    runs.forEach(run => {
      const modelKey = `${run.model_name}_${run.provider}`;
      if (!uniqueModels.has(modelKey)) {
        uniqueModels.set(modelKey, {
          model_name: run.model_name,
          provider: run.provider,
          aggregated_cost: 0,
          aggregated_tokens: 0,
          aggregated_latency: 0,
          aggregated_total_prompts: 0,
          aggregated_completed_prompts: 0,
          all_runs: [],
        });
      }
      
      const aggregatedRun = uniqueModels.get(modelKey);
      aggregatedRun.all_runs.push(run);
      
      // Aggregate run-level totals (from database) - more reliable than prompt-level calculation
      if (run.total_cost) {
        aggregatedRun.aggregated_cost += run.total_cost;
      }
      if (run.total_standard_input_tokens || run.total_cached_input_tokens || run.total_output_tokens) {
        aggregatedRun.aggregated_tokens += (run.total_standard_input_tokens || 0) + 
                                          (run.total_cached_input_tokens || 0) + 
                                          (run.total_output_tokens || 0);
      }
      if (run.latency) {
        aggregatedRun.aggregated_latency += run.latency;
      }
    });
    
    // After adding all runs, calculate unique prompts and completion status
    uniqueModels.forEach((aggregatedRun, modelKey) => {
      const allPrompts = new Set(); // Track unique prompts by text
      const completedPrompts = new Set(); // Track completed prompts by text
      
      // Collect all unique prompts across all runs for this model
      aggregatedRun.all_runs.forEach(runData => {
        if (runData.prompts && runData.prompts.length > 0) {
          runData.prompts.forEach(prompt => {
            if (prompt.prompt) {
              allPrompts.add(prompt.prompt);
              if (prompt.response && prompt.response.trim().length > 0) {
                completedPrompts.add(prompt.prompt);
              }
            }
          });
        }
      });
      
      // Set the deduplicated counts
      aggregatedRun.aggregated_total_prompts = allPrompts.size;
      aggregatedRun.aggregated_completed_prompts = completedPrompts.size;
    });

    return Array.from(uniqueModels.values()).map(aggregatedRun => {
      const modelDisplayName = Utils.formatModelName(aggregatedRun.model_name) || 'Unknown Model';
      const provider = aggregatedRun.provider || 'unknown';
      const runDate = Utils.formatDate(aggregatedRun.all_runs[0].run_created_at);
      
      // Calculate stats based on completed prompts only
      let runTokens = aggregatedRun.aggregated_tokens;
      let runCost = aggregatedRun.aggregated_cost;
      let completedPrompts = aggregatedRun.aggregated_completed_prompts;
      
      const providerColor = Utils.getProviderColor(provider);
      
      // Determine if this run is still in progress
      const totalPrompts = aggregatedRun.aggregated_total_prompts;
      // Use the run's status if available, otherwise fall back to checking completed vs total
      const isRunning = aggregatedRun.all_runs[0].run_status === 'in_progress' || aggregatedRun.all_runs[0].run_status === 'pending' || 
                       (aggregatedRun.all_runs[0].run_status !== 'completed' && completedPrompts < totalPrompts && totalPrompts > 0);
      const hasResults = completedPrompts > 0;
      
      // Latency handling - support both old (seconds) and new (milliseconds) formats
      let totalLatencyMs = aggregatedRun.aggregated_latency;
      // If latency is less than 1000, it's likely stored in seconds (old format)
      if (totalLatencyMs > 0 && totalLatencyMs < 1000) {
        totalLatencyMs = totalLatencyMs * 1000; // Convert to milliseconds
      }
      
      // If run.latency is 0 or missing, calculate it from individual prompt latencies
      if (totalLatencyMs === 0 && aggregatedRun.all_runs.length > 0) {
        aggregatedRun.all_runs.forEach(run => {
          if (run.prompts && run.prompts.length > 0) {
            run.prompts.forEach(prompt => {
              if (prompt.response && prompt.response.trim().length > 0) { // Only count completed prompts
                let promptLatencyMs = prompt.prompt_latency || 0;
                // Handle both milliseconds and seconds format for prompt latency
                if (promptLatencyMs > 0 && promptLatencyMs < 1000) {
                  promptLatencyMs = promptLatencyMs * 1000; // Convert to milliseconds
                }
                totalLatencyMs += promptLatencyMs;
              }
            });
          }
        });
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
      
      // Generate prompts HTML with status indicators - deduplicate prompts across runs
      let promptsHtml = '';
      if (aggregatedRun.all_runs.length > 0) {
        // Collect all unique prompts for this model across all runs
        const uniquePromptsMap = new Map(); // prompt_text -> best_prompt_data
        
        aggregatedRun.all_runs.forEach((run, runIndex) => {
          if (run.prompts && run.prompts.length > 0) {
            run.prompts.forEach((prompt, promptIndex) => {
              if (prompt.prompt) {
                // If we already have this prompt, keep the one with a response (prefer completed over pending)
                const existing = uniquePromptsMap.get(prompt.prompt);
                const hasResponse = prompt.response && prompt.response.trim().length > 0;
                const existingHasResponse = existing && existing.response && existing.response.trim().length > 0;
                
                // Keep the prompt if:
                // 1. We don't have this prompt yet, OR
                // 2. This prompt has a response and the existing one doesn't, OR  
                // 3. Both have responses but this one is more recent (later run)
                if (!existing || 
                    (hasResponse && !existingHasResponse) ||
                    (hasResponse && existingHasResponse && runIndex >= existing.runIndex)) {
                  uniquePromptsMap.set(prompt.prompt, {
                    ...prompt,
                    promptIndex: promptIndex,
                    runIndex: runIndex
                  });
                }
              }
            });
          }
        });
        
        // Now render the deduplicated prompts
        const uniquePrompts = Array.from(uniquePromptsMap.values());
        promptsHtml = uniquePrompts.map((prompt, index) => {
          const isCompleted = prompt.response && prompt.response.trim().length > 0;
          
          if (isCompleted) {
            // Check if this is an error response
            const isError = prompt.response.startsWith('ERROR');
            
            // Individual prompt latency is stored in milliseconds in database (newer runs) or seconds (older runs)
            // Handle both cases by detecting magnitude
            let promptLatencyMs = prompt.prompt_latency || 0;
            // If latency is less than 1000, it's likely stored in seconds (old format)
            if (promptLatencyMs > 0 && promptLatencyMs < 1000) {
              promptLatencyMs = promptLatencyMs * 1000; // Convert to milliseconds
            }
            const promptLatencySeconds = promptLatencyMs / 1000;
            
            // Web search indicator as a clickable badge
            const webSearchBadge = prompt.web_search_used ? 
              `<button class="badge bg-info text-white web-search-badge" 
                      title="Click to view web search sources" 
                      style="border: none; cursor: pointer; transition: all 0.2s ease;" 
                      data-web-search-sources="${Utils.escapeHtmlAttribute(prompt.web_search_sources || '')}"
                      onclick="window.Pages.showWebSearchModal(this)"
                      onmouseover="this.style.backgroundColor='#0a58ca'"
                      onmouseout="this.style.backgroundColor='#0dcaf0'">
                <i class="fas fa-globe me-1"></i>Web Search Results
              </button>` : '';
            
            // Different styling for errors vs successes
            const cardBgClass = isError ? 'bg-danger bg-opacity-10' : 'bg-light';
            const statusIcon = isError ? 
              '<i class="fas fa-exclamation-triangle text-danger me-2"></i>' : 
              '<i class="fas fa-check-circle text-success me-2"></i>';
            const headerClass = isError ? 'text-danger' : 'text-primary';
            
            // Show completed prompt (both successful and failed)
            return `
              <div class="border rounded p-3 mb-3 ${cardBgClass}">
                <div class="d-flex justify-content-between align-items-start mb-2">
                  <h6 class="mb-0 ${headerClass}">
                    ${statusIcon}
                    Prompt ${index + 1} ${isError ? '(Error)' : ''}
                  </h6>
                  <div class="d-flex gap-2 align-items-center">
                    ${webSearchBadge}
                    <span class="badge bg-secondary">${promptLatencySeconds.toFixed(3)}s</span>
                    <span class="badge bg-info">${(prompt.standard_input_tokens || 0) + (prompt.cached_input_tokens || 0)}→${prompt.output_tokens || 0} tokens</span>
                    ${prompt.total_cost ? `<span class="badge bg-success">${Utils.formatCurrency(prompt.total_cost)}</span>` : ''}
                    <button type="button" class="btn btn-sm ${isError ? 'btn-outline-danger' : 'btn-outline-primary'}" 
                            onclick="window.Pages.rerunSinglePrompt(${prompt.prompt_id || prompt.id})"
                            title="Rerun this prompt">
                      <i class="fas fa-redo-alt"></i>
                    </button>
                  </div>
                </div>
                
                <div class="mb-3">
                  <div class="fw-bold text-muted mb-1">Prompt:</div>
                  <div class="p-2 bg-white border rounded small">${Utils.sanitizeHtml(prompt.prompt || 'N/A')}</div>
                </div>
                
                <div>
                  <div class="fw-bold text-muted mb-1">Response:</div>
                  <div class="p-2 bg-white border rounded small">${this.formatPromptResponse(prompt.response || 'N/A')}</div>
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
                  <div class="d-flex gap-2 align-items-center">
                    <span class="badge bg-warning">Pending</span>
                    <button type="button" class="btn btn-sm btn-outline-danger" 
                            onclick="window.Pages.rerunSinglePrompt(${prompt.prompt_id || prompt.id})"
                            title="Force rerun this stuck prompt">
                      <i class="fas fa-redo-alt"></i> Force Rerun
                    </button>
                  </div>
                </div>
                
                <div class="mb-3">
                  <div class="fw-bold text-muted mb-1">Prompt:</div>
                  <div class="p-2 bg-white border rounded small">${Utils.sanitizeHtml(prompt.prompt || 'N/A')}</div>
                </div>
                
                <div>
                  <div class="fw-bold text-muted mb-1">Response:</div>
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
                <div>
                  <h5 class="mb-0">${Utils.sanitizeHtml(modelDisplayName)}</h5>
                  <small class="opacity-75">${statusText}${runDate ? ` • ${runDate}` : ''}</small>
                </div>
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
    }).join('') + '<div style="height: 2rem;"></div>'; // Add extra space at the bottom for scrolling
  }

  /**
   * Render results table view with prompts as rows and models as columns
   * @param {Array} runs - Benchmark runs
   * @returns {string} HTML string
   */
  renderResultsTable(runs) {
    if (!runs || runs.length === 0) {
      return '<div class="text-center text-muted py-4"><h5>No results available</h5></div>';
    }

    // Deduplicate runs by model name and provider
    const uniqueModels = new Map();
    runs.forEach(run => {
      const modelKey = `${run.model_name}_${run.provider}`;
      if (!uniqueModels.has(modelKey)) {
        uniqueModels.set(modelKey, run);
      }
    });

    const modelRuns = Array.from(uniqueModels.values());
    
    // Get all unique prompts across all models
    const allPrompts = new Set();
    modelRuns.forEach(run => {
      if (run.prompts) {
        run.prompts.forEach(prompt => {
          if (prompt.prompt) {
            allPrompts.add(prompt.prompt);
          }
        });
      }
    });

    const promptsList = Array.from(allPrompts);

    if (promptsList.length === 0) {
      return '<div class="text-center text-muted py-4"><h5>No prompts found</h5></div>';
    }

    // Create header row with model names
    const headerCells = modelRuns.map(run => {
      const modelDisplayName = Utils.formatModelName(run.model_name) || 'Unknown Model';
      const provider = run.provider || 'unknown';
      return `
        <th class="text-center" style="min-width: 200px; max-width: 300px;">
          <div class="d-flex flex-column align-items-center">
            ${Utils.createProviderImage(provider, 'mb-1')}
            <small class="fw-bold text-truncate" style="max-width: 100%;" title="${Utils.sanitizeHtml(modelDisplayName)}">
              ${Utils.sanitizeHtml(modelDisplayName)}
            </small>
          </div>
        </th>
      `;
    }).join('');

    // Create data rows
    const dataRows = promptsList.map((promptText, promptIndex) => {
      const promptCells = modelRuns.map(run => {
        // Find the matching prompt in this model's run
        const matchingPrompt = run.prompts ? run.prompts.find(p => p.prompt === promptText) : null;
        
        if (!matchingPrompt) {
          // No prompt found for this model
          return `
            <td class="p-2 text-center" style="background-color: #f8f9fa;">
              <small class="text-muted">No data</small>
            </td>
          `;
        }

        const hasResponse = matchingPrompt.response && matchingPrompt.response.trim().length > 0;
        const isError = matchingPrompt.response && matchingPrompt.response.startsWith('ERROR');
        
        if (!hasResponse) {
          // Pending/in-progress
          return `
            <td class="p-2 text-center" style="background-color: #fff3cd;">
              <div class="d-flex justify-content-center align-items-center" style="min-height: 60px;">
                <small class="text-warning">
                  <i class="fas fa-clock me-1"></i>Pending
                </small>
              </div>
            </td>
          `;
        }

        if (isError) {
          // Error response
          const errorMessage = matchingPrompt.response.substring(0, 100) + (matchingPrompt.response.length > 100 ? '...' : '');
          return `
            <td class="p-2 response-cell" style="background-color: #f8d7da; cursor: pointer;" 
                title="Click to view error details"
                data-prompt-text="${Utils.escapeHtmlAttribute(promptText)}"
                data-response-text="${Utils.escapeHtmlAttribute(matchingPrompt.response)}"
                data-prompt-id="${matchingPrompt.prompt_id || ''}"
                data-modal-title="Error Response">
              <div style="min-height: 60px; max-height: 120px; overflow-y: auto;">
                <small class="text-danger fw-bold">ERROR</small>
                <div class="small text-danger" style="font-size: 0.75rem; line-height: 1.2;">
                  ${Utils.sanitizeHtml(errorMessage)}
                </div>
              </div>
            </td>
          `;
        }

        // Successful response
        const responseLength = matchingPrompt.response.length;
        const truncatedResponse = matchingPrompt.response.substring(0, 200) + (responseLength > 200 ? '...' : '');
        
        // Adjust font size based on response length
        let fontSize = '0.75rem';
        if (responseLength > 1000) fontSize = '0.65rem';
        if (responseLength > 2000) fontSize = '0.6rem';
        
        // Web search indicator
        const webSearchIndicator = matchingPrompt.web_search_used ? 
          `<i class="fas fa-globe text-info me-1" title="Used web search"></i>` : '';

        return `
          <td class="p-2 response-cell" style="background-color: #d1edff; cursor: pointer;" 
              title="Click to view full response"
              data-prompt-text="${Utils.escapeHtmlAttribute(promptText)}"
              data-response-text="${Utils.escapeHtmlAttribute(matchingPrompt.response)}"
              data-prompt-id="${matchingPrompt.prompt_id || ''}"
              data-modal-title="${Utils.escapeHtmlAttribute(Utils.formatModelName(run.model_name))} Response">
            <div style="min-height: 60px; max-height: 120px; overflow-y: auto;">
              <div class="d-flex justify-content-between align-items-start mb-1">
                <div class="d-flex align-items-center">
                  ${webSearchIndicator}
                  <small class="text-success fw-bold">✓</small>
                </div>
                <small class="text-muted">${responseLength.toLocaleString()} chars</small>
              </div>
              <div class="small" style="font-size: ${fontSize}; line-height: 1.2; word-break: break-word;">
                ${Utils.sanitizeHtml(truncatedResponse)}
              </div>
            </div>
          </td>
        `;
      }).join('');

      return `
        <tr>
          <td class="p-2 bg-light" style="max-width: 300px; position: sticky; left: 0; z-index: 1;">
            <div style="max-height: 120px; overflow-y: auto;">
              <strong class="small text-primary">Prompt ${promptIndex + 1}</strong>
              <div class="small text-muted mt-1" style="font-size: 0.75rem; line-height: 1.2;">
                ${Utils.sanitizeHtml(promptText.substring(0, 150) + (promptText.length > 150 ? '...' : ''))}
              </div>
            </div>
          </td>
          ${promptCells}
        </tr>
      `;
    }).join('');

    return `
      <div class="mb-3 d-flex justify-content-between align-items-center">
        <div class="small text-muted">
          <i class="fas fa-mouse me-1"></i>
          <strong>Navigation:</strong> Drag to pan • Ctrl/Cmd + scroll to zoom • Click cells for details • Use scrollbars for precise positioning
        </div>
        <div class="btn-group btn-group-sm" role="group">
          <button class="btn btn-outline-secondary" onclick="window.Pages.zoomResultsTable(0.9)" title="Zoom Out">
            <i class="fas fa-search-minus"></i>
          </button>
          <button class="btn btn-outline-secondary" onclick="window.Pages.zoomResultsTable(1.0)" title="Reset Zoom">
            100%
          </button>
          <button class="btn btn-outline-secondary" onclick="window.Pages.zoomResultsTable(1.1)" title="Zoom In">
            <i class="fas fa-search-plus"></i>
          </button>
        </div>
      </div>
      
      <div class="table-responsive" id="resultsTableWrapper" style="
        overflow: auto; 
        cursor: grab; 
        user-select: none;
        border: 1px solid #dee2e6;
        border-radius: 0.375rem;
      ">
        <table class="table table-bordered table-sm" id="resultsTable" style="
          font-size: 0.8rem; 
          margin: 0;
          transform-origin: top left;
          transition: transform 0.1s ease;
        ">
          <thead class="table-light">
            <tr>
              <th style="position: sticky; left: 0; z-index: 2; background-color: #f8f9fa; min-width: 250px; max-width: 300px;">
                <strong>Prompts</strong>
                <div class="small text-muted mt-1">${promptsList.length} prompts total</div>
              </th>
              ${headerCells}
            </tr>
          </thead>
          <tbody>
            ${dataRows}
          </tbody>
        </table>
      </div>
      
      <div class="mt-3 mb-4 small text-muted">
        <strong>Legend:</strong>
        <span class="ms-3">
          <span class="badge bg-info me-2">✓ Completed</span>
          <span class="badge bg-warning me-2">⏳ Pending</span>
          <span class="badge bg-danger me-2">❌ Error</span>
          <span class="badge bg-secondary">📝 No Data</span>
        </span>
        <div class="mt-1">
          <i class="fas fa-info-circle me-1"></i>
          Click on any response cell to view the full content. Font size scales based on response length.
        </div>
      </div>
    `;
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
  async deleteBenchmark(benchmarkId) {
    const confirmed = await window.Utils.showConfirmDialog(
      'Delete Benchmark',
      'Are you sure you want to delete this benchmark? This action cannot be undone.',
      'danger'
    );

    if (!confirmed) return;

    try {
      const result = await window.API.deleteBenchmark(benchmarkId);
      
      if (result.success) {
        window.Components.showToast('Benchmark deleted successfully', 'success');
        
        // Remove from local data and mark as deleted
        this.benchmarksData = this.benchmarksData.filter(b => b.id !== benchmarkId);
        this.deletedBenchmarkIds.add(benchmarkId);
        
        // Re-render the view
        this.renderBenchmarks();
      } else {
        throw new Error(result.error || 'Failed to delete benchmark');
      }
    } catch (error) {
      console.error('Error deleting benchmark:', error);
      window.Components.showToast(`Failed to delete benchmark: ${error.message}`, 'error');
    }
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
          const defaultModels = ['o3', 'claude-opus-4-20250514-thinking', 'gemini-2.5-pro-preview-06-05'];
          const isDefault = defaultModels.includes(model.id);
          const checkbox = window.Components.createModelCheckbox(model, isDefault);
          providerDiv.appendChild(checkbox);
        });

        modelList.appendChild(providerDiv);
      });
      
      // Set up select all toggle after models are loaded
      this.setupSelectAllModelsToggle();

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
    
    // Update web search per-prompt controls if visible
    const webSearchPromptControls = document.getElementById('webSearchPromptControls');
    const webSearchAllPromptsToggle = document.getElementById('webSearchAllPromptsToggle');
    if (webSearchPromptControls && 
        webSearchAllPromptsToggle && 
        !webSearchAllPromptsToggle.checked && 
        !webSearchPromptControls.classList.contains('d-none')) {
      this.renderWebSearchPromptControls();
    }
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

      // Get selected models - force DOM update with a small delay to ensure Select All has propagated
      await new Promise(resolve => setTimeout(resolve, 50));
      const selectedModels = Array.from(
        document.querySelectorAll('#modelList input[type="checkbox"]:checked')
      ).map(cb => cb.value);

      if (selectedModels.length === 0) {
        window.Components.showToast('At least one model must be selected', 'error');
        return;
      }
      
      // Get web search settings
      const webSearchToggle = document.getElementById('webSearchToggle');
      const webSearchEnabled = webSearchToggle && webSearchToggle.checked;
      const webSearchAllPromptsToggle = document.getElementById('webSearchAllPromptsToggle');
      
      // Get per-prompt web search settings if not using "all prompts" toggle
      let webSearchPrompts = [];
      if (webSearchEnabled && webSearchAllPromptsToggle && !webSearchAllPromptsToggle.checked) {
        webSearchPrompts = Array.from(
          document.querySelectorAll('.web-search-prompt-toggle:checked')
        ).map(cb => parseInt(cb.dataset.promptIndex));
      }

      // Validate token limits before running
      window.Components.showToast('Checking token limits...', 'info');
      
      console.log('DEBUG: About to validate tokens with selectedModels:', selectedModels);
      
      try {
        const validation = await window.API.validateTokens({
          prompts,
          pdfPaths: this.selectedPdfPaths,
          modelNames: selectedModels
        });

        if (validation.status === 'error') {
          window.Components.showToast(`Token validation failed: ${validation.message}`, 'error');
          return;
        }

        const validationResults = validation.validation_results;
        
        // Check if we have proper validation results
        if (!validationResults || typeof validationResults !== 'object') {
          console.warn('Invalid validation results structure:', validation);
          window.Components.showToast('Could not validate token limits. Proceeding anyway...', 'warning');
        } else {
          // If there are models that will exceed limits, show confirmation dialog
          if (!validationResults.valid) {
            const confirmed = await this.showTokenLimitConfirmation(validation.formatted_message, validationResults);
            if (!confirmed) {
              return; // User cancelled
            }
          } else {
            // All models are fine, show success message
            window.Components.showToast('✅ All models can handle the content within their limits', 'success');
          }
        }
        
      } catch (error) {
        console.error('Token validation error:', error);
        window.Components.showToast('Could not validate token limits. Proceeding anyway...', 'warning');
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
        benchmarkDescription: descInput.value.trim(),
        webSearchEnabled,
        webSearchPrompts: webSearchEnabled && webSearchPrompts.length > 0 ? webSearchPrompts : undefined
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
   * Show token limit confirmation dialog
   * @param {string} message - Formatted validation message
   * @param {Object} validationResults - Validation results object
   * @returns {Promise<boolean>} Whether user confirmed to proceed
   */
  async showTokenLimitConfirmation(message, validationResults) {
    return new Promise((resolve) => {
      // Count models that will exceed vs those that won't
      const exceedingModels = [];
      const safeModels = [];
      
      // Check if model_results exists and is an object
      const modelResults = validationResults?.model_results || {};
      
      Object.entries(modelResults).forEach(([modelName, result]) => {
        if (result && result.will_exceed) {
          exceedingModels.push(modelName);
        } else {
          safeModels.push(modelName);
        }
      });

      const modalHtml = `
        <div class="modal fade" id="tokenLimitModal" tabindex="-1">
          <div class="modal-dialog modal-lg">
            <div class="modal-content">
              <div class="modal-header bg-warning text-dark">
                <h5 class="modal-title">
                  <i class="fas fa-exclamation-triangle me-2"></i>
                  Token Limit Warning
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <div class="alert alert-warning">
                  <strong>Some models may fail due to token limits:</strong>
                </div>
                
                ${exceedingModels.length > 0 ? `
                  <div class="mb-3">
                    <h6 class="text-danger">🚫 Models likely to fail:</h6>
                    <ul class="list-unstyled ms-3">
                      ${exceedingModels.map(model => {
                        const result = modelResults[model];
                        const estimatedTokens = result?.estimated_tokens || 0;
                        const contextLimit = result?.context_limit || 0;
                        return `<li class="text-danger">• ${model}: ${estimatedTokens.toLocaleString()} tokens (limit: ${contextLimit.toLocaleString()})</li>`;
                      }).join('')}
                    </ul>
                  </div>
                ` : ''}
                
                ${safeModels.length > 0 ? `
                  <div class="mb-3">
                    <h6 class="text-success">✅ Models that should work:</h6>
                    <ul class="list-unstyled ms-3">
                      ${safeModels.map(model => {
                        const result = modelResults[model];
                        const estimatedTokens = result?.estimated_tokens || 0;
                        const contextLimit = result?.context_limit || 0;
                        return `<li class="text-success">• ${model}: ${estimatedTokens.toLocaleString()} tokens (limit: ${contextLimit.toLocaleString()})</li>`;
                      }).join('')}
                    </ul>
                  </div>
                ` : ''}
                
                <div class="alert alert-info">
                  <strong>💡 Recommendations:</strong>
                  <ul class="mb-0 mt-2">
                    <li>Consider using models with larger context windows (GPT 4.1 series, Gemini models)</li>
                    <li>Reduce the number of PDF files</li>
                    <li>Use shorter prompts</li>
                    <li>Remove models that will exceed limits from your selection</li>
                  </ul>
                </div>
                
                <p class="mb-0">
                  <strong>Do you want to proceed anyway?</strong> Models that exceed limits will show error messages in the results.
                </p>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" id="cancelBtn">
                  Cancel
                </button>
                <button type="button" class="btn btn-warning" id="proceedBtn">
                  <i class="fas fa-exclamation-triangle me-1"></i>
                  Proceed Anyway
                </button>
              </div>
            </div>
          </div>
        </div>
      `;

      // Remove existing modal if any
      const existingModal = document.getElementById('tokenLimitModal');
      if (existingModal) {
        existingModal.remove();
      }

      // Add modal to DOM
      document.body.insertAdjacentHTML('beforeend', modalHtml);
      
      const modal = new bootstrap.Modal(document.getElementById('tokenLimitModal'));
      const proceedBtn = document.getElementById('proceedBtn');
      const cancelBtn = document.getElementById('cancelBtn');

      // Handle proceed
      proceedBtn.addEventListener('click', () => {
        modal.hide();
        resolve(true);
      });

      // Handle cancel
      cancelBtn.addEventListener('click', () => {
        modal.hide();
        resolve(false);
      });

      // Handle modal close
      document.getElementById('tokenLimitModal').addEventListener('hidden.bs.modal', () => {
        document.getElementById('tokenLimitModal').remove();
        resolve(false);
      });

      modal.show();
    });
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
      console.log('Loaded prompt set:', promptSet);
      
      if (!promptSet) {
        throw new Error('Prompt set not found');
      }
      
      // Populate form
      document.getElementById('promptSetName').value = promptSet.name || '';
      document.getElementById('promptSetDescription').value = promptSet.description || '';
      
      // Load prompts
      this.promptSetPrompts = (promptSet.prompts || []).map(p => ({
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
      console.log('Editing prompt set:', promptSet);
      
      if (!promptSet) {
        throw new Error('Prompt set not found');
      }
      
      // Show the creation form
      this.showPromptSetCreation();
      
      // Wait for the form to be rendered
      setTimeout(() => {
        // Populate form with existing data
        document.getElementById('promptSetName').value = promptSet.name || '';
        document.getElementById('promptSetDescription').value = promptSet.description || '';
        
        // Load prompts with proper structure for editing
        this.promptSetPrompts = (promptSet.prompts || []).map((p, index) => ({
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

  /**
   * Format prompt response
   * @param {string} response - Prompt response
   * @returns {string} Formatted response
   */
  formatPromptResponse(response) {
    if (!response) return 'No response';
    
    // Check if marked.js is available
    if (typeof marked !== 'undefined') {
      try {
        // Configure marked for security
        marked.setOptions({
          breaks: true, // Convert line breaks to <br>
          gfm: true, // Enable GitHub Flavored Markdown
          sanitize: false, // We'll sanitize after rendering
          smartLists: true,
          smartypants: false
        });
        
        // Render markdown to HTML
        const htmlContent = marked.parse(response);
        
        // Sanitize the HTML output for security
        return Utils.sanitizeHtml(htmlContent);
      } catch (error) {
        console.warn('Error rendering markdown:', error);
        // Fallback to basic formatting if markdown parsing fails
        return Utils.sanitizeHtml(response);
      }
    } else {
      // Fallback if marked.js is not available
      console.warn('Marked.js not available, falling back to basic formatting');
      return Utils.sanitizeHtml(response);
    }
  }

  /**
   * Show web search sources in a modal
   * @param {HTMLElement} iconElement - The web search icon that was clicked
   */
  showWebSearchModal(iconElement) {
    const webSearchSources = iconElement.getAttribute('data-web-search-sources') || '';
    
    // Format the web search sources for better display
    const formatWebSearchSources = (sources) => {
      if (!sources) return '<div class="text-muted text-center py-4">No web search source data available</div>';
      
      // Try to detect if this is structured data (JSON-like) or plain text
      let formattedSources = sources;
      
      // Check if it looks like structured data from Google (contains "Title:", "URL:", etc.)
      if (sources.includes('Title:') || sources.includes('URL:') || sources.includes('Search queries:')) {
        // Format Google-style structured sources
        formattedSources = sources
          .split('---\n')
          .map(section => {
            if (!section.trim()) return '';
            
            // Parse each section
            const lines = section.trim().split('\n');
            let formatted = '<div class="web-source-item mb-3 p-3 border rounded bg-light">';
            
            lines.forEach(line => {
              const trimmedLine = line.trim();
              if (trimmedLine.startsWith('Title:')) {
                const title = trimmedLine.substring(6).trim();
                formatted += `<h6 class="text-primary mb-2"><i class="fas fa-globe me-2"></i>${Utils.sanitizeHtml(title)}</h6>`;
              } else if (trimmedLine.startsWith('URL:')) {
                const url = trimmedLine.substring(4).trim();
                formatted += `<p class="mb-2"><strong>URL:</strong> <a href="${Utils.sanitizeHtml(url)}" target="_blank" class="text-decoration-none">${Utils.sanitizeHtml(url)}</a></p>`;
              } else if (trimmedLine.startsWith('Search queries:')) {
                const queries = trimmedLine.substring(15).trim();
                formatted += `<p class="mb-2"><strong>Search Queries:</strong> <span class="badge bg-info">${Utils.sanitizeHtml(queries)}</span></p>`;
              } else if (trimmedLine.startsWith('Search entry point:')) {
                const content = trimmedLine.substring(19).trim();
                formatted += `<p class="mb-2"><strong>Search Content:</strong></p><div class="small text-muted bg-white p-2 rounded border">${Utils.sanitizeHtml(content)}</div>`;
              } else if (trimmedLine && !trimmedLine.startsWith('Web search') && !trimmedLine.startsWith('Function call')) {
                formatted += `<p class="mb-1 small">${Utils.sanitizeHtml(trimmedLine)}</p>`;
              }
            });
            
            formatted += '</div>';
            return formatted;
          })
          .filter(section => section.includes('web-source-item'))
          .join('');
        
        if (!formattedSources.trim()) {
          // Fallback to original formatting if parsing failed
          formattedSources = `<pre class="bg-light p-3 rounded" style="white-space: pre-wrap; max-height: 400px; overflow-y: auto;">${Utils.sanitizeHtml(sources)}</pre>`;
        }
      } else {
        // For other providers (OpenAI, Anthropic) or unstructured data, use pre formatting
        formattedSources = `<pre class="bg-light p-3 rounded" style="white-space: pre-wrap; max-height: 400px; overflow-y: auto;">${Utils.sanitizeHtml(sources)}</pre>`;
      }
      
      return formattedSources;
    };
    
    // Create modal HTML
    const modalHtml = `
      <div class="modal fade" id="webSearchModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">
                <i class="fas fa-globe text-info me-2"></i>
                Web Search Sources
              </h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="mb-3">
                <p class="text-muted">
                  This model used web search to find up-to-date information. 
                  Below are the sources and search data returned by the API:
                </p>
              </div>
              <div class="web-search-content">
                ${formatWebSearchSources(webSearchSources)}
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" onclick="window.Pages.copyWebSearchSources('${Utils.sanitizeHtml(webSearchSources).replace(/'/g, "\\'")}')">
                <i class="fas fa-copy me-1"></i>Copy Sources
              </button>
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Remove existing modal if any
    const existingModal = document.getElementById('webSearchModal');
    if (existingModal) {
      existingModal.remove();
    }

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('webSearchModal'));
    modal.show();

    // Clean up modal on hide
    document.getElementById('webSearchModal').addEventListener('hidden.bs.modal', () => {
      document.getElementById('webSearchModal').remove();
      // Additional cleanup to prevent backdrop issues
      this.cleanupWebSearchModal();
    });
  }

  /**
   * Clean up web search modal backdrop
   */
  cleanupWebSearchModal() {
    // Remove any leftover web search modal backdrops
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => {
      // Only remove if there are no other active modals
      if (document.querySelectorAll('.modal.show').length === 0) {
        backdrop.remove();
      }
    });
    
    // Reset body state if no other modals are active
    if (document.querySelectorAll('.modal.show').length === 0) {
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
      document.documentElement.style.overflow = '';
    }
  }

  /**
   * Copy web search sources to clipboard
   * @param {string} sources - The web search sources text
   */
  copyWebSearchSources(sources) {
    navigator.clipboard.writeText(sources).then(() => {
      window.Components.showToast('Web search sources copied to clipboard', 'success');
    }).catch(err => {
      console.error('Failed to copy sources:', err);
      window.Components.showToast('Failed to copy sources', 'error');
    });
  }

  /**
   * Show response modal with full prompt and response content
   * @param {string} promptText - The prompt text
   * @param {string} responseText - The response text
   * @param {string} title - Modal title
   * @param {string} promptId - The prompt ID for rerun functionality
   */
  showResponseModal(promptText, responseText, title = 'Response Details', promptId = null) {
    // Check if this is a completed prompt with a valid ID for rerun functionality
    // Allow rerunning both successful and failed prompts
    const canRerun = promptId && promptId !== '' && promptId !== 'null' && promptId !== 'undefined';
    
    const rerunButtonHtml = canRerun ? `
      <button type="button" class="btn btn-warning" onclick="window.Pages.rerunSinglePrompt(${promptId})">
        <i class="fas fa-redo me-1"></i>Rerun Prompt
      </button>
    ` : '';

    const modalHtml = `
      <div class="modal fade" id="responseModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">
                <i class="fas fa-comment-dots me-2"></i>
                ${Utils.sanitizeHtml(title)}
              </h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="mb-4">
                <h6 class="text-primary mb-2">
                  <i class="fas fa-question-circle me-1"></i>Prompt:
                </h6>
                <div class="p-3 bg-light border rounded">
                  <pre style="white-space: pre-wrap; margin: 0; font-family: inherit;">${Utils.sanitizeHtml(promptText)}</pre>
                </div>
              </div>
              
              <div>
                <h6 class="text-success mb-2">
                  <i class="fas fa-reply me-1"></i>Response:
                </h6>
                <div class="p-3 bg-white border rounded" style="max-height: 400px; overflow-y: auto;">
                  <div style="white-space: pre-wrap; font-family: inherit;">${this.formatPromptResponse(responseText)}</div>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" onclick="window.Pages.copyResponseToClipboard('${Utils.sanitizeHtml(responseText).replace(/'/g, "\\'")}')">
                <i class="fas fa-copy me-1"></i>Copy Response
              </button>
              <button type="button" class="btn btn-outline-primary" onclick="window.Pages.copyFullConversation('${Utils.sanitizeHtml(promptText).replace(/'/g, "\\'")}', '${Utils.sanitizeHtml(responseText).replace(/'/g, "\\'")}')">
                <i class="fas fa-clipboard me-1"></i>Copy Both
              </button>
              ${rerunButtonHtml}
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Force cleanup of any existing modal state
    this.cleanupModals();

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('responseModal'));
    modal.show();

    // Enhanced cleanup on hide
    document.getElementById('responseModal').addEventListener('hidden.bs.modal', () => {
      this.cleanupModals();
    });
  }

  /**
   * Clean up modal backdrop and reset body state
   */
  cleanupModals() {
    // Remove any existing response modals
    const existingModals = document.querySelectorAll('#responseModal');
    existingModals.forEach(modal => modal.remove());
    
    // Remove any leftover modal backdrops
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => backdrop.remove());
    
    // Reset body classes that might be left over
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
    
    // Force body to be scrollable again
    document.documentElement.style.overflow = '';
  }

  /**
   * Copy response to clipboard
   * @param {string} responseText - The response text to copy
   */
  copyResponseToClipboard(responseText) {
    navigator.clipboard.writeText(responseText).then(() => {
      window.Components.showToast('Response copied to clipboard', 'success');
    }).catch(err => {
      console.error('Failed to copy response:', err);
      window.Components.showToast('Failed to copy response', 'error');
    });
  }

  /**
   * Copy full conversation to clipboard
   * @param {string} promptText - The prompt text
   * @param {string} responseText - The response text
   */
  copyFullConversation(promptText, responseText) {
    const fullText = `PROMPT:\n${promptText}\n\nRESPONSE:\n${responseText}`;
    navigator.clipboard.writeText(fullText).then(() => {
      window.Components.showToast('Full conversation copied to clipboard', 'success');
    }).catch(err => {
      console.error('Failed to copy conversation:', err);
      window.Components.showToast('Failed to copy conversation', 'error');
    });
  }

  // ===== FILES PAGE METHODS =====

  /**
   * Initialize files page
   */
  async initFilesPage() {
    await this.loadFiles();
    this.setupFilesEventListeners();
  }

  /**
   * Load and display files
   */
  async loadFiles() {
    try {
      const files = await window.API.getFiles();
      this.renderFiles(files);
    } catch (error) {
      console.error('Error loading files:', error);
      window.Components.showToast('Failed to load files', 'error');
    }
  }

  /**
   * Render files list
   */
  renderFiles(files) {
    const container = document.getElementById('filesListContainer');
    if (!container) return;

    if (files.length === 0) {
      container.innerHTML = `
        <div class="text-center py-5">
          <i class="fas fa-file fa-3x text-muted mb-3"></i>
          <h5 class="text-muted">No Files Yet</h5>
          <p class="text-muted">Upload your first file to get started</p>
          <button class="btn btn-primary" onclick="window.Pages.uploadFile()">
            <i class="fas fa-upload"></i> Upload Your First File
          </button>
        </div>
      `;
      return;
    }

    // Create table with sortable headers
    const tableHtml = `
      <div class="table-responsive">
        <table class="table table-hover" id="filesTable">
          <thead class="table-light">
            <tr>
              <th scope="col" data-sort="name" style="cursor: pointer;">
                File Name <i class="fas fa-sort text-muted"></i>
              </th>
              <th scope="col" data-sort="size" style="cursor: pointer;">
                Size <i class="fas fa-sort text-muted"></i>
              </th>
              <th scope="col" data-sort="date" style="cursor: pointer;">
                Uploaded <i class="fas fa-sort text-muted"></i>
              </th>
              <th scope="col">Status</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${files.map(file => {
              const fileSize = this.formatFileSize(file.file_size_bytes);
              const fileIcon = this.getFileIcon(file.original_filename);
              const createdDate = new Date(file.created_at);
              const formattedDate = createdDate.toLocaleDateString();
              const formattedTime = createdDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
              const existsClass = file.exists_on_disk ? 'text-success' : 'text-danger';
              const existsIcon = file.exists_on_disk ? 'fa-check-circle' : 'fa-exclamation-triangle';
              const existsText = file.exists_on_disk ? 'Available' : 'Missing';

              // Add CSV info if it's a CSV file
              let csvInfo = '';
              if (file.mime_type === 'text/csv' && file.csv_rows > 0) {
                csvInfo = `<br><small class="text-muted">${file.csv_rows.toLocaleString()} rows, ${file.csv_columns} columns</small>`;
              }

              return `
                <tr>
                  <td data-sort="${Utils.sanitizeHtml(file.original_filename).toLowerCase()}">
                    <div class="d-flex align-items-center">
                      <i class="${fileIcon} text-primary me-2"></i>
                      <div>
                        <span>${Utils.sanitizeHtml(file.original_filename)}</span>
                        ${csvInfo}
                      </div>
                    </div>
                  </td>
                  <td data-sort="${file.file_size_bytes}">
                    ${fileSize}
                  </td>
                  <td data-sort="${file.created_at}">
                    <div>
                      <div>${formattedDate}</div>
                      <small class="text-muted">${formattedTime}</small>
                    </div>
                  </td>
                  <td>
                    <span class="badge ${existsClass === 'text-success' ? 'bg-success' : 'bg-warning'}">
                      <i class="fas ${existsIcon} me-1"></i>${existsText}
                    </span>
                  </td>
                  <td>
                    <div class="btn-group btn-group-sm">
                      <button class="btn btn-outline-primary" onclick="window.Pages.viewFileDetails(${file.id})" title="View Details">
                        <i class="fas fa-info-circle"></i>
                      </button>
                      <button class="btn btn-outline-danger" onclick="window.Pages.deleteFile(${file.id}, '${Utils.sanitizeHtml(file.original_filename)}')" title="Delete File">
                        <i class="fas fa-trash"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;

    container.innerHTML = tableHtml;
    
    // Set up table sorting
    this.setupFilesTableSorting();
  }

  /**
   * Set up event listeners for files page
   */
  setupFilesEventListeners() {
    const uploadBtn = document.getElementById('uploadFileBtn');
    if (uploadBtn) {
      uploadBtn.onclick = () => this.uploadFile();
    }
  }

  /**
   * Set up table sorting for files table
   */
  setupFilesTableSorting() {
    const table = document.getElementById('filesTable');
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

          if (sortType === 'name') {
            // Sort by filename (case-insensitive)
            aVal = a.cells[0].dataset.sort;
            bVal = b.cells[0].dataset.sort;
          } else if (sortType === 'size') {
            // Sort by file size (numeric)
            aVal = parseInt(a.cells[1].dataset.sort || 0);
            bVal = parseInt(b.cells[1].dataset.sort || 0);
          } else if (sortType === 'date') {
            // Sort by upload date
            aVal = new Date(a.cells[2].dataset.sort);
            bVal = new Date(b.cells[2].dataset.sort);
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
   * Upload a new file
   */
  async uploadFile() {
    try {
      const filePath = await window.API.openFileDialog({
        properties: ['openFile'],
        filters: [
          { name: 'Supported Files', extensions: ['pdf', 'csv', 'xlsx'] },
          { name: 'PDF Files', extensions: ['pdf'] },
          { name: 'CSV Files', extensions: ['csv'] },
          { name: 'Excel Files', extensions: ['xlsx'] }
        ]
      });

      if (!filePath) return;

      window.Components.showToast('Uploading file...', 'info');

      const result = await window.API.uploadFile(filePath);

      if (result.success) {
        window.Components.showToast(result.message, 'success');
        await this.loadFiles(); // Refresh the files list
      } else {
        window.Components.showToast(result.error, 'error');
      }

    } catch (error) {
      console.error('Error uploading file:', error);
      window.Components.showToast('Failed to upload file', 'error');
    }
  }

  /**
   * View file details
   */
  async viewFileDetails(fileId) {
    try {
      const result = await window.API.getFileDetails(fileId);
      
      if (!result.success) {
        window.Components.showToast(result.error, 'error');
        return;
      }

      const file = result.file;
      this.showFileDetailsModal(file);

    } catch (error) {
      console.error('Error getting file details:', error);
      window.Components.showToast('Failed to load file details', 'error');
    }
  }

  /**
   * Convert CSV records to markdown format
   */
  formatCsvRecordsAsMarkdown(records) {
    if (!records || records.length === 0) {
      return 'No data available';
    }

    // Use Hybrid Structured Format for preview
    const columns = Object.keys(records[0]);
    const lines = [];
    
    // Header with metadata
    lines.push(`Dataset: ${records.length} records (preview)`);
    lines.push(`Columns: ${columns.join(', ')}`);
    lines.push('');
    
    // Show all preview records in compact format
    lines.push('Sample data:');
    for (const record of records) {
      const rowValues = columns.map(col => String(record[col] || ''));
      lines.push(rowValues.join(' | '));
    }
    
    return lines.join('\n');
  }

  /**
   * Generate token analysis HTML for file info modal
   */
  async generateTokenAnalysisHtml(file) {
    // Show token analysis for CSV and PDF files
    if (file.mime_type !== 'text/csv' && file.mime_type !== 'application/pdf') {
      return '';
    }
    
    // For CSV files, require csv_data to be present
    if (file.mime_type === 'text/csv' && !file.csv_data) {
      return '';
    }

    try {
      // Create a sample prompt to test token counting
      const samplePrompt = "Analyze this data and provide insights.";
      
      // Get available models for token counting
      const models = await window.API.getModels();
      if (!models || !models.length) {
        return `
          <h6>Token Analysis</h6>
          <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle me-2"></i>
            Unable to load models for token analysis.
          </div>
        `;
      }

      // Show loading state while calculating
      const loadingHtml = `
        <h6>Token Analysis</h6>
        <div class="mb-3">
          <div class="alert alert-info">
            <i class="fas fa-calculator me-2"></i>
            <strong>Token Usage Estimates:</strong><br>
            Calculating token counts for this file across different model providers...
          </div>
          <div class="d-flex justify-content-center">
            <div class="spinner-border" role="status">
              <span class="visually-hidden">Calculating...</span>
            </div>
          </div>
        </div>
      `;

      // Start with loading state, then update with actual counts
      setTimeout(async () => {
        try {
          const tokenResults = await this.calculateTokenCountsForFile(file, samplePrompt, models);
          this.updateTokenAnalysisInModal(tokenResults);
        } catch (error) {
          console.error('Error calculating token counts:', error);
          this.updateTokenAnalysisInModal(null, error.message);
        }
      }, 100);

      return loadingHtml;

    } catch (error) {
      console.error('Error generating token analysis:', error);
      return `
        <h6>Token Analysis</h6>
        <div class="alert alert-danger">
          <i class="fas fa-exclamation-circle me-2"></i>
          Error calculating token analysis: ${error.message}
        </div>
      `;
    }
  }

  /**
   * Calculate token counts for a file using different model providers
   */
  async calculateTokenCountsForFile(file, samplePrompt, models) {
    const results = [];
    
    // For CSV and PDF files, use actual token counting APIs
    if ((file.mime_type === 'text/csv' && file.csv_data) || file.mime_type === 'application/pdf') {
      // Group models by provider and find the best representative for each
      const providerGroups = {
        'OpenAI': models.filter(m => m.provider === 'openai'),
        'Anthropic': models.filter(m => m.provider === 'anthropic'), 
        'Google': models.filter(m => m.provider === 'google')
      };

      // Collect the best model from each provider
      const testModels = [];
      for (const [providerName, providerModels] of Object.entries(providerGroups)) {
        if (providerModels.length === 0) continue;
        const bestModel = this.getBestModelForProvider(providerName, providerModels);
        testModels.push(bestModel.id);
      }

      try {
        // Call the actual token counting API
        const tokenResults = await window.API.countTokensForFile(
          file.file_path,
          samplePrompt,
          testModels
        );

        if (tokenResults.success && tokenResults.provider_results) {
          // Convert API results to our format
          for (const [providerName, providerModels] of Object.entries(providerGroups)) {
            if (providerModels.length === 0) continue;

            const bestModel = this.getBestModelForProvider(providerName, providerModels);
            const apiResult = tokenResults.provider_results[bestModel.provider];

            if (apiResult && !apiResult.error) {
              // Handle both actual_tokens and estimated_tokens from backend
              const tokenCount = apiResult.actual_tokens !== undefined ? apiResult.actual_tokens : apiResult.estimated_tokens;
              const isEstimate = apiResult.is_estimate || apiResult.actual_tokens === undefined;
              
              results.push({
                provider: providerName,
                modelName: apiResult.model_name,
                displayName: bestModel.name,
                actualTokens: !isEstimate ? tokenCount : undefined,
                estimatedTokens: isEstimate ? tokenCount : undefined,
                contextLimit: apiResult.context_limit,
                willExceed: apiResult.will_exceed,
                modelsInProvider: providerModels.length,
                isEstimate: isEstimate
              });
            } else {
              results.push({
                provider: providerName,
                error: apiResult?.error || 'Token counting failed',
                modelsInProvider: providerModels.length
              });
            }
          }
        } else {
          throw new Error(tokenResults.error || 'Token counting API failed');
        }

      } catch (error) {
        console.error('Error calling token counting API:', error);
        
        // Fall back to estimates if API fails
        const estimatedTokens = file.mime_type === 'text/csv' 
          ? this.estimateCsvTokens(file.csv_data, samplePrompt)
          : this.estimatePdfTokens(file, samplePrompt);
        
        for (const [providerName, providerModels] of Object.entries(providerGroups)) {
          if (providerModels.length === 0) continue;

          const bestModel = this.getBestModelForProvider(providerName, providerModels);
          const contextLimit = this.getContextLimitForModel(bestModel.id);
          const willExceed = estimatedTokens > contextLimit;
          
          results.push({
            provider: providerName,
            modelName: bestModel.id,
            displayName: bestModel.name,
            estimatedTokens: estimatedTokens,
            contextLimit: contextLimit,
            willExceed: willExceed,
            modelsInProvider: providerModels.length,
            isEstimate: true
          });
        }
      }
    }

    return results;
  }

  /**
   * Get the best model for each provider
   */
  getBestModelForProvider(providerName, providerModels) {
    const bestModels = {
      'OpenAI': 'o3',                                    // Best OpenAI model
      'Anthropic': 'claude-opus-4-20250514',           // Best Anthropic model  
      'Google': 'gemini-2.5-pro-preview-06-05'         // Best Google model
    };
    
    const preferredModel = bestModels[providerName];
    
    // Try to find the preferred model first
    const preferred = providerModels.find(m => m.id === preferredModel);
    if (preferred) {
      return preferred;
    }
    
    // If preferred not available, fall back to the one with largest context window
    return providerModels.reduce((best, current) => {
      const currentLimit = this.getContextLimitForModel(current.id);
      const bestLimit = this.getContextLimitForModel(best.id);
      return currentLimit > bestLimit ? current : best;
    });
  }

  /**
   * Estimate tokens for CSV content
   */
  estimateCsvTokens(csvData, samplePrompt) {
    const columns = csvData.columns || [];
    const totalRows = csvData.total_rows || 0;
    
    // Estimate characters per row in markdown format
    const avgColumnNameLength = columns.reduce((sum, col) => sum + col.length, 0) / columns.length || 10;
    const avgValueLength = 15; // Average data value length
    const markdownOverhead = columns.length * 4; // "  column: value\n" format
    
    const charsPerRow = (avgColumnNameLength + avgValueLength + 4) * columns.length + markdownOverhead;
    const totalChars = charsPerRow * totalRows + samplePrompt.length;
    
    // Convert to tokens: roughly 1 token per 3.5-4 characters for English
    return Math.ceil(totalChars / 3.5);
  }

  /**
   * Estimate tokens for PDF files (rough approximation)
   */
  estimatePdfTokens(file, samplePrompt) {
    // Rough estimation based on file size
    // PDFs typically have ~1-2 characters per byte due to formatting overhead
    const avgCharsPerByte = 1.5;
    const estimatedChars = (file.size || 0) * avgCharsPerByte + samplePrompt.length;
    
    // Convert to tokens: roughly 1 token per 3.5-4 characters for English
    return Math.ceil(estimatedChars / 3.5);
  }

  /**
   * Get context limit for specific model with CORRECT OpenAI limits
   */
  getContextLimitForModel(modelName) {
    const limits = {
      // OpenAI models - CORRECTED CONTEXT WINDOWS
      'gpt-4o': 128000,           // 128K
      'gpt-4o-mini': 128000,      // 128K
      'o3': 200000,               // 200K
      'o4-mini': 200000,          // 200K  
      'gpt-4.1': 1047576,         // ~1M
      'gpt-4.1-mini': 1047576,    // ~1M
      'gpt-4.1-nano': 1047576,    // ~1M
      
      // Anthropic models (all 200K)
      'claude-3-5-haiku-20241022': 200000,
      'claude-3-7-sonnet-20250219': 200000,
      'claude-3-7-sonnet-20250219-thinking': 200000,
      'claude-sonnet-4-20250514': 200000,
      'claude-sonnet-4-20250514-thinking': 200000,
      'claude-opus-4-20250514': 200000,
      'claude-opus-4-20250514-thinking': 200000,
      
      // Google models (1M+ tokens)
      'gemini-2.5-flash-preview-05-20': 1000000,
      'gemini-2.5-pro-preview-06-05': 1000000,
    };
    
    return limits[modelName] || 128000; // Conservative default
  }

  /**
   * Update token analysis section in the modal
   */
  updateTokenAnalysisInModal(results, errorMessage = null) {
    const tokenSection = document.querySelector('#fileDetailsModal .token-analysis-section');
    if (!tokenSection) return;

    if (errorMessage) {
      tokenSection.innerHTML = `
        <div class="alert alert-danger">
          <i class="fas fa-exclamation-circle me-2"></i>
          Error calculating token counts: ${errorMessage}
        </div>
      `;
      return;
    }

    if (!results || results.length === 0) {
      tokenSection.innerHTML = `
        <div class="alert alert-warning">
          <i class="fas fa-exclamation-triangle me-2"></i>
          No token count results available.
        </div>
      `;
      return;
    }

    const resultsHtml = results.map(result => {
      if (result.error) {
        return `
          <div class="card border-danger mb-2">
            <div class="card-body py-2">
              <div class="d-flex justify-content-between align-items-center">
                <div>
                  <strong>${result.provider}</strong>
                  <br><small class="text-muted">${result.modelsInProvider} models available</small>
                </div>
                <div class="text-danger">
                  <i class="fas fa-exclamation-circle"></i>
                  <small>Error: ${result.error}</small>
                </div>
              </div>
            </div>
          </div>
        `;
      }

      // Use actualTokens if available, otherwise fall back to estimatedTokens
      const tokenCount = result.actualTokens !== undefined ? result.actualTokens : result.estimatedTokens;
      const isEstimate = result.isEstimate || result.actualTokens === undefined;
      
      // Safety check for undefined values
      if (tokenCount === undefined || result.contextLimit === undefined) {
        return `
          <div class="card border-warning mb-2">
            <div class="card-body py-2">
              <div class="d-flex justify-content-between align-items-center">
                <div>
                  <strong>${result.provider}</strong>
                  <br><small class="text-muted">${result.modelsInProvider} models available</small>
                </div>
                <div class="text-warning">
                  <i class="fas fa-exclamation-triangle"></i>
                  <small>Token count unavailable</small>
                </div>
              </div>
            </div>
          </div>
        `;
      }
      
      const percentage = ((tokenCount / result.contextLimit) * 100).toFixed(1);
      const statusColor = result.willExceed ? 'danger' : 
                         (percentage > 80 ? 'warning' : 'success');
      const statusIcon = result.willExceed ? 'fa-times-circle' : 
                        (percentage > 80 ? 'fa-exclamation-triangle' : 'fa-check-circle');
      const statusText = result.willExceed ? 'Will likely exceed' : 
                        (percentage > 80 ? 'May struggle' : 'Should work fine');
      
      const tokenLabel = isEstimate ? 'Estimated' : 'Actual';
      const tokenIcon = isEstimate ? 'fa-calculator' : 'fa-check';

      return `
        <div class="card border-${statusColor} mb-2">
          <div class="card-body py-2">
            <div class="d-flex justify-content-between align-items-center">
              <div>
                <strong>${result.provider}</strong>
                <br><small class="text-muted">${result.modelsInProvider} models (tested: ${Utils.formatModelName(result.modelName)})</small>
              </div>
              <div class="text-${statusColor}">
                <i class="fas ${statusIcon} me-1"></i>
                <strong>${tokenCount.toLocaleString()}</strong> / ${result.contextLimit.toLocaleString()} tokens
                <br><small>${statusText} (${percentage}%) <i class="fas ${tokenIcon}"></i> ${tokenLabel}</small>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');

    tokenSection.innerHTML = `
      <div class="alert alert-info">
        <i class="fas fa-info-circle me-2"></i>
        <strong>Token counts calculated using sample prompt:</strong> "Analyze this data and provide insights."<br>
        <small>These counts use each provider's official token counting methods. Actual usage may vary based on your specific prompts and selected models.</small>
      </div>
      ${resultsHtml}
    `;
  }

  /**
   * Show file details modal
   */
  async showFileDetailsModal(file) {
    const fileSize = this.formatFileSize(file.file_size_bytes);
    const createdDate = new Date(file.created_at).toLocaleString();
    const existsClass = file.exists_on_disk ? 'text-success' : 'text-danger';
    const existsIcon = file.exists_on_disk ? 'fa-check-circle' : 'fa-exclamation-triangle';
    const existsText = file.exists_on_disk ? 'Available on disk' : 'Missing from disk';

    const uploadsHtml = file.provider_uploads && file.provider_uploads.length > 0 
      ? file.provider_uploads.map(upload => `
          <li class="list-group-item d-flex justify-content-between align-items-center">
            <span>
              <strong>${upload.provider}</strong>
              <br><small class="text-muted">ID: ${upload.provider_file_id}</small>
            </span>
            <small class="text-muted">${new Date(upload.uploaded_at).toLocaleString()}</small>
          </li>
        `).join('')
      : '<li class="list-group-item text-muted">No provider uploads yet</li>';

    // CSV preview section
    let csvPreviewHtml = '';
    if (file.mime_type === 'text/csv' && file.csv_data) {
      try {
        const csvData = typeof file.csv_data === 'string' ? JSON.parse(file.csv_data) : file.csv_data;
        
        // Handle different CSV data formats
        let previewRecords = [];
        if (csvData && Array.isArray(csvData.records)) {
          // New format with records array
          previewRecords = csvData.records.slice(0, 2);
        } else if (Array.isArray(csvData)) {
          // Legacy format - direct array of records
          previewRecords = csvData.slice(0, 2);
        }
        
        if (previewRecords.length > 0) {
          const markdownData = this.formatCsvRecordsAsMarkdown(previewRecords);
          
          // Safely get CSV metadata with fallbacks
          const totalRows = csvData.total_rows || (Array.isArray(csvData.records) ? csvData.records.length : csvData.length || 0);
          const columns = csvData.columns || [];
          
          csvPreviewHtml = `
            <h6>CSV Data Preview</h6>
            <div class="mb-3">
          <div class="row mb-2">
            <div class="col-md-6">
              <strong>Total Rows:</strong> ${totalRows.toLocaleString()}
            </div>
            <div class="col-md-6">
              <strong>Columns:</strong> ${columns.length}
            </div>
          </div>
          ${columns.length > 0 ? `
          <div class="mb-2">
            <strong>Column Names:</strong>
            <div class="d-flex flex-wrap gap-1 mt-1">
              ${columns.map(col => `<span class="badge bg-secondary">${Utils.sanitizeHtml(col)}</span>`).join('')}
            </div>
          </div>
          ` : ''}
          <div>
            <strong>Sample Data (first 2 rows):</strong>
            <pre class="bg-light p-2 mt-1 small" style="max-height: 200px; overflow-y: auto;"><code>${Utils.sanitizeHtml(markdownData)}</code></pre>
          </div>
        </div>
      `;
        }
      } catch (e) {
        console.error('Error parsing CSV data for preview:', e);
        csvPreviewHtml = `
          <h6>CSV Data Preview</h6>
          <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle me-2"></i>
            Unable to parse CSV data for preview.
          </div>
        `;
      }
    }

    // PDF content preview section
    let pdfPreviewHtml = '';
    if (file.mime_type === 'application/pdf') {
      try {
        // Call backend to extract PDF text for preview
        const pdfTextResponse = await window.API.extractPdfText(file.file_path);
        
        if (pdfTextResponse.success && pdfTextResponse.text) {
          const fullText = pdfTextResponse.text;
          const previewText = fullText.substring(0, 2000); // First 2000 characters
          const wordCount = fullText.split(/\s+/).length;
          const charCount = fullText.length;
          
          pdfPreviewHtml = `
            <h6>PDF Content Preview</h6>
            <div class="mb-3">
              <div class="row mb-2">
                <div class="col-md-6">
                  <strong>Total Characters:</strong> ${charCount.toLocaleString()}
                </div>
                <div class="col-md-6">
                  <strong>Word Count:</strong> ${wordCount.toLocaleString()}
                </div>
              </div>
              <div>
                <strong>Content Preview (first 2000 characters):</strong>
                <pre class="bg-light p-2 mt-1 small" style="max-height: 300px; overflow-y: auto;"><code>${Utils.sanitizeHtml(previewText)}${fullText.length > 2000 ? '...' : ''}</code></pre>
              </div>
            </div>
          `;
        } else {
          pdfPreviewHtml = `
            <h6>PDF Content Preview</h6>
            <div class="alert alert-warning">
              <i class="fas fa-exclamation-triangle me-2"></i>
              Unable to extract text content from this PDF file.
            </div>
          `;
        }
      } catch (error) {
        console.error('Error extracting PDF text for preview:', error);
        pdfPreviewHtml = `
          <h6>PDF Content Preview</h6>
          <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle me-2"></i>
            Error extracting PDF content for preview.
          </div>
        `;
      }
    }

    // PDF chunking section
    let pdfChunkingHtml = '';
    if (file.mime_type === 'application/pdf' && file.pdf_chunks && file.pdf_chunks.length > 0) {
      const chunks = file.pdf_chunks;
      const totalChunks = chunks.length;
      const chunksHtml = chunks.map(chunk => {
        const chunkSize = this.formatFileSize(chunk.file_size_bytes);
        const statusIcon = chunk.exists_on_disk ? 'fa-check-circle text-success' : 'fa-exclamation-triangle text-warning';
        const pageRange = chunk.start_page === chunk.end_page ? `Page ${chunk.start_page}` : `Pages ${chunk.start_page}-${chunk.end_page}`;
        
        return `
          <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
            <div>
              <span class="badge bg-primary me-2">Chunk ${chunk.chunk_order}</span>
              <span class="me-3">${pageRange}</span>
              <small class="text-muted">${chunkSize}</small>
            </div>
            <i class="fas ${statusIcon}"></i>
          </div>
        `;
      }).join('');
      
      pdfChunkingHtml = `
        <h6>PDF Chunking Information</h6>
        <div class="mb-3">
          <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            <strong>How this PDF is used for LLM prompting:</strong><br>
            This PDF is automatically split into ${totalChunks} chunks of approximately 5 pages each. 
            When running benchmarks, the system uses keyword matching to select the most relevant chunks 
            that fit within the LLM's context window.
          </div>
          <div class="mb-2">
            <strong>Total Chunks:</strong> ${totalChunks}
          </div>
          <div class="border rounded p-2" style="max-height: 200px; overflow-y: auto;">
            ${chunksHtml}
          </div>
        </div>
      `;
    }

    const modalHtml = `
      <div class="modal fade" id="fileDetailsModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">
                <i class="${this.getFileIcon(file.original_filename)} me-2"></i>
                ${Utils.sanitizeHtml(file.original_filename)}
              </h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="row mb-3">
                <div class="col-md-6">
                  <strong>File Size:</strong> ${fileSize}
                </div>
                <div class="col-md-6">
                  <strong>Status:</strong> 
                  <span class="${existsClass}">
                    <i class="fas ${existsIcon} me-1"></i>${existsText}
                  </span>
                </div>
              </div>
              <div class="row mb-3">
                <div class="col-md-6">
                  <strong>MIME Type:</strong> ${file.mime_type}
                </div>
                <div class="col-md-6">
                  <strong>Uploaded:</strong> ${createdDate}
                </div>
              </div>
              <div class="mb-3">
                <strong>File Path:</strong>
                <br><code>${Utils.sanitizeHtml(file.file_path)}</code>
              </div>
              
              ${csvPreviewHtml}
              ${pdfPreviewHtml}
              
              <div class="token-analysis-section">
                ${await this.generateTokenAnalysisHtml(file)}
              </div>
              
              ${pdfChunkingHtml}
              
              <h6>Provider Uploads</h6>
              <ul class="list-group mb-3">
                ${uploadsHtml}
              </ul>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Remove existing modal if any
    const existingModal = document.getElementById('fileDetailsModal');
    if (existingModal) {
      existingModal.remove();
    }

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('fileDetailsModal'));
    modal.show();

    // Clean up modal when hidden
    document.getElementById('fileDetailsModal').addEventListener('hidden.bs.modal', function() {
      this.remove();
    });
  }

  /**
   * Delete a file
   */
  async deleteFile(fileId, fileName) {
    // Use the createConfirmModal method that exists in Components
    window.Components.createConfirmModal(
      'Delete File',
      `Are you sure you want to delete "${fileName}"? This action cannot be undone.`,
      async () => {
        try {
          const result = await window.API.deleteFile(fileId);

          if (result.success) {
            window.Components.showToast(result.message, 'success');
            await this.loadFiles(); // Refresh the files list
          } else {
            window.Components.showToast(result.error, 'error');
          }

        } catch (error) {
          console.error('Error deleting file:', error);
          window.Components.showToast('Failed to delete file', 'error');
        }
      }
    );
  }

  /**
   * Format file size in human readable format
   */
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * Get appropriate icon for file type
   */
  getFileIcon(filename) {
    const extension = filename.split('.').pop().toLowerCase();
    switch (extension) {
      case 'pdf':
        return 'fas fa-file-pdf';
      case 'csv':
        return 'fas fa-file-csv';
      case 'xlsx':
      case 'xls':
        return 'fas fa-file-excel';
      default:
        return 'fas fa-file';
    }
  }

  /**
   * Sync benchmark - rerun missing, failed, or pending prompts
   * @param {number} benchmarkId - Benchmark ID
   */
  async syncBenchmark(benchmarkId) {
    try {
      // First get sync status to show user what will be synced
      const statusResult = await window.API.getBenchmarkSyncStatus(benchmarkId);
      
      if (!statusResult.success) {
        throw new Error(statusResult.error || 'Failed to get sync status');
      }
      
      const syncStatus = statusResult.sync_status;
      
      if (!syncStatus.sync_needed) {
        window.Components.showToast('Benchmark is already complete - no sync needed', 'info');
        return;
      }
      
      // Show confirmation dialog with sync details
      const modelsNeedingSync = syncStatus.models_needing_sync.length;
      const totalPrompts = syncStatus.total_prompts_to_sync;
      
      const confirmed = await window.Utils.showConfirmDialog(
        'Sync Benchmark',
        `This will rerun ${totalPrompts} prompts across ${modelsNeedingSync} models. Continue?`,
        'warning'
      );

      if (!confirmed) return;

      // Start the sync
      const result = await window.API.syncBenchmark(benchmarkId);
      
      if (result.success) {
        window.Components.showToast(
          `Sync started: ${result.prompts_to_sync} prompts across ${result.models_to_sync} models`, 
          'success'
        );
        
        // Update the benchmark status to show it's running
        const benchmark = this.benchmarksData.find(b => b.id === benchmarkId);
        if (benchmark) {
          benchmark.status = 'running';
        }
        
        // If we're on the details page for this benchmark, refresh it
        if (this.currentBenchmarkId === benchmarkId) {
          setTimeout(() => {
            this.viewBenchmarkDetails(benchmarkId);
          }, 1000);
        } else {
          // Otherwise just refresh the home page
          this.renderBenchmarks();
          setTimeout(() => {
            this.loadBenchmarks(false);
          }, 1000);
        }
        
      } else {
        throw new Error(result.error || 'Failed to start sync');
      }
    } catch (error) {
      console.error('Error syncing benchmark:', error);
      window.Components.showToast(`Failed to sync benchmark: ${error.message}`, 'error');
    }
  }

  /**
   * Rerun a single prompt
   * @param {number} promptId - Prompt ID
   */
  async rerunSinglePrompt(promptId) {
    try {
      // Show confirmation dialog
      const confirmed = await window.Utils.showConfirmDialog(
        'Rerun Prompt',
        'Are you sure you want to rerun this prompt? The previous result will be replaced.',
        'warning'
      );

      if (!confirmed) return;

      // Start the rerun
      const result = await window.API.rerunSinglePrompt(promptId);
      
      if (result.success) {
        window.Components.showToast('Prompt rerun started', 'success');
        
        // Force clear any cached data to ensure fresh UI
        window.API.clearCache('benchmarks');
        
        // If we're viewing benchmark details, refresh immediately and again after delay
        if (this.currentBenchmarkId) {
          this.viewBenchmarkDetails(this.currentBenchmarkId);
          setTimeout(() => {
            this.viewBenchmarkDetails(this.currentBenchmarkId);
          }, 2000);
        }
        
      } else {
        throw new Error(result.error || 'Failed to rerun prompt');
      }
    } catch (error) {
      console.error('Error rerunning prompt:', error);
      window.Components.showToast(`Failed to rerun prompt: ${error.message}`, 'error');
    }
  }

  /**
   * Force refresh the current view to get latest data
   */
  async forceRefresh() {
    try {
      // Clear all caches
      window.API.clearCache('benchmarks');
      
      if (this.currentBenchmarkId) {
        // If viewing benchmark details, refresh them
        window.Components.showToast('Refreshing benchmark data...', 'info');
        await this.viewBenchmarkDetails(this.currentBenchmarkId);
      } else {
        // If on home page, refresh benchmarks list
        window.Components.showToast('Refreshing benchmarks list...', 'info');
        await this.loadBenchmarks(false);
      }
      
      window.Components.showToast('Data refreshed successfully', 'success');
    } catch (error) {
      console.error('Error refreshing data:', error);
      window.Components.showToast(`Failed to refresh: ${error.message}`, 'error');
    }
  }
}

// Create singleton instance
window.Pages = new Pages(); 