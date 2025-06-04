// Import modules
const fs = require('fs').promises; // For file operations
const path = require('path');
const electron = require('electron');
const http = require('http');
const { spawn } = require('child_process');
const { shell } = require('electron');

// Settings management
const settingsPath = path.join(electron.app.getPath('userData'), 'settings.json');

// Default settings
const defaultSettings = {
  apiKeys: {
    openai: '',
    anthropic: '',
    google: ''
  },
  firstTimeSetup: true
};

// Settings store
let settings = { ...defaultSettings };

// Load settings from file
async function loadSettings() {
  try {
    const data = await fs.readFile(settingsPath, 'utf8');
    settings = { ...defaultSettings, ...JSON.parse(data) };
    console.log('[Settings] Loaded settings from:', settingsPath);
  } catch (error) {
    console.log('[Settings] No existing settings file, using defaults');
    settings = { ...defaultSettings };
  }
}

// Save settings to file
async function saveSettings() {
  try {
    await fs.writeFile(settingsPath, JSON.stringify(settings, null, 2));
    console.log('[Settings] Saved settings to:', settingsPath);
  } catch (error) {
    console.error('[Settings] Failed to save settings:', error);
  }
}

// Check if API keys are configured
function hasValidApiKeys() {
  const { apiKeys } = settings;
  return apiKeys.openai || apiKeys.anthropic || apiKeys.google;
}

// Get API keys for environment
function getApiKeysForEnv() {
  return {
    OPENAI_API_KEY: settings.apiKeys.openai || '',
    ANTHROPIC_API_KEY: settings.apiKeys.anthropic || '',
    GOOGLE_API_KEY: settings.apiKeys.google || ''
  };
}

const apiHost = '127.0.0.1';
const apiPort = 8000;
const apiBase = `http://${apiHost}:${apiPort}`;
const WebSocket = require('ws');

// Backend process reference
let backendProcess = null;

// Get electron modules (safely)
const app = electron.app;
const BrowserWindow = electron.BrowserWindow;
const ipcMain = electron.ipcMain;
const dialog = electron.dialog;

// Store reference to main window
let mainWindow = null;

// Get the backend executable path and command
const isDev = app ? !app.isPackaged : true;
const getBackendCommand = () => {
  let commandDetails;
  if (isDev) {
    commandDetails = {
      command: 'python',
      args: [path.join(__dirname, '../../api.py')]
    };
  } else {
    // In production, use the bundled executable
    let backendPath;
    if (process.platform === 'darwin') {
      const arch = process.arch === 'arm64' ? 'arm64' : 'x64';
      backendPath = path.join(process.resourcesPath, 'app.asar.unpacked', 'dist', `api-${arch}`);
      
      // Debug logging
      console.log(`[DEBUG] process.resourcesPath: ${process.resourcesPath}`);
      console.log(`[DEBUG] process.arch: ${process.arch}`);
      console.log(`[DEBUG] Expected backend path: ${backendPath}`);
      
      // Check if the file exists
      const fs = require('fs');
      if (fs.existsSync(backendPath)) {
        console.log(`[DEBUG] ✅ Backend binary found at: ${backendPath}`);
        // Check if it's executable
        try {
          fs.accessSync(backendPath, fs.constants.F_OK | fs.constants.X_OK);
          console.log(`[DEBUG] ✅ Backend binary is executable`);
        } catch (err) {
          console.log(`[DEBUG] ❌ Backend binary is not executable:`, err.message);
        }
      } else {
        console.log(`[DEBUG] ❌ Backend binary NOT found at: ${backendPath}`);
        
        // Let's see what's actually in the directory
        const distDir = path.join(process.resourcesPath, 'app.asar.unpacked', 'dist');
        console.log(`[DEBUG] Checking dist directory: ${distDir}`);
        try {
          const files = fs.readdirSync(distDir);
          console.log(`[DEBUG] Files in dist directory:`, files);
        } catch (err) {
          console.log(`[DEBUG] Could not read dist directory:`, err.message);
          
          // Check if app.asar.unpacked exists
          const unpackedDir = path.join(process.resourcesPath, 'app.asar.unpacked');
          console.log(`[DEBUG] Checking unpacked directory: ${unpackedDir}`);
          try {
            const unpackedFiles = fs.readdirSync(unpackedDir);
            console.log(`[DEBUG] Files in unpacked directory:`, unpackedFiles);
          } catch (err2) {
            console.log(`[DEBUG] Could not read unpacked directory:`, err2.message);
            
            // Check what's in resourcesPath
            console.log(`[DEBUG] Checking resources path: ${process.resourcesPath}`);
            try {
              const resourceFiles = fs.readdirSync(process.resourcesPath);
              console.log(`[DEBUG] Files in resources path:`, resourceFiles);
            } catch (err3) {
              console.log(`[DEBUG] Could not read resources path:`, err3.message);
            }
          }
        }
      }
    } else {
      // Add placeholders for other platforms if needed, or throw error
      // For now, assuming macOS. Windows would be different.
      // backendPath = path.join(process.resourcesPath, 'app.asar.unpacked', 'dist', 'api.exe'); 
      throw new Error('Unsupported platform for packaged backend');
    }
    commandDetails = {
      command: backendPath,
      args: []
    };
  }
  console.log(`[Main Process] Backend command details: ${JSON.stringify(commandDetails)} (isDev: ${isDev})`);
  return commandDetails;
};

