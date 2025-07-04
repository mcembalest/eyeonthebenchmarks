/**
 * Main application initialization and event handling
 */

class App {
  constructor() {
    this.initialized = false;
    this.eventListeners = [];
    this.realTimeUpdatesSetup = false;
    
    this.setupEventListeners();
    this.setupRealTimeUpdates();
    
    // Initialize PDF display
    requestAnimationFrame(() => {
      this.updatePdfDisplay();
    });
    
    console.log('App initialized successfully');
  }

  /**
   * Initialize the application
   */
  async init() {
    if (this.initialized) {
      console.warn('App already initialized');
      return;
    }

    try {
      // Check if API is available
      if (!window.API || !window.API.isAvailable()) {
        throw new Error('Electron API not available. Please ensure the app is running in Electron.');
      }

      // Initialize settings (this will show first-time setup if needed)
      if (window.Settings) {
        await window.Settings.init();
      }

      // Initialize the home page
      await window.Pages.initHomePage();

      this.initialized = true;
      console.log('Application initialized successfully');

    } catch (error) {
      console.error('Failed to initialize application:', error);
      if (window.Components && window.Components.showToast) {
        window.Components.showToast(`Failed to initialize app: ${error.message}`, 'error', 0);
      }
    }
  }

  /**
   * Set up event listeners
   */
  setupEventListeners() {
    // Use event delegation for dynamically created buttons
    document.addEventListener('click', (e) => {
      // Handle run benchmark button
      if (e.target.id === 'runBenchmarkBtn' || e.target.closest('#runBenchmarkBtn')) {
        e.preventDefault();
        window.Pages.runBenchmark();
      }
    });

    // Static event listeners for elements that always exist
    this.addEventListeners([
      // View toggles
      { selector: '#gridViewBtn', event: 'click', handler: () => window.Pages.toggleView('grid') },
      { selector: '#tableViewBtn', event: 'click', handler: () => window.Pages.toggleView('table') },
      
      // Refresh button
      { selector: '#refreshBtn', event: 'click', handler: () => window.Pages.loadBenchmarks(false) },
      
      // Cleanup button for stuck benchmarks
      { selector: '#cleanupBtn', event: 'click', handler: () => this.handleCleanupStuckBenchmarks() },
      
      // Composer page elements
      { selector: '#importCsvBtn', event: 'click', handler: () => this.handleCsvImport() },
      { selector: '#addPromptBtn', event: 'click', handler: () => window.Pages.addPrompt() },
      { selector: '#selectPdfBtn', event: 'click', handler: () => this.handlePdfSelection() },
      { selector: '#selectMultiplePdfsBtn', event: 'click', handler: () => this.handleMultiplePdfSelection() },
      { selector: '#selectExistingFilesBtn', event: 'click', handler: () => this.handleExistingFileSelection() }
    ]);

    // Global event listeners
    document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    window.addEventListener('resize', Utils.debounce(() => this.handleResize(), 250));

    console.log('Event listeners set up successfully');
  }

  /**
   * Add multiple event listeners
   * @param {Array} listeners - Array of listener objects
   */
  addEventListeners(listeners) {
    listeners.forEach(({ selector, event, handler }) => {
      const element = document.querySelector(selector);
      if (element) {
        element.addEventListener(event, handler);
        this.eventListeners.push({ element, event, handler });
      } else {
        console.warn(`Element not found: ${selector}`);
      }
    });
  }

  /**
   * Set up real-time updates from main process
   */
  setupRealTimeUpdates() {
    if (this.realTimeUpdatesSetup) {
      console.log('Real-time updates already set up, skipping...');
      return;
    }
    
    if (window.API && window.API.setupEventListeners) {
      window.API.setupEventListeners({
        onProgress: (data) => {
          console.log('🚀 App received progress event:', data);
          window.Pages.handleProgress(data);
        },
        onComplete: (data) => {
          console.log('🚀 App received complete event:', data);
          window.Pages.handleComplete(data);
        },
        onMainProcessReady: () => {
          console.log('Main process ready signal received');
          // Re-initialize if needed
          if (!this.initialized) {
            this.init();
          } else {
            // If already initialized but backend was down, refresh benchmarks
            console.log('Backend is ready, refreshing benchmarks...');
            window.API.clearCache('benchmarks');
            if (window.Pages && window.Pages.currentPage === 'homeContent') {
              // Force a fresh load with retry logic
              window.Pages.loadBenchmarks(false, 0);
            }
          }
        }
      });
      this.realTimeUpdatesSetup = true;
    }

    console.log('Real-time updates set up successfully');
  }

