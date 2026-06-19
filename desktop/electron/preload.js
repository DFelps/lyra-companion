const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('lyraAvatar', {
  readState: () => ipcRenderer.invoke('read-avatar-state'),
  getConfig: () => ipcRenderer.invoke('get-avatar-config'),
  writeCommand: (command, payload = {}) => ipcRenderer.invoke('write-avatar-command', command, payload),
  toggleClickThrough: () => ipcRenderer.invoke('toggle-click-through'),
  reloadWindow: () => ipcRenderer.invoke('reload-avatar-window'),
  closeWindow: () => ipcRenderer.invoke('close-avatar-window'),
  onClickThroughChanged: (callback) => ipcRenderer.on('click-through-changed', (_event, enabled) => callback(enabled)),
  onToggleHud: (callback) => ipcRenderer.on('toggle-hud', () => callback()),
  onAvatarCommandSent: (callback) => ipcRenderer.on('avatar-command-sent', (_event, command) => callback(command))
})
