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
   * Sanitize HTML to prevent XSS while allowing safe markdown tags
   * @param {string} str - String to sanitize
   * @returns {string} Sanitized string
   */
  static sanitizeHtml(str) {
    if (!str) return '';
    
    // If the string contains HTML tags (likely from markdown), use advanced sanitization
    if (str.includes('<') && str.includes('>')) {
      return Utils.sanitizeMarkdownHtml(str);
    }
    
    // For plain text, use simple escaping
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * Escape string for use in HTML attributes
   * @param {string} str - String to escape
   * @returns {string} Escaped string safe for HTML attributes
   */
  static escapeHtmlAttribute(str) {
    if (!str) return '';
    
    return str
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '&#10;')
      .replace(/\r/g, '&#13;');
  }

  /**
   * Sanitize HTML from markdown while allowing safe tags
   * @param {string} html - HTML string to sanitize
   * @returns {string} Sanitized HTML string
   */
  static sanitizeMarkdownHtml(html) {
    // Create a temporary div to parse the HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    // Define allowed tags and attributes
    const allowedTags = [
      'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'code', 'pre', 
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'blockquote', 'hr',
      'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'del', 'ins', 'mark', 'sub', 'sup'
    ];
    
    const allowedAttributes = {
      'a': ['href', 'title'],
      'img': ['src', 'alt', 'title', 'width', 'height'],
      'code': ['class'],
      'pre': ['class']
    };
    
    // Recursively clean the DOM tree
    function cleanNode(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        return node.textContent;
      }
      
      if (node.nodeType === Node.ELEMENT_NODE) {
        const tagName = node.tagName.toLowerCase();
        
        // Remove disallowed tags but keep their content
        if (!allowedTags.includes(tagName)) {
          return Array.from(node.childNodes).map(cleanNode).join('');
        }
        
        // Clean attributes
        const cleanedElement = document.createElement(tagName);
        const allowedAttrs = allowedAttributes[tagName] || [];
        
        for (const attr of node.attributes) {
          if (allowedAttrs.includes(attr.name)) {
            // Additional validation for href and src attributes
            if (attr.name === 'href' || attr.name === 'src') {
              const value = attr.value.trim();
              // Only allow http, https, and relative URLs
              if (value.startsWith('http://') || value.startsWith('https://') || 
                  value.startsWith('/') || value.startsWith('./') || value.startsWith('../') ||
                  !value.includes(':')) {
                cleanedElement.setAttribute(attr.name, value);
              }
            } else {
              cleanedElement.setAttribute(attr.name, attr.value);
            }
          }
        }
        
        // Clean child nodes
        const cleanedContent = Array.from(node.childNodes).map(cleanNode).join('');
        cleanedElement.innerHTML = cleanedContent;
        
        return cleanedElement.outerHTML;
      }
      
      return '';
    }
    
    return Array.from(tempDiv.childNodes).map(cleanNode).join('');
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
    
    // Handle thinking variants - use base model image
    const isThinking = name.endsWith('-thinking');
    const baseName = isThinking ? name.replace('-thinking', '') : name;
    
    // Handle OpenAI models - be very specific about exact matches
    // Order matters: check more specific patterns first
    if (baseName.includes('gpt-4.1-mini')) {
      return 'assets/gpt-4.1-mini.png';
    }
    if (baseName.includes('gpt-4.1')) {
      return 'assets/gpt-4.1.png';
    }
    if (baseName.includes('gpt-4o-mini')) {
      return 'assets/gpt-4o-mini.png';
    }
    if (baseName.includes('gpt-4o')) {
      return 'assets/gpt-4o.png';
    }
    if (baseName.includes('gpt-4-turbo')) {
      return 'assets/gpt-4-turbo.png';
    }
    // Note: We don't have a standalone gpt-4 model in this project
    if (baseName.includes('gpt-3.5')) {
      return 'assets/gpt-3.5.png';
    }
    
    // Handle o-series models (separate from gpt-4o)
    if (baseName === 'o3' || baseName.includes('o3-mini')) {
      return 'assets/o3.png';
    }
    if (baseName === 'o4-mini' || baseName.includes('o4-mini')) {
      return 'assets/o4-mini.png';
    }
    if (baseName.includes('o1')) {
      return 'assets/o1.png';
    }
    
    // Handle Claude models - match exact API names with date suffixes
    if (baseName.includes('claude-opus-4')) {
      return 'assets/claude-opus-4.png';
    }
    if (baseName.includes('claude-sonnet-4')) {
      return 'assets/claude-sonnet-4.png';
    }
    if (baseName.includes('claude-3-7-sonnet')) {
      return 'assets/claude-3.7-sonnet.png';
    }
    if (baseName.includes('claude-3-5-haiku')) {
      return 'assets/claude-3.5-haiku.png';
    }
    if (baseName.includes('claude-3.5') || baseName.includes('claude-3-5')) {
      return 'assets/claude-3.5.png';
    }
    if (baseName.includes('claude-3.7') || baseName.includes('claude-3-7')) {
      return 'assets/claude-3.7-sonnet.png';
    }
    if (baseName.includes('claude-3')) {
      return 'assets/claude-3.png';
    }
    if (baseName.includes('claude')) {
      return 'assets/claude.png';
    }
    
    // Handle Gemini models - match exact API names with preview suffixes
    if (baseName.includes('gemini-2.5-flash')) {
      return 'assets/gemini-2.5-flash.png';
    }
    if (baseName.includes('gemini-2.5-pro')) {
      return 'assets/gemini-2.5-pro.png';
    }
    if (baseName.includes('gemini-2.5')) {
      return 'assets/gemini-2.5.png';
    }
    if (baseName.includes('gemini-1.5')) {
      return 'assets/gemini-1.5.png';
    }
    if (baseName.includes('gemini')) {
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
    
    // Handle thinking variants - use base model for provider detection
    const isThinking = name.endsWith('-thinking');
    const baseName = isThinking ? name.replace('-thinking', '') : name;
    
    if (baseName.includes('gpt') || baseName.includes('o1') || baseName.includes('o3') || baseName.includes('o4')) {
      return 'openai';
    }
    if (baseName.includes('claude')) {
      return 'anthropic';
    }
    if (baseName.includes('gemini')) {
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
    
    // Handle thinking variants first
    const isThinking = name.endsWith('-thinking');
    const baseName = isThinking ? name.replace('-thinking', '') : name;
    
    // Handle OpenAI models with proper naming - order matters!
    // Check more specific patterns first
    if (baseName.includes('gpt-4.1-mini')) {
      return isThinking ? 'GPT-4.1 Mini (+ Thinking)' : 'GPT-4.1 Mini';
    }
    if (baseName.includes('gpt-4.1')) {
      return isThinking ? 'GPT-4.1 (+ Thinking)' : 'GPT-4.1';
    }
    if (baseName.includes('gpt-4o-mini')) {
      return isThinking ? 'GPT-4o Mini (+ Thinking)' : 'GPT-4o Mini'; // Four-oh Mini
    }
    if (baseName.includes('gpt-4o')) {
      return isThinking ? 'GPT-4o (+ Thinking)' : 'GPT-4o'; // Four-oh
    }
    if (baseName.includes('gpt-4-turbo')) {
      return isThinking ? 'GPT-4 Turbo (+ Thinking)' : 'GPT-4 Turbo';
    }
    // Note: We don't have a standalone gpt-4 model in this project
    if (baseName.includes('gpt-3.5')) {
      return isThinking ? 'GPT-3.5 (+ Thinking)' : 'GPT-3.5';
    }
    
    // Handle o-series models (different from gpt-4o)
    if (baseName === 'o3' || baseName === 'o3-mini') {
      return isThinking ? `${baseName.toUpperCase()} (+ Thinking)` : baseName.toUpperCase(); // O3, O3-MINI
    }
    if (baseName === 'o4-mini') {
      return isThinking ? 'O4 Mini (+ Thinking)' : 'O4 Mini';
    }
    if (baseName === 'o1' || baseName === 'o1-mini' || baseName === 'o1-preview') {
      const formatted = baseName.toUpperCase().replace('-', ' '); // O1, O1 MINI, O1 PREVIEW
      return isThinking ? `${formatted} (+ Thinking)` : formatted;
    }
    
    // Handle Claude models
    if (baseName.includes('claude-3.5-sonnet') || baseName.includes('claude-3-5-sonnet')) {
      return isThinking ? 'Claude 3.5 Sonnet (+ Thinking)' : 'Claude 3.5 Sonnet';
    }
    if (baseName.includes('claude-3.5-haiku') || baseName.includes('claude-3-5-haiku')) {
      return isThinking ? 'Claude 3.5 Haiku (+ Thinking)' : 'Claude 3.5 Haiku';
    }
    if (baseName.includes('claude-3.7-sonnet') || baseName.includes('claude-3-7-sonnet')) {
      return isThinking ? 'Claude 3.7 Sonnet (+ Thinking)' : 'Claude 3.7 Sonnet';
    }
    if (baseName.includes('claude-sonnet-4')) {
      return isThinking ? 'Claude Sonnet 4 (+ Thinking)' : 'Claude Sonnet 4';
    }
    if (baseName.includes('claude-opus-4')) {
      return isThinking ? 'Claude Opus 4 (+ Thinking)' : 'Claude Opus 4';
    }
    if (baseName.includes('claude-3-sonnet')) {
      return isThinking ? 'Claude 3 Sonnet (+ Thinking)' : 'Claude 3 Sonnet';
    }
    if (baseName.includes('claude-3-haiku')) {
      return isThinking ? 'Claude 3 Haiku (+ Thinking)' : 'Claude 3 Haiku';
    }
    if (baseName.includes('claude-3-opus')) {
      return isThinking ? 'Claude 3 Opus (+ Thinking)' : 'Claude 3 Opus';
    }
    
    // Handle Gemini models
    if (baseName.includes('gemini-2.5-flash')) {
      return isThinking ? 'Gemini 2.5 Flash (+ Thinking)' : 'Gemini 2.5 Flash';
    }
    if (baseName.includes('gemini-2.5-pro')) {
      return isThinking ? 'Gemini 2.5 Pro (+ Thinking)' : 'Gemini 2.5 Pro';
    }
    if (baseName.includes('gemini-1.5-pro')) {
      return isThinking ? 'Gemini 1.5 Pro (+ Thinking)' : 'Gemini 1.5 Pro';
    }
    if (baseName.includes('gemini-1.5-flash')) {
      return isThinking ? 'Gemini 1.5 Flash (+ Thinking)' : 'Gemini 1.5 Flash';
    }
    if (baseName.includes('gemini-pro')) {
      return isThinking ? 'Gemini Pro (+ Thinking)' : 'Gemini Pro';
    }
    if (baseName.includes('gemini-flash')) {
      return isThinking ? 'Gemini Flash (+ Thinking)' : 'Gemini Flash';
    }
    
    // Fallback: capitalize first letter of each word
    return modelId.split(/[-_]/).map(word => 
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    ).join(' ');
  }
}

// Export for use in other modules
window.Utils = Utils; 