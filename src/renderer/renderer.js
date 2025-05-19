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
let benchmarksData = []; // Initialize benchmarksData array

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
  
  // PDF is now optional - no validation needed
  
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
      
      // Ensure benchmarkName is accessible here or passed if needed
      const benchmarkNameInput = document.getElementById('benchmarkNameInput');
      const benchmarkName = benchmarkNameInput ? benchmarkNameInput.value.trim() : 'Unnamed Benchmark';

      if (result && result.status === 'success' && result.launched_benchmark_item) { 
        showNotification(`Benchmark "${benchmarkName}" started successfully!`, 'success');
        
        // OPTIMISTIC UPDATE:
        if (!Array.isArray(benchmarksData)) {
            benchmarksData = [];
        }
        // Add to the beginning for most recent items to appear first
        benchmarksData.unshift(result.launched_benchmark_item); 
        renderBenchmarks(benchmarksData); 

        navigateTo('homeContent');
        
        // Keep setTimeout for loadBenchmarks to re-sync after a delay
        setTimeout(() => {
          // Use the enhanced loadBenchmarks with options to preserve in-progress status
          loadBenchmarks({preserveInProgressStatus: true, silentRefresh: true}).then(() => {
            console.log('Benchmarks re-synced after launch with preserved in-progress status');
            // Optional: view details if needed, using ID from launched_benchmark_item
            // if (result.launched_benchmark_item && result.launched_benchmark_item.id) {
            //   setTimeout(() => viewBenchmarkDetails(result.launched_benchmark_item.id), 300);
            // }
          });
        }, 2000); // Slightly longer delay to ensure UI stability 
      } else if (result && result.status === 'success') {
        // Fallback if launched_benchmark_item is missing but still success
        showNotification(`Benchmark "${benchmarkName}" started successfully! (Awaiting details)`, 'success');
        navigateTo('homeContent');
        const gridContainer = document.getElementById('benchmarksGrid');
        if (gridContainer) {
          gridContainer.innerHTML = '<div class="loading">Loading benchmark details...</div>';
        }
        setTimeout(loadBenchmarks, 1000); 
      } else {
        // Use result.message from backend if available, otherwise a generic error
        const errorMessage = result?.message || result?.error || 'Failed to start benchmark - unknown reason';
        throw new Error(errorMessage);
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

// Track deleted benchmark IDs to avoid re-rendering them
let deletedBenchmarkIds = new Set();

// Load benchmark data
async function loadBenchmarks(options = {}) {
  try {
    const homeContent = document.getElementById('homeContent');
    const gridContainer = document.getElementById('benchmarksGrid');
    const tableBody = document.getElementById('benchmarksTable').querySelector('tbody');
    
    if (homeContent && gridContainer && tableBody) {
      // Skip loading indicators if this is a silent refresh (to avoid flashing)
      if (!options.silentRefresh) {
        // Show loading indicators
        gridContainer.innerHTML = '<div class="loading">Loading benchmarks...</div>';
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center">Loading...</td></tr>';
      }
      
      // Store the previous state of benchmarks before fetching new data
      const previousStatus = {};
      
      // First, capture status of currently visible benchmarks
      document.querySelectorAll('.benchmark-card').forEach(card => {
        if (card.dataset.benchmarkId) {
          const id = parseInt(card.dataset.benchmarkId, 10);
          const status = card.dataset.status; // 'in-progress' or 'complete'
          previousStatus[id] = status;
          console.log(`Saved current UI status for benchmark ${id}: ${status}`);
        }
      });
      
      // Fetch benchmarks from the API
      const benchmarks = await window.electronAPI.listBenchmarks();
      
      if (!benchmarks || benchmarks.length === 0) {
        gridContainer.innerHTML = '<div class="empty-state">No benchmarks available. Create a new benchmark to get started.</div>';
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center">No benchmarks available</td></tr>';
        return;
      }
      
      // Filter out any benchmarks we know were deleted locally
      const filteredBenchmarks = benchmarks.filter(benchmark => !deletedBenchmarkIds.has(benchmark.id));
      
      if (benchmarks.length !== filteredBenchmarks.length) {
        const removedIds = benchmarks
          .filter(b => deletedBenchmarkIds.has(b.id))
          .map(b => b.id);
        console.log(`Filtered out ${benchmarks.length - filteredBenchmarks.length} deleted benchmarks from UI: IDs ${removedIds.join(', ')}`);
      }
      
      // Apply status preservation logic - CRITICAL FIX
      filteredBenchmarks.forEach(benchmark => {
        const id = benchmark.id;
        
        // 1. If backend says 'running', ALWAYS show as running, override any saved state
        if (benchmark.status === 'running') {
          console.log(`Backend reports benchmark ${id} as running - preserving running status`);
          benchmark.status = 'running';
        }
        // 2. If benchmark was previously COMPLETE, we need to KEEP it as complete
        // even if the API is confused due to another benchmark running
        else if (previousStatus[id] === 'complete') {
          console.log(`Preserving COMPLETE status for benchmark ${id} from UI state`);
          benchmark.status = 'complete';
        }
        // 3. Default case - use what the backend says if we don't have special handling
      });
      
      // Update the UI with fetched benchmarks
      renderBenchmarks(filteredBenchmarks);
      
      // Update our stored data reference - store the filtered version
      benchmarksData = filteredBenchmarks;
    }
  } catch (error) {
    console.error('Error loading benchmarks:', error);
    const gridContainer = document.getElementById('benchmarksGrid');
    const tableBody = document.getElementById('benchmarksTable').querySelector('tbody');
    
    if (gridContainer && !options.silentRefresh) {
      gridContainer.innerHTML = `<div class="error-state">Error loading benchmarks: ${error.message}</div>`;
    }
    
    if (tableBody && !options.silentRefresh) {
      tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-red-600">Error: ${error.message}</td></tr>`;
    }
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
    
    // Use the status directly from the backend
    let benchmarkStatus = benchmark.status || 'in-progress';
    
    // Normalize status values
    if (benchmarkStatus === 'running' || benchmarkStatus === 'progress') {
      benchmarkStatus = 'in-progress';
    } else if (benchmark.all_models_complete) {
      benchmarkStatus = 'complete';
    }
    
    // A benchmark is only complete when all models are complete
    const isInProgress = benchmarkStatus !== 'complete';
    const statusClass = isInProgress ? 'status-in-progress' : 'status-complete';
    const statusText = isInProgress ? 'In Progress' : 'Complete';
    
    console.log(`Benchmark ${benchmark.id} (${benchmark.label}) status: ${benchmarkStatus}, isInProgress: ${isInProgress}`);
    
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
    // Use the same status determination logic as grid view
    let benchmarkStatus = benchmark.status || 'in-progress';
    
    // Normalize status values
    if (benchmarkStatus === 'running' || benchmarkStatus === 'progress') {
      benchmarkStatus = 'in-progress';
    } else if (benchmark.all_models_complete) {
      benchmarkStatus = 'complete';
    }
    
    // A benchmark is only complete when all models are complete
    const isInProgress = benchmarkStatus !== 'complete';
    const statusClass = isInProgress ? 'in-progress' : 'complete';
    const statusText = isInProgress ? 'In Progress' : 'Complete';
    
    console.log(`Table view: Benchmark ${benchmark.id} (${benchmark.label}) status: ${benchmarkStatus}, isInProgress: ${isInProgress}`);
    
    const row = document.createElement('tr');
    row.dataset.status = statusClass;
    row.dataset.benchmarkId = benchmark.id;
    
    row.innerHTML = `
      <td><span class="status-indicator ${statusClass}"></span></td>
      <td>${benchmark.label || 'Benchmark ' + benchmark.id}</td>
      <td>${benchmark.timestamp}</td>
      <td>${benchmark.model_names ? benchmark.model_names.join(', ') : 'N/A'}</td>
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
                <th>Model</th>
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
                  <td>${p.model_name || 'N/A'}</td>
                  <td>${p.prompt_text}</td>
                  <td>${p.expected_answer || 'N/A'}</td>
                  <td>${p.model_answer || 'N/A'}</td>
                  <td>${typeof p.score === 'number' ? p.score.toFixed(2) : p.score}</td>
                  <td>${p.prompt_latency !== undefined ? p.prompt_latency : (p.latency !== undefined ? p.latency : 'N/A')}</td>
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
                // Create a hidden anchor element to download without opening a window
                const downloadLink = document.createElement('a');
                downloadLink.href = result.url;
                downloadLink.download = `benchmark-${benchmarkId}.csv`;
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
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
  // Confirm deletion
  const confirmDelete = confirm(`Are you sure you want to delete this benchmark?`);
  if (!confirmDelete) {
    return;
  }
  
  try {
    // Immediately record this as deleted to ensure it doesn't reappear in UI
    const benchmarkIdNumber = parseInt(benchmarkId, 10);
    deletedBenchmarkIds.add(benchmarkIdNumber);
    console.log(`Added benchmark ID ${benchmarkIdNumber} to frontend deleted benchmarks list`);
    
    // Show loading state
    const card = document.querySelector(`.benchmark-card[data-benchmark-id="${benchmarkId}"]`);
    if (card) {
      card.classList.add('deleting');
    }
    
    // Call the API to delete the benchmark
    const result = await window.electronAPI.deleteBenchmark(benchmarkId);
    
    if (result.success) {
      // Show success notification
      showNotification('Benchmark deleted successfully', 'success');
      
      // Remove the benchmark card immediately from UI without waiting for database
      if (card) {
        card.remove();
        console.log(`Removed benchmark card ID ${benchmarkId} from UI immediately`);
      }
      
      // Add a small delay to ensure the database is updated
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Force a complete refresh but preserve status of completed benchmarks
      const gridContainer = document.getElementById('benchmarksGrid');
      if (gridContainer) {
        // Show loading state only if we don't have any remaining cards
        const remainingCards = document.querySelectorAll('.benchmark-card');
        if (remainingCards.length === 0) {
          gridContainer.innerHTML = '<div class="loading">Refreshing benchmarks...</div>';
        }
      }
      
      // Use our enhanced loadBenchmarks that preserves completed status and filters deleted items
      await loadBenchmarks({silentRefresh: true});
      console.log('Refreshed benchmarks with deleted IDs filtered out');
      
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
        // CRITICAL FIX: Only update to "Complete" if this is the overall job status, not just a model completing
        // Check if this is a progress update for an individual model or the entire benchmark
        const isModelUpdate = data.model_name && data.status === 'complete';
        const isFullJobComplete = !data.model_name && data.status === 'complete';
        
        if (isFullJobComplete) {
          // Only update to Complete if the entire job/benchmark is done
          statusBadge.textContent = 'Complete';
          statusBadge.className = 'status-badge status-complete';
          benchmarkCard.dataset.status = 'complete';
          
          // Switch to View Details button if we're still showing View Logs
          const viewLogsBtn = benchmarkCard.querySelector('.view-logs-btn');
          if (viewLogsBtn) {
            viewLogsBtn.textContent = 'View Details';
            viewLogsBtn.className = 'view-btn';
          }
          console.log('Benchmark fully complete, showing Complete status');
        } else if (data.status === 'progress' || isModelUpdate) {
          // For progress updates OR when a single model completes (but not all models)
          statusBadge.textContent = 'In Progress';
          statusBadge.className = 'status-badge status-in-progress';
          benchmarkCard.dataset.status = 'in-progress';
          
          if (isModelUpdate) {
            console.log(`Individual model ${data.model_name} complete, but benchmark still in progress`);
          }
        }
      }
    }
  }
});

window.electronAPI.onBenchmarkComplete(data => {
  console.log('Benchmark complete event received:', data);
  
  if (!data || !data.benchmark_id) {
    console.error('Invalid benchmark completion data:', data);
    return;
  }
  
  // Check if this is a transition from in-progress to complete
  const previousStatus = benchmarkStatuses.get(data.benchmark_id);
  console.log(`Checking status transition for benchmark ${data.benchmark_id}:`, {
    previousStatus,
    currentStatus: 'complete',
    data
  });
  
  // Only play sound if this is a real transition from in-progress to complete
  if (previousStatus === 'in-progress') {
    console.log(`Playing sound for benchmark ${data.benchmark_id} completing (was ${previousStatus})`);
    // Make sure we have the audio element ready
    const woohooSound = document.getElementById('woohoo-sound');
    if (woohooSound) {
      console.log('Found audio element, playing sound...');
      woohooSound.currentTime = 0;
      woohooSound.play().catch(err => {
        console.error('Error playing sound:', err);
      });
    } else {
      console.error('Audio element not found!');
    }
  } else {
    console.log(`Skipping sound for benchmark ${data.benchmark_id} - no status transition (was ${previousStatus})`);
  }
  
  // Update stored status
  benchmarkStatuses.set(data.benchmark_id, 'complete');

  // Update progress display and status
  const benchmarkElement = document.querySelector(`[data-benchmark-id="${data.benchmark_id}"]`);
  if (benchmarkElement) {
    // Update the progress text
    const progressElement = benchmarkElement.querySelector('.benchmark-progress');
    if (progressElement) {
      progressElement.textContent = `Complete - Score: ${data.mean_score.toFixed(2)}`;
    }

    // Update the status badge
    const statusBadge = benchmarkElement.querySelector('.status-badge');
    if (statusBadge) {
      statusBadge.textContent = 'Complete';
      statusBadge.className = 'status-badge status-complete';
    }

    // Update the benchmark card's status
    benchmarkElement.dataset.status = 'complete';
  }

  // Add completion message to console
  const completionDiv = document.createElement('div');
  completionDiv.className = 'completion-message';
  
  if (data.all_models_complete) {
    completionDiv.innerHTML = `
      <p style="font-weight: 600; color: #48bb78; margin-bottom: 8px;">✅ All Models Complete!</p>
      <p>Mean Score: <strong>${data.mean_score || 'N/A'}</strong></p>
      <p>Elapsed Time: <strong>${data.elapsed_s || data.duration_seconds || '0'}</strong> seconds</p>
    `;
  } else {
    completionDiv.innerHTML = `
      <p style="font-weight: 600; color: #4299e1; margin-bottom: 8px;">✓ Model ${data.model_name} Complete!</p>
      <p>Mean Score: <strong>${data.mean_score || 'N/A'}</strong></p>
      <p>Elapsed Time: <strong>${data.elapsed_s || data.duration_seconds || '0'}</strong> seconds</p>
      <p><small>Waiting for other models to complete...</small></p>
    `;
  }
  
  const consoleLog = document.getElementById('consoleLog');
  if (consoleLog) {
    consoleLog.appendChild(completionDiv);
    consoleLog.scrollTop = consoleLog.scrollHeight;
    // Auto-hide notification after 3 seconds
    setTimeout(() => {
      notification.classList.add('show');
    }, 100);
  }
});

// Listen for progress updates
window.electronAPI.onBenchmarkProgress(data => {
  console.log('Progress event received:', data);
  
  if (data.benchmark_id) {
    // Track status changes
    if (data.status === 'running' || data.message?.includes('Starting benchmark')) {
      console.log(`Marking benchmark ${data.benchmark_id} as in-progress (status: ${data.status}, message: ${data.message})`);
      benchmarkStatuses.set(data.benchmark_id, 'in-progress');
    }
    
    // Update UI for progress
    const benchmarkCard = document.querySelector(`[data-benchmark-id="${data.benchmark_id}"]`);
    if (benchmarkCard) {
      const statusBadge = benchmarkCard.querySelector('.status-badge');
      if (statusBadge) {
        if (data.status === 'running' || data.status === 'progress' || data.message?.includes('Starting benchmark')) {
          statusBadge.textContent = 'In Progress';
          statusBadge.className = 'status-badge status-in-progress';
          benchmarkCard.dataset.status = 'in-progress';
        }
      }
    }
  }
});

window.electronAPI.onBenchmarkComplete(data => {
  console.log('Benchmark complete event received:', data);
  
  if (!data || !data.benchmark_id) {
    console.error('Invalid benchmark completion data:', data);
    return;
  }
  
  // Check if this is a transition from in-progress to complete
  const previousStatus = benchmarkStatuses.get(data.benchmark_id);
  console.log(`Checking status transition for benchmark ${data.benchmark_id}:`, {
    previousStatus,
    currentStatus: 'complete',
    data
  });
  
  // Only play sound if this is a real transition from in-progress to complete
  if (previousStatus === 'in-progress') {
    console.log(`Playing sound for benchmark ${data.benchmark_id} completing (was ${previousStatus})`);
    // Make sure we have the audio element ready
    const woohooSound = document.getElementById('woohoo-sound');
    if (woohooSound) {
      console.log('Found audio element, playing sound...');
      woohooSound.currentTime = 0;
      woohooSound.play().catch(err => {
        console.error('Error playing sound:', err);
      });
    } else {
      console.error('Audio element not found!');
    }
  } else {
    console.log(`Skipping sound for benchmark ${data.benchmark_id} - no status transition (was ${previousStatus})`);
  }
  
  // Update stored status
  benchmarkStatuses.set(data.benchmark_id, 'complete');

  // Update progress display and status
  const benchmarkElement = document.querySelector(`[data-benchmark-id="${data.benchmark_id}"]`);
  if (benchmarkElement) {
    // Update the progress text
    const progressElement = benchmarkElement.querySelector('.benchmark-progress');
    if (progressElement) {
      progressElement.textContent = `Complete - Score: ${data.mean_score.toFixed(2)}`;
    }

    // Update the status badge
    const statusBadge = benchmarkElement.querySelector('.status-badge');
    if (statusBadge) {
      statusBadge.textContent = 'Complete';
      statusBadge.className = 'status-badge status-complete';
    }

    // Update the benchmark card's status
    benchmarkElement.dataset.status = 'complete';
  }

  // Add completion message to console
  const completionDiv = document.createElement('div');
  completionDiv.className = 'completion-message';
  
  if (data.all_models_complete) {
    completionDiv.innerHTML = `
      <p style="font-weight: 600; color: #48bb78; margin-bottom: 8px;">✅ All Models Complete!</p>
      <p>Mean Score: <strong>${data.mean_score || 'N/A'}</strong></p>
      <p>Elapsed Time: <strong>${data.elapsed_s || data.duration_seconds || '0'}</strong> seconds</p>
    `;
  } else {
    completionDiv.innerHTML = `
      <p style="font-weight: 600; color: #4299e1; margin-bottom: 8px;">✓ Model ${data.model_name} Complete!</p>
      <p>Mean Score: <strong>${data.mean_score || 'N/A'}</strong></p>
      <p>Elapsed Time: <strong>${data.elapsed_s || data.duration_seconds || '0'}</strong> seconds</p>
      <p><small>Waiting for other models to complete...</small></p>
    `;
  }
  
  const consoleLog = document.getElementById('consoleLog');
  if (consoleLog) {
    consoleLog.appendChild(completionDiv);
    consoleLog.scrollTop = consoleLog.scrollHeight;
    // Auto-hide notification after 3 seconds
    setTimeout(() => {
      notification.classList.add('show');
    }, 100);
  }
});

// Keep track of benchmark statuses
const benchmarkStatuses = new Map();

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
  console.log('Main process ready - initializing application'); // Updated log message
  
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
  
  // Add default prompt rows (empty for now)
  const promptsTableBody = document.getElementById('promptsTable').querySelector('tbody');
  const defaultPrompts = [];

  // Add "Add Row" button after the table
  const addRowBtn = document.createElement('button');
  addRowBtn.textContent = 'Add Row';
  addRowBtn.className = 'button';
  addRowBtn.style.marginTop = '10px';
  document.getElementById('promptsTable').parentNode.insertBefore(addRowBtn, document.getElementById('promptsTable').nextSibling);

  // Function to add a new row
  function addNewRow() {
    const row = promptsTableBody.insertRow();
    const promptCell = row.insertCell(0);
    const expectedCell = row.insertCell(1);
    
    // Make cells editable
    promptCell.contentEditable = 'true';
    expectedCell.contentEditable = 'true';
    
    // Add placeholder text
    promptCell.textContent = 'Enter prompt...';
    expectedCell.textContent = 'Enter expected answer...';

    // Clear placeholder on focus
    promptCell.addEventListener('focus', function() {
      if (this.textContent === 'Enter prompt...') {
        this.textContent = '';
      }
    });

    expectedCell.addEventListener('focus', function() {
      if (this.textContent === 'Enter expected answer...') {
        this.textContent = '';
      }
    });
  }

  // Add row button click handler
  addRowBtn.addEventListener('click', addNewRow);
  
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

// NEW WAY: Wait for the main process to signal it's ready
if (window.electronAPI && typeof window.electronAPI.onMainProcessReady === 'function') {
  window.electronAPI.onMainProcessReady(async () => {
    console.log('Renderer received main-process-ready signal. Initializing page...');
    await initPage();
  });
} else {
  console.error('electronAPI.onMainProcessReady is not available. Page initialization will not occur automatically. This may indicate an issue with preload.js.');
  // Fallback to old method if really necessary, but it might re-introduce the bug.
  // document.addEventListener('DOMContentLoaded', async () => {
  //   console.warn('Falling back to DOMContentLoaded for initPage due to missing onMainProcessReady.');
  //   await initPage();
  // });
}

// Ensure any other direct calls to initPage or functions within it that depend on main process readiness
// are also covered by this new mechanism or are confirmed safe to run earlier.