  /**
   * Handle CSV import
   */
  async handleCsvImport() {
    try {
      const filePath = await window.API.openFileDialog({
        properties: ['openFile'],
        filters: [{ name: 'CSV Files', extensions: ['csv'] }]
      });

      if (!filePath) return;

      window.Components.showToast('Reading CSV file...', 'info');

      const parsedData = await window.API.readCsv(filePath);

      if (!parsedData || parsedData.length === 0) {
        window.Components.showToast('CSV file is empty or could not be parsed', 'warning');
        return;
      }

      // Clear existing empty prompts before importing
      window.Pages.clearEmptyPrompts();

      // Add prompts from CSV
      parsedData.forEach(item => {
        if (item.prompt) {
          window.Pages.addPrompt(item.prompt);
        }
      });

      window.Components.showToast(`Imported ${parsedData.length} prompts from CSV`, 'success');

    } catch (error) {
      console.error('Error importing CSV:', error);
      window.Components.showToast(`Failed to import CSV: ${error.message}`, 'error');
    }
  }

  /**
   * Handle PDF file selection
   */
  async handlePdfSelection() {
    try {
      const pdfPath = await window.API.openFileDialog({
        properties: ['openFile'],
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }]
      });

      if (pdfPath) {
        // Add to the array instead of replacing
        if (!window.Pages.selectedPdfPaths.includes(pdfPath)) {
          window.Pages.selectedPdfPaths.push(pdfPath);
          this.updatePdfDisplay();
          
          const fileName = pdfPath.split('/').pop() || pdfPath.split('\\').pop();
          window.Components.showToast(`Added file: ${fileName}`, 'success');
        } else {
          window.Components.showToast('File already selected', 'warning');
        }
      }

    } catch (error) {
      console.error('Error selecting PDF:', error);
      window.Components.showToast(`Failed to select PDF: ${error.message}`, 'error');
    }
  }

  /**
   * Handle multiple PDF file selection
   */
  async handleMultiplePdfSelection() {
    try {
      const pdfPaths = await window.API.openFileDialog({
        properties: ['openFile', 'multiSelections'],
        filters: [{ name: 'PDF Files', extensions: ['pdf'] }]
      });

      if (pdfPaths && Array.isArray(pdfPaths) && pdfPaths.length > 0) {
        let addedCount = 0;
        
        pdfPaths.forEach(pdfPath => {
          if (!window.Pages.selectedPdfPaths.includes(pdfPath)) {
            window.Pages.selectedPdfPaths.push(pdfPath);
            addedCount++;
          }
        });
        
        this.updatePdfDisplay();
        
        if (addedCount > 0) {
          window.Components.showToast(`Added ${addedCount} file(s)`, 'success');
        } else {
          window.Components.showToast('All selected files were already added', 'warning');
        }
      }

    } catch (error) {
      console.error('Error selecting multiple PDFs:', error);
      window.Components.showToast(`Failed to select PDFs: ${error.message}`, 'error');
    }
  }

  /**
   * Handle existing file selection from registered files
   */
  async handleExistingFileSelection() {
    try {
      // Get all registered files
      const files = await window.API.getFiles();
      
      if (!files || files.length === 0) {
        window.Components.showToast('No files registered yet. Upload files first.', 'info');
        return;
      }

      // Create modal for file selection
      this.showFileSelectionModal(files);
      
    } catch (error) {
      console.error('Error loading existing files:', error);
      window.Components.showToast(`Failed to load files: ${error.message}`, 'error');
    }
  }

  /**
   * Show modal for selecting existing files
   */
  showFileSelectionModal(files) {
    // Filter to show only existing files
    const existingFiles = files.filter(file => file.exists_on_disk);
    
    if (existingFiles.length === 0) {
      window.Components.showToast('No valid files available on disk', 'warning');
      return;
    }

    const modalHtml = `
      <div class="modal fade" id="fileSelectionModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">
                <i class="fas fa-folder-open me-2"></i>
                Select Existing Files
              </h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <p class="text-muted mb-3">Select files to include in your benchmark. CSV files will be processed as JSON records.</p>
              
              <div class="file-selection-list" style="max-height: 400px; overflow-y: auto;">
                ${existingFiles.map(file => {
                  const fileSize = this.formatFileSize(file.file_size_bytes);
                  const isSelected = window.Pages.selectedPdfPaths.includes(file.file_path);
                  const fileIcon = this.getFileIcon(file.original_filename);
                  
                  // Add CSV info if available
                  let csvInfo = '';
                  if (file.mime_type === 'text/csv' && file.csv_rows > 0) {
                    csvInfo = `<small class="text-muted ms-2">(${file.csv_rows.toLocaleString()} rows, ${file.csv_columns} columns)</small>`;
                  }
                  
                  return `
                    <div class="form-check p-3 border rounded mb-2 ${isSelected ? 'bg-light' : ''}">
                      <input class="form-check-input file-selection-checkbox" type="checkbox" 
                             value="${Utils.sanitizeHtml(file.file_path)}" 
                             id="file_${file.id}"
                             ${isSelected ? 'checked' : ''}>
                      <label class="form-check-label d-flex justify-content-between align-items-center w-100" for="file_${file.id}">
                        <div>
                          <i class="${fileIcon} text-primary me-2"></i>
                          <strong>${Utils.sanitizeHtml(file.original_filename)}</strong>
                          ${csvInfo}
                          <br>
                          <small class="text-muted">${fileSize} • ${new Date(file.created_at).toLocaleDateString()}</small>
                        </div>
                        ${file.mime_type === 'text/csv' ? '<span class="badge bg-info">CSV</span>' : ''}
                      </label>
                    </div>
                  `;
                }).join('')}
              </div>
              
              <div class="mt-3">
                <button class="btn btn-sm btn-outline-secondary" onclick="window.app.selectAllFiles(true)">
                  <i class="fas fa-check-square me-1"></i>Select All
                </button>
                <button class="btn btn-sm btn-outline-secondary ms-2" onclick="window.app.selectAllFiles(false)">
                  <i class="fas fa-square me-1"></i>Deselect All
                </button>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" onclick="window.app.confirmFileSelection()">
                <i class="fas fa-check me-1"></i>Confirm Selection
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Remove existing modal if any
    const existingModal = document.getElementById('fileSelectionModal');
    if (existingModal) {
      existingModal.remove();
    }

    // Add modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('fileSelectionModal'));
    modal.show();

    // Clean up on hide
    document.getElementById('fileSelectionModal').addEventListener('hidden.bs.modal', () => {
      document.getElementById('fileSelectionModal').remove();
    });
  }

  /**
   * Select or deselect all files in the modal
   */
  selectAllFiles(select) {
    const checkboxes = document.querySelectorAll('.file-selection-checkbox');
    checkboxes.forEach(cb => cb.checked = select);
  }

  /**
   * Confirm file selection from modal
   */
  confirmFileSelection() {
    const selectedFiles = Array.from(document.querySelectorAll('.file-selection-checkbox:checked'))
      .map(cb => cb.value);
    
    if (selectedFiles.length === 0) {
      window.Components.showToast('No files selected', 'warning');
      return;
    }

    // Update the selected files
    window.Pages.selectedPdfPaths = selectedFiles;
    this.updatePdfDisplay();

    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('fileSelectionModal'));
    modal.hide();

    window.Components.showToast(`Selected ${selectedFiles.length} file(s)`, 'success');
  }

  /**
   * Format file size for display
   */
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * Get file icon based on filename
   */
  getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
      'pdf': 'fas fa-file-pdf',
      'csv': 'fas fa-file-csv',
      'xlsx': 'fas fa-file-excel',
      'xls': 'fas fa-file-excel',
      'doc': 'fas fa-file-word',
      'docx': 'fas fa-file-word',
      'txt': 'fas fa-file-alt',
      'json': 'fas fa-file-code'
    };
    return iconMap[ext] || 'fas fa-file';
  }

  /**
   * Update PDF display with current selection
   */
  updatePdfDisplay() {
    const selectedPdfLabel = document.getElementById('selectedPdfLabel');
    if (!selectedPdfLabel) return;

    const pdfPaths = window.Pages.selectedPdfPaths || [];
    
    if (pdfPaths.length === 0) {
      selectedPdfLabel.innerHTML = '<span class="text-muted">No files selected</span>';
    } else if (pdfPaths.length === 1) {
      const fileName = pdfPaths[0].split('/').pop() || pdfPaths[0].split('\\\\').pop();
      selectedPdfLabel.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
          <span class="small">${Utils.sanitizeHtml(fileName)}</span>
          <button class="btn btn-sm btn-outline-danger" onclick="window.app.removePdfFile(0)">
            <i class="fas fa-times"></i>
          </button>
        </div>
      `;
    } else {
      selectedPdfLabel.innerHTML = `
        <div class="selected-files">
          ${pdfPaths.map((path, index) => {
            const fileName = path.split('/').pop() || path.split('\\\\').pop();
            return `
              <div class="d-flex justify-content-between align-items-center">
                <span class="small">${Utils.sanitizeHtml(fileName)}</span>
                <button class="btn btn-sm btn-outline-danger" onclick="window.app.removePdfFile(${index})">
                  <i class="fas fa-times"></i>
                </button>
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    // Show warning for multiple PDFs with real-time token validation
    if (pdfPaths.length > 1) {
      this.showTokenWarningForPdfs(pdfPaths);
    } else {
      // Remove any existing warning
      const existingWarning = document.querySelector('.pdf-token-warning');
      if (existingWarning) {
        existingWarning.remove();
      }
    }
  }

  /**
   * Show token warning for multiple PDFs with real-time validation
   */
  async showTokenWarningForPdfs(pdfPaths) {
    // Remove any existing warning first
    const existingWarning = document.querySelector('.pdf-token-warning');
    if (existingWarning) {
      existingWarning.remove();
    }

    // Get currently selected models
    const selectedModels = Array.from(
      document.querySelectorAll('#modelList input[type="checkbox"]:checked')
    ).map(cb => cb.value);

    if (selectedModels.length === 0) {
      // Show generic warning if no models selected yet
      const selectedPdfLabel = document.getElementById('selectedPdfLabel');
      selectedPdfLabel.insertAdjacentHTML('afterend', `
        <div class="alert alert-warning mt-2 mb-0 small pdf-token-warning">
          <i class="fas fa-exclamation-triangle me-1"></i>
          <strong>Multiple PDFs selected:</strong> Some models may hit token limits. Select models to see specific estimates.
        </div>
      `);
      return;
    }

    // Get a sample prompt to estimate tokens (use first prompt if available)
    const prompts = window.Pages.prompts
      ?.map(p => ({ prompt_text: p.text.trim() }))
      ?.filter(p => p.prompt_text) || [{ prompt_text: "Sample prompt for token estimation" }];

    try {
      // Perform real-time token validation
      const validation = await window.API.validateTokens({
        prompts: prompts.slice(0, 1), // Use just one prompt for estimation
        pdfPaths,
        modelNames: selectedModels
      });

      if (validation.status === 'success' && validation.validation_results) {
        const results = validation.validation_results;
        
        // Categorize models by risk level
        const exceedingModels = [];
        const warningModels = [];
        const safeModels = [];

        Object.entries(results.model_results).forEach(([modelName, result]) => {
          const formattedName = Utils.formatModelName(modelName);
          const tokenInfo = `${result.estimated_tokens.toLocaleString()} / ${result.context_limit.toLocaleString()} tokens`;
          
          if (result.will_exceed) {
            exceedingModels.push(`${formattedName} (${tokenInfo})`);
          } else if (result.estimated_tokens > result.context_limit * 0.8) {
            warningModels.push(`${formattedName} (${tokenInfo})`);
          } else {
            safeModels.push(`${formattedName} (${tokenInfo})`);
          }
        });

        // Create detailed warning message
        let warningHtml = `
          <div class="alert alert-warning mt-2 mb-0 small pdf-token-warning">
            <div class="d-flex align-items-start">
              <i class="fas fa-exclamation-triangle me-2 mt-1"></i>
              <div class="flex-grow-1">
                <strong>Token Analysis for ${pdfPaths.length} PDFs:</strong>
        `;

        if (exceedingModels.length > 0) {
          warningHtml += `
            <div class="mt-1">
              <span class="text-danger fw-bold">🚫 Will likely fail:</span>
              <div class="ms-2">${exceedingModels.join(', ')}</div>
            </div>
          `;
        }

        if (warningModels.length > 0) {
          warningHtml += `
            <div class="mt-1">
              <span class="text-warning fw-bold">⚠️ May struggle:</span>
              <div class="ms-2">${warningModels.join(', ')}</div>
            </div>
          `;
        }

        if (safeModels.length > 0) {
          warningHtml += `
            <div class="mt-1">
              <span class="text-success fw-bold">✅ Should work:</span>
              <div class="ms-2">${safeModels.join(', ')}</div>
            </div>
          `;
        }

        warningHtml += `
              </div>
            </div>
          </div>
        `;

        const selectedPdfLabel = document.getElementById('selectedPdfLabel');
        selectedPdfLabel.insertAdjacentHTML('afterend', warningHtml);

      } else {
        // Fallback to generic warning if validation fails
        const selectedPdfLabel = document.getElementById('selectedPdfLabel');
        selectedPdfLabel.insertAdjacentHTML('afterend', `
          <div class="alert alert-warning mt-2 mb-0 small pdf-token-warning">
            <i class="fas fa-exclamation-triangle me-1"></i>
            <strong>Multiple PDFs selected:</strong> Models with smaller context windows may hit token limits.
            <br><strong>Most likely to fail:</strong> GPT-4o and GPT-4o Mini (128K tokens)
            <br><strong>May fail with large documents:</strong> Claude models and o3/o4-mini (200K tokens)
            <br><strong>Best for large documents:</strong> GPT 4.1 series and Gemini models (1M+ tokens)
          </div>
        `);
      }
    } catch (error) {
      console.error('Error validating tokens for PDF warning:', error);
      // Show generic warning on error
      const selectedPdfLabel = document.getElementById('selectedPdfLabel');
      selectedPdfLabel.insertAdjacentHTML('afterend', `
        <div class="alert alert-warning mt-2 mb-0 small pdf-token-warning">
          <i class="fas fa-exclamation-triangle me-1"></i>
          <strong>Multiple PDFs selected:</strong> Unable to estimate token usage. Some models may hit limits.
        </div>
      `);
    }
  }

  /**
   * Remove a PDF file from selection
   * @param {number} index - Index of file to remove
   */
  removePdfFile(index) {
    if (window.Pages.selectedPdfPaths && index >= 0 && index < window.Pages.selectedPdfPaths.length) {
      const fileName = window.Pages.selectedPdfPaths[index].split('/').pop() || window.Pages.selectedPdfPaths[index].split('\\\\').pop();
      window.Pages.selectedPdfPaths.splice(index, 1);
      this.updatePdfDisplay();
      window.Components.showToast(`Removed file: ${fileName}`, 'info');
    }
  }

  /**
   * Handle keyboard shortcuts
   * @param {KeyboardEvent} e - Keyboard event
   */
  handleKeyboardShortcuts(e) {
    // Ctrl/Cmd + N: New benchmark
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
      e.preventDefault();
      window.Pages.navigateTo('composerContent');
    }

    // Ctrl/Cmd + R: Refresh
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
      e.preventDefault();
      if (window.Pages.currentPage === 'homeContent') {
        window.Pages.loadBenchmarks(false);
      }
    }

    // Escape: Go back to home
    if (e.key === 'Escape') {
      if (window.Pages.currentPage !== 'homeContent') {
        window.Pages.navigateTo('homeContent');
      }
    }

    // Ctrl/Cmd + Enter: Run benchmark (if on composer page)
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      if (window.Pages.currentPage === 'composerContent') {
        e.preventDefault();
        window.Pages.runBenchmark();
      }
    }
  }

  /**
   * Handle window resize
   */
  handleResize() {
    // Adjust layout if needed
    const width = window.innerWidth;
    
    // Switch to table view on small screens
    if (width < 768 && window.Pages.currentView === 'grid') {
      window.Pages.toggleView('table');
    }
  }

  /**
   * Clean up event listeners
   */
  cleanup() {
    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler);
    });
    this.eventListeners = [];
    this.initialized = false;
  }

  /**
   * Handle application errors
   * @param {Error} error - Error object
   * @param {string} context - Error context
   */
  handleError(error, context = 'Application') {
    console.error(`${context} error:`, error);
    
    const message = error.message || 'An unexpected error occurred';
    if (window.Components && window.Components.showToast) {
      window.Components.showToast(`${context}: ${message}`, 'error');
    }
    
    // Report error to main process if available
    if (window.API && window.API.isAvailable() && window.API.electronAPI && window.API.electronAPI.reportError) {
      window.API.electronAPI.reportError({
        message: error.message,
        stack: error.stack,
        context,
        timestamp: new Date().toISOString()
      });
    }
  }

  /**
   * Get application status
   * @returns {Object} Status object
   */
  getStatus() {
    return {
      initialized: this.initialized,
      currentPage: window.Pages ? window.Pages.currentPage : 'unknown',
      currentView: window.Pages ? window.Pages.currentView : 'unknown',
      benchmarksCount: window.Pages ? window.Pages.benchmarksData.length : 0,
      promptsCount: window.Pages ? window.Pages.prompts.length : 0,
      apiAvailable: window.API ? window.API.isAvailable() : false
    };
  }

  /**
   * Handle cleanup of stuck benchmarks
   */
  async handleCleanupStuckBenchmarks() {
    try {
      // Show confirmation dialog
      const confirmed = await window.Utils.showConfirmDialog(
        'Reset Stuck Benchmarks',
        'This will reset any benchmarks that appear to be stuck in running state. Continue?',
        'warning'
      );
      
      if (!confirmed) return;
      
      // Show loading state
      const cleanupBtn = document.getElementById('cleanupBtn');
      const originalContent = cleanupBtn.innerHTML;
      cleanupBtn.disabled = true;
      cleanupBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Cleaning...';
      
      // Call the reset stuck benchmarks API
      const result = await window.API.resetStuckBenchmarks();
      
      if (result.success) {
        const message = result.message || `Reset ${result.reset_count || 0} stuck benchmarks`;
        window.Components.showToast(message, 'success');
        
        // Refresh the benchmarks list
        window.Pages.loadBenchmarks(false);
      } else {
        throw new Error(result.error || 'Failed to reset stuck benchmarks');
      }
      
    } catch (error) {
      console.error('Error cleaning up stuck benchmarks:', error);
      window.Components.showToast(`Failed to cleanup: ${error.message}`, 'error');
    } finally {
      // Restore button state
      const cleanupBtn = document.getElementById('cleanupBtn');
      if (cleanupBtn) {
        cleanupBtn.disabled = false;
        cleanupBtn.innerHTML = '<i class="fas fa-broom me-1"></i>Cleanup';
      }
    }
  }
}

