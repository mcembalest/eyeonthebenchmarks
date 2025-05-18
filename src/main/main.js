// Import modules
const fs = require('fs').promises; // For file operations
const path = require('path');
const electron = require('electron');
const http = require('http');
const apiHost = '127.0.0.1';
const apiPort = 8000;
const apiBase = `http://${apiHost}:${apiPort}`;
const WebSocket = require('ws');

// Get electron modules (safely)
const app = electron.app;
const BrowserWindow = electron.BrowserWindow;
const ipcMain = electron.ipcMain;
const dialog = electron.dialog;

// Store reference to main window
let mainWindow = null;

// Python process paths (relative to original application)
const pythonPath = path.join(__dirname, '../../');

// Helper for HTTP GET JSON
function httpGetJson(path) {
  return new Promise((resolve, reject) => {
    http.get(`${apiBase}${path}`, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

// Helper for HTTP POST JSON
function httpPostJson(path, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const options = {
      hostname: apiHost,
      port: apiPort,
      path: path,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    };
    const req = http.request(options, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

const createWindow = () => {
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
};

// Only run the app setup if we're in Electron (not if just loaded by Node)
if (app) {
  // Create window when app is ready
  app.whenReady().then(async () => { 
    createWindow();

    // Connect to backend WebSocket for real-time events
    const ws = new WebSocket(`ws://${apiHost}:${apiPort}/ws`);
    ws.on('open', () => console.log('Connected to backend WS'));
    ws.on('message', data => {
      try {
        const msg = JSON.parse(data);
        if (mainWindow && mainWindow.webContents) {
          mainWindow.webContents.send(msg.event, msg);
        }
      } catch (e) {
        console.error('Error parsing WS message:', e);
      }
    });
    ws.on('error', err => console.error('WS error:', err));

    // Set up IPC handlers after the window is created
    setupIpcHandlers();

    app.on('activate', () => {
      // On macOS it's common to re-create a window in the app when the
      // dock icon is clicked and there are no other windows open.
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  // Quit when all windows are closed, except on macOS
  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });
}

// Set up all IPC handlers in one function
function setupIpcHandlers() {
  if (!ipcMain) return;
  
  // Basic IPC handlers for UI bridge
  ipcMain.handle('open-file-dialog', async (event, options) => {
    const { filePaths } = await dialog.showOpenDialog(mainWindow, options);
    return filePaths.length > 0 ? filePaths[0] : null;
  });
  
  // CSV reading and parsing handler
  ipcMain.handle('read-parse-csv', async (event, filePath) => {
    console.log(`Main: Received request to read and parse CSV: ${filePath}`);
    if (!filePath || typeof filePath !== 'string') {
      console.error('Main: Invalid file path received for CSV parsing.');
      throw new Error('Invalid file path provided.');
    }
    try {
      const fileContent = await fs.readFile(filePath, 'utf8');
      // Split lines and trim whitespace from each line, filter out empty lines
      const lines = fileContent.split(/\r?\n/).map(line => line.trim()).filter(line => line);

      if (lines.length === 0) {
        console.log('Main: CSV file is empty or contains only whitespace.');
        return [];
      }

      // Split CSV line into fields respecting quoted commas
      const parseCsvLine = (line) => {
        const result = [];
        let current = '';
        let inQuotes = false;
        for (let i = 0; i < line.length; i++) {
          const char = line[i];
          if (char === '"') {
            inQuotes = !inQuotes;
            continue;
          }
          if (char === ',' && !inQuotes) {
            result.push(current);
            current = '';
          } else {
            current += char;
          }
        }
        result.push(current);
        return result.map(v => v.trim());
      };

      // Robust header detection (prompt, expected, expected_answer, ground_truth)
      const headerLineRaw = lines[0].replace(/^\uFEFF/, '');
      const headers = parseCsvLine(headerLineRaw).map(h => h.toLowerCase());

      let promptIndex = headers.findIndex(h => h === 'prompt' || h === 'prompt_text' || h === 'question');
      let expectedIndex = headers.findIndex(h => ['expected', 'expected_answer', 'ground_truth', 'answer'].includes(h));

      if (promptIndex === -1 || expectedIndex === -1) {
        console.error(`Main: CSV headers did not contain required columns. Found headers: ${headers.join(', ')}`);
        // Attempt to use first two columns if headers are not standard
        if (headers.length >= 2) {
          console.warn('Main: Defaulting to first column as prompt and second as expected.');
          promptIndex = 0;
          expectedIndex = 1;
        } else {
          throw new Error('CSV must have at least two columns, or standard headers (prompt, expected).');
        }
      }
      
      const data = [];
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line === '') continue; // Skip empty lines
        
        const values = parseCsvLine(line);
        
        if (values.length > Math.max(promptIndex, expectedIndex)) {
          const promptText = values[promptIndex];
          const expectedText = values[expectedIndex];
          if (promptText) { // Ensure prompt is not empty
            data.push({ prompt: promptText, expected: expectedText || '' }); // Allow empty expected answer
          }
        } else {
          console.warn(`Skipping line ${i+1} due to insufficient columns: ${line}`);
        }
      }
      
      console.log(`Main: Parsed ${data.length} prompts from CSV.`);
      return data;
    } catch (error) {
      console.error('Main: Error reading or parsing CSV:', error);
      // Send a more specific error back to renderer
      throw new Error(`Failed to parse CSV: ${error.message}`); 
    }
  });

  // List benchmarks via HTTP
  ipcMain.handle('list-benchmarks', async () => {
    try {
      return await httpGetJson('/benchmarks/all');
    } catch (err) {
      console.error('Error listing benchmarks:', err);
      return [];
    }
  });

  // Run benchmark via HTTP
  ipcMain.handle('run-benchmark', async (event, { prompts, pdfPath, modelNames, benchmarkName, benchmarkDescription }) => {
    try {
      const result = await httpPostJson('/launch', { prompts, pdfPath, modelNames, benchmarkName, benchmarkDescription });
      return { success: result.status === 'success', ...result };
    } catch (err) {
      console.error('Error running benchmark:', err);
      return { success: false, error: err.message };
    }
  });

  // Get benchmark details via HTTP
  ipcMain.handle('get-benchmark-details', async (event, benchmarkId) => {
    try {
      return await httpGetJson(`/benchmarks/${benchmarkId}`);
    } catch (err) {
      console.error('Error getting benchmark details:', err);
      return { success: false, error: err.message };
    }
  });

  // Export benchmark to CSV via HTTP
  ipcMain.handle('export-benchmark-to-csv', async (event, benchmarkId) => {
    // Frontend can open the CSV URL directly or implement download separately
    return { url: `${apiBase}/benchmarks/${benchmarkId}/export` };
  });

  // IPC for deleting a benchmark
  ipcMain.handle('delete-benchmark', async (event, benchmarkId) => {
    try {
      console.log(`Main: Received delete-benchmark request for ID: ${benchmarkId}`);
      
      // The handle_delete_benchmark method in app.py should return a status
      const result = await httpPostJson('/delete', { benchmarkId });
      
      const finalResult = result || { success: false, error: 'No result returned from handle_delete_benchmark' };
      
      // Log deletion success
      if (finalResult.success) {
        console.log('Benchmark deleted successfully');
      }
      
      // Always return a structured response
      return finalResult;
    } catch (error) {
      console.error(`Error in delete-benchmark IPC handler for ID ${benchmarkId}:`, error);
      // Ensure we always return a response to the renderer
      return { success: false, error: error.message || `Failed to delete benchmark ${benchmarkId}` };
    }
  });

  // IPC for updating benchmark details (renaming)
  ipcMain.handle('update-benchmark-details', async (event, { benchmarkId, newLabel, newDescription }) => {
    try {
      console.log(`Main: Received update-benchmark-details for ID: ${benchmarkId}, New Label: '${newLabel}', New Desc: '${newDescription}'`);
      
      // The handle_update_benchmark_details method in app.py should return a status
      const result = await httpPostJson('/update', { benchmarkId, newLabel, newDescription });
      
      // Ensure we have a valid result object to return
      const finalResult = result || { success: false, error: 'No result returned from handle_update_benchmark_details' };
      
      // Always return a structured response
      return finalResult;
    } catch (error) {
      console.error(`Error in update-benchmark-details IPC handler for ID ${benchmarkId}:`, error);
      // Ensure we always return a response to the renderer
      return { success: false, error: error.message || `Failed to update benchmark ${benchmarkId}` };
    }
  });

  // IPC for getting available models
  ipcMain.handle('get-available-models', async () => {
    try {
      const models = await httpGetJson('/models');
      return { success: true, models };
    } catch (error) {
      console.error('Error getting available models from API:', error);
      return { success: false, models: [], error: error.message };
    }
  });
}
