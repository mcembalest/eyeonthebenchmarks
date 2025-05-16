// Import modules
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
      // Format arguments for Python script
      const args = [
        '--pdf', pdfPath,
        '--models', modelNames.join(','),
        '--prompts', JSON.stringify(prompts)
      ];
      
      const results = await runPythonCommand('run_benchmark.py', args);
      return JSON.parse(results[0]);
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
}
