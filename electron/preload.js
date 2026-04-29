/**
 * electron/preload.js — Context bridge between main process and renderer.
 * Exposes minimal typed APIs to the renderer via window.edmd.
 */
'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('edmd', {
  getWsPort:  () => ipcRenderer.invoke('get-ws-port'),
  getVersion: () => ipcRenderer.invoke('get-version'),

  // Window controls (used by custom titlebar)
  minimize:   () => ipcRenderer.invoke('win-minimize'),
  maximize:   () => ipcRenderer.invoke('win-maximize'),
  fullscreen: () => ipcRenderer.invoke('win-fullscreen'),
  close:      () => ipcRenderer.invoke('win-close'),
  isMaximized:() => ipcRenderer.invoke('win-is-max'),
  openExternal:   (url)  => ipcRenderer.invoke('open-external', url),
  getEdmdConfig:  ()     => ipcRenderer.invoke('get-edmd-config'),
  saveEdmdConfig: (data) => ipcRenderer.invoke('save-edmd-config', data),
  browseFile:     (opts) => ipcRenderer.invoke('browse-file', opts),
  openLog:        ()     => ipcRenderer.invoke('open-log'),
  getLogPath:     ()     => ipcRenderer.invoke('get-log-path'),
});
