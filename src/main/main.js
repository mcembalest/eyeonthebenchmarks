const electron = require('electron');
const { app, BrowserWindow, ipcMain, dialog } = electron;
const path = require('path');
const { PythonShell } = require('python-shell');

// Store reference to main window
let mainWindow;

// Python process paths (relative to original application)
const pythonPath = path.join(__dirname, '../../../');

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

// Quit app when all windows are closed (Windows & Linux)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Re-create window on macOS when dock icon is clicked
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
