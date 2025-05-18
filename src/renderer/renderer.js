function navigateTo(pageId) {
  document.querySelectorAll('.page').forEach(page => {
    page.classList.remove('active');
  });
  document.getElementById(pageId).classList.add('active');
}

// Element references
const newBenchmarkBtn = document.getElementById('newBenchmarkBtn');
const gridViewBtn = document.getElementById('gridViewBtn');
const tableViewBtn = document.getElementById('tableViewBtn');
const refreshBtn = document.getElementById('refreshBtn');
const importCsvBtn = document.getElementById('importCsvBtn');
const selectPdfBtn = document.getElementById('selectPdfBtn');
const runBtn = document.getElementById('runBtn');
const returnHomeBtn = document.getElementById('returnHomeBtn');
const consoleReturnBtn = document.getElementById('consoleReturnBtn');
const exportCsvBtn = document.getElementById('exportCsvBtn');

let selectedPdfPath = null;

// Basic event handlers
newBenchmarkBtn.addEventListener('click', () => navigateTo('composerContent'));
returnHomeBtn.addEventListener('click', () => navigateTo('homeContent'));
consoleReturnBtn.addEventListener('click', () => navigateTo('homeContent'));

// CSV Import handler
if (importCsvBtn) {
  importCsvBtn.addEventListener('click', async () => {
    const filePath = await window.electronAPI.openFileDialog({
      properties: ['openFile'],
      filters: [{ name: 'CSV Files', extensions: ['csv'] }]
    });

    if (filePath) {
      console.log('Selected CSV file:', filePath);
      // Request main process to read and parse CSV
      const parsedData = await window.electronAPI.readParseCsv(filePath);
      console.log('Parsed CSV data:', parsedData);

      if (parsedData && parsedData.length > 0) {
        populatePromptsTable(parsedData);
      } else {
        alert('CSV file is empty or could not be parsed correctly.');
      }
    }
  });
} else {
  console.warn('importCsvBtn not found. CSV import functionality will not be available.');
}

// Function to populate the prompts table from CSV data
function populatePromptsTable(data) {
  const promptsTableBody = document.getElementById('promptsTable').querySelector('tbody');
  promptsTableBody.innerHTML = ''; // Clear existing rows

  data.forEach(item => {
    if (item.prompt !== undefined && item.expected !== undefined) {
      const row = promptsTableBody.insertRow();
      const promptCell = row.insertCell();
      const expectedCell = row.insertCell();

      promptCell.textContent = item.prompt;
      expectedCell.textContent = item.expected;
    } else {
      console.warn('Skipping row due to missing prompt or expected data:', item);
    }
  });
}

// Export to CSV handler
exportCsvBtn.addEventListener('click', () => {
  // Get the current benchmark ID from the UI
  const consoleContent = document.getElementById('consoleLog');
  const idMatch = consoleContent.innerHTML.match(/Benchmark Details \(ID: (\d+)\)/);
  
  if (idMatch && idMatch[1]) {
    const benchmarkId = parseInt(idMatch[1], 10);
    console.log(`Exporting benchmark ID ${benchmarkId} to CSV...`);
    
    // Show a loading indicator
    const exportBtn = document.getElementById('exportCsvBtn');
    const originalText = exportBtn.textContent;
    exportBtn.textContent = 'Exporting...';
    exportBtn.disabled = true;
    
    // Call the export function
    window.electronAPI.exportBenchmarkToCsv(benchmarkId)
      .then(result => {
        console.log('Export result:', result);
        if (result && result.url) {
          window.open(result.url);
          showNotification('Exporting CSV...', 'success', 5000);
        } else {
          throw new Error(result?.error || 'Export failed');
        }
      })
      .catch(error => {
        console.error('Export error:', error);
        showNotification(`Error exporting benchmark: ${error.message || error}`, 'error', 5000);
      })
      .finally(() => {
        // Restore button state
        exportBtn.textContent = originalText;
        exportBtn.disabled = false;
      });
  } else {
    alert('No benchmark is currently selected. Please view a benchmark first.');
  }
});

// View toggle between grid and table
gridViewBtn.addEventListener('click', () => {
  document.getElementById('benchmarksGrid').classList.add('active');
  document.getElementById('benchmarksTable').classList.remove('active');
  gridViewBtn.classList.add('active');
  tableViewBtn.classList.remove('active');
});

tableViewBtn.addEventListener('click', () => {
  document.getElementById('benchmarksGrid').classList.remove('active');
  document.getElementById('benchmarksTable').classList.add('active');
  gridViewBtn.classList.remove('active');
  tableViewBtn.classList.add('active');
});

// Refresh benchmark data
refreshBtn.addEventListener('click', loadBenchmarks);

