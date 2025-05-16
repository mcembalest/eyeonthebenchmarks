# EOTM Benchmark Todos

## [MAJOR REFACTOR - HIGH PRIORITY] Qt to Electron Migration

### Quick Start - 90 Minutes Implementation

#### Step 1: Initial Project Setup (15 minutes)
```bash
# Create project directory structure
mkdir -p eotm-electron/{src,src/main,src/renderer,src/preload}

# Initialize npm project
cd eotm-electron
npm init -y

# Install essential dependencies
npm install --save electron electron-builder python-shell
npm install --save-dev electron-packager

# Create basic package.json configuration
```

package.json essentials:
```json
{
  "name": "eotm-electron",
  "version": "1.0.0",
  "description": "EOTM Benchmark Tool",
  "main": "src/main/main.js",
  "scripts": {
    "start": "electron .",
    "build": "electron-builder"
  },
  "dependencies": {
    "electron": "^30.0.0",
    "python-shell": "^5.0.0"
  },
  "devDependencies": {
    "electron-packager": "^17.1.2"
  }
}
```

#### Step 2: Create Minimal Main Process (15 minutes)
src/main/main.js:
```javascript
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { PythonShell } = require('python-shell');

// Store reference to main window
let mainWindow;

// Python process paths (relative to original application)
const pythonPath = path.join(__dirname, '../../../eyeonthebenchmarks');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/preload.js')
    }
  });

  // Load the index.html file
  mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));

  // Set application icon (macOS dock)
  if (process.platform === 'darwin') {
    app.dock.setIcon(path.join(__dirname, '../renderer/assets/icon.png'));
  }
}

// Create window when app is ready
app.whenReady().then(createWindow);

// Basic IPC handlers for UI bridge
ipcMain.handle('open-file-dialog', async (event, options) => {
  const { filePaths } = await dialog.showOpenDialog(mainWindow, options);
  return filePaths.length > 0 ? filePaths[0] : null;
});

// Python bridge function - simplified initial implementation
function runPythonCommand(command, args) {
  return new Promise((resolve, reject) => {
    const options = {
      mode: 'text',
      pythonPath: 'python',  // Use system Python
      pythonOptions: ['-u'], // Unbuffered
      scriptPath: pythonPath,
      args: args
    };
    
    PythonShell.run(command, options, (err, results) => {
      if (err) reject(err);
      else resolve(results);
    });
  });
}

// Example IPC for benchmark listing
ipcMain.handle('list-benchmarks', async () => {
  try {
    const results = await runPythonCommand('list_benchmarks.py', []);
    return JSON.parse(results[0]); // Assuming Python script returns JSON
  } catch (error) {
    console.error('Error listing benchmarks:', error);
    return [];
  }
});

// Quit app when all windows are closed (Windows & Linux)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Re-create window on macOS when dock icon is clicked
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
```

#### Step 3: Create Preload Script (10 minutes)
src/preload/preload.js:
```javascript
const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use IPC
contextBridge.exposeInMainWorld('electronAPI', {
  // File dialogs
  openFileDialog: (options) => ipcRenderer.invoke('open-file-dialog', options),
  
  // Benchmark operations
  listBenchmarks: () => ipcRenderer.invoke('list-benchmarks'),
  runBenchmark: (prompts, pdfPath, modelNames) => {
    return ipcRenderer.invoke('run-benchmark', { prompts, pdfPath, modelNames });
  },
  getBenchmarkDetails: (id) => ipcRenderer.invoke('get-benchmark-details', id),
  
  // Navigation
  navigateTo: (page) => ipcRenderer.send('navigate-to', page),
  
  // System events - receive updates from main process
  onBenchmarkProgress: (callback) => {
    ipcRenderer.on('benchmark-progress', (event, data) => callback(data));
  },
  onBenchmarkComplete: (callback) => {
    ipcRenderer.on('benchmark-complete', (event, data) => callback(data));
  }
});
```

