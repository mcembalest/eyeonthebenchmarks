class Utils {
  /**
   * Format a date string to a readable format
   * @param {string} dateString - ISO date string
   * @returns {string} Formatted date
   */
  static formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (error) {
      console.error('Error formatting date:', error);
      return dateString;
    }
  }

  /**
   * Format a number as currency
   * @param {number} amount - Amount to format
   * @param {number} decimals - Number of decimal places
   * @returns {string} Formatted currency
   */
  static formatCurrency(amount, decimals = 6) {
    if (typeof amount !== 'number') return '$0.00';
    return `$${amount.toFixed(decimals)}`;
  }

  /**
   * Format a number with commas
   * @param {number} num - Number to format
   * @returns {string} Formatted number
   */
  static formatNumber(num) {
    if (typeof num !== 'number') return '0';
    return num.toLocaleString();
  }

  /**
   * Truncate text to a specified length
   * @param {string} text - Text to truncate
   * @param {number} maxLength - Maximum length
   * @returns {string} Truncated text
   */
  static truncateText(text, maxLength = 100) {
    if (!text || text.length <= maxLength) return text || '';
    return text.substring(0, maxLength) + '...';
  }

  /**
   * Debounce function calls
   * @param {Function} func - Function to debounce
   * @param {number} wait - Wait time in milliseconds
   * @returns {Function} Debounced function
   */
  static debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * Generate a unique ID
   * @returns {string} Unique ID
   */
  static generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  }

  /**
   * Sanitize HTML to prevent XSS
   * @param {string} str - String to sanitize
   * @returns {string} Sanitized string
   */
  static sanitizeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * Get provider color class based on provider name
   * @param {string} provider - Provider name
   * @returns {string} Bootstrap color class
   */
  static getProviderColor(provider) {
    const colors = {
      'openai': 'success',
      'anthropic': 'warning',
      'google': 'info',
      'unknown': 'secondary'
    };
    return colors[provider?.toLowerCase()] || 'secondary';
  }

  /**
   * Get status color class based on status
   * @param {string} status - Status string
   * @returns {string} Bootstrap color class
   */
  static getStatusColor(status) {
    const colors = {
      'complete': 'success',
      'in-progress': 'primary',
      'running': 'primary',
      'failed': 'danger',
      'error': 'danger'
    };
    return colors[status?.toLowerCase()] || 'secondary';
  }

  /**
   * Validate email format
   * @param {string} email - Email to validate
   * @returns {boolean} Is valid email
   */
  static isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Deep clone an object
   * @param {any} obj - Object to clone
   * @returns {any} Cloned object
   */
  static deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof Array) return obj.map(item => Utils.deepClone(item));
    if (typeof obj === 'object') {
      const clonedObj = {};
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          clonedObj[key] = Utils.deepClone(obj[key]);
        }
      }
      return clonedObj;
    }
  }

  /**
   * Check if an object is empty
   * @param {object} obj - Object to check
   * @returns {boolean} Is empty
   */
  static isEmpty(obj) {
    if (!obj) return true;
    if (Array.isArray(obj)) return obj.length === 0;
    if (typeof obj === 'object') return Object.keys(obj).length === 0;
    return false;
  }

  /**
   * Sleep for a specified time
   * @param {number} ms - Milliseconds to sleep
   * @returns {Promise} Promise that resolves after the specified time
   */
  static sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Retry a function with exponential backoff
   * @param {Function} fn - Function to retry
   * @param {number} maxRetries - Maximum number of retries
   * @param {number} baseDelay - Base delay in milliseconds
   * @returns {Promise} Promise that resolves with the function result
   */
  static async retry(fn, maxRetries = 3, baseDelay = 1000) {
    let lastError;
    
    for (let i = 0; i <= maxRetries; i++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        if (i === maxRetries) break;
        
        const delay = baseDelay * Math.pow(2, i);
        await Utils.sleep(delay);
      }
    }
    
    throw lastError;
  }

  /**
   * Get provider image path based on provider name
   * @param {string} provider - Provider name
   * @returns {string} Image path
   */
  static getProviderImage(provider) {
    const images = {
      'openai': 'assets/openai.png',
      'anthropic': 'assets/anthropic.png',
      'google': 'assets/google.png'
    };
    return images[provider?.toLowerCase()] || null;
  }

  /**
   * Get model image filename
   * @param {string} modelName - Model name (formatted or raw)
   * @returns {string} Image path
   */
  static getModelImage(modelName) {
    if (!modelName) return 'assets/default-model.png';
    
    const name = modelName.toLowerCase();
    
    // Handle OpenAI models - be very specific about exact matches
    // Order matters: check more specific patterns first
    if (name.includes('gpt-4.1-mini')) {
      return 'assets/gpt-4.1-mini.png';
    }
    if (name.includes('gpt-4.1')) {
      return 'assets/gpt-4.1.png';
    }
    if (name.includes('gpt-4o-mini')) {
      return 'assets/gpt-4o-mini.png';
    }
    if (name.includes('gpt-4o')) {
      return 'assets/gpt-4o.png';
    }
    if (name.includes('gpt-4-turbo')) {
      return 'assets/gpt-4-turbo.png';
    }
    // Note: We don't have a standalone gpt-4 model in this project
    if (name.includes('gpt-3.5')) {
      return 'assets/gpt-3.5.png';
    }
    
    // Handle o-series models (separate from gpt-4o)
    if (name === 'o3' || name.includes('o3-mini')) {
      return 'assets/o3.png';
    }
    if (name === 'o4-mini' || name.includes('o4-mini')) {
      return 'assets/o4-mini.png';
    }
    if (name.includes('o1')) {
      return 'assets/o1.png';
    }
    
    // Handle Claude models - match exact API names with date suffixes
    if (name.includes('claude-opus-4')) {
      return 'assets/claude-opus-4.png';
    }
    if (name.includes('claude-sonnet-4')) {
      return 'assets/claude-sonnet-4.png';
    }
    if (name.includes('claude-3-7-sonnet')) {
      return 'assets/claude-3.7-sonnet.png';
    }
    if (name.includes('claude-3-5-haiku')) {
      return 'assets/claude-3.5-haiku.png';
    }
    if (name.includes('claude-3.5') || name.includes('claude-3-5')) {
      return 'assets/claude-3.5.png';
    }
    if (name.includes('claude-3.7') || name.includes('claude-3-7')) {
      return 'assets/claude-3.7-sonnet.png';
    }
    if (name.includes('claude-3')) {
      return 'assets/claude-3.png';
    }
    if (name.includes('claude')) {
      return 'assets/claude.png';
    }
    
    // Handle Gemini models - match exact API names with preview suffixes
    if (name.includes('gemini-2.5-flash')) {
      return 'assets/gemini-2.5-flash.png';
    }
    if (name.includes('gemini-2.5-pro')) {
      return 'assets/gemini-2.5-pro.png';
    }
    if (name.includes('gemini-2.5')) {
      return 'assets/gemini-2.5.png';
    }
    if (name.includes('gemini-1.5')) {
      return 'assets/gemini-1.5.png';
    }
    if (name.includes('gemini')) {
      return 'assets/gemini.png';
    }
    
    return 'assets/default-model.png';
  }

  /**
   * Get provider from model name
   * @param {string} modelName - Model name
   * @returns {string} Provider name
   */
  static getProviderFromModel(modelName) {
    if (!modelName) return 'unknown';
    
    const name = modelName.toLowerCase();
    
    if (name.includes('gpt') || name.includes('o1') || name.includes('o3') || name.includes('o4')) {
      return 'openai';
    }
    if (name.includes('claude')) {
      return 'anthropic';
    }
    if (name.includes('gemini')) {
      return 'google';
    }
    
    return 'unknown';
  }

  /**
   * Create an image element for a model
   * @param {string} modelName - Model name
   * @param {string} className - CSS classes to apply
   * @param {boolean} useModelSpecificIcon - Whether to use model-specific icons (true) or company logos (false)
   * @returns {string} HTML img element or fallback
   */
  static createModelImage(modelName, className = 'model-image', useModelSpecificIcon = false) {
    const formattedName = Utils.formatModelName(modelName);
    
    if (useModelSpecificIcon) {
      // Use model-specific icons (for detailed results)
      const imagePath = Utils.getModelImage(modelName);
      if (imagePath && imagePath !== 'assets/default-model.png') {
        return `<img src="${imagePath}" alt="${formattedName}" class="${className}" style="width: 24px; height: 24px; object-fit: contain;" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline';">
                <i class="fas fa-microchip" style="display: none;"></i>`;
      }
      // Fallback to icon
      return `<i class="fas fa-microchip"></i>`;
    } else {
      // Use company logos (for home page, grids, tables, etc.)
      const provider = Utils.getProviderFromModel(modelName);
      const providerImage = Utils.getProviderImage(provider);
      
      if (providerImage) {
        return `<img src="${providerImage}" alt="${provider}" class="${className}" style="width: 20px; height: 20px; object-fit: contain;" title="${formattedName}">`;
      }
      
      // Fallback to colored badge
      const color = Utils.getProviderColor(provider);
      return `<span class="badge bg-${color}" title="${formattedName}">${provider?.toUpperCase() || 'UNKNOWN'}</span>`;
    }
  }

  /**
   * Create an image element for a provider
   * @param {string} provider - Provider name
   * @param {string} className - CSS classes to apply
   * @returns {string} HTML img element or fallback
   */
  static createProviderImage(provider, className = 'provider-image') {
    const imagePath = Utils.getProviderImage(provider);
    if (imagePath) {
      return `<img src="${imagePath}" alt="${provider}" class="${className}" style="width: 20px; height: 20px; object-fit: contain;">`;
    }
    // Fallback to colored badge
    const color = Utils.getProviderColor(provider);
    return `<span class="badge bg-${color}">${provider?.toUpperCase() || 'UNKNOWN'}</span>`;
  }

  /**
   * Format model name for display
   * @param {string} modelId - Raw model ID
   * @returns {string} Formatted model name
   */
  static formatModelName(modelId) {
    if (!modelId) return 'Unknown Model';
    
    const name = modelId.toLowerCase();
    
    // Handle OpenAI models with proper naming - order matters!
    // Check more specific patterns first
    if (name.includes('gpt-4.1-mini')) {
      return 'GPT-4.1 Mini';
    }
    if (name.includes('gpt-4.1')) {
      return 'GPT-4.1';
    }
    if (name.includes('gpt-4o-mini')) {
      return 'GPT-4o Mini'; // Four-oh Mini
    }
    if (name.includes('gpt-4o')) {
      return 'GPT-4o'; // Four-oh
    }
    if (name.includes('gpt-4-turbo')) {
      return 'GPT-4 Turbo';
    }
    // Note: We don't have a standalone gpt-4 model in this project
    if (name.includes('gpt-3.5')) {
      return 'GPT-3.5';
    }
    
    // Handle o-series models (different from gpt-4o)
    if (name === 'o3' || name === 'o3-mini') {
      return name.toUpperCase(); // O3, O3-MINI
    }
    if (name === 'o4-mini') {
      return 'O4 Mini';
    }
    if (name === 'o1' || name === 'o1-mini' || name === 'o1-preview') {
      return name.toUpperCase().replace('-', ' '); // O1, O1 MINI, O1 PREVIEW
    }
    
    // Handle Claude models
    if (name.includes('claude-3.5-sonnet') || name.includes('claude-3-5-sonnet')) {
      return 'Claude 3.5 Sonnet';
    }
    if (name.includes('claude-3.5-haiku') || name.includes('claude-3-5-haiku')) {
      return 'Claude 3.5 Haiku';
    }
    if (name.includes('claude-3.7-sonnet') || name.includes('claude-3-7-sonnet')) {
      return 'Claude 3.7 Sonnet';
    }
    if (name.includes('claude-sonnet-4')) {
      return 'Claude Sonnet 4';
    }
    if (name.includes('claude-opus-4')) {
      return 'Claude Opus 4';
    }
    if (name.includes('claude-3-sonnet')) {
      return 'Claude 3 Sonnet';
    }
    if (name.includes('claude-3-haiku')) {
      return 'Claude 3 Haiku';
    }
    if (name.includes('claude-3-opus')) {
      return 'Claude 3 Opus';
    }
    
    // Handle Gemini models
    if (name.includes('gemini-2.5-flash')) {
      return 'Gemini 2.5 Flash';
    }
    if (name.includes('gemini-2.5-pro')) {
      return 'Gemini 2.5 Pro';
    }
    if (name.includes('gemini-1.5-pro')) {
      return 'Gemini 1.5 Pro';
    }
    if (name.includes('gemini-1.5-flash')) {
      return 'Gemini 1.5 Flash';
    }
    if (name.includes('gemini-pro')) {
      return 'Gemini Pro';
    }
    if (name.includes('gemini-flash')) {
      return 'Gemini Flash';
    }
    
    // Fallback: capitalize first letter of each word
    return modelId.split(/[-_]/).map(word => 
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    ).join(' ');
  }
}

// Export for use in other modules
window.Utils = Utils; 