// PDF selection
selectPdfBtn.addEventListener('click', async () => {
  const pdfPath = await window.electronAPI.openFileDialog({
    properties: ['openFile'],
    filters: [{ name: 'PDF Files', extensions: ['pdf'] }]
  });
  
  if (pdfPath) {
    selectedPdfPath = pdfPath;
    const pathParts = pdfPath.split('/');
    document.getElementById('selectedPdfLabel').textContent = pathParts[pathParts.length - 1];
  }
});

// Run benchmark
runBtn.addEventListener('click', () => {
  // Get prompts from table
  const promptsTable = document.getElementById('promptsTable');
  const prompts = [];
  
  for (let i = 1; i < promptsTable.rows.length; i++) {
    const row = promptsTable.rows[i];
    const promptText = row.cells[0].textContent.trim();
    const expectedAnswer = row.cells[1].textContent.trim();
    
    if (promptText) {
      prompts.push({
        prompt_text: promptText,
        expected_answer: expectedAnswer
      });
    }
  }
  
  // Get selected models
  const modelList = document.getElementById('modelList');
  const selectedModels = [];
  
  modelList.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {
    selectedModels.push(checkbox.value);
  });

  // Get benchmark name and description
  const benchmarkName = document.getElementById('benchmarkNameInput').value.trim();
  const benchmarkDescription = document.getElementById('benchmarkDescriptionInput').value.trim();
  
  // Validate inputs
  if (!benchmarkName) {
    alert('Please enter a name for the benchmark.');
    return;
  }

  if (prompts.length === 0) {
    alert('Please enter at least one prompt.');
    return;
  }
  
  if (!selectedPdfPath) {
    alert('Please select a PDF file.');
    return;
  }
  
  if (selectedModels.length === 0) {
    alert('Please select at least one model.');
    return;
  }
  
  // Disable the run button to prevent multiple clicks
  runBtn.disabled = true;
  const originalText = runBtn.textContent;
  runBtn.textContent = 'Starting...';
  
  // Start benchmark run
  window.electronAPI.runBenchmark(prompts, selectedPdfPath, selectedModels, benchmarkName, benchmarkDescription)
    .then((result) => {
      console.log('Benchmark launch result:', result);
      
      if (result && result.success) {
        // Show success notification
        showNotification(`Benchmark "${benchmarkName}" started successfully!`, 'success');
        
        // Navigate to home
        navigateTo('homeContent');
        
        // Clear the benchmarks grid and show loading
        const gridContainer = document.getElementById('benchmarksGrid');
        if (gridContainer) {
          gridContainer.innerHTML = '<div class="loading">Loading new benchmark...</div>';
        }
        
        // Give it a moment for the database to update, then refresh
        setTimeout(() => {
          loadBenchmarks().then(() => {
            console.log('Benchmarks refreshed after launch');
            // If we have a benchmark ID, try to view its details
            if (result.benchmarkId) {
              // Small delay to ensure UI is ready
              setTimeout(() => {
                viewBenchmarkDetails(result.benchmarkId);
              }, 300);
            }
          });
        }, 1000);
      } else {
        throw new Error(result?.error || 'Failed to start benchmark');
      }
    })
    .catch(error => {
      console.error('Error starting benchmark:', error);
      showNotification(`Error starting benchmark: ${error.message || 'Unknown error'}`, 'error');
    })
    .finally(() => {
      // Re-enable the button
      runBtn.disabled = false;
      runBtn.textContent = originalText;
    });
});

// Load benchmark data
async function loadBenchmarks() {
  const gridContainer = document.getElementById('benchmarksGrid');
  const loadingHtml = '<div class="loading">Loading benchmarks...</div>';
  
  if (gridContainer) {
    gridContainer.innerHTML = loadingHtml;
  }
  
  try {
    console.log('Loading benchmarks...');
    const response = await window.electronAPI.listBenchmarks();
    console.log('Benchmarks response:', response);
    
    // Handle different response formats
    let benchmarks = [];
    if (Array.isArray(response)) {
      benchmarks = response; // Direct array response
    } else if (response && Array.isArray(response.result)) {
      benchmarks = response.result; // Response with result array
    } else if (response && response.benchmarks) {
      benchmarks = response.benchmarks; // Response with benchmarks property
    }
    
    console.log('Processed benchmarks:', benchmarks);
    
    if (!benchmarks || !Array.isArray(benchmarks)) {
      throw new Error('Invalid benchmark data format received');
    }
    
    // Sort benchmarks by timestamp (newest first)
    benchmarks.sort((a, b) => {
      const timeA = new Date(a.timestamp || 0).getTime();
      const timeB = new Date(b.timestamp || 0).getTime();
      return timeB - timeA;
    });
    
    // Clear the loading message and render the benchmarks
    if (gridContainer) {
      gridContainer.innerHTML = '';
      renderBenchmarks(benchmarks);
    }
    
    return benchmarks; // Return the loaded benchmarks for chaining
  } catch (error) {
    console.error('Error loading benchmarks:', error);
    const errorHtml = `
      <div class="error">
        <h3>Error loading benchmarks</h3>
        <p>${error.message || 'Unknown error occurred'}</p>
        <hr>
        <button onclick="loadBenchmarks()" class="btn btn-sm btn-outline-secondary mt-2">
          <i class="fas fa-sync-alt me-1"></i> Retry
        </button>
      </div>
    `;
    
    if (gridContainer) {
      gridContainer.innerHTML = errorHtml;
    }
    
    throw error; // Re-throw to allow error handling by the caller
  }
}