#### Step 4: Create Basic HTML/CSS for Home Page (20 minutes)
src/renderer/index.html:
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>EOTMBench</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>EOTM Benchmarks</h1>
      <button id="newBenchmarkBtn">New Benchmark</button>
    </header>
    
    <div id="homeContent" class="page active">
      <div class="view-toggle">
        <button id="gridViewBtn" class="active">Grid View</button>
        <button id="tableViewBtn">Table View</button>
      </div>
      
      <div id="benchmarksGrid" class="benchmarks-container grid-view active">
        <!-- Benchmark cards will be loaded here -->
        <div class="loading">Loading benchmarks...</div>
      </div>
      
      <table id="benchmarksTable" class="benchmarks-container table-view">
        <thead>
          <tr>
            <th>Status</th>
            <th>Label</th>
            <th>Date</th>
            <th>Models</th>
            <th>Files</th>
          </tr>
        </thead>
        <tbody>
          <!-- Benchmark rows will be loaded here -->
        </tbody>
      </table>
      
      <button id="refreshBtn">🔄 Refresh</button>
    </div>
    
    <div id="composerContent" class="page">
      <!-- Benchmark composer content will go here -->
      <div class="composer-container">
        <div class="prompts-section">
          <h2>Test Prompts</h2>
          <button id="importCsvBtn">Import from CSV</button>
          <table id="promptsTable">
            <thead>
              <tr>
                <th>Prompt</th>
                <th>Expected</th>
              </tr>
            </thead>
            <tbody>
              <!-- Default rows will be added by JavaScript -->
            </tbody>
          </table>
        </div>
        
        <div class="settings-section">
          <div class="model-selection">
            <h3>Select Model(s)</h3>
            <div id="modelList" class="model-list">
              <!-- Model options will be added by JavaScript -->
            </div>
          </div>
          
          <div class="pdf-selection">
            <h3>Select PDF</h3>
            <button id="selectPdfBtn">Select PDF</button>
            <span id="selectedPdfLabel">No PDF selected</span>
          </div>
        </div>
        
        <div class="actions">
          <button id="runBtn" class="primary">Run Benchmark ▸</button>
          <button id="returnHomeBtn">Return to Home</button>
        </div>
      </div>
    </div>
    
    <div id="consoleContent" class="page">
      <!-- Console output will go here -->
      <div id="consoleLog" class="console-log"></div>
      <div class="console-actions">
        <button id="exportCsvBtn">Export to CSV</button>
        <button id="consoleReturnBtn">Return to Home</button>
      </div>
    </div>
  </div>
  
  <script src="renderer.js"></script>
</body>
</html>
```

#### Step 5: Create Initial Renderer Logic (20 minutes)
src/renderer/renderer.js:
```javascript
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
      navigateTo('homeContent'); // Navigate back to home after starting run
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
      <h3>${benchmark.label}</h3>
      <p>Date: ${benchmark.timestamp}</p>
      <p>Models: ${benchmark.models.join(', ')}</p>
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
      <td><span class="status-indicator"></span></td>
      <td>${benchmark.label}</td>
      <td>${benchmark.timestamp}</td>
      <td>${benchmark.models.join(', ')}</td>
      <td>${benchmark.files.join(', ')}</td>
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
        <p>PDF: ${details.pdf_path}</p>
        <p>Model: ${details.model_name || 'N/A'}</p>
        <p>Mean Score: ${details.mean_score || 'N/A'}</p>
        <p>Total Items: ${details.total_items || 'N/A'}</p>
        <p>Elapsed Time: ${details.elapsed_seconds || 'N/A'}s</p>
        
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
});

