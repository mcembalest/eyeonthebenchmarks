const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs').promises;

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'test-preload.js')
        }
    });

    mainWindow.loadFile('test.html');
    mainWindow.webContents.openDevTools();
}

// Handle sound verification
ipcMain.handle('verify-sound', async () => {
    const soundPath = path.join(__dirname, 'src', 'renderer', 'assets', 'homer-woohoo.mp3');
    try {
        await fs.access(soundPath);
        console.log('Sound file exists at:', soundPath);
        return soundPath;
    } catch (error) {
        console.error('Sound file not found at:', soundPath);
        throw error;
    }
});

app.whenReady().then(createWindow);
