/**
 * Settings module for handling API keys and configuration
 */

class Settings {
  constructor() {
    this.settings = null;
    this.setupEventListeners();
  }

  /**
   * Initialize settings functionality
   */
  async init() {
    try {
      // Check if this is first-time setup
      const apiKeyStatus = await window.electronAPI.checkApiKeys();
      
      if (apiKeyStatus.success && apiKeyStatus.isFirstTime) {
        this.showFirstTimeSetup();
      }
      
      // Load current settings
      await this.loadSettings();
    } catch (error) {
      console.error('Error initializing settings:', error);
    }
  }

  /**
   * Load settings from main process
   */
  async loadSettings() {
    try {
      const result = await window.electronAPI.getSettings();
      if (result.success) {
        this.settings = result.settings;
        this.populateSettingsForm();
      }
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  }

  /**
   * Setup event listeners for settings UI
   */
  setupEventListeners() {
    // Settings button in header
    document.addEventListener('click', (e) => {
      if (e.target.closest('#settingsBtn')) {
        this.showSettingsPage();
      }
    });

    // Settings page buttons
    document.addEventListener('click', (e) => {
      if (e.target.closest('#saveSettingsBtn')) {
        this.saveSettings();
      } else if (e.target.closest('#cancelSettingsBtn')) {
        this.hideSettingsPage();
      }
    });

    // Password visibility toggles
    this.setupPasswordToggles();

    // First-time setup modal buttons
    document.addEventListener('click', (e) => {
      if (e.target.closest('#completeSetupBtn')) {
        this.completeFirstTimeSetup();
      } else if (e.target.closest('#skipSetupBtn')) {
        this.skipFirstTimeSetup();
      }
    });
  }

  /**
   * Setup password visibility toggles
   */
  setupPasswordToggles() {
    const toggles = [
      { button: '#toggleOpenaiKey', input: '#openaiApiKey' },
      { button: '#toggleAnthropicKey', input: '#anthropicApiKey' },
      { button: '#toggleGoogleKey', input: '#googleApiKey' },
      { button: '#toggleSetupOpenaiKey', input: '#setupOpenaiKey' },
      { button: '#toggleSetupAnthropicKey', input: '#setupAnthropicKey' },
      { button: '#toggleSetupGoogleKey', input: '#setupGoogleKey' }
    ];

    toggles.forEach(({ button, input }) => {
      document.addEventListener('click', (e) => {
        if (e.target.closest(button)) {
          const inputField = document.querySelector(input);
          const buttonElement = document.querySelector(button);
          const icon = buttonElement.querySelector('i');
          
          if (inputField.type === 'password') {
            inputField.type = 'text';
            icon.className = 'fas fa-eye-slash';
          } else {
            inputField.type = 'password';
            icon.className = 'fas fa-eye';
          }
        }
      });
    });
  }

  /**
   * Show first-time setup modal
   */
  showFirstTimeSetup() {
    const modal = new bootstrap.Modal(document.getElementById('firstTimeSetupModal'));
    modal.show();
  }

  /**
   * Hide first-time setup modal
   */
  hideFirstTimeSetup() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('firstTimeSetupModal'));
    if (modal) {
      modal.hide();
    }
  }

  /**
   * Complete first-time setup
   */
  async completeFirstTimeSetup() {
    const apiKeys = {
      openai: document.getElementById('setupOpenaiKey').value.trim(),
      anthropic: document.getElementById('setupAnthropicKey').value.trim(),
      google: document.getElementById('setupGoogleKey').value.trim()
    };

    // Check if at least one key is provided
    const hasAnyKey = Object.values(apiKeys).some(key => key !== '');
    
    if (!hasAnyKey) {
      window.Components.showToast('Please provide at least one API key to continue.', 'warning');
      return;
    }

    const completeButton = document.getElementById('completeSetupBtn');
    const originalText = completeButton.textContent;
    
    try {
      // Show loading state
      completeButton.disabled = true;
      completeButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving and starting backend...';
      
      window.Components.showToast('Saving API keys and restarting backend...', 'info');
      
      const result = await window.electronAPI.updateApiKeys(apiKeys);
      
      if (result.success) {
        this.hideFirstTimeSetup();
        window.Components.showToast('API keys saved and backend restarted successfully!', 'success');
        
        // Clear the form
        document.getElementById('setupOpenaiKey').value = '';
        document.getElementById('setupAnthropicKey').value = '';
        document.getElementById('setupGoogleKey').value = '';
        
        // Reload settings
        await this.loadSettings();
      } else {
        window.Components.showToast(`Error saving API keys: ${result.error}`, 'error');
      }
    } catch (error) {
      console.error('Error completing setup:', error);
      window.Components.showToast('Failed to save API keys. Please try again.', 'error');
    } finally {
      // Restore button state
      completeButton.disabled = false;
      completeButton.textContent = originalText;
    }
  }

  /**
   * Skip first-time setup
   */
  async skipFirstTimeSetup() {
    try {
      // Mark first-time setup as complete without saving keys
      const result = await window.electronAPI.updateApiKeys({});
      
      if (result.success) {
        this.hideFirstTimeSetup();
        window.Components.showToast('You can configure API keys later in Settings.', 'info');
      }
    } catch (error) {
      console.error('Error skipping setup:', error);
      this.hideFirstTimeSetup();
    }
  }

  /**
   * Show settings page
   */
  showSettingsPage() {
    // Use the unified navigation system
    if (window.Pages) {
      window.Pages.navigateTo('settingsContent');
    } else {
      // Fallback for direct navigation
      document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
      });
      document.getElementById('settingsContent').classList.add('active');
    }
    
    // Load current settings
    this.loadSettings();
  }

  /**
   * Hide settings page and return to home
   */
  hideSettingsPage() {
    // Use the unified navigation system to go back to home
    if (window.Pages) {
      window.Pages.navigateTo('homeContent');
    } else {
      // Fallback for direct navigation
      document.getElementById('settingsContent').classList.remove('active');
      document.getElementById('homeContent').classList.add('active');
    }
  }

  /**
   * Populate settings form with current values
   */
  populateSettingsForm() {
    if (this.settings && this.settings.apiKeys) {
      document.getElementById('openaiApiKey').value = this.settings.apiKeys.openai || '';
      document.getElementById('anthropicApiKey').value = this.settings.apiKeys.anthropic || '';
      document.getElementById('googleApiKey').value = this.settings.apiKeys.google || '';
    }
  }

  /**
   * Save settings
   */
  async saveSettings() {
    const apiKeys = {
      openai: document.getElementById('openaiApiKey').value.trim(),
      anthropic: document.getElementById('anthropicApiKey').value.trim(),
      google: document.getElementById('googleApiKey').value.trim()
    };

    const saveButton = document.getElementById('saveSettingsBtn');
    const originalText = saveButton.textContent;

    try {
      // Show loading state
      saveButton.disabled = true;
      saveButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving and restarting backend...';
      
      window.Components.showToast('Saving API keys and restarting backend...', 'info');
      
      const result = await window.electronAPI.updateApiKeys(apiKeys);
      
      if (result.success) {
        window.Components.showToast('Settings saved and backend restarted successfully!', 'success');
        await this.loadSettings();
        this.hideSettingsPage();
      } else {
        window.Components.showToast(`Error saving settings: ${result.error}`, 'error');
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      window.Components.showToast('Failed to save settings. Please try again.', 'error');
    } finally {
      // Restore button state
      saveButton.disabled = false;
      saveButton.textContent = originalText;
    }
  }

  /**
   * Check if API keys are configured
   */
  async checkApiKeys() {
    try {
      const result = await window.electronAPI.checkApiKeys();
      return result.success ? result.hasApiKeys : false;
    } catch (error) {
      console.error('Error checking API keys:', error);
      return false;
    }
  }

  /**
   * Show warning if no API keys are configured
   */
  async showApiKeyWarningIfNeeded() {
    const hasKeys = await this.checkApiKeys();
    
    if (!hasKeys) {
      window.Components.showToast(
        'No API keys configured. Some features may not work. Go to Settings to configure them.',
        'warning',
        10000
      );
    }
  }
}

// Create global instance
window.Settings = new Settings(); 