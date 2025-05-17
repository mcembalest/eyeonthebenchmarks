// Import modules
const fs = require('fs').promises; // For file operations
const path = require('path');
const { PythonShell } = require('python-shell');
const electron = require('electron');

// Get electron modules (safely)
const app = electron.app;
const BrowserWindow = electron.BrowserWindow;
const ipcMain = electron.ipcMain;
const dialog = electron.dialog;

// Store reference to main window
let mainWindow = null;

// Python process paths (relative to original application)
const pythonPath = path.join(__dirname, '../../');

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

    // Initialize AppLogic bridge
    global.app_logic = {
      // Helper to call Python AppLogic methods and process results/UI events
      _callPythonAppLogic: async function(methodName, methodArgs = {}) {
        if (!mainWindow) {
          console.error('Cannot call Python AppLogic: mainWindow is not available.');
          throw new Error('Main window is not available for Python communication.');
        }
        try {
          console.log(`Calling AppLogic method: ${methodName} with args:`, methodArgs);
          const rawOutputLines = await runPythonCommand('app.py', [
            methodName,
            JSON.stringify(methodArgs)
          ]);

          let finalResult = null;
          if (rawOutputLines && rawOutputLines.length > 0) {
            rawOutputLines.forEach(line => {
              try {
                const parsedLine = JSON.parse(line);
                if (parsedLine && parsedLine.ui_bridge_event && mainWindow && mainWindow.webContents) {
                  // This is a UI event from Python's ScriptUiBridge
                  console.log(`Forwarding UI event from Python: ${parsedLine.ui_bridge_event}`, parsedLine.data);
                  mainWindow.webContents.send(parsedLine.ui_bridge_event, parsedLine.data);
                } else {
                  // Assume it's the method's final result (or part of it if multiple JSONs are printed)
                  // Convention: last JSON object not marked as ui_bridge_event is the result.
                  finalResult = parsedLine;
                }
              } catch (e) {
                // Line is not JSON or not relevant, log it if needed
                console.log('Non-JSON/unhandled line from app.py:', line);
              }
            });
          } else {
            console.warn(`No output received from app.py for method ${methodName}`);
          }
          
          if (finalResult && finalResult.hasOwnProperty('python_error')) {
            console.error(`Error from Python (${methodName}):`, finalResult.python_error);
            throw new Error(finalResult.python_error);
          }
          return finalResult;
        } catch (error) {
          console.error(`Error calling Python AppLogic method ${methodName}:`, error);
          throw error; // Re-throw to be caught by IPC handler
        }
      },

      launch_benchmark_run: function(prompts, pdfPath, modelNames, label, description) {
        return this._callPythonAppLogic('launch_benchmark_run', { prompts, pdfPath, modelNames, label, description });
      },
      handle_delete_benchmark: function(benchmarkId) {
        return this._callPythonAppLogic('handle_delete_benchmark', { benchmark_id: benchmarkId });
      },
      handle_update_benchmark_details: function(benchmarkId, newLabel, newDescription) {
        return this._callPythonAppLogic('handle_update_benchmark_details', { benchmark_id: benchmarkId, new_label: newLabel, new_description: newDescription });
      },
      
      list_benchmarks: function() {
        return this._callPythonAppLogic('list_benchmarks', {});
      }
      // Add other AppLogic methods here if needed
    };

    // Set up IPC handlers after the window is created and app_logic is defined
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

