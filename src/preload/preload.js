const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use IPC
contextBridge.exposeInMainWorld('electronAPI', {
  // File dialogs
  openFileDialog: (options) => ipcRenderer.invoke('open-file-dialog', options),
  readParseCsv: (filePath) => ipcRenderer.invoke('read-parse-csv', filePath),
  
  // Benchmark operations with debugging
  listBenchmarks: async () => {
    console.log('Preload: Requesting benchmarks from main process');
    try {
      const result = await ipcRenderer.invoke('list-benchmarks');
      console.log('Preload: Received benchmark data:', result);
      return result;
    } catch (error) {
      console.error('Preload: Error fetching benchmarks:', error);
      return [];
    }
  },
  runBenchmark: (prompts, pdfPath, modelNames, benchmarkName, benchmarkDescription) => {
    console.log('Preload: runBenchmark called with name:', benchmarkName, 'desc:', benchmarkDescription);
    return ipcRenderer.invoke('run-benchmark', { prompts, pdfPath, modelNames, benchmarkName, benchmarkDescription });
  },
  getBenchmarkDetails: (id) => ipcRenderer.invoke('get-benchmark-details', id),
  exportBenchmarkToCsv: (id) => ipcRenderer.invoke('export-benchmark-to-csv', id),
  deleteBenchmark: (benchmarkId) => {
    console.log('Preload: deleteBenchmark called for ID:', benchmarkId);
    return ipcRenderer.invoke('delete-benchmark', benchmarkId);
  },
  updateBenchmarkDetails: (benchmarkId, newLabel, newDescription) => {
    console.log('Preload: updateBenchmarkDetails called for ID:', benchmarkId, 'New Label:', newLabel, 'New Desc:', newDescription);
    return ipcRenderer.invoke('update-benchmark-details', { benchmarkId, newLabel, newDescription });
  },
  
  // Get available models from Python
  getAvailableModels: async () => {
    console.log('Preload: Requesting available models from main process');
    try {
      const result = await ipcRenderer.invoke('get-available-models');
      console.log('Preload: Received model data:', result);
      return result;
    } catch (error) {
      console.error('Preload: Error fetching models:', error);
      return { success: false, models: [] };
    }
  },
  
  // Navigation
  navigateTo: (page) => ipcRenderer.send('navigate-to', page),

  // Sound playback - get verified path from main process
  playSound: (soundPath, shouldPlay = true) => ipcRenderer.invoke('play-sound', soundPath, shouldPlay),
  
  // System events - receive updates from main process
  onBenchmarkProgress: (callback) => ipcRenderer.on('benchmark-progress', (_, data) => callback(data)),
  onBenchmarkComplete: (callback) => ipcRenderer.on('benchmark-complete', (_, data) => callback(data)),
  onMainProcessReady: (callback) => ipcRenderer.on('main-process-ready', (_event, ...args) => callback(...args)),
});
