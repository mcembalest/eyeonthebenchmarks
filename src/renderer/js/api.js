/**
 * API module for communicating with the main process
 */

class API {
  constructor() {
    this.electronAPI = window.electronAPI;
    this.cache = new Map();
    this.cacheTimeout = 30000; // 30 seconds
  }

  /**
   * Check if electronAPI is available
   * @returns {boolean} Is available
   */
  isAvailable() {
    return !!this.electronAPI;
  }

  /**
   * Get cached data if available and not expired
   * @param {string} key - Cache key
   * @returns {any|null} Cached data or null
   */
  getCached(key) {
    const cached = this.cache.get(key);
    if (!cached) return null;
    
    if (Date.now() - cached.timestamp > this.cacheTimeout) {
      this.cache.delete(key);
      return null;
    }
    
    return cached.data;
  }

  /**
   * Set cached data
   * @param {string} key - Cache key
   * @param {any} data - Data to cache
   */
  setCached(key, data) {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  /**
   * Clear cache
   * @param {string} key - Optional specific key to clear
   */
  clearCache(key = null) {
    if (key) {
      this.cache.delete(key);
    } else {
      this.cache.clear();
    }
  }

  /**
   * Get list of all benchmarks
   * @param {boolean} useCache - Whether to use cached data
   * @returns {Promise<Array>} List of benchmarks
   */
  async getBenchmarks(useCache = true) {
    console.log('API.getBenchmarks called with useCache:', useCache);
    const cacheKey = 'benchmarks';
    
    if (useCache) {
      const cached = this.getCached(cacheKey);
      if (cached) {
        console.log('Returning cached benchmarks:', cached);
        return cached;
      }
    }

    try {
      console.log('Calling electronAPI.listBenchmarks...');
      const benchmarks = await this.electronAPI.listBenchmarks();
      console.log('electronAPI.listBenchmarks returned:', benchmarks);
      this.setCached(cacheKey, benchmarks);
      return benchmarks || [];
    } catch (error) {
      console.error('Error fetching benchmarks:', error);
      throw new Error(`Failed to load benchmarks: ${error.message}`);
    }
  }

  /**
   * Get benchmark details by ID
   * @param {number} id - Benchmark ID
   * @returns {Promise<Object>} Benchmark details
   */
  async getBenchmarkDetails(id) {
    if (!id) throw new Error('Benchmark ID is required');

    try {
      const details = await this.electronAPI.getBenchmarkDetails(id);
      if (!details) throw new Error('Benchmark not found');
      return details;
    } catch (error) {
      console.error('Error fetching benchmark details:', error);
      throw new Error(`Failed to load benchmark details: ${error.message}`);
    }
  }

  /**
   * Run a new benchmark
   * @param {Object} config - Benchmark configuration
   * @returns {Promise<Object>} Benchmark run result
   */
  async runBenchmark(config) {
    const { prompts, pdfPaths, modelNames, benchmarkName, benchmarkDescription, webSearchEnabled, webSearchPrompts } = config;

    // Validate required fields
    if (!benchmarkName?.trim()) {
      throw new Error('Benchmark name is required');
    }
    if (!prompts || prompts.length === 0) {
      throw new Error('At least one prompt is required');
    }
    if (!modelNames || modelNames.length === 0) {
      throw new Error('At least one model must be selected');
    }

    // Process web search prompts if specified
    let processedPrompts = prompts;
    if (webSearchEnabled && Array.isArray(webSearchPrompts)) {
      // Mark individual prompts for web search based on webSearchPrompts array
      processedPrompts = prompts.map((prompt, index) => ({
        ...prompt,
        web_search: webSearchPrompts.includes(index)
      }));
    } else if (webSearchEnabled) {
      // If webSearchEnabled is true but no specific prompts are provided, enable for all
      processedPrompts = prompts.map(prompt => ({
        ...prompt,
        web_search: true
      }));
    }

    try {
      const result = await this.electronAPI.runBenchmark(
        processedPrompts,
        pdfPaths || [],
        modelNames,
        benchmarkName.trim(),
        benchmarkDescription?.trim() || '',
        !!webSearchEnabled
      );

      // Clear benchmarks cache since we have a new one
      this.clearCache('benchmarks');
      
      return result;
    } catch (error) {
      console.error('Error running benchmark:', error);
      throw new Error(`Failed to start benchmark: ${error.message}`);
    }
  }

  /**
   * Delete a benchmark
   * @param {number} benchmarkId - Benchmark ID
   * @returns {Promise<Object>} API response
   */
  async deleteBenchmark(benchmarkId) {
    try {
      const result = await this.makeRequest('/delete', {
        method: 'POST',
        body: JSON.stringify({ benchmark_id: benchmarkId })
      });
      
      // Clear benchmarks cache since we deleted one
      this.clearCache('benchmarks');
      
      return result;
    } catch (error) {
      console.error('Error deleting benchmark:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Rerun a single prompt from an existing benchmark
   * @param {number} promptId - Prompt ID
   * @returns {Promise<Object>} API response
   */
  async rerunSinglePrompt(promptId) {
    try {
      const result = await this.electronAPI.rerunSinglePrompt(promptId);
      
      // Clear benchmarks cache since we updated prompt results
      this.clearCache('benchmarks');
      
      return result;
    } catch (error) {
      console.error('Error rerunning prompt:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Get sync status for a benchmark
   * @param {number} benchmarkId - Benchmark ID
   * @returns {Promise<Object>} API response with sync status
   */
  async getBenchmarkSyncStatus(benchmarkId) {
    try {
      const result = await this.makeRequest(`/benchmarks/${benchmarkId}/sync-status`);
      
      // The API already returns {success: true, sync_status: {...}}, so return it directly
      return result;
    } catch (error) {
      console.error('Error getting benchmark sync status:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Sync a benchmark by rerunning missing, failed, or pending prompts
   * @param {number} benchmarkId - Benchmark ID
   * @returns {Promise<Object>} API response
   */
  async syncBenchmark(benchmarkId) {
    try {
      const result = await this.makeRequest(`/benchmarks/${benchmarkId}/sync`, {
        method: 'POST'
      });
      
      // Clear benchmarks cache since status will change
      this.clearCache('benchmarks');
      
      // The API already returns {success: true, ...}, so return it directly
      return result;
    } catch (error) {
      console.error('Error syncing benchmark:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Update benchmark details
   * @param {number} id - Benchmark ID
   * @param {string} label - New label
   * @param {string} description - New description
   * @returns {Promise<Object>} Update result
   */
  async updateBenchmark(id, label, description) {
    if (!id) throw new Error('Benchmark ID is required');

    try {
      const result = await this.electronAPI.updateBenchmarkDetails(id, label, description);
      
      // Clear cache since data has changed
      this.clearCache('benchmarks');
      
      return result;
    } catch (error) {
      console.error('Error updating benchmark:', error);
      throw new Error(`Failed to update benchmark: ${error.message}`);
    }
  }

  /**
   * Export benchmark to CSV
   * @param {number} id - Benchmark ID
   * @returns {Promise<Object>} Export result
   */
  async exportBenchmark(id) {
    if (!id) throw new Error('Benchmark ID is required');

    try {
      const result = await this.electronAPI.exportBenchmark(id);
      return result;
    } catch (error) {
      console.error('Error exporting benchmark:', error);
      throw new Error(`Failed to export benchmark: ${error.message}`);
    }
  }

  /**
   * Get available models
   * @param {boolean} useCache - Whether to use cached data
   * @returns {Promise<Array>} List of available models
   */
  async getModels(useCache = true) {
    const cacheKey = 'models';
    
    if (useCache) {
      const cached = this.getCached(cacheKey);
      if (cached) return cached;
    }

    try {
      const result = await this.electronAPI.getAvailableModels();
      
      if (!result || !result.success) {
        throw new Error('Failed to get models from API');
      }

      let models = [];
      if (Array.isArray(result.models)) {
        models = result.models;
      } else if (typeof result.models === 'object') {
        // Flatten provider-grouped models
        for (const provider in result.models) {
          if (Array.isArray(result.models[provider])) {
            models = models.concat(result.models[provider]);
          }
        }
      }

      // Transform to objects with id and display name
      const formattedModels = models.map(modelId => ({
        id: modelId,
        name: this.formatModelName(modelId),
        provider: this.getModelProvider(modelId)
      }));

      this.setCached(cacheKey, formattedModels);
      return formattedModels;
    } catch (error) {
      console.error('Error fetching models:', error);
      throw new Error(`Failed to load models: ${error.message}`);
    }
  }

  /**
   * Format model name for display
   * @param {string} modelId - Model ID
   * @returns {string} Formatted name
   */
  formatModelName(modelId) {
    return modelId
      .split('-')
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  /**
   * Get model provider from model ID
   * @param {string} modelId - Model ID
   * @returns {string} Provider name
   */
  getModelProvider(modelId) {
    if (modelId.startsWith('gpt-') || 
        modelId.startsWith('o3') || 
        modelId.startsWith('o4') || 
        modelId.includes('openai')) {
      return 'openai';
    }
    if (modelId.startsWith('claude-') || modelId.includes('anthropic')) {
      return 'anthropic';
    }
    if (modelId.startsWith('gemini-') || modelId.includes('google')) {
      return 'google';
    }
    return 'unknown';
  }

  /**
   * Open file dialog
   * @param {Object} options - Dialog options
   * @returns {Promise<string|null>} Selected file path
   */
  async openFileDialog(options) {
    try {
      return await this.electronAPI.openFileDialog(options);
    } catch (error) {
      console.error('Error opening file dialog:', error);
      throw new Error(`Failed to open file dialog: ${error.message}`);
    }
  }

  /**
   * Read and parse CSV file
   * @param {string} filePath - Path to CSV file
   * @returns {Promise<Array>} Parsed CSV data
   */
  async readCsv(filePath) {
    try {
      return await this.electronAPI.readParseCsv(filePath);
    } catch (error) {
      console.error('Error reading CSV:', error);
      throw new Error(`Failed to read CSV file: ${error.message}`);
    }
  }

  /**
   * Extract text content from PDF file
   * @param {string} filePath - Path to PDF file
   * @returns {Promise<Object>} Extracted text data
   */
  async extractPdfText(filePath) {
    try {
      return await this.electronAPI.extractPdfText(filePath);
    } catch (error) {
      console.error('Error extracting PDF text:', error);
      throw new Error(`Failed to extract PDF text: ${error.message}`);
    }
  }

  /**
   * Set up event listeners for real-time updates
   * @param {Object} callbacks - Event callbacks
   */
  setupEventListeners(callbacks = {}) {
    if (callbacks.onProgress && this.electronAPI.onBenchmarkProgress) {
      this.electronAPI.onBenchmarkProgress(callbacks.onProgress);
    }

    if (callbacks.onComplete && this.electronAPI.onBenchmarkComplete) {
      this.electronAPI.onBenchmarkComplete(callbacks.onComplete);
    }

    if (callbacks.onMainProcessReady && this.electronAPI.onMainProcessReady) {
      this.electronAPI.onMainProcessReady(callbacks.onMainProcessReady);
    }
  }

  // ===== PROMPT SET METHODS =====

  /**
   * Create a new prompt set
   * @param {string} name - Prompt set name
   * @param {string} description - Prompt set description
   * @param {Array<string>} prompts - Array of prompt texts
   * @returns {Promise<Object>} Creation result
   */
  async createPromptSet(name, description, prompts) {
    const cacheKey = 'prompt_sets';
    
    try {
      const response = await this.makeRequest('/prompt-sets', {
        method: 'POST',
        body: JSON.stringify({ name, description, prompts })
      });

      // Clear cache to force refresh
      this.cache.delete(cacheKey);
      
      return response;
    } catch (error) {
      console.error('Error creating prompt set:', error);
      throw error;
    }
  }

  /**
   * Get all prompt sets
   * @param {boolean} useCache - Whether to use cached data
   * @returns {Promise<Array>} Array of prompt sets
   */
  async getPromptSets(useCache = true) {
    const cacheKey = 'prompt_sets';
    
    if (useCache && this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    try {
      const promptSets = await this.makeRequest('/prompt-sets');
      this.cache.set(cacheKey, promptSets);
      return promptSets;
    } catch (error) {
      console.error('Error fetching prompt sets:', error);
      throw error;
    }
  }

  /**
   * Get detailed information about a specific prompt set
   * @param {number} promptSetId - Prompt set ID
   * @returns {Promise<Object>} Prompt set details
   */
  async getPromptSetDetails(promptSetId) {
    const cacheKey = `prompt_set_${promptSetId}`;
    
    try {
      const response = await this.makeRequest(`/prompt-sets/${promptSetId}`);
      // Handle potential data structure mismatch - extract prompt_set if wrapped
      const details = response.prompt_set || response;
      this.cache.set(cacheKey, details);
      return details;
    } catch (error) {
      console.error(`Error fetching prompt set ${promptSetId}:`, error);
      throw error;
    }
  }

  /**
   * Update a prompt set
   * @param {number} promptSetId - Prompt set ID
   * @param {Object} updates - Updates to apply
   * @returns {Promise<Object>} Update result
   */
  async updatePromptSet(promptSetId, updates) {
    const cacheKey = 'prompt_sets';
    const detailsCacheKey = `prompt_set_${promptSetId}`;
    
    try {
      const response = await this.makeRequest(`/prompt-sets/${promptSetId}`, {
        method: 'PUT',
        body: JSON.stringify(updates)
      });

      // Clear cache to force refresh
      this.cache.delete(cacheKey);
      this.cache.delete(detailsCacheKey);
      
      return response;
    } catch (error) {
      console.error(`Error updating prompt set ${promptSetId}:`, error);
      throw error;
    }
  }

  /**
   * Delete a prompt set
   * @param {number} promptSetId - Prompt set ID
   * @returns {Promise<Object>} Deletion result
   */
  async deletePromptSet(promptSetId) {
    const cacheKey = 'prompt_sets';
    const detailsCacheKey = `prompt_set_${promptSetId}`;
    
    try {
      const response = await this.makeRequest(`/prompt-sets/${promptSetId}`, {
        method: 'DELETE'
      });

      // Clear cache to force refresh
      this.cache.delete(cacheKey);
      this.cache.delete(detailsCacheKey);
      
      return response;
    } catch (error) {
      console.error(`Error deleting prompt set ${promptSetId}:`, error);
      throw error;
    }
  }

  /**
   * Get the next available prompt set number for auto-naming
   * @returns {Promise<number>} Next available number
   */
  async getNextPromptSetNumber() {
    try {
      const response = await this.makeRequest('/prompt-sets/next-number');
      return response.next_number;
    } catch (error) {
      console.error('Error getting next prompt set number:', error);
      return 1; // Fallback to 1
    }
  }

  // ===== FILE MANAGEMENT METHODS =====

  /**
   * Upload and register a file in the system
   * @param {string} filePath - Path to the file to upload
   * @returns {Promise<Object>} Upload result
   */
  async uploadFile(filePath) {
    const cacheKey = 'files';
    
    try {
      const response = await this.makeRequest('/files/upload', {
        method: 'POST',
        body: JSON.stringify({ filePath })
      });

      // Clear cache to force refresh
      this.cache.delete(cacheKey);
      
      return response;
    } catch (error) {
      console.error('Error uploading file:', error);
      throw error;
    }
  }

  /**
   * Get all registered files
   * @param {boolean} useCache - Whether to use cached data
   * @returns {Promise<Array>} Array of files
   */
  async getFiles(useCache = true) {
    const cacheKey = 'files';
    
    if (useCache && this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    try {
      const files = await this.makeRequest('/files');
      this.cache.set(cacheKey, files);
      return files;
    } catch (error) {
      console.error('Error fetching files:', error);
      throw error;
    }
  }

  /**
   * Get detailed information about a specific file
   * @param {number} fileId - File ID
   * @returns {Promise<Object>} File details
   */
  async getFileDetails(fileId) {
    const cacheKey = `file_${fileId}`;
    
    try {
      const details = await this.makeRequest(`/files/${fileId}`);
      this.cache.set(cacheKey, details);
      return details;
    } catch (error) {
      console.error(`Error fetching file ${fileId}:`, error);
      throw error;
    }
  }

  /**
   * Delete a file from the system
   * @param {number} fileId - File ID
   * @returns {Promise<Object>} Deletion result
   */
  async deleteFile(fileId) {
    const cacheKey = 'files';
    const detailsCacheKey = `file_${fileId}`;
    
    try {
      const response = await this.makeRequest(`/files/${fileId}`, {
        method: 'DELETE'
      });

      // Clear cache to force refresh
      this.cache.delete(cacheKey);
      this.cache.delete(detailsCacheKey);
      
      return response;
    } catch (error) {
      console.error(`Error deleting file ${fileId}:`, error);
      throw error;
    }
  }

  /**
   * Make a request to the API server
   * @param {string} endpoint - API endpoint
   * @param {Object} options - Request options
   * @returns {Promise<any>} Response data
   */
  async makeRequest(endpoint, options = {}) {
    const url = `http://127.0.0.1:8000${endpoint}`;
    const defaultOptions = {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    };

    const requestOptions = { ...defaultOptions, ...options };

    try {
      const response = await fetch(url, requestOptions);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      throw error;
    }
  }

  /**
   * Reset benchmarks that are stuck in running state
   * @returns {Promise<Object>} Reset result
   */
  async resetStuckBenchmarks() {
    try {
      const result = await this.electronAPI.resetStuckBenchmarks();
      
      // Clear benchmarks cache since we may have reset some
      this.clearCache('benchmarks');
      
      return result;
    } catch (error) {
      console.error('Error resetting stuck benchmarks:', error);
      throw new Error(`Failed to reset stuck benchmarks: ${error.message}`);
    }
  }

  /**
   * Validate token limits for prompts and files
   * @param {Object} config - Validation configuration
   * @returns {Promise<Object>} Validation results
   */
  async validateTokens(config) {
    const { prompts, pdfPaths, modelNames } = config;

    try {
      const result = await this.electronAPI.validateTokens(
        prompts || [],
        pdfPaths || [],
        modelNames || []
      );

      return result;
    } catch (error) {
      console.error('Error validating tokens:', error);
      throw new Error(`Failed to validate tokens: ${error.message}`);
    }
  }

  /**
   * Count tokens for a specific file using different model providers
   * @param {string} filePath - Path to the file
   * @param {string} samplePrompt - Sample prompt to test with
   * @param {Array<string>} modelNames - Model names to test
   * @returns {Promise<Object>} Token count results
   */
  async countTokensForFile(filePath, samplePrompt, modelNames) {
    try {
      const result = await this.makeRequest('/count-tokens-for-file', {
        method: 'POST',
        body: JSON.stringify({
          file_path: filePath,
          sample_prompt: samplePrompt,
          model_names: modelNames
        })
      });

      return result;
    } catch (error) {
      console.error('Error counting tokens for file:', error);
      throw new Error(`Failed to count tokens: ${error.message}`);
    }
  }
}

// Create singleton instance
window.API = new API(); 