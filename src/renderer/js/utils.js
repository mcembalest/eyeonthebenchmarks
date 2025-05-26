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
   * Get model image path based on model name
   * @param {string} modelName - Model name
   * @returns {string} Image path or null if not found
   */
  static getModelImage(modelName) {
    if (!modelName) return null;
    
    // Clean the model name by removing date strings and normalizing
    const cleanName = modelName.toLowerCase()
      .replace(/-\d{4}-\d{2}-\d{2}.*$/, '') // Remove date strings like -2024-12-17
      .replace(/-\d{8}.*$/, '') // Remove date strings like -20241217
      .replace(/-preview.*$/, '') // Remove preview suffixes
      .replace(/\s+/g, '-') // Replace spaces with hyphens
      .trim();
    
    // List of available model images (based on the assets folder)
    const availableModels = [
      'claude-opus-4',
      'claude-sonnet-4', 
      'claude-3.7-sonnet',
      'claude-3.5-haiku',
      'gemini-2.5-flash',
      'gemini-2.5-pro',
      'gpt-4o-mini',
      'gpt-4.1-nano',
      'gpt-4.1-mini',
      'gpt-4o',
      'gpt-4.1',
      'o4-mini',
      'o3'
    ];
    
    // Check if we have an exact match
    if (availableModels.includes(cleanName)) {
      return `assets/${cleanName}.png`;
    }
    
    // Special handling for Claude models with dots converted to hyphens
    if (cleanName.includes('claude-3.5') || cleanName.includes('claude-3-5')) {
      if (cleanName.includes('haiku')) {
        return 'assets/claude-3.5-haiku.png';
      }
    }
    
    if (cleanName.includes('claude-3.7') || cleanName.includes('claude-3-7')) {
      if (cleanName.includes('sonnet')) {
        return 'assets/claude-3.7-sonnet.png';
      }
    }
    
    // Try partial matches for common model families
    for (const available of availableModels) {
      if (cleanName.includes(available) || available.includes(cleanName)) {
        return `assets/${available}.png`;
      }
    }
    
    return null;
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
   * Create an image element for a model
   * @param {string} modelName - Model name
   * @param {string} className - CSS classes to apply
   * @returns {string} HTML img element or fallback
   */
  static createModelImage(modelName, className = 'model-image') {
    const imagePath = Utils.getModelImage(modelName);
    const formattedName = Utils.formatModelName(modelName);
    
    if (imagePath) {
      return `<img src="${imagePath}" alt="${formattedName}" class="${className}" style="width: 24px; height: 24px; object-fit: contain;">`;
    }
    // Fallback to icon
    return `<i class="fas fa-microchip"></i>`;
  }

  /**
   * Format model name for display with proper capitalization and formatting
   * @param {string} modelName - Raw model name from API
   * @returns {string} Formatted model name for display
   */
  static formatModelName(modelName) {
    if (!modelName) return 'Unknown Model';
    
    let formatted = modelName;
    
    // Replace hyphens with dots for version numbers in Claude models
    formatted = formatted.replace(/claude-3-5/gi, 'Claude 3.5');
    formatted = formatted.replace(/claude-3-7/gi, 'Claude 3.7');
    
    // Handle other Claude models
    formatted = formatted.replace(/claude-(\w+)-(\d+)/gi, 'Claude $1 $2');
    formatted = formatted.replace(/claude-(\w+)/gi, 'Claude $1');
    
    // Handle GPT models
    formatted = formatted.replace(/gpt-(\d+\.?\d*)-?(\w*)/gi, (match, version, variant) => {
      let result = `GPT-${version}`;
      if (variant) {
        result += ` ${variant.charAt(0).toUpperCase() + variant.slice(1)}`;
      }
      return result;
    });
    
    // Handle O models (OpenAI's O series)
    formatted = formatted.replace(/^o(\d+)-?(\w*)/gi, (match, version, variant) => {
      let result = `O${version}`;
      if (variant) {
        result += ` ${variant.charAt(0).toUpperCase() + variant.slice(1)}`;
      }
      return result;
    });
    
    // Handle Gemini models
    formatted = formatted.replace(/gemini-(\d+\.?\d*)-?(\w*)/gi, (match, version, variant) => {
      let result = `Gemini ${version}`;
      if (variant) {
        result += ` ${variant.charAt(0).toUpperCase() + variant.slice(1)}`;
      }
      return result;
    });
    
    // Remove date strings and preview suffixes
    formatted = formatted.replace(/-\d{4}-\d{2}-\d{2}.*$/gi, '');
    formatted = formatted.replace(/-\d{8}.*$/gi, '');
    formatted = formatted.replace(/-preview.*$/gi, '');
    
    // Capitalize first letter if not already handled
    if (!formatted.match(/^(GPT|Claude|Gemini|O\d)/)) {
      formatted = formatted.charAt(0).toUpperCase() + formatted.slice(1);
    }
    
    return formatted.trim();
  }
}

// Export for use in other modules
window.Utils = Utils; 