// Helper for HTTP GET JSON
function httpGetJson(urlPath) { // Changed parameter name for clarity
  const fullUrl = `${apiBase}${urlPath}`;
  console.log(`[Main Process] httpGetJson: Attempting GET ${fullUrl}`);
  return new Promise((resolve, reject) => {
    http.get(fullUrl, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        console.log(`[Main Process] httpGetJson: Received response for ${fullUrl}, statusCode: ${res.statusCode}`);
        // Check for successful status code first
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try { 
            resolve(JSON.parse(data)); 
          } catch (e) { 
            console.error(`[Main Process] JSON parse error for ${fullUrl}:`, e);
            console.error('[Main Process] Raw response data:', data);
            reject(new Error(`Failed to parse JSON response from ${fullUrl}: ${e.message}`)); 
          }
        } else {
          console.error(`[Main Process] HTTP error ${res.statusCode} for ${fullUrl}:`, data);
          reject(new Error(`HTTP ${res.statusCode} from ${fullUrl}: ${data.substring(0, 100)}${data.length > 100 ? '...' : ''}`));
        }
      });
    }).on('error', err => {
      console.error(`[Main Process] Network error for ${fullUrl}:`, err);
      reject(err);
    });
  });
}

// Helper for HTTP POST JSON
function httpPostJson(urlPath, payload) { // Changed parameter name for clarity
  const fullUrl = `${apiBase}${urlPath}`;
  console.log(`[Main Process] httpPostJson: Attempting POST to ${fullUrl}`);
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const options = {
      hostname: apiHost,
      port: apiPort,
      path: urlPath,
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
        // Check if response is empty
        if (!data || data.trim() === '') {
          console.warn(`[Main Process] Empty response received from ${fullUrl}`);
          resolve({ success: false, error: 'Empty response from server' });
          return;
        }
        
        try { 
          // Try to parse the response as JSON
          const parsedData = JSON.parse(data);
          resolve(parsedData); 
        }
        catch (e) { 
          // If parsing fails, log the problematic response and return a formatted error
          console.error(`[Main Process] Invalid JSON response from ${fullUrl}:`, data);
          console.error(`[Main Process] JSON parse error:`, e.message);
          // Return a proper JSON object with the error message
          resolve({ 
            success: false, 
            error: `Server returned invalid JSON: ${data.substring(0, 100)}${data.length > 100 ? '...' : ''}` 
          });
        }
      });
    });
    req.on('error', (error) => {
      console.error(`[Main Process] Network error for ${fullUrl}:`, error.message);
      reject(error);
    });
    req.write(body);
    req.end();
  });
}

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/preload.js')
    }
  });

  // Open DevTools in development only
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  // Load the index.html file
  mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));

  // Send 'main-process-ready' signal to renderer AFTER the window content has loaded.
  // This ensures that the renderer doesn't try to communicate with the main process
  // (e.g., to get models via IPC which then makes an HTTP call) before the main process
  // (especially the backend python server) is fully ready and the renderer's own page is loaded.
  // The call to createWindow() in app.whenReady() is already made after `await startBackend()`,
  // so backend readiness should be established before this point.
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('Main window content (index.html) has finished loading. Sending main-process-ready signal.');
    // Ensure mainWindow and its webContents still exist, as 'did-finish-load' is async.
    if (mainWindow && mainWindow.webContents) {
        mainWindow.webContents.send('main-process-ready');
    } else {
        console.warn('mainWindow or webContents not available at did-finish-load, cannot send main-process-ready signal.');
    }
  });

  // Set application icon (macOS dock)
  if (process.platform === 'darwin') {
    app.dock.setIcon(path.join(__dirname, '../renderer/assets/icon.png'));
  }
};

