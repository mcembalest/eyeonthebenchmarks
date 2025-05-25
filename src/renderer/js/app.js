/**
 * Main application initialization and event handling
 */

class App {
  constructor() {
    this.initialized = false;
    this.eventListeners = [];
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

      // Set up event listeners
      this.setupEventListeners();

      // Set up real-time updates
      this.setupRealTimeUpdates();

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
      
      // Composer page elements
      { selector: '#importCsvBtn', event: 'click', handler: () => this.handleCsvImport() },
      { selector: '#addPromptBtn', event: 'click', handler: () => window.Pages.addPrompt() },
      { selector: '#selectPdfBtn', event: 'click', handler: () => this.handlePdfSelection() }
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
          }
        }
      });
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
        window.Pages.selectedPdfPath = pdfPath;
        const fileName = pdfPath.split('/').pop() || pdfPath.split('\\').pop();
        
        const label = document.getElementById('selectedPdfLabel');
        if (label) {
          label.textContent = fileName;
          label.className = 'ms-3 text-success';
        }

        window.Components.showToast(`Selected file: ${fileName}`, 'success');
      }

    } catch (error) {
      console.error('Error selecting PDF:', error);
      window.Components.showToast(`Failed to select PDF: ${error.message}`, 'error');
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