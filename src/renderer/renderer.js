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
        if (result.success) {
          alert(`Benchmark exported to CSV successfully!\nSaved to: ${result.filepath}`);
        } else {
          alert(`Error exporting benchmark: ${result.error}`);
        }
      })
      .catch(error => {
        console.error('Export error:', error);
        alert(`Error exporting benchmark: ${error.message || error}`);
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
      // Show success message and navigate home
      alert(`Benchmark "${benchmarkName}" started successfully!\n\nYou can view progress by clicking on the benchmark card.`);
      navigateTo('homeContent');
      loadBenchmarks(); // Refresh the list to show the new benchmark
    })
    .catch(error => {
      alert(`Error starting benchmark: ${error}`);
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
  if (gridContainer) {
    gridContainer.innerHTML = '<div class="loading">Loading benchmarks...</div>';
  }
  
  try {
    console.log('Loading benchmarks...');
    const benchmarks = await window.electronAPI.listBenchmarks();
    console.log('Benchmarks loaded:', benchmarks);
    
    if (!benchmarks || !Array.isArray(benchmarks)) {
      throw new Error('Invalid benchmark data received');
    }
    
    // Clear the loading message and render the benchmarks
    if (gridContainer) {
      gridContainer.innerHTML = '';
    }
    renderBenchmarks(benchmarks);
  } catch (error) {
    console.error('Error loading benchmarks:', error);
    if (gridContainer) {
      gridContainer.innerHTML = `
        <div class="error">
          <h3>Error loading benchmarks</h3>
          <p>${error.message}</p>
        </div>
      `;
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
    
    // Check if benchmark is in progress
    // Determine proper status text and class - default to 'in-progress' if not explicitly 'completed'
    // This ensures new benchmarks show as 'in progress' instead of immediately showing as 'complete'
    const benchmarkStatus = benchmark.status || 'running';
    const isInProgress = benchmarkStatus === 'running' || benchmarkStatus === 'pending';
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
      const benchmarkName = benchmark.label || 'Benchmark ' + benchmark.id;
      if (confirm(`Are you sure you want to delete benchmark '${benchmarkName}'? This action cannot be undone.`)) {
        handleDeleteBenchmark(benchmarkId);
      }
    });
    
    gridContainer.appendChild(card);
  });
  
  // Populate table view
  benchmarks.forEach(benchmark => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><span class="status-indicator ${benchmark.status || 'running'}"></span></td>
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
  console.log(`Requesting details for benchmark ID: ${benchmarkId}`);
  const details = await window.electronAPI.getBenchmarkDetails(benchmarkId);
  console.log('Received benchmark details:', details);

  if (!details) {
    alert('Could not load details for this benchmark.');
    return;
  }

    // Populate consoleLog with details
    const consoleLog = document.getElementById('consoleLog');
    // Basic display - customize as needed
    consoleLog.innerHTML = `
      <h2>Benchmark Details (ID: ${details.id})</h2>
      <p><strong>Name:</strong> ${details.label || 'N/A'}</p>
      <p><strong>Description:</strong> ${details.description || 'N/A'}</p>
      <p><strong>Timestamp:</strong> ${details.timestamp}</p>
      <p><strong>Models:</strong> ${details.models ? details.models.join(', ') : 'N/A'}</p>
      <p><strong>PDF File(s):</strong> ${details.files ? details.files.join(', ') : 'N/A'}</p>
      <h3>Results:</h3>
      <pre>${JSON.stringify(details.results, null, 2)}</pre>
      <button id="exportCsvBtnCurrent">Export This Benchmark to CSV</button>
    `;
    
    // Add export button event listener
    const exportBtn = document.getElementById('exportCsvBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        window.electronAPI.exportBenchmarkToCsv(details.id)
          .then(result => {
            if (result.success) {
              alert(`Benchmark exported successfully to ${result.filepath}`);
            } else {
              alert(`Error exporting benchmark: ${result.error}`);
            }
          })
          .catch(error => {
            console.error('Export error:', error);
            alert(`Error exporting benchmark: ${error.message || error}`);
          });
      });
    }

    navigateTo('consoleContent'); // Switch to the console view
}

// Handle benchmark deletion
async function handleDeleteBenchmark(benchmarkId) {
  console.log(`Requesting deletion for benchmark ID: ${benchmarkId}`);
  const result = await window.electronAPI.deleteBenchmark(benchmarkId);
  if (result && result.success) {
    alert('Benchmark deleted successfully.');
    loadBenchmarks(); // Refresh the list
  } else {
    alert(`Failed to delete benchmark: ${result ? result.error : 'Unknown error'}`);
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
      <p>Total Items: <strong>${data.total_items || '0'}</strong></p>
      <p>Elapsed Time: <strong>${data.elapsed_seconds || '0'}</strong> seconds</p>
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
  const promptsTable = document.getElementById('promptsTable');
  const defaultPrompts = [
    {prompt: "what year did this piece get written", expected: "2025"},
    {prompt: "what is happening faster, decarbonization or electrification", expected: "decarbonization"},
    {prompt: "whats the meaning of the title of this piece", expected: "heliocentrism means the solar and green transition is further away than it appears to optimists, they imagine exponential growth of solar despite the necessity of other energies like natural gas and the fact that energy transitions are linear not exponential"}
  ];
  
  defaultPrompts.forEach(item => {
    const row = promptsTable.insertRow();
    const promptCell = row.insertCell(0);
    const expectedCell = row.insertCell(1);
    promptCell.textContent = item.prompt;
    expectedCell.textContent = item.expected;
    
    // Make cells editable
    promptCell.contentEditable = 'true';
    expectedCell.contentEditable = 'true';
  });
  
  // Add extra empty row for new entries
  const emptyRow = promptsTable.insertRow();
  const emptyPromptCell = emptyRow.insertCell(0);
  const emptyExpectedCell = emptyRow.insertCell(1);
  emptyPromptCell.contentEditable = 'true';
  emptyExpectedCell.contentEditable = 'true';
  
  // Load initial benchmark data
  loadBenchmarks();
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', initPage);