// Only run the app setup if we're in Electron (not if just loaded by Node)
if (app) {
  // Create window when app is ready
  // Start the backend process
const checkBackendRunning = () => {
  const modelsUrl = `${apiBase}/models`;
  console.log(`[Main Process] checkBackendRunning: Pinging ${modelsUrl}`);
  return new Promise((resolve) => {
    const testRequest = http.get(modelsUrl, (res) => {
      console.log(`[Main Process] checkBackendRunning: Ping response status: ${res.statusCode}`);
      resolve(res.statusCode === 200);
    });
    testRequest.on('error', (err) => {
      console.error(`[Main Process] checkBackendRunning: Ping error: ${err.message}`);
      resolve(false);
    });
  });
};

const startBackend = async () => {
  console.log('[Main Process] startBackend: Checking if backend is already running...');
  // Check if backend is already running
  const isRunning = await checkBackendRunning();
  if (isRunning) {
    console.log('[Main Process] Backend is already running, skipping startup.');
    return;
  }

  const { command, args } = getBackendCommand();
  console.log(`[Main Process] Attempting to start backend with command: '${command}' and args: [${args.join(', ')}]`);
  
  // Set up environment variables with API keys from settings
  const env = { ...process.env, ...getApiKeysForEnv() };
  
  // Add detailed pre-spawn debugging
  console.log('[DEBUG] About to spawn backend with:');
  console.log('[DEBUG] - Command:', command);
  console.log('[DEBUG] - Args:', JSON.stringify(args));
  console.log('[DEBUG] - Env keys:', Object.keys(env).filter(k => k.includes('API')));
  console.log('[DEBUG] - Working directory:', process.cwd());
  
  try {
    backendProcess = spawn(command, args, { env });
    console.log('[DEBUG] Backend process spawned successfully, PID:', backendProcess.pid);
  } catch (spawnError) {
    console.error('[Main Process] CRITICAL: Error spawning backend process:', spawnError);
    console.error('[DEBUG] Spawn error details:', {
      code: spawnError.code,
      errno: spawnError.errno,
      syscall: spawnError.syscall,
      path: spawnError.path
    });
    throw new Error(`Failed to spawn backend: ${spawnError.message}`);
  }

  backendProcess.stdout.on('data', (data) => {
    const output = data.toString().trim();
    console.log('[Backend STDOUT]:', output);
    
    // Send stdout to renderer for debugging
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send('backend-status', {
        status: 'starting',
        message: 'Backend starting...',
        debug: `STDOUT: ${output.substring(0, 100)}${output.length > 100 ? '...' : ''}`
      });
    }
  });

  backendProcess.stderr.on('data', (data) => {
    const output = data.toString().trim();
    console.error('[Backend STDERR]:', output);
    
    // Send stderr to renderer for debugging
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send('backend-status', {
        status: 'starting',
        message: 'Backend starting (with warnings)...',
        debug: `STDERR: ${output.substring(0, 200)}${output.length > 200 ? '...' : ''}`
      });
    }
  });

  backendProcess.on('error', (err) => {
    console.error('[Main Process] Backend process error event:', err);
    console.error('[DEBUG] Error details:', {
      code: err.code,
      errno: err.errno,
      syscall: err.syscall,
      path: err.path,
      spawnargs: err.spawnargs
    });
    
    // Send error details to renderer
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send('backend-status', {
        status: 'error',
        message: `Backend process error: ${err.code || err.message}`,
        error: err.message,
        debug: `Error code: ${err.code}, syscall: ${err.syscall}`
      });
    }
  });

  backendProcess.on('close', (code, signal) => {
    console.log(`[Main Process] Backend process exited with code ${code}, signal ${signal}`);
    
    // Send exit info to renderer
    if (mainWindow && mainWindow.webContents && code !== 0) {
      mainWindow.webContents.send('backend-status', {
        status: 'error',
        message: `Backend process exited unexpectedly (code: ${code})`,
        debug: `Exit code: ${code}, signal: ${signal}`
      });
    }
    
    backendProcess = null;
  });

  // Wait for backend to be ready with retries
  const maxRetries = 30; // Increased retries to 60 seconds total
  const retryDelay = 2000; // 2 second delay
  
  for (let i = 0; i < maxRetries; i++) {
    console.log(`[Main Process] startBackend: Waiting for backend to be ready (attempt ${i + 1}/${maxRetries})...`);
    
    // Send status update to renderer
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send('backend-status', {
        status: 'starting',
        message: `Starting backend service... (${i + 1}/${maxRetries})`,
        progress: (i + 1) / maxRetries * 100
      });
    }
    
    const isReady = await checkBackendRunning();
    if (isReady) {
      console.log('[Main Process] Backend is confirmed ready.');
      
      // Send ready status to renderer
      if (mainWindow && mainWindow.webContents) {
        mainWindow.webContents.send('backend-status', {
          status: 'ready',
          message: 'Backend service is ready!',
          progress: 100
        });
      }
      
      return;
    }
    console.log(`[Main Process] Backend not ready yet, retrying in ${retryDelay / 1000}s...`);
    await new Promise(resolve => setTimeout(resolve, retryDelay));
  }
  
  console.error('[Main Process] Backend failed to start or become responsive after maximum retries.');
  
  // Send error status to renderer instead of showing dialog
  if (mainWindow && mainWindow.webContents) {
    mainWindow.webContents.send('backend-status', {
      status: 'error',
      message: 'Backend service failed to start after 60 seconds',
      error: 'Timeout waiting for backend to respond'
    });
  }
  
  throw new Error('Backend failed to start');
};