// Python bridge function - enhanced with detailed logging
function runPythonCommand(command, args) {
  return new Promise((resolve, reject) => {
    console.log(`Running Python command: ${command} with args:`, args);
    
    // Get conda executable path from environment if available
    const condaPath = process.env.CONDA_EXE || ''; // Path to conda executable
    const condaPrefix = process.env.CONDA_PREFIX || ''; // Path to active conda environment
    
    // If we're in a conda environment, use its Python
    let pythonExecutable = 'python'; // Default fallback
    if (condaPrefix) {
      // We're in an active conda environment, use its Python
      console.log(`Using conda environment at: ${condaPrefix}`);
      if (process.platform === 'win32') {
        pythonExecutable = path.join(condaPrefix, 'python.exe');
      } else {
        pythonExecutable = path.join(condaPrefix, 'bin', 'python');
      }
    } else {
      console.log('No active conda environment detected, using system Python');
    }
    
    const options = {
      mode: 'text',
      pythonPath: pythonExecutable,  // Use conda environment Python if available
      pythonOptions: ['-u'], // Unbuffered output
      scriptPath: pythonPath,
      args: args || []
    };
    
    console.log(`Full command path: ${path.join(pythonPath, command)}`);
    console.log('Python shell options:', JSON.stringify(options));
    
    // Use the PythonShell class directly for better control
    const pyshell = new PythonShell(command, options);
    
    let stdoutData = [];
    let stderrData = [];
    
    // Capture stdout
    pyshell.on('message', function (message) {
      console.log(`Python stdout: ${message}`);
      stdoutData.push(message);
    });
    
    // Capture stderr
    pyshell.on('stderr', function (stderr) {
      console.log(`Python stderr: ${stderr}`);
      stderrData.push(stderr);
    });
    
    // Handle script end
    pyshell.end(function (err, exitCode, exitSignal) {
      console.log(`Python script ended with code ${exitCode}`);
      
      if (err) {
        console.error('Python error:', err);
        reject(err);
      } else {
        console.log(`Collected ${stdoutData.length} stdout lines`);
        resolve(stdoutData);
      }
    });
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

      // Robust header detection (prompt, expected, expected_answer, ground_truth)
      const headerLine = lines[0].toLowerCase();
      // Remove potential BOM character from the first header before splitting
      const headers = headerLine.replace(/^\uFEFF/, '').split(',').map(h => h.trim().replace(/^"|"$/g, '')); // remove outer quotes from headers

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
        
        const values = line.split(',').map(v => v.trim().replace(/^"|"$/g, '')); // Basic CSV split, remove quotes
        
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

  // Benchmark listing IPC handler - get data directly from Python
  ipcMain.handle('list-benchmarks', async () => {
    try {
      console.log('Requesting benchmark data from Python...');
      if (!global.app_logic) {
        throw new Error('AppLogic not initialized');
      }
      
      const response = await global.app_logic._callPythonAppLogic('list_benchmarks', {});
      console.log('Got benchmark data from Python:', response);
      
      // Extract the benchmarks array from the response object
      const benchmarks = response?.result;
      
      if (!benchmarks || !Array.isArray(benchmarks)) {
        console.error('Invalid benchmark data received:', response);
        return [];
      }
      
      return benchmarks;
    } catch (error) {
      console.error('Error listing benchmarks:', error);
      return [];
    }
  });

  // IPC for running benchmarks
  ipcMain.handle('run-benchmark', async (event, { prompts, pdfPath, modelNames, benchmarkName, benchmarkDescription }) => {
    try {
      // Assuming app_logic is initialized and available in this scope
      // You might need to adjust how app_logic is accessed depending on your main.js structure
      if (!global.app_logic) {
        console.error('AppLogic not initialized or available.');
        throw new Error('Backend logic (AppLogic) is not ready.');
      }

      console.log('Main: Forwarding run-benchmark to AppLogic with name:', benchmarkName, 'desc:', benchmarkDescription);
      // Call the method on the AppLogic instance
      // The AppLogic class in app.py handles the actual benchmark execution process
      // It will use file_store.save_benchmark with the label and description
      await global.app_logic.launch_benchmark_run(prompts, pdfPath, modelNames, benchmarkName, benchmarkDescription);

      // The AppLogic instance will handle progress updates and completion signals to the renderer.
      // No direct JSON parsing or result handling needed here anymore for the run initiation.
      return { success: true, message: 'Benchmark run initiated via AppLogic.' };

    } catch (error) {
      console.error('Error in run-benchmark IPC handler:', error);
      return { success: false, error: error.message || 'Failed to start benchmark run' };
    }
  });

  // IPC for getting benchmark details
  ipcMain.handle('get-benchmark-details', async (event, benchmarkId) => {
    try {
      const results = await runPythonCommand('get_benchmark_details.py', [benchmarkId]);
      return JSON.parse(results[0]);
    } catch (error) {
      console.error('Error getting benchmark details:', error);
      throw error;
    }
  });
  
  // IPC for exporting benchmark to CSV
  ipcMain.handle('export-benchmark-to-csv', async (event, benchmarkId) => {
    try {
      console.log(`Exporting benchmark ID ${benchmarkId} to CSV...`);
      
      // Call the export_benchmark.py script
      const results = await runPythonCommand('export_benchmark.py', [benchmarkId]);
      
      // Parse the results
      try {
        const parsedResult = JSON.parse(results[0]);
        console.log('CSV export result:', parsedResult);
        return parsedResult;
      } catch (parseError) {
        console.error('Error parsing export result:', parseError);
        return { success: false, error: 'Error parsing export result' };
      }
    } catch (error) {
      console.error('Error exporting benchmark to CSV:', error);
      return { success: false, error: String(error) };
    }
  });
  
  // IPC for deleting a benchmark
  ipcMain.handle('delete-benchmark', async (event, benchmarkId) => {
    try {
      if (!global.app_logic) {
        console.error('AppLogic not initialized or available for delete-benchmark.');
        throw new Error('Backend logic (AppLogic) is not ready.');
      }
      console.log(`Main: Received delete-benchmark request for ID: ${benchmarkId}`);
      // The handle_delete_benchmark method in app.py should return a status
      const result = await global.app_logic.handle_delete_benchmark(benchmarkId);
      
      // If deletion was successful, regenerate the benchmark_data.json file
      if (result && result.success) {
        console.log('Benchmark deleted successfully, regenerating benchmark_data.json...');
        const { exec } = require('child_process');
        
        // Run the load_benchmarks.sh script to regenerate the JSON file
        await new Promise((resolve, reject) => {
          exec('./load_benchmarks.sh', { cwd: process.cwd() }, (error, stdout, stderr) => {
            if (error) {
              console.error(`Error regenerating benchmark data: ${error.message}`);
              // Continue even if regeneration fails
              resolve();
              return;
            }
            if (stderr) {
              console.error(`Regeneration stderr: ${stderr}`);
            }
            console.log(`Benchmark data regenerated: ${stdout}`);
            resolve();
          });
        });
      }
      
      return result;
    } catch (error) {
      console.error(`Error in delete-benchmark IPC handler for ID ${benchmarkId}:`, error);
      return { success: false, error: error.message || `Failed to delete benchmark ${benchmarkId}` };
    }
  });

  // IPC for updating benchmark details (renaming)
  ipcMain.handle('update-benchmark-details', async (event, { benchmarkId, newLabel, newDescription }) => {
    try {
      if (!global.app_logic) {
        console.error('AppLogic not initialized or available for update-benchmark-details.');
        throw new Error('Backend logic (AppLogic) is not ready.');
      }
      console.log(`Main: Received update-benchmark-details for ID: ${benchmarkId}, New Label: '${newLabel}', New Desc: '${newDescription}'`);
      // The handle_update_benchmark_details method in app.py should return a status
      const result = await global.app_logic.handle_update_benchmark_details(benchmarkId, newLabel, newDescription);
      return result; // Assuming result is { success: true } or { success: false, error: '...' }
    } catch (error) {
      console.error(`Error in update-benchmark-details IPC handler for ID ${benchmarkId}:`, error);
      return { success: false, error: error.message || `Failed to update benchmark ${benchmarkId}` };
    }
  });

  // IPC for getting available models
  ipcMain.handle('get-available-models', async () => {
    try {
      console.log('Getting available models from Python...');
      
      // Call the available_models.py script
      const results = await runPythonCommand('engine/available_models.py', []);
      
      // The last line should contain our JSON data
      if (!results || results.length === 0) {
        console.error('No output received from available_models.py');
        return { success: false, models: [] };
      }
      
      // Find the line that has JSON data (models list)
      let modelsJson = null;
      for (let i = results.length - 1; i >= 0; i--) {
        try {
          const parsed = JSON.parse(results[i]);
          if (Array.isArray(parsed)) {
            modelsJson = parsed;
            break;
          }
        } catch (e) {
          // Not JSON, continue looking
        }
      }
      
      if (!modelsJson) {
        console.error('Could not find valid models JSON in output:', results);
        return { success: false, models: [] };
      }
      
      console.log('Available models:', modelsJson);
      return { success: true, models: modelsJson };
    } catch (error) {
      console.error('Error getting available models:', error);
      return { success: false, models: [], error: String(error) };
    }
  });
}
