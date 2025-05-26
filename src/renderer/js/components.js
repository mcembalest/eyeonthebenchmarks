/**
 * UI Components and notification system
 */

class Components {
  constructor() {
    this.toastContainer = document.getElementById('toastContainer');
  }

  /**
   * Show a toast notification
   * @param {string} message - Message to display
   * @param {string} type - Type of notification (success, error, warning, info)
   * @param {number} duration - Duration in milliseconds (0 for persistent)
   * @returns {HTMLElement} Toast element
   */
  showToast(message, type = 'info', duration = 5000) {
    const toastId = Utils.generateId();
    const iconMap = {
      success: 'fas fa-check-circle',
      error: 'fas fa-exclamation-circle',
      warning: 'fas fa-exclamation-triangle',
      info: 'fas fa-info-circle'
    };

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.setAttribute('data-bs-autohide', duration > 0 ? 'true' : 'false');
    if (duration > 0) {
      toast.setAttribute('data-bs-delay', duration.toString());
    }

    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center">
          <i class="${iconMap[type]} me-2"></i>
          ${Utils.sanitizeHtml(message)}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    this.toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();

    // Remove from DOM after hiding
    toast.addEventListener('hidden.bs.toast', () => {
      toast.remove();
    });

    return toast;
  }

  /**
   * Create a loading spinner
   * @param {string} text - Loading text
   * @param {string} size - Size (sm, md, lg)
   * @returns {HTMLElement} Spinner element
   */
  createSpinner(text = 'Loading...', size = 'md') {
    const sizeClass = size === 'sm' ? 'spinner-border-sm' : '';
    
    const spinner = document.createElement('div');
    spinner.className = 'd-flex justify-content-center align-items-center flex-column';
    spinner.innerHTML = `
      <div class="spinner-border text-primary ${sizeClass}" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="text-muted mt-2 mb-0">${Utils.sanitizeHtml(text)}</p>
    `;
    
    return spinner;
  }

  /**
   * Create an empty state message
   * @param {string} title - Title text
   * @param {string} message - Message text
   * @param {string} icon - Font Awesome icon class
   * @returns {HTMLElement} Empty state element
   */
  createEmptyState(title, message, icon = 'fas fa-inbox') {
    const emptyState = document.createElement('div');
    emptyState.className = 'd-flex justify-content-center align-items-center flex-column h-100 text-center';
    emptyState.innerHTML = `
      <i class="${icon} fa-3x text-muted mb-3"></i>
      <h4 class="text-muted">${Utils.sanitizeHtml(title)}</h4>
      <p class="text-muted">${Utils.sanitizeHtml(message)}</p>
    `;
    
    return emptyState;
  }

  /**
   * Create an error state message
   * @param {string} title - Error title
   * @param {string} message - Error message
   * @param {Function} onRetry - Retry callback
   * @returns {HTMLElement} Error state element
   */
  createErrorState(title, message, onRetry = null) {
    const errorState = document.createElement('div');
    errorState.className = 'd-flex justify-content-center align-items-center flex-column h-100 text-center';
    
    const retryButton = onRetry ? `
      <button class="btn btn-outline-danger mt-3" onclick="(${onRetry.toString()})()">
        <i class="fas fa-redo me-1"></i>Try Again
      </button>
    ` : '';

    errorState.innerHTML = `
      <i class="fas fa-exclamation-triangle fa-3x text-danger mb-3"></i>
      <h4 class="text-danger">${Utils.sanitizeHtml(title)}</h4>
      <p class="text-muted">${Utils.sanitizeHtml(message)}</p>
      ${retryButton}
    `;
    
    return errorState;
  }