// Render benchmarks in grid and table views
function renderBenchmarks(benchmarks) {
  console.log('Rendering benchmarks:', benchmarks);
  
  const gridContainer = document.getElementById('benchmarksGrid');
  console.log('Grid container found:', !!gridContainer);
  
  const tableContainer = document.getElementById('benchmarksTable');
  console.log('Table container found:', !!tableContainer);
  
  let tableBody;
  if (tableContainer) {
    tableBody = tableContainer.querySelector('tbody');
    console.log('Table body found:', !!tableBody);
  }
  
  // Clear existing content
  if (gridContainer) gridContainer.innerHTML = '';
  if (tableBody) tableBody.innerHTML = '';
  
  if (!benchmarks || benchmarks.length === 0) {
    console.log('No benchmarks to display');
    if (gridContainer) {
      gridContainer.innerHTML = '<div class="empty">No benchmarks found</div>';
    }
    return;
  }
  
  console.log('Proceeding to create UI elements for', benchmarks.length, 'benchmarks');
  
  // Populate grid view
  console.log('Rendering benchmarks:', benchmarks);
  benchmarks.forEach(benchmark => {
    console.log('Processing benchmark:', {
      id: benchmark.id,
      label: benchmark.label,
      description: benchmark.description,
      timestamp: benchmark.timestamp
    });
    
    const card = document.createElement('div');
    card.className = 'benchmark-card';
    // Get a nice title for the benchmark
    const title = benchmark.label || benchmark.description?.split('\n')[0] || `Benchmark ${benchmark.id}`;
    console.log('Using title:', title, 'for benchmark:', benchmark.id);
    
    // Format model names for display
    const modelNames = benchmark.model_names || [];
    const modelsText = modelNames.length > 0 
      ? modelNames.join(', ')
      : 'No models';
    
    // Check if benchmark is in progress
    const benchmarkStatus = benchmark.status || 'complete';
    // Treat 'progress' as in-progress too
    const isInProgress = benchmarkStatus === 'running' || benchmarkStatus === 'pending' || benchmarkStatus === 'progress';
    const statusClass = isInProgress ? 'status-in-progress' : 'status-complete';
    const statusText = isInProgress ? 'In Progress' : 'Complete';
    
    // Set data attributes for styling and identification
    card.dataset.status = isInProgress ? 'in-progress' : 'complete';
    card.dataset.benchmarkId = benchmark.id;
    
    card.innerHTML = `
      <div class="benchmark-header">
        <h3>${title}</h3>
        <span class="status-badge ${statusClass}">${statusText}</span>
      </div>
      <p class="benchmark-date">${new Date(benchmark.timestamp).toLocaleString()}</p>
      <div class="benchmark-models">
        <span class="models-label">Models:</span>
        <span class="models-list" title="${modelNames.length > 0 ? modelNames.join(', ') : 'No models'}">
          ${modelsText}
        </span>
      </div>
      <div class="card-actions">
        ${isInProgress ? 
          `<button class="view-logs-btn" data-id="${benchmark.id}">View Logs</button>` : 
          `<button class="view-btn" data-id="${benchmark.id}">View Details</button>`
        }
        <button class="edit-btn" data-id="${benchmark.id}">✏️ Edit</button>
        <button class="delete-btn" data-id="${benchmark.id}">🗑️ Delete</button>
      </div>
    `;
    
    // Add event listener for view logs button if it exists
    const viewLogsBtn = card.querySelector('.view-logs-btn');
    if (viewLogsBtn) {
      viewLogsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        viewBenchmarkDetails(benchmark.id);
        // Auto-scroll to the bottom of the log
        setTimeout(() => {
          const consoleLog = document.getElementById('consoleLog');
          if (consoleLog) {
            consoleLog.scrollTop = consoleLog.scrollHeight;
          }
        }, 100);
      });
    }
    
    // Add event listener for view details button if it exists
    const viewDetailsBtn = card.querySelector('.view-btn');
    if (viewDetailsBtn) {
      viewDetailsBtn.addEventListener('click', () => {
        viewBenchmarkDetails(benchmark.id);
      });
    }
    
    // Note: viewLogsBtn is already handled above at line ~339

    card.querySelector('.edit-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      const benchmarkId = benchmark.id;
      const currentLabel = benchmark.label || '';
      const currentDescription = benchmark.description || '';

      // Create modal overlay
      const modalOverlay = document.createElement('div');
      modalOverlay.className = 'modal-overlay';
      
      // Create modal content
      const modalContent = document.createElement('div');
      modalContent.className = 'modal-content';
      modalContent.innerHTML = `
        <h2>Edit Benchmark</h2>
        <div class="form-group">
          <label for="editBenchmarkName">Name:</label>
          <input type="text" id="editBenchmarkName" value="${currentLabel}" placeholder="Enter benchmark name">
        </div>
        <div class="form-group">
          <label for="editBenchmarkDescription">Description:</label>
          <textarea id="editBenchmarkDescription" placeholder="Enter benchmark description">${currentDescription}</textarea>
        </div>
        <div class="modal-actions">
          <button class="cancel">Cancel</button>
          <button class="save">Save Changes</button>
        </div>
      `;
      
      modalOverlay.appendChild(modalContent);
      document.body.appendChild(modalOverlay);
      
      // Focus the name input
      const nameInput = modalContent.querySelector('#editBenchmarkName');
      nameInput.focus();
      nameInput.select();
      
      // Handle save/cancel
      return new Promise((resolve) => {
        const handleSave = async () => {
          const newLabel = nameInput.value;
          const newDescription = modalContent.querySelector('#editBenchmarkDescription').value;
          
          console.log(`Attempting to update benchmark ${benchmarkId}:`, {
            currentLabel,
            newLabel: newLabel.trim(),
            currentDescription,
            newDescription: newDescription.trim()
          });
          
          try {
            // Call the update function and wait for the result
            const result = await window.electronAPI.updateBenchmarkDetails(benchmarkId, newLabel.trim(), newDescription.trim());
            console.log('Update result:', result);
            
            if (result && result.success) {
              console.log('Benchmark update successful');
              modalOverlay.remove();
              navigateTo('homeContent'); // Go back to home
              await loadBenchmarks(); // Refresh the list
            } else {
              const errorMsg = result ? result.error : 'Unknown error';
              console.error('Failed to update benchmark:', errorMsg);
              alert(`Failed to update benchmark: ${errorMsg}`);
            }
          } catch (error) {
            console.error('Error updating benchmark:', error);
            alert(`Error updating benchmark: ${error.message || 'Unknown error'}`);
          } finally {
            modalOverlay.remove();
            resolve();
          }
        };
        
        const handleCancel = () => {
          modalOverlay.remove();
          resolve();
        };
        
        modalContent.querySelector('.save').addEventListener('click', handleSave);
        modalContent.querySelector('.cancel').addEventListener('click', handleCancel);
        
        // Handle Enter key in inputs
        const handleEnterKey = (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSave();
          }
        };
        
        nameInput.addEventListener('keypress', handleEnterKey);
        
        // Handle Escape key
        document.addEventListener('keydown', function escapeHandler(e) {
          if (e.key === 'Escape') {
            document.removeEventListener('keydown', escapeHandler);
            handleCancel();
          }
        });
      });
    });

    card.querySelector('.delete-btn').addEventListener('click', (e) => {
      e.stopPropagation(); // Prevent card click event if any
      const benchmarkId = benchmark.id;
      handleDeleteBenchmark(benchmarkId);
    });
    
    gridContainer.appendChild(card);
  });
  
  // Populate table view
  benchmarks.forEach(benchmark => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><span class="status-indicator ${benchmark.status || 'complete'}"></span></td>
      <td>${benchmark.label || 'Benchmark ' + benchmark.id}</td>
      <td>${benchmark.timestamp}</td>
      <td>${benchmark.models ? benchmark.models.join(', ') : 'N/A'}</td>
      <td>${benchmark.files ? benchmark.files.join(', ') : 'N/A'}</td>
    `;
    
    row.addEventListener('click', () => {
      viewBenchmarkDetails(benchmark.id);
    });
    
    tableBody.appendChild(row);
  });
}

// Handle benchmark detail updates (renaming/description change)
// Note: This functionality is now handled directly in the edit button click handler

// View benchmark details
async function viewBenchmarkDetails(benchmarkId) {
  try {
    if (!benchmarkId) {
      throw new Error('No benchmark ID provided');
    }
    
    console.log(`Requesting details for benchmark ID: ${benchmarkId}`);
    
    // Show loading state
    const consoleLog = document.getElementById('consoleLog');
    if (consoleLog) {
      consoleLog.innerHTML = `
        <div class="text-center py-4">
          <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
          </div>
          <p class="mt-2">Loading benchmark details...</p>
        </div>
      `;
    }
    
    // Navigate to console view first to show loading state
    navigateTo('consoleContent');
    
    // Get benchmark details
    const details = await window.electronAPI.getBenchmarkDetails(benchmarkId);
    console.log('Received benchmark details:', details);

    if (!details || !details.id) {
      throw new Error('Invalid or empty response from server');
    }

    // Format timestamp if it exists
    let formattedTimestamp = 'N/A';
    if (details.timestamp) {
      try {
        const date = new Date(details.timestamp);
        formattedTimestamp = date.toLocaleString();
      } catch (e) {
        console.error('Error formatting timestamp:', e);
        formattedTimestamp = details.timestamp;
      }
    }
    
    // Format results for display using prompt-level data
    let resultsHtml = '<p>No results available.</p>';
    if (details.prompts_data && details.prompts_data.length > 0) {
      resultsHtml = `
        <div class="table-responsive">
          <table class="table table-sm table-hover">
            <thead>
              <tr>
                <th>Prompt</th>
                <th>Expected</th>
                <th>Actual</th>
                <th>Score</th>
                <th>Latency (ms)</th>
              </tr>
            </thead>
            <tbody>
              ${details.prompts_data.map(p => `
                <tr>
                  <td>${p.prompt_text}</td>
                  <td>${p.expected_answer || 'N/A'}</td>
                  <td>${p.actual_answer || 'N/A'}</td>
                  <td>${typeof p.score === 'number' ? p.score.toFixed(2) : p.score}</td>
                  <td>${p.latency_ms !== undefined ? p.latency_ms : 'N/A'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }
    
    // Update the UI with benchmark details
    if (consoleLog) {
      consoleLog.innerHTML = `
        <div class="benchmark-details">
          <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="mb-0">${details.label || `Benchmark ${details.id}`}</h2>
            <div>
              <button id="refreshDetailsBtn" class="btn btn-outline-secondary btn-sm me-2">
                <i class="fas fa-sync-alt"></i> Refresh
              </button>
              <button id="exportCsvBtn" class="btn btn-primary btn-sm">
                <i class="fas fa-file-export me-1"></i> Export to CSV
              </button>
            </div>
          </div>
          
          <div class="card mb-4">
            <div class="card-body">
              <div class="row">
                <div class="col-md-6">
                  <div class="mb-3">
                    <h6 class="text-muted mb-1">Description</h6>
                    <p class="mb-0">${details.description || 'No description provided'}</p>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="mb-3">
                    <h6 class="text-muted mb-1">Created</h6>
                    <p class="mb-0">${formattedTimestamp}</p>
                  </div>
                </div>
              </div>
              
              <div class="row">
                <div class="col-md-6">
                  <div class="mb-3">
                    <h6 class="text-muted mb-1">Models</h6>
                    <p class="mb-0">${details.models ? details.models.join(', ') : 'N/A'}</p>
                  </div>
                </div>
                <div class="col-md-6">
                  <div class="mb-3">
                    <h6 class="text-muted mb-1">Files</h6>
                    <p class="mb-0 text-truncate" title="${details.files ? details.files.join(', ') : ''}">
                      ${details.files ? details.files.join(', ') : 'N/A'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="card">
            <div class="card-header">
              <h5 class="mb-0">Results</h5>
            </div>
            <div class="card-body">
              ${resultsHtml}
            </div>
          </div>
        </div>
      `;
      
      // Add event listeners
      const refreshBtn = document.getElementById('refreshDetailsBtn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          viewBenchmarkDetails(benchmarkId);
        });
      }
      
      const exportBtn = document.getElementById('exportCsvBtn');
      if (exportBtn) {
        exportBtn.addEventListener('click', () => {
          showNotification('Preparing export...', 'info');
          exportBtn.disabled = true;
          exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Exporting...';
          
          window.electronAPI.exportBenchmarkToCsv(benchmarkId)
            .then(result => {
              if (result && result.url) {
                window.open(result.url);
                showNotification('Exporting CSV...', 'success', 5000);
              } else {
                throw new Error(result?.error || 'Export failed');
              }
            })
            .catch(error => {
              console.error('Export error:', error);
              showNotification(`Export failed: ${error.message || 'Unknown error'}`, 'error');
            })
            .finally(() => {
              if (exportBtn) {
                exportBtn.disabled = false;
                exportBtn.innerHTML = '<i class="fas fa-file-export me-1"></i> Export to CSV';
              }
            });
        });
      }
    }
  } catch (error) {
    console.error('Error in viewBenchmarkDetails:', error);
    const errorMessage = error.message || 'Failed to load benchmark details';
    
    const consoleLog = document.getElementById('consoleLog');
    if (consoleLog) {
      consoleLog.innerHTML = `
        <div class="alert alert-danger">
          <h4 class="alert-heading">Error loading benchmark</h4>
          <p>${errorMessage}</p>
          <hr>
          <button onclick="window.history.back()" class="btn btn-sm btn-outline-secondary me-2">
            <i class="fas fa-arrow-left me-1"></i> Go Back
          </button>
          <button onclick="loadBenchmarks()" class="btn btn-sm btn-outline-primary">
            <i class="fas fa-home me-1"></i> View All Benchmarks
          </button>
        </div>
      `;
    }
    
    showNotification(`Error: ${errorMessage}`, 'error');
  }
}

/**
 * Shows a notification with the given message and type
 * @param {string} message - The message to display
 * @param {string} type - The type of notification ('success', 'error', 'warning')
 * @param {number} [duration=3000] - How long to show the notification in ms
 */
function showNotification(message, type = 'success', duration = 3000) {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  
  // Add icon based on type
  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  else if (type === 'error') icon = '❌';
  else if (type === 'warning') icon = '⚠️';
  
  notification.innerHTML = `
    <span class="icon">${icon}</span>
    <div class="notification-content">${message}</div>
    <button class="notification-close" aria-label="Close">&times;</button>
  `;
  
  // Add close button handler
  const closeBtn = notification.querySelector('.notification-close');
  closeBtn.addEventListener('click', () => {
    notification.classList.add('hide');
    setTimeout(() => notification.remove(), 300);
  });
  
  // Auto-remove after duration
  if (duration > 0) {
    setTimeout(() => {
      if (notification.parentNode) { // Check if still in DOM
        notification.classList.add('hide');
        setTimeout(() => notification.remove(), 300);
      }
    }, duration);
  }
  
  // Add to DOM
  document.body.appendChild(notification);
  
  // Trigger reflow to enable animation
  // eslint-disable-next-line no-unused-expressions
  notification.offsetHeight;
  
  return notification;
}

// Handle benchmark deletion
async function handleDeleteBenchmark(benchmarkId) {
  console.log(`Requesting deletion for benchmark ID: ${benchmarkId}`);
  
  // Show a confirmation dialog
  const confirmed = confirm('Are you sure you want to delete this benchmark? This action cannot be undone.');
  if (!confirmed) {
    return; // User cancelled the deletion
  }
  
  // Show loading state
  const notification = showNotification('Deleting benchmark...', 'warning', 0);
  
  try {
    const result = await window.electronAPI.deleteBenchmark(benchmarkId);
    
    if (notification.parentNode) {
      notification.classList.add('hide');
      setTimeout(() => notification.remove(), 300);
    }
    
    if (result && result.success) {
      console.log('Benchmark deleted successfully, refreshing list...');
      showNotification('Benchmark deleted successfully', 'success');
      
      // Add a small delay to ensure the database is updated
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Force a complete refresh of the benchmark list
      const gridContainer = document.getElementById('benchmarksGrid');
      if (gridContainer) {
        // Show loading state
        gridContainer.innerHTML = '<div class="loading">Refreshing benchmarks...</div>';
      }
      
      // Get fresh benchmark data
      const benchmarks = await window.electronAPI.listBenchmarks();
      console.log('Refreshed benchmarks after deletion:', benchmarks);
      
      // Clear the current view and re-render
      if (gridContainer) {
        gridContainer.innerHTML = '';
        renderBenchmarks(benchmarks);
      }
      
      // If we're currently viewing the deleted benchmark, navigate back to home
      const consoleContent = document.getElementById('consoleContent');
      if (consoleContent && consoleContent.classList.contains('active')) {
        const currentBenchmarkId = consoleContent.querySelector('h2')?.textContent?.match(/ID: (\d+)/)?.[1];
        if (currentBenchmarkId && parseInt(currentBenchmarkId, 10) === benchmarkId) {
          navigateTo('homeContent');
        }
      }
    } else {
      const errorMsg = result ? result.error : 'Unknown error';
      console.error('Failed to delete benchmark:', errorMsg);
      showNotification(`Failed to delete benchmark: ${errorMsg}`, 'error', 5000);
    }
  } catch (error) {
    console.error('Error deleting benchmark:', error);
    showNotification(
      `Error deleting benchmark: ${error.message || 'Unknown error'}`,
      'error',
      5000
    );
    
    // Still try to refresh the list even if there was an error
    try {
      await loadBenchmarks();
    } catch (refreshError) {
      console.error('Error refreshing benchmark list:', refreshError);
    }
  }
}

// Listen for progress updates
window.electronAPI.onBenchmarkProgress(data => {
  // Update progress indicators
  console.log('Benchmark progress:', data);
  
  // Update the console log if we're on the console page
  const consoleLog = document.getElementById('consoleLog');
  const consoleContent = document.getElementById('consoleContent');
  
  if (consoleLog && consoleContent && consoleContent.classList.contains('active')) {
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    logEntry.textContent = data.message;
    
    // Highlight important messages
    if (data.message.toLowerCase().includes('error') || data.message.toLowerCase().includes('failed')) {
      logEntry.style.color = '#e53e3e';
      logEntry.style.fontWeight = '500';
    } else if (data.message.toLowerCase().includes('complete') || data.message.toLowerCase().includes('success')) {
      logEntry.style.color = '#2f855a';
      logEntry.style.fontWeight = '500';
    }
    
    consoleLog.appendChild(logEntry);
    consoleLog.scrollTop = consoleLog.scrollHeight; // Auto-scroll to bottom
  }
  
  // Update the benchmark card status if we have the benchmark ID
  if (data.benchmark_id) {
    const benchmarkCard = document.querySelector(`.benchmark-card[data-benchmark-id="${data.benchmark_id}"]`);
    if (benchmarkCard) {
      const statusBadge = benchmarkCard.querySelector('.status-badge');
      if (statusBadge) {
        if (data.status === 'complete') {
          statusBadge.textContent = 'Complete';
          statusBadge.className = 'status-badge status-complete';
          benchmarkCard.dataset.status = 'complete';
          
          // Switch to View Details button if we're still showing View Logs
          const viewLogsBtn = benchmarkCard.querySelector('.view-logs-btn');
          if (viewLogsBtn) {
            viewLogsBtn.textContent = 'View Details';
            viewLogsBtn.className = 'view-btn';
          }
        } else if (data.status === 'progress') {
          // Show ongoing progress status
          statusBadge.textContent = 'In Progress';
          statusBadge.className = 'status-badge status-in-progress';
          benchmarkCard.dataset.status = 'in-progress';
        }
      }
    }
  }
});

// Listen for completion updates
window.electronAPI.onBenchmarkComplete(data => {
  // Update UI when benchmark completes
  console.log('Benchmark complete:', data);
  
  // Show completion message in the console if it's open
  const consoleLog = document.getElementById('consoleLog');
  const consoleContent = document.getElementById('consoleContent');
  
  if (consoleLog && consoleContent && consoleContent.classList.contains('active')) {
    const completionDiv = document.createElement('div');
    completionDiv.className = 'completion-message';
    completionDiv.innerHTML = `
      <p style="font-weight: 600; color: #2f855a; margin-bottom: 8px;">✅ Benchmark Complete!</p>
      <p>Mean Score: <strong>${data.mean_score || 'N/A'}</strong></p>
      <p>Total Items: <strong>${data.items || '0'}</strong></p>
      <p>Elapsed Time: <strong>${data.elapsed_s || data.duration_seconds || '0'}</strong> seconds</p>
    `;
    consoleLog.appendChild(completionDiv);
    consoleLog.scrollTop = consoleLog.scrollHeight;
  }
  
  // Update the benchmark card status
  if (data.benchmark_id) {
    const benchmarkCard = document.querySelector(`.benchmark-card[data-benchmark-id="${data.benchmark_id}"]`);
    if (benchmarkCard) {
      benchmarkCard.dataset.status = 'complete';
      
      const statusBadge = benchmarkCard.querySelector('.status-badge');
      if (statusBadge) {
        statusBadge.textContent = 'Complete';
        statusBadge.className = 'status-badge status-complete';
      }
      
      // Replace View Logs button with View Details if it exists
      const viewLogsBtn = benchmarkCard.querySelector('.view-logs-btn');
      if (viewLogsBtn) {
        viewLogsBtn.textContent = 'View Details';
        viewLogsBtn.className = 'view-btn';
      }
    }
  }
  
  // Refresh the benchmark list to show updated status
  loadBenchmarks();
  
  // Show a notification if the console isn't open
  if (!consoleContent || !consoleContent.classList.contains('active')) {
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.innerHTML = `
      <p>✅ Benchmark completed successfully!</p>
      <p><small>Click <a href="#" class="view-benchmark-link" data-id="${data.benchmark_id}">here</a> to view results</small></p>
    `;
    
    // Add click handler for the view link
    notification.querySelector('.view-benchmark-link').addEventListener('click', (e) => {
      e.preventDefault();
      viewBenchmarkDetails(data.benchmark_id);
      notification.remove();
    });
    
    // Auto-remove notification after 10 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
      }
    }, 10000);
    
    document.body.appendChild(notification);
    
    // Auto-hide notification after 3 seconds
    setTimeout(() => {
      notification.classList.add('show');
    }, 100);
  }
});

// Populate the model list with available models from Python files
async function populateModelList() {
  const modelListContainer = document.getElementById('modelList');
  if (!modelListContainer) {
    console.warn('modelList container not found.');
    return;
  }
  try {
    // Clear any existing model entries completely
    modelListContainer.innerHTML = '<p>Loading models...</p>';

    // Get models dynamically from Python files
    const result = await window.electronAPI.getAvailableModels();
    
    // Clear loading message
    modelListContainer.innerHTML = '';
    
    // Check if we got a valid response
    if (!result || !result.success) {
      console.error('Failed to get models from API:', result);
      modelListContainer.innerHTML = '<p>Error: Could not load models.</p>';
      return;
    }
    
    // Create a flat list of all models from all providers
    let allModels = [];
    
    // Extract models from the response - could be flat list or provider-grouped
    if (Array.isArray(result.models)) {
      // It's already a flat list
      allModels = result.models;
    } else if (typeof result.models === 'object') {
      // It's grouped by provider, so flatten it
      for (const provider in result.models) {
        if (Array.isArray(result.models[provider])) {
          allModels = allModels.concat(result.models[provider]);
        }
      }
    }
    
    if (allModels.length === 0) {
      console.error('No models found in response:', result);
      modelListContainer.innerHTML = '<p>No models available.</p>';
      return;
    }
    
    console.log('Found models:', allModels);
    
    // Transform the flat list into objects with id and name
    const formattedModels = allModels.map(modelId => {
      // Create a more user-friendly display name
      const displayName = modelId
        .split('-')
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
      
      return { id: modelId, name: displayName };
    });
    
    // Populate with the dynamic model list
    populateModelListWithModels(formattedModels);
  } catch (error) {
    console.error('Error populating model list:', error);
    modelListContainer.innerHTML = '<p>Error loading models.</p>';
  }
}

// Helper function to populate model list with model objects
function populateModelListWithModels(models) {
  const modelListContainer = document.getElementById('modelList');
  if (!modelListContainer) return;
  
  // Container already cleared above, now populate it
  models.forEach(model => {
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = model.id;
    checkbox.value = model.id;
    checkbox.name = 'model';
    
    // Check if this is gpt-4o-mini (our default)
    if (model.id === 'gpt-4o-mini') {
      checkbox.checked = true;
    }
    
    const label = document.createElement('label');
    label.htmlFor = model.id;
    label.textContent = model.name;
    
    const div = document.createElement('div');
    div.appendChild(checkbox);
    div.appendChild(label);
    modelListContainer.appendChild(div);
  });
}

// Initialize page
async function initPage() {
  console.log('DOM loaded - initializing application');
  
  // Call model list population
  await populateModelList();
  
  // Set up refresh button
  const refreshBtn = document.getElementById('refreshBtn');
  if (refreshBtn) {
    console.log('Found refresh button, setting up event listener');
    refreshBtn.addEventListener('click', () => {
      console.log('Refresh button clicked');
      // Clear any existing content
      const gridContainer = document.getElementById('benchmarksGrid');
      if (gridContainer) {
        gridContainer.innerHTML = '<div class="loading">Loading benchmarks...</div>';
      }
      // Force reload benchmarks
      loadBenchmarks();
    });
  } else {
    console.error('Refresh button not found!');
  }
  
  // Add default prompt rows
  const promptsTableBody = document.getElementById('promptsTable').querySelector('tbody');
  const defaultPrompts = [
    {prompt: "what year did this piece get written", expected: "2025"},
  ];
  
  defaultPrompts.forEach(item => {
    const row = promptsTableBody.insertRow();
    const promptCell = row.insertCell(0);
    const expectedCell = row.insertCell(1);
    promptCell.textContent = item.prompt;
    expectedCell.textContent = item.expected;
    
    // Make cells editable
    promptCell.contentEditable = 'true';
    expectedCell.contentEditable = 'true';
  });
  
  // Add extra empty row for new entries
  const emptyRow = promptsTableBody.insertRow();
  const emptyPromptCell = emptyRow.insertCell(0);
  const emptyExpectedCell = emptyRow.insertCell(1);
  emptyPromptCell.contentEditable = 'true';
  emptyExpectedCell.contentEditable = 'true';
  
  // Load initial benchmark data
  loadBenchmarks();
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', initPage);
