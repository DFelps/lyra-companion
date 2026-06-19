const { app, BrowserWindow, globalShortcut, screen, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')
const { pathToFileURL } = require('url')

let win
let clickThrough = false

const projectRoot = path.resolve(__dirname, '../..')
const statePath = path.join(projectRoot, 'data', 'avatar', 'state.json')
const poseDir = path.join(projectRoot, 'assets', 'lyra', 'poses', '01_idle_default')
const partsDir = path.join(poseDir, '01_parts')

function ensureStateFile() {
  fs.mkdirSync(path.dirname(statePath), { recursive: true })

  if (!fs.existsSync(statePath)) {
    fs.writeFileSync(statePath, JSON.stringify({
      mode: 'idle',
      eye: 'open',
      mouth: 'closed',
      expression: 'neutral',
      speaking: false,
      mouth_level: 0,
      text: '',
      updated_at: Date.now() / 1000
    }, null, 2))
  }
}

function createWindow() {
  ensureStateFile()

  const display = screen.getPrimaryDisplay()
  const { width, height } = display.workAreaSize

  win = new BrowserWindow({
    width: 430,
    height: 760,
    x: width - 460,
    y: height - 790,
    frame: false,
    transparent: true,
    resizable: true,
    alwaysOnTop: true,
    hasShadow: false,
    skipTaskbar: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  win.setAlwaysOnTop(true, 'screen-saver')
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'))
}

app.whenReady().then(() => {
  createWindow()

  globalShortcut.register('CommandOrControl+Shift+L', () => {
    if (!win) return
    clickThrough = !clickThrough
    win.setIgnoreMouseEvents(clickThrough, { forward: true })
    win.webContents.send('click-through-changed', clickThrough)
  })

  globalShortcut.register('CommandOrControl+Shift+R', () => {
    if (win) win.reload()
  })
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})

ipcMain.handle('read-avatar-state', () => {
  try {
    return JSON.parse(fs.readFileSync(statePath, 'utf8'))
  } catch (error) {
    return null
  }
})

ipcMain.handle('get-avatar-config', () => ({
  poseBaseUrl: pathToFileURL(poseDir).href,
  partsBaseUrl: pathToFileURL(partsDir).href,
  baseImage: '01_idle_default.png'
}))
