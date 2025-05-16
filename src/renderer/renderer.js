// Navigation handler
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
  
  // Validate inputs
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
  
  // Start benchmark run
  window.electronAPI.runBenchmark(prompts, selectedPdfPath, selectedModels)
    .then(() => {
      navigateTo('consoleContent'); // Navigate to console to show progress
    })
    .catch(error => {
      alert(`Error starting benchmark: ${error}`);
    });
});

// Load benchmark data
async function loadBenchmarks() {
  try {
    const benchmarks = await window.electronAPI.listBenchmarks();
    renderBenchmarks(benchmarks);
  } catch (error) {
    console.error('Error loading benchmarks:', error);
    document.getElementById('benchmarksGrid').innerHTML = 
      '<div class="error">Error loading benchmarks</div>';
  }
}

// Render benchmarks in grid and table views
function renderBenchmarks(benchmarks) {
  const gridContainer = document.getElementById('benchmarksGrid');
  const tableBody = document.getElementById('benchmarksTable').querySelector('tbody');
  
  // Clear existing content
  gridContainer.innerHTML = '';
  tableBody.innerHTML = '';
  
  if (benchmarks.length === 0) {
    gridContainer.innerHTML = '<div class="empty">No benchmarks found</div>';
    return;
  }
  
  // Populate grid view
  benchmarks.forEach(benchmark => {
    const card = document.createElement('div');
    card.className = 'benchmark-card';
    card.innerHTML = `
      <h3>${benchmark.label || 'Benchmark ' + benchmark.id}</h3>
      <p>Date: ${benchmark.timestamp}</p>
      <p>Models: ${benchmark.models ? benchmark.models.join(', ') : 'N/A'}</p>
      <button class="view-btn" data-id="${benchmark.id}">View Details</button>
    `;
    
    card.querySelector('.view-btn').addEventListener('click', () => {
      viewBenchmarkDetails(benchmark.id);
    });
    
    gridContainer.appendChild(card);
  });
  
  // Populate table view
  benchmarks.forEach(benchmark => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><span class="status-indicator ${benchmark.status || 'completed'}"></span></td>
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

// View benchmark details
function viewBenchmarkDetails(benchmarkId) {
  window.electronAPI.getBenchmarkDetails(benchmarkId)
    .then(details => {
      // Display benchmark details in console view
      const consoleLog = document.getElementById('consoleLog');
      consoleLog.innerHTML = `
        <h2>Benchmark Details (ID: ${details.id})</h2>
        <p>Run at: ${details.timestamp}</p>
        <p>PDF: ${details.pdf_path || 'N/A'}</p>
        <p>Models: ${details.models ? details.models.join(', ') : 'N/A'}</p>
        <p>Mean Score: ${details.mean_score !== undefined ? details.mean_score : 'N/A'}</p>
        <p>Total Items: ${details.total_items !== undefined ? details.total_items : 'N/A'}</p>
        <p>Elapsed Time: ${details.elapsed_seconds !== undefined ? details.elapsed_seconds + 's' : 'N/A'}</p>
        
        <h3>Detailed Results</h3>
      `;
      
      if (details.prompts_data && details.prompts_data.length > 0) {
        details.prompts_data.forEach((prompt, index) => {
          consoleLog.innerHTML += `
            <div class="prompt-result">
              <p><strong>Prompt ${index + 1}:</strong> ${prompt.prompt_text}</p>
              <p><strong>Expected:</strong> ${prompt.expected_answer}</p>
              <p><strong>Answer:</strong> ${prompt.actual_answer}</p>
              <p><strong>Score:</strong> ${prompt.score}</p>
            </div>
          `;
        });
      } else {
        consoleLog.innerHTML += '<p>No detailed prompt data available for this run.</p>';
      }
      
      navigateTo('consoleContent');
    })
    .catch(error => {
      alert(`Error loading benchmark details: ${error}`);
    });
}

// Listen for progress updates
window.electronAPI.onBenchmarkProgress(data => {
  // Update progress indicators
  console.log('Benchmark progress:', data);
  
  // Update the console log if we're on the console page
  const consoleLog = document.getElementById('consoleLog');
  if (document.getElementById('consoleContent').classList.contains('active')) {
    consoleLog.innerHTML += `<p class="log-entry">${data.message}</p>`;
    consoleLog.scrollTop = consoleLog.scrollHeight; // Auto-scroll to bottom
  }
});

// Listen for completion updates
window.electronAPI.onBenchmarkComplete(data => {
  // Update UI when benchmark completes
  console.log('Benchmark complete:', data);
  
  // Show completion message
  const consoleLog = document.getElementById('consoleLog');
  if (document.getElementById('consoleContent').classList.contains('active')) {
    consoleLog.innerHTML += `
      <div class="completion-message">
        <p><strong>Benchmark Complete!</strong></p>
        <p>Mean Score: ${data.mean_score}</p>
        <p>Total Items: ${data.total_items}</p>
        <p>Elapsed Time: ${data.elapsed_seconds}s</p>
      </div>
    `;
    consoleLog.scrollTop = consoleLog.scrollHeight;
  }
  
  loadBenchmarks(); // Refresh benchmark list
});

// Initialize page
function initPage() {
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
  
  // Add model options
  const modelList = document.getElementById('modelList');
  const models = [
    "gpt-4o", "gpt-4o-mini", "claude-3-opus", "claude-3-sonnet", 
    "gpt-4-turbo", "gpt-4", "claude-3-haiku"
  ];
  
  models.forEach(model => {
    const label = document.createElement('label');
    label.className = 'model-option';
    label.innerHTML = `
      <input type="checkbox" value="${model}" ${model === 'gpt-4o-mini' ? 'checked' : ''}>
      ${model}
    `;
    modelList.appendChild(label);
  });
  
  // Load initial benchmark data
  loadBenchmarks();
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', initPage);