const restartBackend = async () => {
  console.log('[Main Process] Restarting backend...');
  
  // Kill existing backend process if it exists
  if (backendProcess && !backendProcess.killed) {
    console.log('[Main Process] Terminating existing backend process...');
    backendProcess.kill('SIGTERM');
    
    // Wait a moment for the process to terminate
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  
  // Reset the process reference
  backendProcess = null;
  
  // Start the backend again
  await startBackend();
  console.log('[Main Process] Backend restarted successfully!');
};

// App lifecycle and window creation
// Clean up the backend process
app.on('will-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});

app.whenReady().then(async () => {
  // Load settings first
  await loadSettings();
  
  // Set up IPC handlers BEFORE creating window to ensure they're ready
  setupIpcHandlers();
  
  // Create window first so loading screen shows immediately
  createWindow();
  
  // Start the backend after window is created
  try {
    await startBackend();
  } catch (e) {
    console.error('Backend startup error:', e);
    // Send error to renderer instead of showing dialog
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send('backend-status', {
        status: 'error',
        message: 'Failed to start backend service',
        error: e.message
      });
    }
  }

    // Connect to backend WebSocket for real-time events
    const ws = new WebSocket(`ws://${apiHost}:${apiPort}/ws`);
    ws.on('open', () => console.log('Connected to backend WS'));
    ws.on('message', data => {
      try {
        const msg = JSON.parse(data);
        console.log('🌐 Main Process: Received WebSocket message:', msg);
        
        if (mainWindow && mainWindow.webContents && (msg.ui_bridge_event || msg.event)) {
          // Extract the event name - prefer ui_bridge_event for compatibility, fallback to event
          const eventName = msg.ui_bridge_event || msg.event;
          const eventData = msg.data || msg;
          
          console.log('🌐 Main Process: Forwarding event:', eventName, 'with data:', eventData);
          
          // Special handling for benchmark progress events
          if (eventName === 'benchmark-progress') {
            // Make sure we properly identify the initial 'running' status
            if (eventData.status === 'running' || eventData.message?.includes('Starting benchmark')) {
              eventData.status = 'running';
            }
            console.log('🌐 Main Process: Sending benchmark-progress event to renderer with data:', eventData);
          }
          
          mainWindow.webContents.send(eventName, eventData);
          console.log('🌐 Main Process: Event sent to renderer successfully');
        } else {
          console.log('🌐 Main Process: Not forwarding message - missing window, webContents, or event field');
        }
      } catch (e) {
        console.error('🌐 Main Process: Error parsing WS message:', e);
      }
    });
    ws.on('error', err => console.error('WS error:', err));

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
const setupIpcHandlers = () => {
  // Handle playing sound effects
  ipcMain.handle('play-sound', async (event, soundPath, shouldPlay = true) => {
    console.log('Received request to play sound:', soundPath, 'shouldPlay:', shouldPlay);
    
    // Try multiple paths to find the sound file
    const possiblePaths = [
      // Production path (inside asar)
      path.join(app.getAppPath(), 'src', soundPath),
      // Development path (relative to main.js)
      path.join(__dirname, '..', soundPath),
      // Absolute path (if already resolved)
      soundPath
    ];
    
    let foundPath = null;
    
    // First find the file
    for (const fullPath of possiblePaths) {
      try {
        await fs.access(fullPath);
        console.log('Sound file found at:', fullPath);
        foundPath = fullPath;
        break;
      } catch (error) {
        console.log('Sound file not found at:', fullPath);
        continue;
      }
    }
    
    if (!foundPath) {
      throw new Error('Sound file not found in any location');
    }
    
    if (shouldPlay) {
      console.log('Playing sound effect...');
      // Play the sound using afplay on macOS
      if (process.platform === 'darwin') {
        const { spawn } = require('child_process');
        spawn('afplay', [foundPath]);
      }
      // TODO: Add support for other platforms here
    } else {
      console.log('Skipping sound playback - shouldPlay is false');
    }
    
    return foundPath;
  });

  if (!ipcMain) return;
  
  // Basic IPC handlers for UI bridge
  ipcMain.handle('open-file-dialog', async (event, options) => {
    const { filePaths } = await dialog.showOpenDialog(mainWindow, options);
    
    // If multiSelections was requested, return the full array
    if (options.properties && options.properties.includes('multiSelections')) {
      return filePaths.length > 0 ? filePaths : [];
    }
    
    // Otherwise return single file path (backward compatibility)
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

      // Robust header detection (prompt only for MVP)
      const headerLineRaw = lines[0].replace(/^\\uFEFF/, '');
      const headers = parseCsvLine(headerLineRaw).map(h => h.toLowerCase());

      let promptIndex = headers.findIndex(h => h === 'prompt' || h === 'prompt_text' || h === 'question');

      if (promptIndex === -1) {
        console.error(`Main: CSV headers did not contain required prompt column. Found headers: ${headers.join(', ')}`);
        // Attempt to use first column if headers are not standard
        if (headers.length >= 1) {
          console.warn('Main: Defaulting to first column as prompt.');
          promptIndex = 0;
        } else {
          throw new Error('CSV must have at least one column with prompt data.');
        }
      }
      
      const data = [];
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line === '') continue; // Skip empty lines
        
        const values = parseCsvLine(line);
        
        if (values.length > promptIndex) {
          const promptText = values[promptIndex];
          if (promptText) { // Ensure prompt is not empty
            data.push({ prompt: promptText }); // MVP - only prompt text
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
  ipcMain.handle('run-benchmark', async (event, prompts, pdfPaths, modelNames, benchmarkName, benchmarkDescription, webSearchEnabled) => {
    try {
      const result = await httpPostJson('/launch', { 
        prompts, 
        pdfPaths, 
        modelNames, 
        benchmarkName, 
        benchmarkDescription,
        webSearchEnabled
      });
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
    try {
      const exportUrl = `${apiBase}/benchmarks/${benchmarkId}/export`;
      console.log(`Main: Opening CSV export URL: ${exportUrl}`);
      
      // Open the CSV export URL in the default browser to trigger download
      await shell.openExternal(exportUrl);
      
      return { 
        success: true, 
        message: 'CSV export opened in browser',
        url: exportUrl 
      };
    } catch (error) {
      console.error('Error exporting benchmark to CSV:', error);
      return { 
        success: false, 
        error: error.message || 'Failed to export benchmark to CSV' 
      };
    }
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

  // IPC for resetting stuck benchmarks
  ipcMain.handle('reset-stuck-benchmarks', async () => {
    try {
      console.log('Main: Received reset-stuck-benchmarks request');
      const result = await httpPostJson('/reset-stuck-benchmarks', {});
      console.log('Main: Reset stuck benchmarks result:', result);
      return result;
    } catch (error) {
      console.error('Error resetting stuck benchmarks:', error);
      return { success: false, error: error.message };
    }
  });

  // Validate tokens via HTTP
  ipcMain.handle('validate-tokens', async (event, { prompts, pdfPaths, modelNames }) => {
    try {
      const result = await httpPostJson('/validate-tokens', { prompts, pdfPaths, modelNames });
      return result;
    } catch (err) {
      console.error('Error validating tokens:', err);
      return { status: 'error', message: err.message };
    }
  });

  // Settings-related IPC handlers
  ipcMain.handle('get-settings', async () => {
    try {
      return { success: true, settings };
    } catch (error) {
      console.error('Error getting settings:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('save-settings', async (event, newSettings) => {
    try {
      settings = { ...settings, ...newSettings };
      await saveSettings();
      return { success: true };
    } catch (error) {
      console.error('Error saving settings:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('update-api-keys', async (event, apiKeys) => {
    try {
      settings.apiKeys = { ...settings.apiKeys, ...apiKeys };
      settings.firstTimeSetup = false; // Mark first-time setup as complete
      await saveSettings();
      console.log('[Settings] API keys updated successfully');
      
      // Restart the backend to pick up new API keys
      console.log('[Settings] Restarting backend with new API keys...');
      await restartBackend();
      console.log('[Settings] Backend restarted with new API keys');
      
      return { success: true };
    } catch (error) {
      console.error('Error updating API keys:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('check-api-keys', async () => {
    try {
      const hasKeys = hasValidApiKeys();
      return { 
        success: true, 
        hasApiKeys: hasKeys,
        isFirstTime: settings.firstTimeSetup 
      };
    } catch (error) {
      console.error('Error checking API keys:', error);
      return { success: false, error: error.message };
    }
  });

  // Shell functionality
  ipcMain.handle('shell-open-external', async (event, url) => {
    try {
      await shell.openExternal(url);
      return { success: true };
    } catch (error) {
      console.error('Error opening external URL:', error);
      return { success: false, error: error.message };
    }
  });

  // IPC for rerunning a single prompt
  ipcMain.handle('rerun-single-prompt', async (event, promptId) => {
    try {
      console.log(`Main: Received rerun-single-prompt request for ID: ${promptId}`);
      const result = await httpPostJson('/rerun-prompt', { prompt_id: promptId });
      console.log('Main: Rerun single prompt result:', result);
      return result;
    } catch (error) {
      console.error('Error rerunning single prompt:', error);
      return { success: false, error: error.message };
    }
  });
}