// Global error handler
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  if (window.app) {
    window.app.handleError(event.error, 'Global');
  }
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  if (window.app) {
    window.app.handleError(new Error(event.reason), 'Promise');
  }
});

// Initialize app when DOM is ready and main process is ready
document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM loaded, waiting for main process...');
  
  // Reduce delay for module loading check
  setTimeout(() => {
    console.log('Modules should be loaded now. Checking availability...');
    console.log('window.API available:', !!window.API);
    console.log('window.Components available:', !!window.Components);
    console.log('window.Pages available:', !!window.Pages);
    
    // Create app instance
    window.app = new App();
    
    let initializationStarted = false;
    
    const initializeApp = () => {
      if (initializationStarted) {
        console.log('App initialization already started, skipping...');
        return;
      }
      initializationStarted = true;
      console.log('Starting app initialization...');
      
      // Force hide loading overlay in case it's still showing
      if (window.hideLoadingOverlay) {
        console.log('Force hiding loading overlay during app initialization...');
        window.hideLoadingOverlay();
      }
      
      // Real-time updates are already set up in constructor
      
      window.app.init();
    };
    
    // Check if API and Components are available
    if (window.API && window.API.isAvailable()) {
      console.log('API is available, checking for main process ready event...');
      // Check if main process ready event is available
      if (window.API.electronAPI && window.API.electronAPI.onMainProcessReady) {
        console.log('Main process ready event available, setting up listener...');
        // Wait for main process ready signal
        window.API.electronAPI.onMainProcessReady(() => {
          console.log('Main process ready signal received, initializing app...');
          initializeApp();
        });
        
        // Reduced fallback timeout from 3 seconds to 1 second
        setTimeout(() => {
          if (!initializationStarted) {
            console.log('Main process ready signal timeout, initializing anyway...');
            initializeApp();
          }
        }, 1000);
      } else {
        // Fallback: initialize immediately
        console.log('Main process ready event not available, initializing immediately...');
        initializeApp();
      }
    } else {
      console.error('Electron API not available');
      if (window.Components && window.Components.showToast) {
        window.Components.showToast('Application failed to initialize: Electron API not available', 'error', 0);
      } else {
        alert('Application failed to initialize: Electron API not available');
      }
    }
  }, 50); // Reduced from 100ms to 50ms
});

// Export for debugging
window.App = App; 