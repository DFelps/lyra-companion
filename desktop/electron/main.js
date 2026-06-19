const { app, BrowserWindow, globalShortcut, screen, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')
const crypto = require('crypto')
const { pathToFileURL } = require('url')

let win
let clickThrough = false

const projectRoot = path.resolve(__dirname, '../..')
const statePath = path.join(projectRoot, 'data', 'avatar', 'state.json')
const commandPath = path.join(projectRoot, 'data', 'avatar', 'commands.json')
const posesDir = path.join(projectRoot, 'assets', 'lyra', 'poses')

const defaultState = {
  mode: 'idle',
  pose: null,
  eye: 'open',
  mouth: 'closed',
  expression: 'neutral',
  speaking: false,
  mouth_level: 0,
  text: '',
  controls: {
    microphone: false,
    screen: false,
    listening: false
  },
  updated_at: Date.now() / 1000
}

function ensureAvatarFiles() {
  fs.mkdirSync(path.dirname(statePath), { recursive: true })

  if (!fs.existsSync(statePath)) {
    fs.writeFileSync(statePath, JSON.stringify(defaultState, null, 2), 'utf8')
  }
}

function readStateFile() {
  try {
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'))
    return {
      ...defaultState,
      ...state,
      controls: {
        ...defaultState.controls,
        ...(state.controls || {})
      }
    }
  } catch (error) {
    return defaultState
  }
}

function writeAvatarCommand(command, payload = {}) {
  fs.mkdirSync(path.dirname(commandPath), { recursive: true })

  const item = {
    id: crypto.randomUUID(),
    command,
    payload,
    created_at: Date.now() / 1000
  }

  const tempPath = `${commandPath}.tmp`
  fs.writeFileSync(tempPath, JSON.stringify(item, null, 2), 'utf8')
  fs.renameSync(tempPath, commandPath)

  return item
}

function setClickThrough(enabled) {
  if (!win) return false

  clickThrough = Boolean(enabled)
  win.setIgnoreMouseEvents(clickThrough, { forward: true })
  win.webContents.send('click-through-changed', clickThrough)
  return clickThrough
}

function createWindow() {
  ensureAvatarFiles()

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
    setClickThrough(!clickThrough)
  })

  globalShortcut.register('CommandOrControl+Shift+H', () => {
    if (win) win.webContents.send('toggle-hud')
  })

  globalShortcut.register('CommandOrControl+Shift+R', () => {
    if (win) win.reload()
  })

  globalShortcut.register('CommandOrControl+Shift+S', () => {
    writeAvatarCommand('stop_activity')
    if (win) win.webContents.send('avatar-command-sent', 'stop_activity')
  })

  globalShortcut.register('CommandOrControl+Shift+Q', () => {
    if (win) win.close()
  })
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})

ipcMain.handle('read-avatar-state', () => readStateFile())

ipcMain.handle('get-avatar-config', () => ({
  projectRoot,
  statePath,
  commandPath,
  posesBaseUrl: pathToFileURL(posesDir).href,
  poses: {
    idleDefault: {
      id: '01_idle_default',
      baseImage: '01_idle_default.png',
      partsDir: '01_parts',
      eyes: ['open', 'closed', 'serious', 'happy'],
      mouths: ['closed', 'middle_open', 'open', 'smile', 'surprise']
    },
    idleShift: {
      id: '02_idle_shift',
      baseImage: '02_idle_shift.png',
      partsDir: '02_parts',
      eyes: ['open', 'closed', 'serious', 'happy'],
      mouths: ['closed', 'middle_open', 'open', 'smile', 'surprise']
    },
    idleSoft: {
      id: '03_idle_soft',
      baseImage: '03_idle_soft.png',
      partsDir: '03_parts',
      eyes: ['open', 'closed', 'serious'],
      mouths: ['closed', 'middle_open', 'open', 'smile', 'surprise']
    },
    thinking: {
      id: '04_thinking',
      baseImage: '04_thinking.png',
      partsDir: '04_parts',
      eyes: ['open', 'closed'],
      mouths: ['closed']
    },
    listening: {
      id: '05_listening',
      baseImage: '05_listening.png',
      partsDir: '05_parts',
      eyes: ['open', 'closed', 'serious'],
      mouths: ['closed', 'middle_open', 'open', 'smile', 'surprise']
    },
    approach: {
      id: '06_approach',
      baseImage: '06_approach.png',
      partsDir: '06_parts',
      eyes: ['open', 'closed', 'serious'],
      mouths: ['closed', 'middle_open', 'open', 'smile', 'surprise']
    }
  }
}))

ipcMain.handle('write-avatar-command', (_event, command, payload) => {
  return writeAvatarCommand(command, payload || {})
})

ipcMain.handle('toggle-click-through', () => {
  return setClickThrough(!clickThrough)
})

ipcMain.handle('reload-avatar-window', () => {
  if (win) win.reload()
  return true
})

ipcMain.handle('close-avatar-window', () => {
  if (win) win.close()
  return true
})