// Listen for completion updates
window.electronAPI.onBenchmarkComplete(data => {
  // Update UI when benchmark completes
  console.log('Benchmark complete:', data);
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
  });
  
  // Add model options
  const modelList = document.getElementById('modelList');
  const models = [
    "gpt-4o", "gpt-4o-mini"
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
```

#### Step 6: Add Basic Styling (10 minutes)
src/renderer/styles.css:
```css
/* Base styles */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  margin: 0;
  padding: 0;
  background-color: #f4f5f7;
  color: #222;
}

#app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

header {
  background-color: #e0e3e8;
  padding: 10px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

header h1 {
  font-size: 24px;
  margin: 0;
  color: #2d3a4a;
}

button {
  background-color: #3a4657;
  color: white;
  border: 1px solid #2d3a4a;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
}

button:hover {
  background-color: #232b36;
}

button.primary {
  font-size: 16px;
  padding: 12px 20px;
}

/* Page container styles */
.page {
  display: none;
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.page.active {
  display: block;
}

/* Grid view */
.benchmarks-container {
  margin: 20px 0;
}

.benchmarks-container.grid-view {
  display: none;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}

.benchmarks-container.grid-view.active {
  display: grid;
}

.benchmark-card {
  background: #f7f8fa;
  border: 1.5px solid #c2c6cc;
  border-radius: 14px;
  padding: 20px;
}

.benchmark-card h3 {
  margin-top: 0;
  color: #2d3a4a;
}

/* Table view */
.benchmarks-container.table-view {
  display: none;
  width: 100%;
  border-collapse: collapse;
}

.benchmarks-container.table-view.active {
  display: table;
}

.benchmarks-container.table-view th {
  background-color: #e0e3e8;
  color: #2d3a4a;
  font-weight: bold;
  text-align: left;
  padding: 10px;
}

.benchmarks-container.table-view td {
  padding: 10px;
  border-bottom: 1px solid #e0e3e8;
}

.benchmarks-container.table-view tr:nth-child(even) {
  background-color: #f0f1f3;
}

.benchmarks-container.table-view tr:hover {
  background-color: #e0e3e8;
  cursor: pointer;
}

/* View toggle */
.view-toggle {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.view-toggle button {
  background-color: #e0e3e8;
  color: #2d3a4a;
}

.view-toggle button.active {
  background-color: #3a4657;
  color: white;
}

/* Composer page */
.composer-container {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

#promptsTable {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}

#promptsTable th {
  background-color: #e0e3e8;
  color: #2d3a4a;
  padding: 10px;
  text-align: left;
}

#promptsTable td {
  padding: 10px;
  border-bottom: 1px solid #e0e3e8;
}

.model-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.model-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.actions {
  grid-column: span 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
}

/* Console page */
.console-log {
  background-color: #fcfcfd;
  border: 1px solid #c2c6cc;
  border-radius: 4px;
  padding: 15px;
  margin-bottom: 20px;
  min-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  font-family: monospace;
}

.console-actions {
  display: flex;
  justify-content: space-between;
}

.prompt-result {
  margin-bottom: 20px;
  padding: 10px;
  border-left: 3px solid #3a4657;
  background-color: #f0f1f3;
}

/* Utilities */
.loading, .error, .empty {
  padding: 20px;
  text-align: center;
}

.error {
  color: #721c24;
  background-color: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 4px;
}

.empty {
  color: #666;
  font-style: italic;
}
```

#### Bridging Strategy for Python App Integration
1. Create a Python-to-JS bridge using a simple HTTP API approach or python-shell
2. Create a helper script to facilitate communication:

list_benchmarks.py (example bridge script):
```python
import sys
import json
from pathlib import Path
sys.path.append(str(Path.cwd()))

try:
    from engine.file_store import load_all_benchmarks_with_models
    benchmarks = load_all_benchmarks_with_models()
    print(json.dumps(benchmarks))
except Exception as e:
    print(json.dumps({"error": str(e)}))
```

#### Step 7: Integration Testing (10 minutes)
- Test running the Electron app with the existing Python codebase
- Test basic functionality: listing benchmarks, creating new benchmark, viewing results
- Fix any immediate issues

#### Step 8: Packaging and Distribution - Later Stage (not for 90-min version)
- Add electron-builder configuration
- Create installers for different platforms
- Test distribution packages

### Project Setup and Architecture
- [ ] Create Electron project structure
  - [ ] Set up package.json with required dependencies
  - [ ] Configure electron-builder for packaging
  - [ ] Create main.js for the main process
  - [ ] Establish preload.js for secure IPC communication
  - [ ] Set up folder structure for renderer process HTML/CSS/JS files

### Core Architecture Components
- [ ] Create ElectronUIBridgeImpl class implementing the AppUIBridge protocol
  - [ ] Implement IPC (inter-process communication) between main and renderer processes
  - [ ] Design proper thread-safety handling for async operations
  - [ ] Create synchronous and asynchronous bridge methods as needed
- [ ] Adapt AppLogic class to work with Electron
  - [ ] Ensure BenchmarkWorker works correctly in Node.js environment without Qt dependencies
  - [ ] Maintain the UI-agnostic design of the core business logic
- [ ] Design proper event handling system to replace Qt signals/slots
  - [ ] Replace QTimer with appropriate JavaScript alternatives

### UI Component Migration
- [ ] Port HomePage 
  - [ ] Create equivalent HTML/CSS/JS for the grid and table view of benchmarks
  - [ ] Implement card-based and table-based views with toggle functionality
  - [ ] Create refresh button and functionality
  - [ ] Migrate QTableWidget functionality to HTML tables with similar styling
- [ ] Port ComposerPage
  - [ ] Create form for benchmark creation with equivalent functionality
  - [ ] Implement editable table for prompts equivalent to QTableWidget
  - [ ] Add model selection list with checkboxes
  - [ ] Create PDF selection button and file handling
- [ ] Port RunConsoleWidget
  - [ ] Create console output display for benchmark runs
  - [ ] Implement auto-scrolling for new log entries
  - [ ] Add export to CSV and return to home buttons

### File and Dialog Operations
- [ ] Create Electron equivalents for all Qt dialog operations
  - [ ] Replace QFileDialog with Electron's dialog module
  - [ ] Implement PDF file selection dialog
  - [ ] Implement CSV import/export dialogs
- [ ] Ensure all file path handling works correctly in Electron environment
  - [ ] Adapt Path objects to work with Node.js path handling
  - [ ] Handle file permissions properly on all platforms

### Styling and Visual Components
- [ ] Convert Qt stylesheet (ui_styles.py) to CSS or other web styling
  - [ ] Consider using Tailwind CSS, styled-components, or similar modern approach
  - [ ] Port all CSS stylesheets from APP_STYLESHEET to web equivalents
  - [ ] Recreate CardSection styling and other custom widget styles
- [ ] Create responsive design considerations not present in original Qt app

### Platform Integration
- [ ] Replace macOS dock icon code (NSApplication) with Electron's app.dock API
- [ ] Handle platform-specific behaviors and ensure consistent experience
- [ ] Implement proper window management (minimize, maximize, close)

### Threading and Performance
- [ ] Replace threading approach from Qt to Node.js/Electron patterns
  - [ ] Replace QThread with worker_threads in Node.js or equivalent
  - [ ] Ensure proper IPC communication for worker threads
- [ ] Handle UI updates from background operations correctly
  - [ ] Replace QTimer.singleShot(0, lambda:...) patterns with appropriate alternatives

### Testing and Deployment
- [ ] Implement testing strategy for Electron app
- [ ] Create build and packaging scripts
- [ ] Test application on all target platforms (macOS, Windows, Linux)
- [ ] Create installer packages for distribution

## Core Focus & Application Goals
- [HIGH PRIORITY] Ensure overall benchmark creation and deployment process is extremely frictionless, especially for non-AI users.
- [HIGH PRIORITY] Enable easy export of benchmark results to **CSV files** (for analysis and chart creation in tools like Excel).
- [ ] (Clarify) No direct application-to-Excel integration needed. Output is CSV.
- [x] Decouple application logic from Qt (currently `[completed]` - UI bridge pattern implemented in main_qt.py)
- [ ] Implement VBA macro reception (if for Python-side execution of user-defined scoring logic, otherwise re-evaluate)
- [ ] Allow model customization (beyond predefined list)

## UI
- [ ] Display model icon next to model name consistently (including benchmark creation dropdown)
- [ ] Improve UI responsiveness during benchmark runs
- [ ] Add progress indicators for long operations (file uploads, benchmark runs)

## Models
### OpenAI
- [x] Add support for gpt4o (+mini) (currently `[done]`)
- [x] Add support for gpt4.1 (+mini, nano) (currently `[done]`)
- [x] **BUG**: gpt 4.1 nano did not save results even after a successful run (FIXED)
- [ ] Add support for o3-mini
- [ ] Add support for o3
- [ ] Add support for o4-mini
- [ ] Add support for gpt-image-1 (Likely an image generation model, see "Image Generation Benchmarks")

### Google
- [ ] Add support for Gemini 2.5 Flash
- [ ] Add support for Gemini 2.5 Pro
- [ ] (Consider Gemini models for image generation if applicable)
- [ ] Implement Google API client with proper authentication

## Cloud Providers & File Handling
### File Upload & Sync
- [x] **OpenAI**: Ensure files are sent after upload and not re-uploaded (check local DB) (currently `[done]`)
- [ ] **Google**: Implement file sending after upload (check local DB, avoid re-uploads)

### File Preprocessing (Indexes/Vector Stores)
- [ ] **OpenAI**: Preprocess files into indexes/vector stores in advance.
    - [ ] Create vector stores for all context files upon initial processing.
    - [ ] Use vector stores strategically: especially for very long documents (e.g., >N pages/tokens) where direct prompting is infeasible. Prefer full-text context for shorter documents.
- [ ] **Google**: Preprocess files into indexes/vector stores in advance (similar strategy).
    - [ ] Investigate using Google Cloud/Storage/Drive for Gemini.
    - [ ] Investigate using Vertex AI for Google models.

## Benchmarks
### Core Functionality
- [x] Save benchmarks (currently `[done]`)
- [x] Load benchmarks (currently `[done]`)
- [x] View benchmarks from load screen (currently `[done]`)
- [x] Create benchmarks from a CSV (currently `[done]`)
- [ ] **BUG**: New benchmark overwrites the last benchmark (Needs re-verification given user feedback)
- [x] **BUG**: Incorrect token count (FIXED - now correctly handling standard and cached tokens separately)
- [ ] Replace 'Answer' with 'Response' in UI and data structures where appropriate (clarify if 'Expected Answer' vs 'Model Response')

### Benchmark Creation
## Benchmark Execution

~~Currently, the benchmark creation process uses placeholder/filler data instead of actually running the models.~~ 

The benchmark execution now uses real OpenAI API calls with token counting and cost calculation. The following tasks represent the current state and future enhancements:

### API Integration
- [x] Integrate OpenAI models directly via `engine/models_openai.py`
  - [x] Support for GPT models (gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4)
  - [x] Implement proper API key handling via environment variables
  - [x] Add token counting for OpenAI models (standard and cached tokens)
- [ ] Create additional model-specific API clients for other providers
  - [ ] Create `anthropic_client.py` for Claude models (claude-3-opus, claude-3-sonnet, claude-3-haiku)
  - [ ] Create dedicated Google API client for Gemini models

### Benchmark Engine
- [x] Update `run_benchmark.py` to use real API calls instead of placeholder data
  - [x] Replace the placeholder code with actual API calls to the respective model providers (OpenAI implemented)
  - [x] Implement proper error handling for API rate limits, token limits, etc.
  - [x] Add progress reporting via IPC to show real-time benchmark status
  - [x] Implement proper token counting for both standard and cached inputs
  - [x] Calculate actual costs based on model pricing

### Scoring Implementation
- [x] Implement benchmark scoring for comparing expected vs. actual answers
  - [x] Basic exact match scoring
  - [x] Partial match scoring with length-based weighting
  - [x] Word overlap detection for partial credit
  - [ ] Semantic similarity scoring using embeddings (future enhancement)
  - [ ] Custom scoring functions for specific benchmark types

### UI Improvements
- [x] Add progress tracking in logs for models being benchmarked
- [x] Display token usage and cost estimates in benchmark details
- [x] Improve the benchmark results display with detailed metrics (standard/cached tokens, costs)
- [ ] Add real-time progress visualization in the UI
- [ ] Streamline the process of setting up prompts and expected outputs
- [ ] Add template prompts for common benchmark scenarios

## Code Structure Analysis and Cleanup Plan

The repository currently contains several redundant and overlapping Python files that need to be organized and consolidated. This section outlines which files to keep, which to delete, and the recommended structure for future development.

### Key Files to Keep

| File | Purpose | Status |
|------|---------|--------|
| `engine/file_store.py` | Core database functionality | KEEP - Central database management module |
| `engine/models_openai.py` | OpenAI API integration | KEEP - Primary API client for OpenAI models |
| `engine/exporter.py` | CSV export functionality | KEEP - Handles benchmark data export |
| `run_benchmark.py` | Electron UI bridge for running benchmarks | KEEP - Recently updated to use real models |
| `list_benchmarks.py` | Electron UI bridge for listing benchmarks | KEEP - Required for Electron integration |
| `get_benchmark_details.py` | Electron UI bridge for benchmark details | KEEP - Required for Electron integration |
| `export_benchmark.py` | Electron UI bridge for CSV export | KEEP - Implements exporter integration |

### Files to Deprecate/Remove

| File | Reason | Replacement |
|------|--------|-------------|
| `old_qt (archived)/runner.py` | Redundant with `run_benchmark.py` | Use `run_benchmark.py` for benchmark execution (moved to archived folder) |
| `app.py` | Qt-specific application logic | Useful parts incorporated into Electron bridge scripts |
| `old_qt (archived)/*` | Legacy Qt UI files | Already replaced by Electron interface |
| `test_script.py` | Likely just for testing | Remove if not needed for automated tests |

### Recommended Codebase Structure

```
/eyeonthebenchmarks
  /engine/                   # Core functionality
    /__init__.py            # Package initialization
    /file_store.py          # Database management
    /models_openai.py       # OpenAI API client
    /exporter.py            # Export functionality
  /src/                     # Electron app
    /main/                  # Main process
    /renderer/              # Renderer process
    /preload/               # Preload scripts
  # Bridge scripts for Electron
  run_benchmark.py          # Execute benchmarks
  list_benchmarks.py        # List benchmarks
  get_benchmark_details.py  # Get benchmark details
  export_benchmark.py       # Export benchmark data
  # Config files
  load_benchmarks.sh        # Script to refresh benchmark data
  package.json              # Electron dependencies
```

### Implementation Plan

1. **Consolidate Core Functionality**
   - [x] Verify all needed functionality from `engine/runner.py` is in `run_benchmark.py`
   - [x] Ensure `file_store.py` is used consistently across all scripts instead of direct SQL queries
   - [x] Extract any useful logic from `app.py` into the appropriate bridge scripts

2. **Improve API Integration**
   - [x] Implement proper API clients for OpenAI models
   - [ ] Implement API clients for additional model providers (Anthropic, Google, etc.)
   - [x] Add token counting and cost calculation for OpenAI models
   - [ ] Add token counting and cost calculation for other supported models
   - [x] Implement caching mechanism to avoid redundant API calls (using file hash for OpenAI)

3. **Standardize Error Handling and Logging**
   - [x] Implement consistent logging across all bridge scripts
   - [x] Add proper error handling with detailed error messages for troubleshooting
   - [x] Update log file paths to use relative paths instead of hardcoded absolute paths

### CSV Export Functionality
- [x] Implement CSV export functionality for benchmark results
- [ ] Add option to export raw response data for further analysis
- [ ] Ensure proper formatting of token counts and costs in CSV exports
- [ ] Add header information with benchmark metadata

### Additional Features
- [ ] Allow loading images as part of benchmark questions (especially for multi-modal models)
- [ ] Fix pasting text into the spreadsheet component (ensure smooth data entry)
- [ ] Restrict "Open Prompts CSV" button to only the new benchmark creation page (remove from homepage for clarity)
- [ ] **BUG**: Creating new benchmarks does not work correctly - investigate and fix
- [ ] **BUG**: Ensure new benchmarks are properly saved to the database with correct IDs

### Benchmark Execution & Sync
- [x] Navigate to home screen after hitting 'Start'/'Run' (instead of console) (currently `[done]`)
- [ ] Implement "Sync" functionality: Rerun a benchmark to fill in only missing prompt runs (e.g., new model or new questions on existing benchmark)
- [ ] Use batch API by default for runs exceeding a certain threshold (cost/efficiency)
- [ ] Allow running multiple benchmarks concurrently in the background
- [ ] Allow running a benchmark with different models easily
- [ ] Simplify running a new model on an existing benchmark (e.g., view benchmark, see run models, click to add new model run)

### Reporting & Plotting
- [HIGH PRIORITY] Generate **CSV files** that users can easily use to make charts.
- [ ] Implement exporter.py to generate detailed CSV exports with all metrics
- [ ] Auto-update relevant reports and plots within the app when new runs are added (long-term)
- [ ] Add custom report templates for different analysis needs

### Contexts for Benchmarks
- [HIGH PRIORITY] Allow flexible context configuration.
- [x] Support specific PDF as context (currently `[done]`)
- [ ] Support a directory of files as context (models to access multiple sources simultaneously)
    - [ ] Modify `engine.runner.run_benchmark` to accept a list of file paths or a directory path.
    - [ ] Update PDF pre-flight checks in `engine.runner.run_benchmark` for multiple files.
    - [ ] Adapt `engine.file_store` and `engine.models_openai.openai_upload` for lists of files / multiple OpenAI file IDs.
    - [ ] Investigate how OpenAI `responses` API handles multiple `file_id`s; update `openai_ask`.
    - [ ] UI: Allow selection of a directory or multiple files in ComposerPage.
- [ ] Support internet search as context
    - [ ] Allow configurable internet search modes (e.g., open loop/extensive research vs. quick lookup)
    - [ ] Design mechanism in `engine.runner.run_benchmark` to enable/configure internet search.
    - [ ] In `engine.models_openai`, determine strategy for internet search with `responses` API (direct instruction or pre-fetch results).
    - [ ] UI: Add options in ComposerPage to enable and configure internet search modes.
- [ ] Explore "deep research" capabilities (note: official APIs might be limited)
- [ ] UI: Clearly display PDF/context limitations (file size, page count, token limits from `runner.py`) to the user during the benchmark setup phase in `ComposerPage`.
- [ ] Consider adding an option for Optical Character Recognition (OCR) for image-based PDFs - low priority.

### Metrics
- [MAJOR TODO] Accurately Calculate and Report Cost per Candidate, incorporating KV Caching.
    - [x] Define database schema to store standard input tokens and cached input tokens separately (implemented in file_store.py)
    - [x] Update runner.py to track and return standard_input_tokens, cached_input_tokens, and output_tokens separately
    - [ ] Define and store pricing tiers for different models (e.g., GPT-4.1: $2.00/$0.50/$8.00, GPT-4.1-mini: $0.40/$0.10/$1.60, GPT-4.1-nano: $0.100/$0.025/$0.400 per 1M input/cached-input/output tokens respectively).
    - [x] Modify token processing to differentiate and record: standard input tokens, cached input tokens, and output tokens for each prompt run (implemented in runner.py).
    - [ ] Research and implement mechanisms with the OpenAI `responses` API to:
        - [ ] Reliably trigger KV caching for repeated token prefixes.
        - [ ] Verify or get confirmation from API responses if caching was utilized (if possible).
    - [ ] Implement logic to calculate cost based on token breakdown and model-specific pricing.
    - [ ] Add UI components to display detailed cost breakdowns in benchmark views
    - [ ] Include cost breakdowns in CSV exports
- [x] Measure latency per candidate (implemented - each prompt result includes latency_ms)
- [ ] Measure reasoning cost accurately (re-evaluate if distinct from token costs or if it implies a different metric)

## Image Generation Benchmarks
- [HIGH PRIORITY] Enable benchmarking of image generation models.
- [ ] Integrate support for image generation models (e.g., gpt-image-1, DALL-E series, Gemini vision)
- [ ] Allow defining constraints for image generation prompts (e.g., "must include X," "must not include Y," style guidance)
- [ ] Develop/Integrate scoring mechanisms for image outputs (see Scoring section)
    - [ ] Explore system-defined image scoring (e.g., CLIP scores, aesthetic scores if available via API)
    - [ ] Explore user-provided/manual image scoring rubrics
- [ ] Implement image storage and retrieval in the database

## Scoring
### Core Functionality
- [x] Basic scoring: check for expected answer in output (currently `[done]` - implemented in simple_score function in runner.py)
- [ ] Make scoring configurable during benchmark setup (dropdown of choices, beyond `expected in output`)
- [ ] Handle image outputs for scoring (critical for Image Generation Benchmarks)
- [ ] Allow scoring configuration via Visual Basic macros (if for Python-side execution of user-defined scoring logic)
- [ ] Allow custom scoring item by item (varied correctness logic per question)
- [ ] Implement manual user review as a scoring mechanism
    - [ ] Support blind manual review (A/B testing for subjective evaluations)
- [ ] Add semantic similarity scoring option (not just substring matching)

## Architecture & Performance Improvements
- [x] Implement UI bridge pattern for better separation of concerns (implemented in ui_bridge.py)
- [ ] Optimize file handling for large PDFs (streaming approach instead of loading entire content)
- [ ] Add comprehensive error handling and recovery mechanisms
- [ ] Implement caching layer for frequently accessed data
- [ ] Add automated testing for core functionality
- [ ] Improve multithreading to prevent UI freezing during operations

## Database & Data Access Improvements
- [x] Fixed the database path in scripts to correctly point to eotm_file_store.sqlite
- [x] Implemented correct handling of schema with standard_input_tokens and cached_input_tokens stored separately
- [x] Created load_benchmarks.sh script that runs list_benchmarks.py and saves output to benchmark_data.json
- [x] Modified the Electron app to read benchmark data from JSON file instead of executing Python each time
- [x] Updated get_benchmark_details.py to use the correct database schema and relationships
- [ ] **CRITICAL BUG**: Fix ID mismatch between benchmarks table (IDs 6, 7) and benchmark_runs table (IDs 8, 9 with foreign keys 6, 7)
- [ ] Update get_benchmark_details.py to distinguish between benchmark IDs and run IDs
- [ ] Ensure benchmark_data.json is properly regenerated when new benchmarks are created
- [ ] Investigate issues with creating new benchmarks and ensure they're saved correctly
- [ ] Add more robust error handling and debugging information in Python-Electron bridge
- [ ] Consider implementing a proper API layer between Python and Electron for better integration