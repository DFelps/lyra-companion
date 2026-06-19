const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('lyraAvatar', {
  readState: () => ipcRenderer.invoke('read-avatar-state'),
  getConfig: () => ipcRenderer.invoke('get-avatar-config'),
  onClickThroughChanged: (callback) => ipcRenderer.on('click-through-changed', (_event, enabled) => callback(enabled))
})