  /**
   * Create a benchmark card
   * @param {Object} benchmark - Benchmark data
   * @param {Object} callbacks - Event callbacks
   * @returns {HTMLElement} Benchmark card element
   */
  createBenchmarkCard(benchmark, callbacks = {}) {
    const card = document.createElement('div');
    card.className = 'col-md-6 col-lg-4 mb-4';
    card.setAttribute('data-benchmark-id', benchmark.id);

    const statusColor = Utils.getStatusColor(benchmark.status);
    const isRunning = benchmark.status === 'running' || benchmark.status === 'in-progress';
    
    const models = benchmark.model_names || [];
    const modelsText = models.length > 0 ? models.join(', ') : 'No models';

    card.innerHTML = `
      <div class="card h-100 shadow-sm">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h6 class="mb-0 text-truncate" title="${Utils.sanitizeHtml(benchmark.label || `Benchmark ${benchmark.id}`)}">
            ${Utils.sanitizeHtml(benchmark.label || `Benchmark ${benchmark.id}`)}
          </h6>
          <span class="badge bg-${statusColor}">
            ${isRunning ? '<i class="fas fa-spinner fa-spin me-1"></i>' : ''}
            ${benchmark.status === 'complete' ? 'Complete' : 'Running'}
          </span>
        </div>
        <div class="card-body">
          <p class="card-text text-muted small mb-2">
            <i class="fas fa-calendar me-1"></i>
            ${Utils.formatDate(benchmark.created_at || benchmark.timestamp)}
          </p>
          <div class="card-text small mb-3">
            <div class="d-flex align-items-center flex-wrap gap-1">
              ${models.length > 0 ? models.map(modelName => 
                Utils.createModelImage(modelName, 'model-icon-small')
              ).join('') : '<span class="text-muted">No models</span>'}
            </div>
          </div>
          ${benchmark.description ? `
            <p class="card-text small text-muted">
              ${Utils.truncateText(benchmark.description, 80)}
            </p>
          ` : ''}
        </div>
        <div class="card-footer bg-transparent">
          <div class="btn-group w-100" role="group">
            <button class="btn btn-outline-primary btn-sm view-btn" data-id="${benchmark.id}">
              <i class="fas fa-eye me-1"></i>
              ${isRunning ? 'View Progress' : 'View Results'}
            </button>
            <button class="btn btn-outline-secondary btn-sm edit-btn" data-id="${benchmark.id}">
              <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-outline-danger btn-sm delete-btn" data-id="${benchmark.id}">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      </div>
    `;

    // Add event listeners
    const viewBtn = card.querySelector('.view-btn');
    const editBtn = card.querySelector('.edit-btn');
    const deleteBtn = card.querySelector('.delete-btn');

    if (viewBtn && callbacks.onView) {
      viewBtn.addEventListener('click', () => callbacks.onView(benchmark.id));
    }

    if (editBtn && callbacks.onEdit) {
      editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        callbacks.onEdit(benchmark);
      });
    }

    if (deleteBtn && callbacks.onDelete) {
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        callbacks.onDelete(benchmark.id);
      });
    }

    return card;
  }

  /**
   * Create a table row for benchmark
   * @param {Object} benchmark - Benchmark data
   * @param {Object} callbacks - Event callbacks
   * @returns {HTMLElement} Table row element
   */
  createBenchmarkRow(benchmark, callbacks = {}) {
    const row = document.createElement('tr');
    row.setAttribute('data-benchmark-id', benchmark.id);
    row.className = 'cursor-pointer';

    const statusColor = Utils.getStatusColor(benchmark.status);
    const isRunning = benchmark.status === 'running' || benchmark.status === 'in-progress';
    
    const models = benchmark.model_names || [];
    const modelsText = models.length > 0 ? models.join(', ') : 'No models';

    row.innerHTML = `
      <td>
        <span class="badge bg-${statusColor}">
          ${isRunning ? '<i class="fas fa-spinner fa-spin me-1"></i>' : ''}
          ${benchmark.status === 'complete' ? 'Complete' : 'Running'}
        </span>
      </td>
      <td>
        <div>
          <strong>${Utils.sanitizeHtml(benchmark.label || `Benchmark ${benchmark.id}`)}</strong>
          ${benchmark.description ? `<br><small class="text-muted">${Utils.truncateText(benchmark.description, 60)}</small>` : ''}
        </div>
      </td>
      <td>
        <small>${Utils.formatDate(benchmark.created_at || benchmark.timestamp)}</small>
      </td>
      <td>
        <div class="d-flex align-items-center flex-wrap gap-1">
          ${models.length > 0 ? models.map(modelName => 
            Utils.createModelImage(modelName, 'model-icon-small')
          ).join('') : '<span class="text-muted">No models</span>'}
        </div>
      </td>
      <td>
        <div class="btn-group btn-group-sm" role="group">
          <button class="btn btn-outline-primary view-btn" data-id="${benchmark.id}">
            <i class="fas fa-eye"></i>
          </button>
          <button class="btn btn-outline-secondary edit-btn" data-id="${benchmark.id}">
            <i class="fas fa-edit"></i>
          </button>
          <button class="btn btn-outline-danger delete-btn" data-id="${benchmark.id}">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      </td>
    `;

    // Add event listeners
    const viewBtn = row.querySelector('.view-btn');
    const editBtn = row.querySelector('.edit-btn');
    const deleteBtn = row.querySelector('.delete-btn');

    if (viewBtn && callbacks.onView) {
      viewBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        callbacks.onView(benchmark.id);
      });
    }

    if (editBtn && callbacks.onEdit) {
      editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        callbacks.onEdit(benchmark);
      });
    }

    if (deleteBtn && callbacks.onDelete) {
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        callbacks.onDelete(benchmark.id);
      });
    }

    // Row click to view details
    if (callbacks.onView) {
      row.addEventListener('click', () => callbacks.onView(benchmark.id));
    }

    return row;
  }

  /**
   * Create a prompt input component
   * @param {string} value - Initial value
   * @param {Function} onRemove - Remove callback
   * @returns {HTMLElement} Prompt input element
   */
  createPromptInput(value = '', onRemove = null) {
    const promptDiv = document.createElement('div');
    promptDiv.className = 'prompt-item mb-3 p-3 border rounded bg-light';

    promptDiv.innerHTML = `
      <div class="d-flex align-items-start">
        <div class="flex-grow-1 me-2">
          <textarea class="form-control prompt-input" rows="2" 
                    placeholder="Enter your prompt here...">${Utils.sanitizeHtml(value)}</textarea>
        </div>
        <button class="btn btn-outline-danger btn-sm remove-prompt-btn" type="button">
          <i class="fas fa-times"></i>
        </button>
      </div>
    `;

    // Add remove functionality
    const removeBtn = promptDiv.querySelector('.remove-prompt-btn');
    if (removeBtn && onRemove) {
      removeBtn.addEventListener('click', () => {
        onRemove(promptDiv);
      });
    }

    return promptDiv;
  }

  /**
   * Create a model checkbox component
   * @param {Object} model - Model data
   * @param {boolean} checked - Initial checked state
   * @returns {HTMLElement} Model checkbox element
   */
  createModelCheckbox(model, checked = false) {
    const div = document.createElement('div');
    div.className = 'form-check mb-2';

    const formattedName = Utils.formatModelName(model.name);

    div.innerHTML = `
      <input class="form-check-input" type="checkbox" value="${model.id}" 
             id="model-${model.id}" ${checked ? 'checked' : ''}>
      <label class="form-check-label d-flex justify-content-between align-items-center" 
             for="model-${model.id}">
        <div class="d-flex align-items-center">
          ${Utils.createModelImage(model.name, 'me-2')}
          <span>${Utils.sanitizeHtml(formattedName)}</span>
        </div>
        ${Utils.createProviderImage(model.provider, 'ms-2')}
      </label>
    `;

    return div;
  }

  /**
   * Create a confirmation modal
   * @param {string} title - Modal title
   * @param {string} message - Modal message
   * @param {Function} onConfirm - Confirm callback
   * @param {Function} onCancel - Cancel callback
   * @returns {HTMLElement} Modal element
   */
  createConfirmModal(title, message, onConfirm, onCancel = null) {
    const modalId = `modal-${Utils.generateId()}`;
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = modalId;
    modal.setAttribute('tabindex', '-1');
    modal.setAttribute('aria-hidden', 'true');

    modal.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">${Utils.sanitizeHtml(title)}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p>${Utils.sanitizeHtml(message)}</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" class="btn btn-danger confirm-btn">Confirm</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    const bsModal = new bootstrap.Modal(modal);
    const confirmBtn = modal.querySelector('.confirm-btn');

    // Handle confirm
    confirmBtn.addEventListener('click', () => {
      bsModal.hide();
      if (onConfirm) onConfirm();
    });

    // Handle cancel
    modal.addEventListener('hidden.bs.modal', () => {
      modal.remove();
      if (onCancel) onCancel();
    });

    bsModal.show();
    return modal;
  }

  /**
   * Update benchmark card status
   * @param {number} benchmarkId - Benchmark ID
   * @param {string} status - New status
   */
  updateBenchmarkStatus(benchmarkId, status) {
    const card = document.querySelector(`[data-benchmark-id="${benchmarkId}"]`);
    if (!card) return;

    const badge = card.querySelector('.badge');
    if (!badge) return;

    const statusColor = Utils.getStatusColor(status);
    const isRunning = status === 'running' || status === 'in-progress';

    badge.className = `badge bg-${statusColor}`;
    badge.innerHTML = `
      ${isRunning ? '<i class="fas fa-spinner fa-spin me-1"></i>' : ''}
      ${status === 'complete' ? 'Complete' : 'Running'}
    `;
  }

  /**
   * Update benchmark card with new data (including models)
   * @param {number} benchmarkId - Benchmark ID
   * @param {Object} benchmarkData - Updated benchmark data
   */
  updateBenchmarkCard(benchmarkId, benchmarkData) {
    const card = document.querySelector(`[data-benchmark-id="${benchmarkId}"]`);
    if (!card) return;

    // Update status badge
    const badge = card.querySelector('.badge');
    if (badge) {
      const statusColor = Utils.getStatusColor(benchmarkData.status);
      const isRunning = benchmarkData.status === 'running' || benchmarkData.status === 'in-progress';

      badge.className = `badge bg-${statusColor}`;
      badge.innerHTML = `
        ${isRunning ? '<i class="fas fa-spinner fa-spin me-1"></i>' : ''}
        ${benchmarkData.status === 'complete' ? 'Complete' : 'Running'}
      `;
    }

    // Update model icons
    const modelsContainer = card.querySelector('.card-body .d-flex');
    if (modelsContainer) {
      const models = benchmarkData.model_names || [];
      
      if (models.length > 0) {
        modelsContainer.innerHTML = models.map(modelName => 
          Utils.createModelImage(modelName, 'model-icon-small')
        ).join('');
      } else {
        modelsContainer.innerHTML = '<span class="text-muted">No models</span>';
      }
      
      // Also update the table view if it exists
      const modelsRow = card.querySelector('td:nth-child(4) .d-flex');
      if (modelsRow) {
        if (models.length > 0) {
          modelsRow.innerHTML = models.map(modelName => 
            Utils.createModelImage(modelName, 'model-icon-small')
          ).join('');
        } else {
          modelsRow.innerHTML = '<span class="text-muted">No models</span>';
        }
      }
    }
  }
}

// Create singleton instance
window.Components = new Components(); 