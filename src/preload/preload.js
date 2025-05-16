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
