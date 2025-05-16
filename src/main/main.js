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
  app.whenReady().then(() => {
    createWindow();

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

// Python bridge function - enhanced with detailed logging
function runPythonCommand(command, args) {
  return new Promise((resolve, reject) => {
    console.log(`Running Python command: ${command} with args:`, args);
    
    const options = {
      mode: 'text',
      pythonPath: 'python',  // Use system Python
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

      const promptIndex = headers.findIndex(h => h === 'prompt' || h === 'prompt_text' || h === 'question');
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

  // Benchmark listing IPC handler - read from pre-generated JSON file
  ipcMain.handle('list-benchmarks', async () => {
    try {
      console.log('Reading benchmark data from file...');
      
      // Path to the benchmark data file
      const dataFilePath = path.join(process.cwd(), 'benchmark_data.json');
      console.log(`Looking for benchmark data at: ${dataFilePath}`);
      
      // Check if the file exists
      if (!require('fs').existsSync(dataFilePath)) {
        console.error(`Benchmark data file not found at: ${dataFilePath}`);
        
        // Try to generate it by running the shell script
        console.log('Attempting to generate benchmark data by running shell script...');
        
        const { exec } = require('child_process');
        
        await new Promise((resolve, reject) => {
          exec('./load_benchmarks.sh', { cwd: process.cwd() }, (error, stdout, stderr) => {
            if (error) {
              console.error(`Error running shell script: ${error.message}`);
              reject(error);
              return;
            }
            if (stderr) {
              console.error(`Shell script stderr: ${stderr}`);
            }
            console.log(`Shell script stdout: ${stdout}`);
            resolve();
          });
        });
        
        // Check again if file exists after running script
        if (!require('fs').existsSync(dataFilePath)) {
          console.error('Failed to generate benchmark data file');
          return [];
        }
      }
      
      // Read the file
      const fileData = require('fs').readFileSync(dataFilePath, 'utf8');
      console.log(`Read ${fileData.length} bytes from benchmark data file`);
      
      try {
        const parsedData = JSON.parse(fileData);
        console.log('Successfully parsed benchmark data from file');
        console.log('Number of benchmarks found:', parsedData.length);
        return parsedData;
      } catch (parseError) {
        console.error('Error parsing benchmark JSON from file:', parseError);
        return [];
      }
    } catch (error) {
      console.error('Error listing benchmarks:', error);
      return [];
    }
  });

  // IPC for running benchmarks
  ipcMain.handle('run-benchmark', async (event, { prompts, pdfPath, modelNames }) => {
    try {
      console.log('Starting benchmark run with:', { pdfCount: 1, modelCount: modelNames.length, promptCount: prompts.length });
      
      // Format arguments for Python script
      const args = [
        '--pdf', pdfPath,
        '--models', modelNames.join(','),
        '--prompts', JSON.stringify(prompts)
      ];
      
      console.log('Running benchmark Python script...');
      const results = await runPythonCommand('run_benchmark.py', args);
      console.log('Raw results from run_benchmark.py:', results); // Log all output lines

      if (!results || results.length === 0) {
        throw new Error('No output received from run_benchmark.py');
      }
      
      // Attempt to parse the last line of the output as JSON
      const lastLine = results[results.length - 1];
      let parsedResult;
      try {
        parsedResult = JSON.parse(lastLine);
      } catch (e) {
        console.error('Failed to parse last line from Python script as JSON:', lastLine, e);
        throw new Error('Invalid JSON output from run_benchmark.py: ' + lastLine);
      }
      console.log('Parsed benchmark creation result (from last line):', parsedResult);
      
      console.log('Refreshing benchmark_data.json by running load_benchmarks.sh...');
      const { exec } = require('child_process');
      
      await new Promise((resolve, reject) => {
        exec('./load_benchmarks.sh', { cwd: process.cwd() }, (error, stdout, stderr) => {
          if (error) {
            console.error(`Error running load_benchmarks.sh: ${error.message}`);
            // Log stderr if present, even on error
            if (stderr) {
              console.error(`load_benchmarks.sh stderr: ${stderr}`);
            }
            reject(error);
            return;
          }
          if (stderr) {
            // Log stderr even if the script technically succeeded (exit code 0)
            console.warn(`load_benchmarks.sh stderr (non-fatal): ${stderr}`);
          }
          console.log(`load_benchmarks.sh stdout: ${stdout}`);
          resolve();
        });
      });
      console.log('benchmark_data.json should now be updated.');
      
      mainWindow.webContents.send('benchmark-complete', { 
        success: true, 
        benchmarkId: parsedResult.benchmark_id || parsedResult.id || null 
      });
      
      return { 
        success: true, 
        message: 'Benchmark run successfully', 
        benchmarkId: parsedResult.benchmark_id || parsedResult.id || null 
      };
    } catch (error) {
      console.error('Error running benchmark:', error);
      throw error;
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
  
  // IPC for getting available models
  ipcMain.handle('get-available-models', async (event) => {
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
