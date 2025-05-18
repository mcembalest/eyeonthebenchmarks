const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('testAPI', {
    verifySound: () => ipcRenderer.invoke('verify-sound')
});
