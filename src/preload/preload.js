const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use IPC
contextBridge.exposeInMainWorld('electronAPI', {
  // File dialogs
  openFileDialog: (options) => ipcRenderer.invoke('open-file-dialog', options),
  
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
  runBenchmark: (prompts, pdfPath, modelNames) => {
    return ipcRenderer.invoke('run-benchmark', { prompts, pdfPath, modelNames });
  },
  getBenchmarkDetails: (id) => ipcRenderer.invoke('get-benchmark-details', id),
  exportBenchmarkToCsv: (id) => ipcRenderer.invoke('export-benchmark-to-csv', id),
  
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
