# -*- coding: utf-8 -*-
"""
Modlist Manager - Plugin de Mod Organizer 2
============================================

Plugin que abre una interfaz web en el navegador para gestionar, ver y editar
la lista de mods del perfil activo de MO2.

Enfoque:
  - Lee los datos desde el CSV exportado por MO2 (File > Export mod list > CSV).
  - Si el CSV no existe, lo genera automaticamente leyendo meta.ini + modlist.txt.
  - Los comentarios se cargan desde meta.ini de cada mod (campo 'comments').
  - Los DLCs del juego se ocultan automaticamente; la lista parte desde el
    primer separador.
  - El estado activo/inactivo se detecta desde Mod_Estado (+/-/activo/inactivo).
  - UI rediseñada inspirada en fomod_db_explorer (tema azul oscuro, cards).
  - Settings en MO2: puerto, auto-start, debug, rotacion diaria de logs.

Autor: Krou705
Version: 3.2.0
"""

import os
import sys
import json
import re
import csv
import io
import base64
import logging
import threading
import webbrowser
import configparser
import urllib.parse
import urllib.request
import http.server
import socketserver
import mimetypes
import datetime
import struct
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import mobase
except ImportError:
    mobase = None

# ==================== HTML embebido ====================
HTML_CONTENT = r'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Modlist Manager</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg: #0f1419;
  --card: #1a2029;
  --card-hover: #232b36;
  --border: #2a3441;
  --border-light: #3a4453;
  --text: #e4e7eb;
  --text-dim: #8b95a3;
  --text-muted: #6b7280;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-dim: #1e40af;
  --green: #10b981;
  --red: #ef4444;
  --orange: #f59e0b;
  --purple: #a855f7;
  --gray: #6b7280;
  --font: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
  --mono: 'SF Mono', Monaco, Consolas, monospace;
  --radius: 10px;
  --radius-sm: 6px;
}
body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* === Topbar === */
.topbar {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  padding: 10px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}
.topbar .brand {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: 8px;
}
.topbar .brand .logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  background: var(--accent);
  color: white;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 800;
}
.topbar .profile-tag {
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-dim);
}
.topbar .profile-tag strong { color: var(--text); }
.topbar .spacer { flex: 1; }
.topbar .actions { display: flex; align-items: center; gap: 8px; }
.topbar .refresh-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  color: var(--text-dim);
}
.topbar .refresh-indicator:hover { background: var(--card-hover); }
.topbar .refresh-indicator .dot {
  width: 8px; height: 8px; border-radius: 50%;
}
.topbar .refresh-indicator .dot.on { background: var(--green); }
.topbar .refresh-indicator .dot.off { background: var(--red); }
.btn {
  background: var(--card-hover);
  border: 1px solid var(--border-light);
  color: var(--text);
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font);
  transition: all 0.15s;
}
.btn:hover { background: var(--border-light); }
.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}
.btn-primary:hover { background: var(--accent-hover); }
.btn-danger {
  background: var(--red);
  border-color: var(--red);
  color: white;
}
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-icon {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-dim);
  width: 28px; height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 16px;
}
.btn-icon:hover { background: var(--card-hover); color: var(--text); }

/* === Tabs === */
.tabs {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  display: flex;
  padding: 0 12px;
  flex-shrink: 0;
}
.tab {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-dim);
  padding: 12px 18px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
  transition: all 0.15s;
}
.tab:hover { color: var(--text); background: var(--card-hover); }
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

/* === Content === */
.content {
  flex: 1;
  overflow: hidden;
  position: relative;
}
.tab-panel {
  display: none;
  height: 100%;
  overflow: auto;
  padding: 16px;
}
.tab-panel.active { display: block; }

/* === Stats grid === */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.stats-actions {
  margin-left: auto;
  display: flex;
  gap: 12px;
}
.stats-action-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  flex: 1;
}
.stat-box {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
}
.stat-label {
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
}
.stat-value.green { color: var(--green); }
.stat-value.orange { color: var(--orange); }
.stat-value.red { color: var(--red); }
.stat-value.purple { color: var(--purple); }
.stat-value.blue { color: var(--accent); }

/* === Controls bar === */
.controls {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  margin-bottom: 14px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}
.search-input {
  flex: 1;
  min-width: 200px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  color: var(--text);
  font-size: 13px;
  font-family: var(--font);
}
.search-input:focus { outline: none; border-color: var(--accent); }
.select {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 7px 10px;
  color: var(--text);
  font-size: 13px;
  font-family: var(--font);
  cursor: pointer;
}
.select:focus { outline: none; border-color: var(--accent); }

/* === CSV missing notice === */
.notice {
  background: var(--card);
  border: 2px solid var(--orange);
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: 14px;
}
.notice h3 {
  color: var(--orange);
  margin-bottom: 10px;
  font-size: 18px;
}
.notice p { color: var(--text-dim); margin-bottom: 10px; }
.notice ol { color: var(--text-dim); margin-left: 20px; }
.notice ol li { margin-bottom: 6px; }
.notice code {
  background: var(--bg);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--accent);
  font-family: var(--mono);
  font-size: 12px;
}

/* === Mod table === */
.table-wrap {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: auto;
  max-height: calc(100vh - 280px);
}
.mod-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.mod-table thead {
  position: sticky;
  top: 0;
  z-index: 5;
}
.mod-table th {
  background: var(--card-hover);
  border-bottom: 2px solid var(--border-light);
  padding: 10px 12px;
  text-align: left;
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  resize: horizontal;
  overflow: hidden;
  position: relative;
  min-width: 50px;
}
.mod-table th::after {
  content: "";
  position: absolute;
  top: 0; right: 0; bottom: 0;
  width: 4px;
  cursor: col-resize;
}
.mod-table th:hover::after { background: var(--accent); opacity: 0.4; }
.mod-table td {
  padding: 7px 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.mod-table tbody tr:hover { background: var(--card-hover); }

/* Column widths */
.col-status { width: 50px; text-align: center; min-width: 50px; }
.col-priority { width: 80px; text-align: right; min-width: 65px; font-variant-numeric: tabular-nums; }
.col-name { min-width: 200px; width: 300px; }
.col-category { width: 140px; min-width: 80px; }
.col-version { width: 90px; min-width: 60px; }
.col-comment { width: 200px; min-width: 100px; }
.col-comment2 { width: 200px; min-width: 100px; }
.col-link { width: 70px; text-align: center; min-width: 50px; }

/* Status cell */
.status-on { color: var(--green); font-weight: 700; font-size: 14px; }
.status-off { color: var(--text-muted); font-size: 14px; }

/* Separator rows */
tr.sep-row {
  cursor: pointer;
  user-select: none;
}
tr.sep-row td {
  background: var(--sep-bg, linear-gradient(90deg, var(--accent-dim), var(--accent)));
  color: var(--sep-text, white);
  font-weight: 700;
  padding: 10px 12px;
  border-bottom: 2px solid var(--border-light);
  font-size: 14px;
}
tr.sep-row .sep-toggle {
  display: inline-block;
  width: 16px;
  transition: transform 0.15s;
  color: var(--sep-text, white);
}
tr.sep-row.collapsed .sep-toggle { transform: rotate(-90deg); }

/* Mod rows */
tr.mod-row.missing {
  color: var(--red);
}
tr.mod-row.missing .mod-name {
  text-decoration: line-through;
}
tr.mod-row.missing td {
  background: rgba(239, 68, 68, 0.08);
}
.mod-link {
  color: var(--accent);
  text-decoration: none;
  font-size: 12px;
}
.mod-link:hover { text-decoration: underline; }
.badge {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  margin-left: 6px;
}
.badge-deleted { background: var(--red); color: white; }
td.editable { cursor: pointer; }
td.editable:hover { background: rgba(59, 130, 246, 0.1); }

/* === Panels === */
.panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  margin-bottom: 14px;
}
.panel h2 {
  font-size: 18px;
  margin-bottom: 8px;
  color: var(--text);
}
.panel h3 {
  font-size: 15px;
  margin-bottom: 8px;
  color: var(--accent);
}
.panel p { color: var(--text-dim); margin-bottom: 12px; }
.panel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 900px) { .panel-grid { grid-template-columns: 1fr; } }
.btn-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
textarea, input[type=text]:not(.search-input) {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  padding: 8px 10px;
  font-family: var(--mono);
  font-size: 12px;
  resize: vertical;
}
textarea:focus, input[type=text]:focus { outline: none; border-color: var(--accent); }
.input-row { margin-bottom: 8px; }
hr { border: none; border-top: 1px solid var(--border); margin: 14px 0; }

/* === Editor === */
.editor-controls { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.editor-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}
.editor-list {
  list-style: none;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  max-height: 300px;
  overflow: auto;
  padding: 4px;
}
.editor-list li {
  padding: 5px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  font-family: var(--mono);
  word-break: break-all;
}
.editor-list li:last-child { border-bottom: none; }
.editor-diff {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  font-family: var(--mono);
  font-size: 12px;
}
.diff-only-current { color: var(--orange); }
.diff-only-imported { color: var(--accent); }
.diff-match { color: var(--text-muted); }

/* === Nemesis === */
.nem-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  margin-bottom: 14px;
}
.nem-tab {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-dim);
  padding: 10px 18px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
}
.nem-tab:hover { color: var(--text); }
.nem-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.nem-mode-bar {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 14px;
  padding: 10px 14px;
  background: var(--card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  flex-wrap: wrap;
}
.nem-mode-bar label {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-dim);
  font-size: 13px;
  cursor: pointer;
}
.nem-table-wrap {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 14px;
  margin-bottom: 14px;
}
.nem-table { width: 100%; border-collapse: collapse; }
.nem-table th {
  text-align: left;
  padding: 8px 10px;
  background: var(--card-hover);
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.nem-table td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--border);
}
.nem-table tr:hover { background: var(--card-hover); }
.nem-table tr.manual-row { background: rgba(59, 130, 246, 0.05); }
.nem-table tr.manual-row input[type=text] {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 4px 8px;
  border-radius: 4px;
  font-family: var(--mono);
  font-size: 12px;
}
.nem-table tr.manual-row input[type=text]:focus { outline: none; border-color: var(--accent); }
.btn-delete-manual {
  background: var(--red);
  color: white;
  border: none;
  width: 24px; height: 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}
.btn-delete-manual:hover { opacity: 0.85; }

/* Boton eliminar mod en la tabla principal */
.btn-delete-mod {
  background: var(--red);
  color: white;
  border: none;
  width: 22px; height: 22px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  margin-left: 6px;
  display: inline-block;
  vertical-align: middle;
}
.btn-delete-mod:hover { opacity: 0.85; }

/* Boton toggle "Ocultar eliminados" - estado activo */
#btn-hide-deleted.active {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

/* Boton olvidar en la pestaña de eliminados */
.btn-forget-mod {
  background: var(--red);
  color: white;
  border: none;
  width: 24px; height: 22px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  font-weight: 700;
}
.btn-forget-mod:hover { opacity: 0.85; }

/* Badge para "carpeta no encontrada" (no marcada como eliminada) */
.badge-folder-missing {
  background: var(--orange);
  color: white;
}

/* Drag-and-drop */
.mod-table tr.dragging { opacity: 0.5; }
.mod-table tr.drag-over { border-top: 3px solid var(--accent); }
.priority-input:focus { outline: none; border-color: var(--accent); }

/* Boton de color en separadores */
.sep-color-btn {
  background: rgba(255,255,255,0.15);
  border: none;
  color: white;
  cursor: pointer;
  font-size: 14px;
  width: 24px; height: 24px;
  border-radius: 4px;
  margin-right: 8px;
  display: inline-block;
  vertical-align: middle;
}
.sep-color-btn:hover { background: rgba(255,255,255,0.3); }

.nem-image-wrap {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 14px;
  margin-bottom: 14px;
}
.image-upload-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.image-upload-row input[type=file] {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 6px;
  border-radius: var(--radius-sm);
  color: var(--text);
}
.nem-images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.nem-image-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.nem-image-card img { width: 100%; display: block; cursor: pointer; }
.nem-image-card .image-actions {
  padding: 6px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--card-hover);
  font-size: 12px;
  color: var(--text-dim);
}
.nem-info {
  color: var(--text-dim);
  font-size: 12px;
  padding: 10px 14px;
  background: var(--card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

/* === Toast === */
.toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: var(--card);
  color: var(--text);
  padding: 12px 18px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  border-left: 4px solid var(--accent);
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  z-index: 1000;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
  font-size: 13px;
  max-width: 400px;
}
.toast.show { opacity: 1; }
.toast.error { border-left-color: var(--red); }
.toast.success { border-left-color: var(--green); }
.toast.warning { border-left-color: var(--orange); }

/* === Modal === */
.modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal.hidden { display: none; }
.modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.7);
}
.modal-content {
  position: relative;
  background: var(--card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  width: 520px;
  max-width: 90vw;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.modal-header {
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.modal-header h3 { font-size: 16px; color: var(--accent); }
.modal-close {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
}
.modal-close:hover { color: var(--text); }
.modal-body { padding: 18px; }
.form-row { margin-bottom: 14px; }
.form-row label {
  display: block;
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.form-row input, .form-row textarea {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  font-family: var(--font);
  font-size: 13px;
}
.form-row input:disabled { opacity: 0.5; cursor: not-allowed; }
.form-row input:focus, .form-row textarea:focus { outline: none; border-color: var(--accent); }
.modal-footer {
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* === Scrollbar === */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
/*EXTENSION_CSS*/
</style>
</head>
<body>

<!-- Topbar -->
<div class="topbar">
  <div class="brand">
    <span class="logo">M</span>
    <span>Modlist Manager</span>
  </div>
  <div class="profile-tag">
    <span data-i18n="topbar.profile">Perfil:</span>
    <strong id="profile-name">—</strong>
  </div>
  <div class="spacer"></div>
  <div class="actions">
    <div class="refresh-indicator" id="refresh-toggle" title="Click to pause/resume auto-refresh">
      <span class="dot on" id="refresh-dot"></span>
      <span id="refresh-label">Auto</span>
    </div>
    <button class="btn btn-sm" id="btn-refresh" data-i18n="topbar.refresh">Actualizar</button>
  </div>
</div>

<!-- Tabs -->
<div class="tabs">
  <button class="tab active" data-tab="modlist" data-i18n="tabs.modlist">Lista de mods</button>
  <button class="tab" data-tab="deleted" data-i18n="tabs.deleted">Eliminados</button>
  <button class="tab" data-tab="nemesis" data-i18n="tabs.nemesis">Nemesis / Pandora / Custom</button>
  <button class="tab" data-tab="backups" data-i18n="tabs.backups">Respaldos</button>
  <button class="tab" data-tab="plugins" data-i18n="tabs.plugins">Plugins</button>
  <button class="tab" data-tab="versions" data-i18n="tabs.versions">Versiones</button>
  <!--EXTENSION_TAB-->
  <button class="tab" data-tab="import_export" data-i18n="tabs.import_export">Importar / Exportar</button>
</div>

<!-- Content -->
<div class="content">

  <!-- Tab: Modlist -->
  <section id="tab-modlist" class="tab-panel active">
    <div class="stats-bar" id="stats-bar">
      <div class="stats-grid" id="stats-grid">
        <div class="stat-box"><div class="stat-label" data-i18n="modlist.stat_total">Total</div><div class="stat-value blue" id="stat-total">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="modlist.stat_active">Activos</div><div class="stat-value green" id="stat-active">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="modlist.stat_inactive">Inactivos</div><div class="stat-value orange" id="stat-inactive">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="modlist.stat_missing">Eliminados</div><div class="stat-value red" id="stat-missing">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="modlist.stat_separators">Separadores</div><div class="stat-value purple" id="stat-separators">0</div></div>
      </div>
      <div class="stats-actions">
        <div class="stats-action-col">
          <button class="btn btn-sm" id="btn-expand-all" data-i18n="modlist.expand_all">Expandir todo</button>
          <button class="btn btn-sm" id="btn-collapse-all" data-i18n="modlist.collapse_all">Contraer todo</button>
        </div>
        <div class="stats-action-col">
          <button class="btn btn-sm" id="btn-hide-deleted" data-i18n="modlist.hide_deleted" data-i18n-title="modlist.hide_deleted_title">Ocultar eliminados</button>
          <button class="btn btn-primary btn-sm" id="btn-sync-mo2" data-i18n="modlist.sync_mo2" data-i18n-title="modlist.sync_mo2_title">Sincronizar desde MO2</button>
          <button class="btn btn-sm" id="btn-refresh-csv" data-i18n="modlist.refresh_csv" data-i18n-title="modlist.refresh_csv_title">Actualizar desde CSV</button>
        </div>
      </div>
    </div>

    <div class="controls">
      <input type="text" class="search-input" id="search-input" data-i18n-placeholder="modlist.search_placeholder" placeholder="Buscar mod...">
      <select class="select" id="filter-separator"><option value="" data-i18n="modlist.filter_all_separators">Todos los separadores</option></select>
      <select class="select" id="filter-status">
        <option value="" data-i18n="modlist.filter_all_status">Todos</option>
        <option value="active" data-i18n="modlist.filter_active">Activos</option>
        <option value="inactive" data-i18n="modlist.filter_inactive">Inactivos</option>
        <option value="missing" data-i18n="modlist.filter_missing">Eliminados</option>
      </select>
      <select class="select" id="filter-category"><option value="" data-i18n="modlist.filter_all_categories">Todas las categorias</option></select>
      <select class="select" id="filter-tags"><option value="" data-i18n="modlist.filter_all_tags">Todas las etiquetas</option></select>
    </div>

    <div class="notice" id="csv-notice" style="display:none;">
      <h3 data-i18n="csv.missing_title">No se encontro el CSV de MO2</h3>
      <p data-i18n="csv.missing_desc">Para que el plugin funcione, necesitas exportar tu lista de mods desde MO2:</p>
      <ol>
        <li data-i18n="csv.missing_step1">En MO2, ve a Open List Options (Opciones de lista abierta) &gt; Export CSV (Exportar lista a CSV)</li>
        <li data-i18n="csv.missing_step2">Selecciona "Todos los mods instalados"</li>
        <li data-i18n="csv.missing_step3">Marca todas las columnas a exportar (especialmente Mod_Prioridad)</li>
        <li><span data-i18n="csv.missing_step4">Guarda el archivo como</span> <strong style="color:var(--accent);">modlist.csv</strong> <button class="btn btn-sm" id="btn-copy-csvname" style="padding:1px 8px;font-size:11px;margin-left:6px;" data-i18n="csv.copy_btn">Copiar</button> <span data-i18n="csv.missing_step4b">en una de estas rutas:</span></li>
      </ol>
      <p style="margin-left:20px;"><span data-i18n="csv.missing_plugin_path">Carpeta del plugin:</span> <code id="csv-expected-path"></code></p>
      <p style="margin-left:20px;"><span data-i18n="csv.missing_mo2_path">Raiz de MO2:</span> <code id="csv-mo2-path"></code></p>
      <p style="margin-top:10px;" data-i18n="csv.missing_step5">Despues pulsa "Actualizar" arriba a la derecha</p>
    </div>

    <div class="table-wrap" id="table-wrap">
      <table class="mod-table" id="modlist-table">
        <thead>
          <tr>
            <th class="col-status" data-col="status" data-i18n="modlist.col_status">Act</th>
            <th class="col-priority" data-col="priority" data-i18n="modlist.col_order">#</th>
            <th id="th-trad" style="display:none;width:60px;text-align:center;">Trad</th>
            <th class="col-name" data-col="name" data-i18n="modlist.col_name">Mod</th>
            <th class="col-category" data-col="category" data-i18n="modlist.col_category">Categoria</th>
            <th class="col-version" data-col="version" data-i18n="modlist.col_version">Version</th>
            <th class="col-comment" data-col="comment" data-i18n="modlist.col_comment">Comentario</th>
            <th class="col-comment2" data-col="comment2" data-i18n="modlist.col_comment2">Comentario 2</th>
            <th class="col-link" data-col="link" data-i18n="modlist.col_link">Link</th>
            <th style="width:40px;text-align:center;">📂</th>
          </tr>
        </thead>
        <tbody id="modlist-tbody"></tbody>
      </table>
    </div>
  </section>

  <!-- Tab: Nemesis -->
  <section id="tab-nemesis" class="tab-panel">
    <div class="nem-tabs">
      <button class="nem-tab active" data-engine="nemesis">Nemesis</button>
      <button class="nem-tab" data-engine="pandora">Pandora</button>
      <button class="nem-tab" data-engine="custom">Custom</button>
    </div>
    <div class="nem-mode-bar">
      <label><input type="checkbox" id="nem-show-table" checked><span data-i18n="nemesis.show_table">Mostrar tabla</span></label>
      <label><input type="checkbox" id="nem-show-image" checked><span data-i18n="nemesis.show_image">Mostrar imagen</span></label>
      <button class="btn btn-sm" id="nem-autodetect" data-i18n="nemesis.autodetect">Auto-detectar</button>
      <button class="btn btn-primary btn-sm" id="nem-add-row" data-i18n="nemesis.add_row">Agregar fila</button>
    </div>
    <div class="nem-table-wrap" id="nem-table-wrap">
      <h3 data-i18n="nemesis.table_title">Mods con animaciones</h3>
      <table class="nem-table">
        <thead><tr>
          <th data-i18n="nemesis.col_active">Activado</th>
          <th data-i18n="nemesis.col_mod">Mod</th>
          <th data-i18n="nemesis.col_folder">Carpeta detectada</th>
          <th data-i18n="nemesis.col_comment">Comentario</th>
          <th data-i18n="nemesis.col_link">Link</th>
          <th data-i18n="nemesis.col_actions">Acciones</th>
        </tr></thead>
        <tbody id="nemesis-tbody"></tbody>
      </table>
    </div>
    <div class="nem-image-wrap" id="nem-image-wrap">
      <h3 data-i18n="nemesis.image_title">Captura del engine</h3>
      <div class="image-upload-row">
        <input type="file" id="nem-image-input" accept="image/*">
        <button class="btn btn-primary" id="nem-image-upload" data-i18n="nemesis.upload">Subir captura</button>
      </div>
      <div id="nemesis-images" class="nem-images"></div>
    </div>
    <div class="nem-info" id="nemesis-info"></div>
  </section>

  <!-- Tab: Respaldos -->
  <section id="tab-backups" class="tab-panel">
    <div class="panel">
      <h2 data-i18n="backups.title">Respaldos</h2>
      <p data-i18n="backups.desc">Crea y restaura respaldos por separado de tu lista de mods y del estado de Nemesis.</p>
      <p id="backups-location" style="font-size:12px;color:var(--text-dim);margin-bottom:10px;"></p>
      <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px;margin-bottom:14px;font-size:12px;color:var(--text-dim);">
        <strong data-i18n="backups.what_backup">Que se respalda:</strong>
        <ul style="margin-left:16px;margin-top:4px;">
          <li data-i18n="backups.what_modlist">Lista de mods: prioridad, nombre, categoria, version, comentario MO2, link</li>
          <li data-i18n="backups.what_memory">Overrides: comentario 2, categoria editada, link editado, etiquetas</li>
          <li data-i18n="backups.what_nemesis">Nemesis/Pandora/Custom: mods activados, desactivados, manuales</li>
        </ul>
      </div>

      <div class="nem-tabs">
        <button class="nem-tab active" data-backup-type="modlist" data-i18n="backups.modlist_tab">Lista de mods</button>
        <button class="nem-tab" data-backup-type="nemesis" data-i18n="backups.nemesis_tab">Nemesis / Pandora / Custom</button>
      </div>

      <div class="btn-row">
        <button class="btn btn-primary" id="btn-create-backup" data-i18n="backups.create">Crear respaldo</button>
        <button class="btn" id="btn-refresh-backups" data-i18n="backups.refresh">Actualizar lista</button>
      </div>

      <div class="editor-comparison">
        <div>
          <h3 data-i18n="backups.current">Estado actual</h3>
          <div id="backup-current-info" style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;font-size:13px;color:var(--text-dim);min-height:80px;"></div>
        </div>
        <div>
          <h3 data-i18n="backups.available">Respaldos disponibles</h3>
          <ul id="backups-list" class="editor-list" style="max-height:300px;"></ul>
        </div>
      </div>

      <div id="backup-detail" class="editor-diff" style="margin-top:14px;"></div>
    </div>
  </section>

  <!-- Tab: Plugins -->
  <section id="tab-plugins" class="tab-panel">
    <div class="panel">
      <h2 data-i18n="plugins.title">Plugin Slots</h2>
      <p data-i18n="plugins.desc">Muestra que mods ocupan slots de plugins (.esp/.esm/.esl) en tu load order. El limite del juego es de 255 plugins activos. Los .esp marcados como ESL (ESPFE) se detectan leyendo la cabecera binaria y se cuentan como Light, no como ESP estandar.</p>
      <div class="stats-grid" id="plugins-stats">
        <div class="stat-box"><div class="stat-label" data-i18n="plugins.total_active">Activos</div><div class="stat-value" style="color:var(--accent);font-size:24px;" id="stat-total-active">0</div></div>
        <div class="stat-box"><div class="stat-label">ESM</div><div class="stat-value purple" id="stat-esm">0</div></div>
        <div class="stat-box"><div class="stat-label">ESP</div><div class="stat-value blue" id="stat-esp">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="plugins.esm_esp">ESM+ESP</div><div class="stat-value orange" id="stat-plugin-slots">0</div></div>
        <div class="stat-box"><div class="stat-label">ESL</div><div class="stat-value green" id="stat-esl">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="plugins.remaining">/ 255</div><div class="stat-value" style="color:var(--text-dim);" id="stat-remaining-slots">255</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="plugins.mods_with">Mods con plugin</div><div class="stat-value" style="color:var(--accent);" id="stat-mods-with-plugins">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="plugins.mods_without">Mods sin plugin</div><div class="stat-value" style="color:var(--text-muted);" id="stat-mods-without-plugins">0</div></div>
      </div>
      <div class="controls">
        <input type="text" class="search-input" id="plugins-search" data-i18n-placeholder="modlist.search_placeholder" placeholder="Buscar mod...">
        <select class="select" id="plugins-filter">
          <option value="" data-i18n="plugins.filter_all">Todos</option>
          <option value="with" data-i18n="plugins.filter_with">Con plugins</option>
          <option value="without" data-i18n="plugins.filter_without">Sin plugins</option>
          <option value="light" data-i18n="plugins.filter_light">Light (.esl / ESPFE)</option>
          <option value="esp" data-i18n="plugins.filter_esp">ESP estandar</option>
          <option value="standard" data-i18n="plugins.filter_standard">Standard</option>
          <option value="esm" data-i18n="plugins.filter_esm">ESM</option>
          <option value="base" data-i18n="plugins.filter_base">Base Game</option>
        </select>
        <select class="select" id="plugins-sort">
          <option value="name" data-i18n="plugins.sort_name">Ordenar: Nombre</option>
          <option value="count" data-i18n="plugins.sort_count">Ordenar: Cantidad</option>
          <option value="type" data-i18n="plugins.sort_type">Ordenar: Tipo</option>
          <option value="active" data-i18n="plugins.sort_active">Ordenar: Activo</option>
        </select>
        <button class="btn btn-sm" id="btn-plugins-refresh" data-i18n="plugins.scan">Escanear</button>
      </div>
      <div class="table-wrap">
        <table class="mod-table" id="plugins-table">
          <thead><tr>
            <th class="col-status" data-i18n="modlist.col_status">Act</th>
            <th class="col-name" data-i18n="modlist.col_name">Mod</th>
            <th data-i18n="plugins.col_files" style="max-width:400px;">Archivos de plugin</th>
            <th data-i18n="plugins.col_count" style="width:80px;">Cant.</th>
            <th data-i18n="plugins.col_type">Tipo</th>
          </tr></thead>
          <tbody id="plugins-tbody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- Tab: Versions -->
  <section id="tab-versions" class="tab-panel">
    <div class="panel">
      <h2 data-i18n="versions.title">Versiones de mods</h2>

      <!-- Sub-tabs -->
      <div class="nem-tabs" id="versions-subtabs">
        <button class="nem-tab active" data-vsubtab="mods" data-i18n="versions.subtab_mods">Mods</button>
        <button class="nem-tab" data-vsubtab="custom" data-i18n="versions.subtab_custom">Personalizada</button>
        <button class="nem-tab" data-vsubtab="backups" data-i18n="versions.subtab_backups">Respaldos</button>
      </div>

      <!-- Sub-tab: Mods (auto-generated from meta.ini) -->
      <div class="versions-subpanel" id="vsub-mods">
        <p data-i18n="versions.desc">Lista los mods instalados con su ID de Nexus, version actual y enlace directo a la version instalada. El enlace de version permite descargar archivos especificos incluso si el autor los ha archivado, usando el file_id del meta.ini.</p>
        <div class="stats-grid" id="versions-stats">
          <div class="stat-box"><div class="stat-label" data-i18n="versions.total">Total mods</div><div class="stat-value" style="color:var(--accent);font-size:24px;" id="stat-versions-total">0</div></div>
          <div class="stat-box"><div class="stat-label" data-i18n="versions.with_link">Con enlace de version</div><div class="stat-value green" id="stat-versions-with-link">0</div></div>
          <div class="stat-box"><div class="stat-label" data-i18n="versions.without_link">Sin enlace</div><div class="stat-value orange" id="stat-versions-without-link">0</div></div>
          <div class="stat-box"><div class="stat-label" data-i18n="versions.with_nexus_id">Con Nexus ID</div><div class="stat-value blue" id="stat-versions-with-nexus">0</div></div>
          <div class="stat-box"><div class="stat-label" data-i18n="versions.multi_file">Multi-archivo</div><div class="stat-value purple" id="stat-versions-multi">0</div></div>
        </div>
        <div class="controls">
          <input type="text" class="search-input" id="versions-search" data-i18n-placeholder="modlist.search_placeholder" placeholder="Buscar mod...">
          <select class="select" id="versions-filter-sep">
            <option value="" data-i18n="versions.filter_all_sep">Todos los separadores</option>
          </select>
          <select class="select" id="versions-filter-type">
            <option value="" data-i18n="versions.filter_all_types">Todos</option>
            <option value="with_link" data-i18n="versions.filter_with_link">Con enlace de version</option>
            <option value="without_link" data-i18n="versions.filter_without_link">Sin enlace</option>
            <option value="multi" data-i18n="versions.filter_multi">Multi-archivo</option>
          </select>
          <button class="btn btn-sm" id="btn-versions-refresh" data-i18n="versions.refresh">Actualizar</button>
        </div>
        <div class="table-wrap">
          <table class="mod-table" id="versions-table">
            <thead><tr>
              <th class="col-status" data-i18n="versions.col_active">Act</th>
              <th class="col-name" data-i18n="modlist.col_name">Mod</th>
              <th data-i18n="versions.col_nexus_id" style="width:120px;">Nexus ID</th>
              <th data-i18n="versions.col_file_id" style="width:120px;">File ID</th>
              <th class="col-version" data-i18n="modlist.col_version">Version</th>
              <th data-i18n="versions.col_version_link" style="min-width:160px;">Enlace de version</th>
              <th data-i18n="versions.col_separator" style="min-width:140px;">Separador</th>
              <th data-i18n="versions.col_comment" style="min-width:140px;">Comentario</th>
              <th data-i18n="versions.col_actions" style="width:80px;">Acciones</th>
            </tr></thead>
            <tbody id="versions-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- Sub-tab: Custom (manual version links) -->
      <div class="versions-subpanel" id="vsub-custom" style="display:none;">
        <p data-i18n="versions.custom_desc">Agrega manualmente enlaces a versiones especificas de mods. Introduce el ID del mod, ID de archivo (file_id) y nombre. El enlace se genera automaticamente. Los datos se guardan en el perfil y pueden respaldarse.</p>
        <div class="stats-grid" id="custom-versions-stats">
          <div class="stat-box"><div class="stat-label" data-i18n="versions.custom_total">Entradas</div><div class="stat-value" style="color:var(--accent);font-size:24px;" id="stat-custom-total">0</div></div>
        </div>
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;margin-bottom:10px;">
          <strong data-i18n="versions.add_entry">Agregar entrada</strong>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;align-items:flex-end;">
            <div>
              <label style="font-size:11px;color:var(--text-dim);" data-i18n="versions.field_mod_name">Nombre del mod</label><br>
              <input type="text" id="cv-mod-name" style="width:200px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:4px 8px;font-size:13px;" data-i18n-placeholder="versions.field_mod_name_ph" placeholder="Interesting NPCs SE">
            </div>
            <div>
              <label style="font-size:11px;color:var(--text-dim);" data-i18n="versions.field_mod_id">Mod ID</label><br>
              <input type="number" id="cv-mod-id" style="width:100px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:4px 8px;font-size:13px;" placeholder="131938">
            </div>
            <div>
              <label style="font-size:11px;color:var(--text-dim);" data-i18n="versions.field_file_id">File ID</label><br>
              <input type="number" id="cv-file-id" style="width:100px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:4px 8px;font-size:13px;" placeholder="731810">
            </div>
            <div>
              <label style="font-size:11px;color:var(--text-dim);" data-i18n="versions.field_version">Version</label><br>
              <input type="text" id="cv-version" style="width:80px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:4px 8px;font-size:13px;" placeholder="4.4.3">
            </div>
            <div>
              <label style="font-size:11px;color:var(--text-dim);" data-i18n="versions.field_comment">Comentario</label><br>
              <input type="text" id="cv-comment" style="width:200px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:4px 8px;font-size:13px;" data-i18n-placeholder="versions.field_comment_ph" placeholder="Version archivada">
            </div>
            <button type="button" class="btn btn-primary btn-sm" id="btn-cv-add" data-i18n="versions.add_btn">Agregar</button>
          </div>
          <div id="cv-preview" style="margin-top:8px;font-size:12px;color:var(--text-dim);"></div>
        </div>
        <div class="controls">
          <input type="text" class="search-input" id="cv-search" data-i18n-placeholder="modlist.search_placeholder" placeholder="Buscar...">
          <button class="btn btn-sm" id="btn-cv-refresh" data-i18n="versions.refresh">Actualizar</button>
        </div>
        <div class="table-wrap">
          <table class="mod-table" id="custom-versions-table">
            <thead><tr>
              <th class="col-name" data-i18n="modlist.col_name">Mod</th>
              <th data-i18n="versions.col_nexus_id" style="width:100px;">Mod ID</th>
              <th data-i18n="versions.col_file_id" style="width:100px;">File ID</th>
              <th class="col-version" data-i18n="modlist.col_version">Version</th>
              <th data-i18n="versions.col_version_link" style="min-width:140px;">Enlace</th>
              <th class="col-comment" data-i18n="versions.col_comment">Comentario</th>
              <th class="col-status" data-i18n="versions.col_delete">Eliminar</th>
            </tr></thead>
            <tbody id="custom-versions-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- Sub-tab: Backups -->
      <div class="versions-subpanel" id="vsub-backups" style="display:none;">
        <p data-i18n="versions.backups_desc">Crea y restaura respaldos de la lista de mods (con enlaces de version) y de la lista personalizada. Los respaldos se guardan como JSON.</p>
        <div class="controls">
          <button type="button" class="btn btn-primary btn-sm" id="btn-vb-create-mods" data-i18n="versions.backup_mods">Respaldar lista de mods</button>
          <button type="button" class="btn btn-primary btn-sm" id="btn-vb-create-custom" data-i18n="versions.backup_custom">Respaldar lista personalizada</button>
          <button type="button" class="btn btn-sm" id="btn-vb-refresh" data-i18n="versions.refresh">Actualizar</button>
        </div>
        <div class="table-wrap" style="margin-top:10px;">
          <table class="mod-table" id="version-backups-table">
            <thead><tr>
              <th data-i18n="versions.backup_name" style="min-width:200px;">Nombre</th>
              <th data-i18n="versions.backup_type" style="width:120px;">Tipo</th>
              <th data-i18n="versions.backup_entries" style="width:80px;">Entradas</th>
              <th data-i18n="versions.backup_date" style="width:160px;">Fecha</th>
              <th data-i18n="versions.backup_actions" style="width:200px;">Acciones</th>
            </tr></thead>
            <tbody id="version-backups-tbody"></tbody>
          </table>
        </div>
      </div>

    </div>
  </section>

  <!-- Tab: Deleted Mods -->
  <section id="tab-deleted" class="tab-panel">
    <div class="panel">
      <h2 data-i18n="deleted.title">Mods eliminados</h2>
      <p data-i18n="deleted.desc">Estos mods estaban en tu lista pero su carpeta ya no existe en disco. Usa esta vista para aislarlos de la lista principal y decidir si quieres olvidarlos (eliminarlos de la base de datos) o reinstalarlos.</p>
      <div class="stats-grid" id="deleted-stats">
        <div class="stat-box"><div class="stat-label" data-i18n="deleted.total">Total eliminados</div><div class="stat-value red" id="stat-deleted-total">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="deleted.marked">Marcados como eliminados</div><div class="stat-value red" id="stat-deleted-marked">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="deleted.missing_folder">Carpeta no encontrada</div><div class="stat-value orange" id="stat-deleted-missing">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="deleted.with_separator">En un separador</div><div class="stat-value purple" id="stat-deleted-in-sep">0</div></div>
        <div class="stat-box"><div class="stat-label" data-i18n="deleted.no_separator">Sin separador</div><div class="stat-value" style="color:var(--text-dim);" id="stat-deleted-no-sep">0</div></div>
      </div>
      <div class="controls">
        <input type="text" class="search-input" id="deleted-search" data-i18n-placeholder="modlist.search_placeholder" placeholder="Buscar mod...">
        <select class="select" id="deleted-filter-sep">
          <option value="" data-i18n="deleted.filter_all_sep">Todos los separadores</option>
        </select>
        <select class="select" id="deleted-filter-type">
          <option value="" data-i18n="deleted.filter_all_types">Todos los tipos</option>
          <option value="marked" data-i18n="deleted.filter_marked">Marcados como eliminados</option>
          <option value="missing" data-i18n="deleted.filter_missing">Carpeta no encontrada</option>
        </select>
        <button class="btn btn-sm" id="btn-deleted-refresh" data-i18n="deleted.refresh">Actualizar</button>
        <button type="button" class="btn btn-danger btn-sm" id="btn-forget-all" data-i18n="deleted.forget_all" data-i18n-title="deleted.forget_all_title">Olvidar todos</button>
      </div>
      <div class="table-wrap">
        <table class="mod-table" id="deleted-table">
          <thead><tr>
            <th class="col-status" data-i18n="deleted.col_forget">Olvidar</th>
            <th class="col-priority" data-i18n="modlist.col_order">#</th>
            <th class="col-name" data-i18n="modlist.col_name">Mod</th>
            <th class="col-category" data-i18n="modlist.col_category">Categoria</th>
            <th class="col-version" data-i18n="modlist.col_version">Version</th>
            <th class="col-comment" data-i18n="modlist.col_comment">Comentario</th>
            <th class="col-comment2" data-i18n="modlist.col_comment2">Comentario 2</th>
            <th data-i18n="deleted.col_separator" style="min-width:140px;">Separador</th>
            <th data-i18n="deleted.col_reason">Motivo</th>
          </tr></thead>
          <tbody id="deleted-tbody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- Tab: Importar / Exportar -->
  <section id="tab-import_export" class="tab-panel">
    <div class="panel">
      <h2 data-i18n="io.title">Importar / Exportar respaldos</h2>
      <p data-i18n="io.desc">Importa o exporta respaldos en formato JSON para compartir o cargar listas desde otras carpetas o perfiles. Puedes exportar tu lista de mods o el estado de Nemesis/Pandora/Custom, e importar respaldos externos.</p>
      <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px;margin-top:10px;font-size:12px;color:var(--text-dim);">
        <strong data-i18n="io.what_export">Que se exporta/importa:</strong>
        <ul style="margin-left:16px;margin-top:4px;">
          <li data-i18n="io.what_modlist">Lista de mods: prioridad, nombre, categoria, version, comentario MO2, link</li>
          <li data-i18n="io.what_memory">Overrides: comentario 2, categoria editada, link editado, etiquetas</li>
          <li data-i18n="io.what_nemesis">Nemesis/Pandora/Custom: mods activados, desactivados, manuales (solo lista, no imagenes)</li>
        </ul>
      </div>
    </div>
    <div class="panel-grid">
      <div class="panel">
        <h3 data-i18n="io.export_title">Exportar respaldo</h3>
        <div class="form-row">
          <label data-i18n="io.export_type">Tipo de respaldo</label>
          <select class="select" id="io-export-type">
            <option value="modlist" data-i18n="io.type_modlist">Lista de mods</option>
            <option value="nemesis" data-i18n="io.type_nemesis">Nemesis / Pandora / Custom (solo lista)</option>
          </select>
        </div>
        <div class="form-row">
          <label data-i18n="io.export_name">Nombre del archivo (sin extension)</label>
          <input type="text" id="io-export-name" data-i18n-placeholder="io.export_name_placeholder" placeholder="mi_respaldo">
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" id="btn-io-export" data-i18n="io.export_btn">Exportar JSON</button>
        </div>
      </div>
      <div class="panel">
        <h3 data-i18n="io.import_title">Importar respaldo</h3>
        <p data-i18n="io.import_desc">Selecciona un archivo JSON de respaldo para cargarlo. Esto reemplazara la lista actual o el estado de Nemesis segun el tipo del archivo.</p>
        <div class="form-row">
          <label data-i18n="io.import_file">Seleccionar archivo JSON</label>
          <input type="file" id="io-import-file" accept=".json">
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" id="btn-io-import" data-i18n="io.import_btn" style="display:none;">Importar JSON</button>
          <button class="btn" id="btn-io-view" data-i18n="io.view_btn" style="display:none;">Ver lista</button>
          <button class="btn" id="btn-io-compare" data-i18n="io.compare_btn" style="display:none;">Comparar con actual</button>
        </div>
        <div id="io-import-result" style="margin-top:10px;font-size:13px;color:var(--text-dim);"></div>
      </div>
    </div>
    <div id="io-view-detail" class="editor-diff" style="margin-top:14px;"></div>
  </section>

  <!--EXTENSION_PANEL-->
</div>

<!-- Modal de color para separadores -->
<div class="modal hidden" id="sep-color-modal">
  <div class="modal-backdrop"></div>
  <div class="modal-content" style="width:380px;">
    <div class="modal-header">
      <h3 data-i18n="modlist.sep_color_title">Color del separador</h3>
      <button class="modal-close" id="sep-color-modal-close">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-row">
        <label data-i18n="modlist.sep_color_label">Selecciona un color</label>
        <div style="display:flex;gap:10px;align-items:center;">
          <input type="color" id="sep-color-picker" value="#3b82f6" style="width:60px;height:40px;border:none;background:none;cursor:pointer;">
          <input type="text" id="sep-color-hex" value="#3b82f6" style="width:100px;font-family:var(--mono);font-size:13px;text-align:center;">
        </div>
      </div>
      <div class="form-row">
        <label data-i18n="modlist.sep_color_presets">Colores predefinidos</label>
        <div id="sep-color-presets" style="display:grid;grid-template-columns:repeat(8,1fr);gap:6px;"></div>
      </div>
      <div class="form-row">
        <button class="btn btn-sm" id="sep-color-clear" data-i18n="modlist.sep_color_clear">Quitar color</button>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-primary" id="sep-color-save" data-i18n="modal.save">Guardar</button>
      <button class="btn" id="sep-color-cancel" data-i18n="modal.cancel">Cancelar</button>
    </div>
  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<!-- Modal -->
<div class="modal hidden" id="mod-modal">
  <div class="modal-backdrop"></div>
  <div class="modal-content">
    <div class="modal-header">
      <h3 id="mod-modal-title">Editar mod</h3>
      <button class="modal-close" id="mod-modal-close">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-row"><label data-i18n="modal.name">Nombre</label><input type="text" id="mod-modal-name" disabled></div>
      <div class="form-row"><label data-i18n="modal.category">Categoria (editable)</label><input type="text" id="mod-modal-category"></div>
      <div class="form-row"><label data-i18n="modal.version">Version</label><input type="text" id="mod-modal-version" disabled></div>
      <div class="form-row"><label data-i18n="modal.link">Link</label><input type="text" id="mod-modal-link" placeholder="https://..."></div>
      <div class="form-row"><label data-i18n="modal.comment">Comentario MO2</label><textarea id="mod-modal-comment" rows="2"></textarea></div>
      <div class="form-row"><label data-i18n="modal.comment2">Comentario 2</label><textarea id="mod-modal-comment2" rows="3"></textarea></div>
      <div class="form-row"><label data-i18n="modal.tags">Etiquetas (separadas por coma)</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input type="text" id="mod-modal-tags" style="flex:1;">
          <select class="select" id="mod-modal-tags-selector" style="width:180px;"><option value="" data-i18n="modal.add_tag">+ Anadir etiqueta</option></select>
        </div>
        <div id="mod-modal-tags-chips" style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;"></div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-primary" id="mod-modal-save" data-i18n="modal.save">Guardar</button>
      <button class="btn" id="mod-modal-cancel" data-i18n="modal.cancel">Cancelar</button>
    </div>
  </div>
</div>

<script>
// ==================== utils.js ====================
function escapeHtml(s){if(s===null||s===undefined)return"";return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");}
function showToast(m,t="info",d=3000){const e=document.getElementById("toast");e.textContent=m;e.className="toast show "+t;clearTimeout(e._t);e._t=setTimeout(()=>{e.className="toast "+t;},d);}
function debounce(fn,ms){let t=null;return function(...a){clearTimeout(t);t=setTimeout(()=>fn.apply(this,a),ms);};}
function formatBytes(b){if(b<1024)return b+" B";if(b<1048576)return(b/1024).toFixed(1)+" KB";return(b/1048576).toFixed(1)+" MB";}
function fileToBase64(f){return new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>{const i=r.result.indexOf(",");res(i>=0?r.result.slice(i+1):r.result);};r.onerror=rej;r.readAsDataURL(f);});}
function downloadTextFile(f,t,m="text/plain"){const b=new Blob([t],{type:m+";charset=utf-8"});const u=URL.createObjectURL(b);const a=document.createElement("a");a.href=u;a.download=f;document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(u);}
window.AppState={state:null,lastImported:null,settings:{},paused:false,currentNemesisEngine:"nemesis"};

// ==================== i18n.js ====================
const I18n={current:"es",translations:{},
  async init(){await this.load();},
  async load(){try{const r=await fetch("/i18n.json");if(!r.ok)throw 0;const d=await r.json();this.translations=d.strings||{};this.current=d.language||"es";this.apply();document.dispatchEvent(new CustomEvent("i18n:changed",{detail:{lang:this.current}}));}catch(e){console.error("i18n load error",e);}},
  t(k){return this.translations[k]||k;},
  apply(){document.querySelectorAll("[data-i18n]").forEach(e=>{e.textContent=this.t(e.getAttribute("data-i18n"));});document.querySelectorAll("[data-i18n-placeholder]").forEach(e=>{e.placeholder=this.t(e.getAttribute("data-i18n-placeholder"));});document.querySelectorAll("[data-i18n-title]").forEach(e=>{e.title=this.t(e.getAttribute("data-i18n-title"));});document.title=this.t("app.title");}
};
window.I18n=I18n;

// ==================== api.js ====================
const Api={
  async getState(){const r=await fetch("/api/state");const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async refreshFromCsv(){const r=await fetch("/api/refresh_from_csv",{method:"POST"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async refreshFromMo2(){const r=await fetch("/api/refresh_from_mo2",{method:"POST"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async generateCsv(){const r=await fetch("/api/generate_csv",{method:"POST"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async reorderMods(names){const r=await fetch("/api/reorder",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({names})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async updatePriority(name,priority){const r=await fetch(`/api/mods/${encodeURIComponent(name)}/priority`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({priority})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async updateMod(n,o){const r=await fetch("/api/mods/"+encodeURIComponent(n),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(o)});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async forgetMod(n){const r=await fetch("/api/mods/"+encodeURIComponent(n)+"/forget",{method:"POST"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d;},
  async forgetAllMods(names){const r=await fetch("/api/mods/forget_all",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({names})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async setCollapse(s,c){const r=await fetch("/api/collapse/"+encodeURIComponent(s),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({collapsed:c})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d;},
  async listSnapshots(type="modlist"){const r=await fetch(`/api/backups?type=${type}`);const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async createSnapshot(type="modlist"){const r=await fetch(`/api/backups?type=${type}`,{method:"POST"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async deleteSnapshot(f){const r=await fetch("/api/backups/"+encodeURIComponent(f),{method:"DELETE"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d;},
  async getBackup(f){const r=await fetch("/api/backups/"+encodeURIComponent(f));const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async restoreBackup(f,opts={}){const r=await fetch("/api/backups/"+encodeURIComponent(f),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(opts)});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async restoreFromJson(db,opts={}){const r=await fetch("/api/restore_json",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({database:db,...opts})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async exportList(f){const r=await fetch("/api/export?format="+f);const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async importText(t){const r=await fetch("/api/import",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:t})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async importUrl(u){const r=await fetch("/api/import/url",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:u})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async getNemesis(){const r=await fetch("/api/nemesis");const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async saveNemesis(d){const r=await fetch("/api/nemesis",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(d)});const j=await r.json();if(!j.ok)throw new Error(j.error);return j;},
  async uploadNemesisImage(f,b){const r=await fetch("/api/nemesis/image",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename:f,data_base64:b})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async deleteNemesisImage(f){const r=await fetch("/api/nemesis/image/"+encodeURIComponent(f),{method:"DELETE"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d;},
  async getSettings(){const r=await fetch("/api/settings");const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async getMemory(){const r=await fetch("/api/memory");const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async saveSettings(s){const r=await fetch("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(s)});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async getCustomVersions(){const r=await fetch("/api/custom_versions");const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async addCustomVersion(e){const r=await fetch("/api/custom_versions",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async updateCustomVersion(i,e){const r=await fetch("/api/custom_versions/"+i,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async deleteCustomVersion(i){const r=await fetch("/api/custom_versions/"+i,{method:"DELETE"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d;},
  async getVersionComments(){const r=await fetch("/api/version_comments");const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async saveVersionComment(modName,comment){const r=await fetch("/api/version_comments",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mod_name:modName,comment:comment})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async listVersionBackups(){const r=await fetch("/api/version_backups");const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async createVersionBackup(t,l){const r=await fetch("/api/version_backups",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({type:t,label:l||""})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async getVersionBackup(f){const r=await fetch("/api/version_backups/"+encodeURIComponent(f));const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async restoreVersionBackup(f){const r=await fetch("/api/version_backups/"+encodeURIComponent(f),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({restore:true})});const d=await r.json();if(!d.ok)throw new Error(d.error);return d.data;},
  async deleteVersionBackup(f){const r=await fetch("/api/version_backups/"+encodeURIComponent(f),{method:"DELETE"});const d=await r.json();if(!d.ok)throw new Error(d.error);return d;},
};
window.Api=Api;

// ==================== modlist.js ====================
const ModlistTab={filters:{search:"",separator:"",status:"",category:"",tags:""},lastState:null,editingMod:null,hideDeleted:false,_delegationInit:false,_lastStateHash:"",
  init(){
    // Configurar event delegation en el tbody (una sola vez)
    this.initDelegation();
    // Cargar preferencia "ocultar eliminados" desde localStorage
    this.hideDeleted=localStorage.getItem("mlm_hide_deleted")==="1";
    const hbtn=document.getElementById("btn-hide-deleted");
    if(this.hideDeleted)hbtn.classList.add("active");
    hbtn.addEventListener("click",()=>{
      this.hideDeleted=!this.hideDeleted;
      localStorage.setItem("mlm_hide_deleted",this.hideDeleted?"1":"0");
      hbtn.classList.toggle("active",this.hideDeleted);
      this.render();
    });
    document.getElementById("search-input").addEventListener("input",debounce(e=>{this.filters.search=e.target.value.toLowerCase();this.render();},200));
    document.getElementById("filter-separator").addEventListener("change",e=>{
      this.filters.separator=e.target.value;
      const sepName=e.target.value;
      if(sepName&&this.lastState){
        // Optimizacion: actualizar estado local inmediatamente
        for(const s of this.lastState.sections){
          if(s.separator){
            const shouldCollapse=s.separator.name!==sepName;
            if(s.collapsed!==shouldCollapse){
              s.collapsed=shouldCollapse;
              Api.setCollapse(s.separator.name,shouldCollapse).catch(()=>{});
            }
          }
        }
        this.render();
        // Hacer scroll hasta el separador
        setTimeout(()=>{
          const row=document.querySelector(`tr.sep-row[data-modname="${CSS.escape(sepName)}"]`);
          if(row)row.scrollIntoView({behavior:"smooth",block:"start"});
        },100);
      }else if(this.lastState){
        // "Todos los separadores": expandir todo
        for(const s of this.lastState.sections){
          if(s.separator&&s.collapsed){
            s.collapsed=false;
            Api.setCollapse(s.separator.name,false).catch(()=>{});
          }
        }
        this.render();
      }else{
        this.render();
      }
    });
    document.getElementById("filter-status").addEventListener("change",e=>{this.filters.status=e.target.value;this.render();});
    document.getElementById("filter-category").addEventListener("change",e=>{this.filters.category=e.target.value;this.render();});
    document.getElementById("filter-tags").addEventListener("change",e=>{this.filters.tags=e.target.value;this.render();});
    document.getElementById("btn-expand-all").addEventListener("click",()=>{
      if(!this.lastState)return;
      for(const s of this.lastState.sections){if(s.separator){s.collapsed=false;Api.setCollapse(s.separator.name,false).catch(()=>{});}}
      this.render();
    });
    document.getElementById("btn-collapse-all").addEventListener("click",()=>{
      if(!this.lastState)return;
      for(const s of this.lastState.sections){if(s.separator){s.collapsed=true;Api.setCollapse(s.separator.name,true).catch(()=>{});}}
      this.render();
    });
    document.getElementById("btn-sync-mo2").addEventListener("click",async()=>{
      try{
        showToast(I18n.t("modlist.syncing_mo2"),"info");
        const r=await Api.refreshFromMo2();
        showToast(I18n.t("modlist.synced_mo2")+": "+r.updated+" mods","success");
        await this.refresh();
      }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    });
    document.getElementById("btn-refresh-csv").addEventListener("click",async()=>{
      if(!confirm(I18n.t("modlist.confirm_refresh_csv")))return;
      try{
        showToast(I18n.t("modlist.refreshing_csv"),"info");
        const r=await Api.refreshFromCsv();
        showToast(I18n.t("modlist.refreshed_csv")+": "+r.updated+" mods","success");
        await this.refresh();
      }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    });
    document.getElementById("mod-modal-close").addEventListener("click",()=>this.closeModal());
    const btnCopyCsv=document.getElementById("btn-copy-csvname");
    if(btnCopyCsv)btnCopyCsv.addEventListener("click",()=>{navigator.clipboard.writeText("modlist.csv").then(()=>showToast(I18n.t("csv.copied")+": modlist.csv","success")).catch(()=>{});});
    document.getElementById("mod-modal-cancel").addEventListener("click",()=>this.closeModal());
    document.getElementById("mod-modal-save").addEventListener("click",()=>this.saveMod());
    document.querySelector("#mod-modal .modal-backdrop").addEventListener("click",()=>this.closeModal());
    document.getElementById("mod-modal-tags-selector").addEventListener("change",(e)=>{
      if(!e.target.value)return;
      const input=document.getElementById("mod-modal-tags");
      const tags=input.value.split(",").map(s=>s.trim()).filter(Boolean);
      if(!tags.includes(e.target.value)){tags.push(e.target.value);}
      input.value=tags.join(", ");
      this.renderTagChips(tags);
      this.populateTagSelector(tags);
      e.target.value="";
    });
    document.getElementById("mod-modal-tags").addEventListener("input",()=>{
      const tags=document.getElementById("mod-modal-tags").value.split(",").map(s=>s.trim()).filter(Boolean);
      this.renderTagChips(tags);
      this.populateTagSelector(tags);
    });
    document.addEventListener("i18n:changed",()=>{if(this.lastState)this.render();});
    this.initResizableColumns();
  },
  initDelegation(){
    // Event delegation: un solo set de listeners en el tbody en lugar de uno por fila
    // Esto reduce drasticamente el uso de memoria para listas grandes (4000+ mods)
    if(this._delegationInit)return;
    this._delegationInit=true;
    const tb=document.getElementById("modlist-tbody");
    if(!tb)return;
    // Helper: encontrar el <tr> mas cercano a un elemento
    const findTr=(el)=>{
      while(el&&el.tagName!=="TR"){el=el.parentElement;}
      return el;
    };
    // Helper: encontrar un mod por nombre en lastState
    const findMod=(name)=>{
      if(!this.lastState)return null;
      for(const m of this.lastState.mods){if(m.name===name)return m;}
      return null;
    };
    // Click: manejar boton eliminar, boton color de separador, toggle de separador
    tb.addEventListener("click",async(e)=>{
      // Boton eliminar mod (solo mods eliminados)
      if(e.target.classList.contains("btn-delete-mod")){
        e.stopPropagation();
        const modname=e.target.dataset.modname;
        if(!confirm(I18n.t("modlist.confirm_delete")))return;
        try{
          await Api.forgetMod(modname);
          showToast(I18n.t("modlist.deleted_ok"),"success");
          await this.refresh();
        }catch(err){showToast(I18n.t("topbar.error")+": "+err.message,"error");}
        return;
      }
      // Boton de color de separador
      if(e.target.classList.contains("sep-color-btn")){
        e.stopPropagation();
        this.openSepColorModal(e.target.dataset.sepName);
        return;
      }
      // Click en fila de separador: toggle expandir/contraer
      const tr=findTr(e.target);
      if(tr&&tr.classList.contains("sep-row")){
        const sepName=tr.dataset.modname;
        const sec=this.lastState.sections.find(s=>s.separator&&s.separator.name===sepName);
        if(sec){
          // Optimizacion: actualizar estado local y re-renderizar inmediatamente
          // sin esperar a la llamada API. Guardar en backend en segundo plano.
          sec.collapsed=!sec.collapsed;
          this.render();
          // Guardar en backend sin esperar (fire and forget)
          Api.setCollapse(sepName,sec.collapsed).catch(()=>{});
        }
      }
    });
    // Doble click: abrir modal para editar
    tb.addEventListener("dblclick",(e)=>{
      const tr=findTr(e.target);
      if(!tr)return;
      const modname=tr.dataset.modname;
      if(!modname)return;
      const mod=findMod(modname);
      if(mod)this.openModal(mod);
    });
    // Change: input de prioridad
    tb.addEventListener("change",async(e)=>{
      if(e.target.classList.contains("priority-input")){
        const modname=e.target.dataset.modname;
        const newPrio=parseInt(e.target.value);
        if(isNaN(newPrio))return;
        try{
          await Api.updatePriority(modname,newPrio);
          showToast(I18n.t("modlist.priority_updated"),"success");
          await this.refresh();
        }catch(err){showToast(I18n.t("topbar.error")+": "+err.message,"error");}
      }
    });
    // Click en input de prioridad: parar propagacion (no toggle separador)
    tb.addEventListener("click",(e)=>{
      if(e.target.classList.contains("priority-input"))e.stopPropagation();
    });
    // Drag-and-drop: delegado en el tbody
    tb.addEventListener("dragstart",(e)=>{
      const tr=findTr(e.target);
      if(!tr)return;
      const modname=tr.dataset.modname;
      this._draggedMod=modname;
      tr.classList.add("dragging");
      e.dataTransfer.effectAllowed="move";
      e.dataTransfer.setData("text/plain",modname);
    });
    tb.addEventListener("dragend",(e)=>{
      const tr=findTr(e.target);
      if(tr)tr.classList.remove("dragging");
      this._draggedMod=null;
      document.querySelectorAll(".drag-over").forEach(el=>el.classList.remove("drag-over"));
    });
    tb.addEventListener("dragover",(e)=>{
      e.preventDefault();
      e.dataTransfer.dropEffect="move";
    });
    tb.addEventListener("dragenter",(e)=>{
      const tr=findTr(e.target);
      if(!tr)return;
      if(this._draggedMod&&tr.dataset.modname!==this._draggedMod){
        e.preventDefault();
        document.querySelectorAll(".drag-over").forEach(el=>el.classList.remove("drag-over"));
        tr.classList.add("drag-over");
      }
    });
    tb.addEventListener("dragleave",(e)=>{
      const tr=findTr(e.target);
      if(tr&&!tr.contains(e.relatedTarget)){
        tr.classList.remove("drag-over");
      }
    });
    tb.addEventListener("drop",async(e)=>{
      e.preventDefault();
      const tr=findTr(e.target);
      if(!tr)return;
      tr.classList.remove("drag-over");
      const targetName=tr.dataset.modname;
      if(!this._draggedMod||this._draggedMod===targetName)return;
      await this.reorderMods(this._draggedMod,targetName);
    });
    // Click en boton de carpeta
    tb.addEventListener("click",async(e)=>{
      if(e.target.classList.contains("modlist-folder-btn")){
        e.stopPropagation();
        const modname=e.target.dataset.modname;
        try{
          const r=await fetch("/api/open_mod_folder/"+encodeURIComponent(modname),{method:"POST"});
          const d=await r.json();
          if(!d.ok)throw new Error(d.error);
        }catch(err){showToast(I18n.t("topbar.error")+": "+err.message,"error");}
      }
    });
  },
  initResizableColumns(){
    const t=document.getElementById("modlist-table");if(!t)return;
    const ths=t.querySelectorAll("thead th[data-col]");
    const saved=this.loadColumnWidths();
    ths.forEach(th=>{const c=th.dataset.col;if(saved[c])th.style.width=saved[c]+"px";new MutationObserver(()=>this.saveColumnWidths()).observe(th,{attributes:true,attributeFilter:["style"]});});
  },
  loadColumnWidths(){try{const r=localStorage.getItem("mlm_col_widths");return r?JSON.parse(r):{};}catch(e){return{};}},
  saveColumnWidths(){const t=document.getElementById("modlist-table");if(!t)return;const w={};t.querySelectorAll("thead th[data-col]").forEach(th=>{const x=th.getBoundingClientRect().width;if(x>0)w[th.dataset.col]=Math.round(x);});try{localStorage.setItem("mlm_col_widths",JSON.stringify(w));}catch(e){}},
  async refresh(){
    try{
      const s=await Api.getState();
      // Optimizacion: si los datos no cambiaron, no re-renderizar
      // (evita re-render innecesario durante el polling cada 5s)
      const hash=this._computeStateHash(s);
      const filtersChanged=hash!==this._lastStateHash;
      this.lastState=s;AppState.state=s;
      this._lastStateHash=hash;
      this.populateFilters(s);
      if(filtersChanged||!this._renderedOnce){
        this._renderedOnce=true;
        this.render();
      }
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  _computeStateHash(s){
    // Hash simple: combina stats + numero de mods + updated_at + filtros activos
    // + estado de colapso de separadores
    const st=s.stats||{};
    const f=this.filters;
    // Incluir estado de colapso de separadores en el hash
    const collapseState=(s.sections||[]).map(sec=>sec.collapsed?"1":"0").join("");
    return JSON.stringify({
      t:st.total,a:st.active,i:st.inactive,m:st.missing,s:st.separators,
      ua:s.updated_at||"",
      fs:f.search+f.status+f.category+f.tags,
      hd:this.hideDeleted?"1":"0",
      cs:collapseState
    });
  },
  render(){
    if(!this.lastState)return;
    const st=this.lastState;
    // CSV missing
    const notice=document.getElementById("csv-notice");
    const tw=document.getElementById("table-wrap");
    const sg=document.getElementById("stats-grid");
    if(st.csv_missing){
      notice.style.display="block";tw.style.display="none";sg.style.display="none";
      document.getElementById("csv-expected-path").textContent=st.csv_expected_path||"";
      document.getElementById("csv-mo2-path").textContent=st.csv_mo2_path||"";
      return;
    }
    notice.style.display="none";tw.style.display="";sg.style.display="";
    document.getElementById("stat-total").textContent=st.stats.total;
    document.getElementById("stat-active").textContent=st.stats.active;
    document.getElementById("stat-inactive").textContent=st.stats.inactive;
    document.getElementById("stat-missing").textContent=st.stats.missing;
    document.getElementById("stat-separators").textContent=st.stats.separators;
    const tb=document.getElementById("modlist-tbody");
    // Cargar configuracion de colores de separadores
    const sepColors=this.loadSepColors();
    // Construir todas las filas como strings HTML para insercion batch
    const htmlParts=[];
    const hasActiveFilters=this.filters.search||this.filters.status||this.filters.category||this.filters.tags;
    for(const sec of st.sections){
      if(sec.separator){
        htmlParts.push(this.renderSeparatorHtml(sec,sepColors));
      }
      if(sec.collapsed&&!hasActiveFilters)continue;
      const mods=sec.mods.filter(m=>this.matchFilters(m));
      if(hasActiveFilters&&mods.length===0)continue;
      const sepColor=sec.separator?sepColors[sec.separator.name]:null;
      for(let i=0;i<mods.length;i++){
        const m=mods[i];
        m._rowColor=null;
        m._rowTextColor=null;
        if(sepColor&&sepColor.color){
          m._rowColor=this.alternateColor(sepColor.color,i%2===0);
        }
        htmlParts.push(this.renderModRowHtml(m));
      }
    }
    // Insercion batch: una sola operacion innerHTML en lugar de miles de appendChild
    // Si la lista es muy grande, renderizar en chunks para no congelar el UI
    const CHUNK_THRESHOLD=800;  // arriba de esto, renderizar en chunks
    if(htmlParts.length<=CHUNK_THRESHOLD){
      tb.innerHTML=htmlParts.join("");
    }else{
      // Renderizado por chunks: primeros N, luego el resto via requestAnimationFrame
      const CHUNK_SIZE=600;
      tb.innerHTML=htmlParts.slice(0,CHUNK_SIZE).join("");
      // Anadir indicador de carga
      const loadRow=document.createElement("tr");
      loadRow.id="modlist-load-more";
      loadRow.innerHTML=`<td colspan="${window.Extensions?10:9}" style="text-align:center;color:var(--accent);padding:12px;font-size:13px;">${I18n.t("modlist.loading_more").replace("{count}",htmlParts.length-CHUNK_SIZE)}</td>`;
      tb.appendChild(loadRow);
      let offset=CHUNK_SIZE;
      const renderChunk=()=>{
        const end=Math.min(offset+CHUNK_SIZE,htmlParts.length);
        // Quitar indicador de carga anterior
        const lr=document.getElementById("modlist-load-more");
        if(lr)lr.remove();
        // Insertar siguiente chunk
        const chunkHtml=htmlParts.slice(offset,end).join("");
        tb.insertAdjacentHTML("beforeend",chunkHtml);
        offset=end;
        if(offset<htmlParts.length){
          // Anadir indicador de carga para el siguiente chunk
          const lr2=document.createElement("tr");
          lr2.id="modlist-load-more";
          lr2.innerHTML=`<td colspan="${window.Extensions?10:9}" style="text-align:center;color:var(--accent);padding:12px;font-size:13px;">${I18n.t("modlist.loading_more").replace("{count}",htmlParts.length-offset)}</td>`;
          tb.appendChild(lr2);
          requestAnimationFrame(renderChunk);
        }
      };
      requestAnimationFrame(renderChunk);
    }
  },
  loadSepColors(){
    try{
      const raw=localStorage.getItem("mlm_sep_colors");
      return raw?JSON.parse(raw):{};
    }catch(e){return {};}
  },
  saveSepColors(colors){
    try{localStorage.setItem("mlm_sep_colors",JSON.stringify(colors));}catch(e){}
  },
  autoTextColor(hex){
    // Calcula la luminancia del color de fondo:
    // si es claro (lum > 0.6), el texto debe ser negro para que se lea
    try{
      const h=hex.replace("#","");
      const r=parseInt(h.substr(0,2),16);
      const g=parseInt(h.substr(2,2),16);
      const b=parseInt(h.substr(4,2),16);
      const lum=(0.299*r+0.587*g+0.114*b)/255;
      return lum>0.6?"#000000":"#ffffff";
    }catch(e){return "#ffffff";}
  },
  alternateColor(hex,alt){
    // Genera un tono mas claro o mas oscuro del color base
    try{
      const h=hex.replace("#","");
      const r=parseInt(h.substr(0,2),16);
      const g=parseInt(h.substr(2,2),16);
      const b=parseInt(h.substr(4,2),16);
      if(alt){
        // Mas claro
        const nr=Math.min(255,r+40);
        const ng=Math.min(255,g+40);
        const nb=Math.min(255,b+40);
        return`rgb(${nr},${ng},${nb},0.15)`;
      }else{
        // Mas oscuro
        const nr=Math.max(0,r-20);
        const ng=Math.max(0,g-20);
        const nb=Math.max(0,b-20);
        return`rgb(${nr},${ng},${nb},0.15)`;
      }
    }catch(e){return null;}
  },
  openSepColorModal(sepName){
    const colors=this.loadSepColors();
    const current=colors[sepName]||{color:"#3b82f6",text:"#ffffff"};
    this._editingSepName=sepName;
    const modal=document.getElementById("sep-color-modal");
    const picker=document.getElementById("sep-color-picker");
    const hexInput=document.getElementById("sep-color-hex");
    picker.value=current.color;
    hexInput.value=current.color;
    // Sincronizar picker <-> hex input
    picker.oninput=()=>{hexInput.value=picker.value;};
    hexInput.oninput=()=>{
      if(/^#[0-9a-fA-F]{6}$/.test(hexInput.value)){picker.value=hexInput.value;}
    };
    // Generar colores predefinidos
    const presets=document.getElementById("sep-color-presets");
    presets.innerHTML="";
    const presetColors=["#ef4444","#f59e0b","#10b981","#3b82f6","#8b5cf6","#ec4899","#06b6d4","#84cc16","#f97316","#6366f1","#14b8a6","#a855f7","#eab308","#22c55e","#64748b","#dc2626"];
    for(const c of presetColors){
      const sw=document.createElement("div");
      sw.style.background=c;
      sw.style.width="100%";sw.style.height="28px";
      sw.style.borderRadius="4px";sw.style.cursor="pointer";
      sw.style.border="2px solid transparent";
      sw.title=c;
      sw.addEventListener("click",()=>{
        picker.value=c;hexInput.value=c;
        presets.querySelectorAll("div").forEach(d=>d.style.border="2px solid transparent");
        sw.style.border="2px solid white";
      });
      if(c.toLowerCase()===current.color.toLowerCase())sw.style.border="2px solid white";
      presets.appendChild(sw);
    }
    modal.classList.remove("hidden");
    // Configurar botones (solo una vez)
    if(!this._sepColorModalInit){
      this._sepColorModalInit=true;
      document.getElementById("sep-color-modal-close").addEventListener("click",()=>modal.classList.add("hidden"));
      document.getElementById("sep-color-cancel").addEventListener("click",()=>modal.classList.add("hidden"));
      document.querySelector("#sep-color-modal .modal-backdrop").addEventListener("click",()=>modal.classList.add("hidden"));
      document.getElementById("sep-color-save").addEventListener("click",()=>{
        const color=document.getElementById("sep-color-picker").value;
        const colors=this.loadSepColors();
        if(!this._editingSepName)return;
        colors[this._editingSepName]={color:color,text:this.autoTextColor(color)};
        this.saveSepColors(colors);
        modal.classList.add("hidden");
        this.render();
      });
      document.getElementById("sep-color-clear").addEventListener("click",()=>{
        const colors=this.loadSepColors();
        if(!this._editingSepName)return;
        delete colors[this._editingSepName];
        this.saveSepColors(colors);
        modal.classList.add("hidden");
        this.render();
      });
    }
  },
  renderModRowHtml(m){
    // Devuelve el HTML de una fila de mod (sin event listeners - usa event delegation)
    const cls=m.missing||m.deleted_from_disk?"mod-row missing":"mod-row";
    const rowStyle=m._rowColor?` style="background:${m._rowColor};"`:"";
    const draggable=m.deleted_from_disk?"":" draggable=\"true\"";
    const statusChar=m.active?"X":"O";
    const statusClass=m.active?"status-on":"status-off";
    const orderText=m.order_number!=null?m.order_number:"—";
    const cat=m.category_override||m.category||"";
    // Link: usar link_override si existe, sino m.link (que ya incluye url del meta.ini)
    const link=m.link_override||m.link||"";
    let linkHtml="";
    if(link)linkHtml=`<a href="${escapeHtml(link)}" target="_blank" rel="noopener" class="mod-link">${I18n.t("modlist.open_link")}</a>`;
    const badge=(m.deleted_from_disk)?`<span class="badge badge-deleted">${I18n.t("modlist.badge_deleted")}</span>`:"";
    const statusContent=m.deleted_from_disk
      ?`<button type="button" class="btn-delete-mod" data-modname="${escapeHtml(m.name)}" title="${I18n.t("modlist.delete_row")}">&times;</button>`
      :`<span class="${statusClass}">${statusChar}</span>`;
    const priorityHtml=m.deleted_from_disk
      ?`<span>${orderText}</span>`
      :`<input type="number" class="priority-input" value="${m.order_number!=null?m.order_number:''}" data-modname="${escapeHtml(m.name)}" min="0" style="width:70px;background:var(--bg);border:1px solid var(--border);color:var(--text);text-align:right;border-radius:3px;padding:2px 6px;font-size:12px;">`;
    // Columna Trad (solo si la extension esta instalada)
    let tradCellHtml="";
    if(window.Extensions){
      const td=(window._tradData||{})[m.name]||{};
      const tType=td.translation_type||"";
      const BADGE_LABELS={T:"TR",D:"DSD",M:"MCM",S:"SC",O:"SK",OT:"OT",NO:"NO"};
      const BADGE_COLORS={T:"#2196F3",D:"#4CAF50",M:"#FF9800",S:"#9C27B0",O:"#E91E63",OT:"#00BCD4",NO:"#607D8B"};
      const badge=tType?`<span class="trad-badge" style="background:${BADGE_COLORS[tType]||"#999"};color:white;">${BADGE_LABELS[tType]||tType}</span>`:`<span class="trad-badge trad-badge-none">—</span>`;
      tradCellHtml=`<td style="text-align:center;width:60px;">${badge}</td>`;
    }
    // Boton de carpeta
    const folderBtn=`<td style="text-align:center;width:40px;"><button type="button" class="btn btn-sm modlist-folder-btn" data-modname="${escapeHtml(m.name)}" title="Abrir carpeta" style="padding:2px 4px;font-size:11px;">📂</button></td>`;
    return `<tr class="${cls}" data-modname="${escapeHtml(m.name)}"${draggable}${rowStyle}><td class="col-status">${statusContent}</td><td class="col-priority">${priorityHtml}</td>${tradCellHtml}<td class="col-name editable">${escapeHtml(m.display_name||m.name)}${badge}</td><td class="col-category editable">${escapeHtml(cat)}</td><td class="col-version">${escapeHtml(m.version||"")}</td><td class="col-comment">${escapeHtml(m.comment||"")}</td><td class="col-comment2 editable">${escapeHtml(m.comment2||"")}</td><td class="col-link">${linkHtml}</td>${folderBtn}</tr>`;
  },
  renderSeparatorHtml(sec,sepColors){
    // Devuelve el HTML de una fila de separador (sin event listeners - usa event delegation)
    const sep=sec.separator;
    const cls="sep-row"+(sec.collapsed?" collapsed":"");
    const sepColor=sepColors[sep.name];
    let styleAttr="";
    if(sepColor&&sepColor.color){
      const textColor=this.autoTextColor(sepColor.color);
      styleAttr=` style="--sep-bg:${sepColor.color};--sep-text:${textColor};"`;
    }
    const sepComment=sep.comment?` <span style="opacity:0.7;font-weight:400;font-size:12px;">— ${escapeHtml(sep.comment)}</span>`:"";
    const colorBtn=`<button type="button" class="sep-color-btn" data-sep-name="${escapeHtml(sep.name)}" title="${I18n.t("modlist.sep_color")}">🎨</button>`;
    // Colspan: 8 columnas base + 1 (Trad si extension) + 1 (carpeta) = 9 o 10
    const colspan=window.Extensions?10:9;
    return `<tr class="${cls}" data-modname="${escapeHtml(sep.name)}" draggable="true"${styleAttr}><td colspan="${colspan}">${colorBtn}<span class="sep-toggle">${sec.collapsed?"▶":"▼"}</span> ${escapeHtml(sep.display_name||sep.name)}${sepComment}</td></tr>`;
  },
  matchFilters(m){
    if(m.is_separator)return true;
    // "Ocultar eliminados": si esta activado, filtrar mods missing o deleted_from_disk
    // (excepto cuando el filtro de status es "missing", para poder verlos al buscar eliminados)
    if(this.hideDeleted&&this.filters.status!=="missing"&&(m.missing||m.deleted_from_disk))return false;
    if(this.filters.search){
      const hay=(m.name+" "+(m.display_name||"")+" "+(m.category||"")+" "+(m.comment||"")+" "+(m.comment2||"")).toLowerCase();
      if(!hay.includes(this.filters.search))return false;
    }
    if(this.filters.status==="active"&&!m.active)return false;
    if(this.filters.status==="inactive"&&m.active)return false;
    if(this.filters.status==="missing"&&!(m.missing||m.deleted_from_disk))return false;
    if(this.filters.category){const c=m.category_override||m.category||"";if(c!==this.filters.category)return false;}
    if(this.filters.tags){if(!(m.tags||[]).includes(this.filters.tags))return false;}
    return true;
  },
  populateFilters(s){
    const ss=document.getElementById("filter-separator");const cs=ss.value;
    ss.innerHTML=`<option value="">${I18n.t("modlist.filter_all_separators")}</option>`;
    for(const sec of s.sections){if(sec.separator){const o=document.createElement("option");o.value=sec.separator.name;o.textContent=sec.separator.display_name||sec.separator.name;ss.appendChild(o);}}
    ss.value=cs;
    const cts=document.getElementById("filter-category");const cc=cts.value;
    const set=new Set();
    for(const m of s.mods){const c=m.category_override||m.category;if(c)set.add(c);}
    cts.innerHTML=`<option value="">${I18n.t("modlist.filter_all_categories")}</option>`;
    for(const c of Array.from(set).sort()){const o=document.createElement("option");o.value=c;o.textContent=c;cts.appendChild(o);}
    cts.value=cc;
    // Poblar filtro de etiquetas
    const ts=document.getElementById("filter-tags");const tc=ts.value;
    const tagSet=new Set();
    for(const m of s.mods){if(m.tags){for(const t of m.tags){if(t)tagSet.add(t);}}}
    ts.innerHTML=`<option value="">${I18n.t("modlist.filter_all_tags")}</option>`;
    for(const t of Array.from(tagSet).sort()){const o=document.createElement("option");o.value=t;o.textContent=t;ts.appendChild(o);}
    ts.value=tc;
  },
  openModal(m){
    this.editingMod=m;
    document.getElementById("mod-modal-title").textContent=I18n.t("modal.title_edit")+": "+(m.display_name||m.name);
    document.getElementById("mod-modal-name").value=m.display_name||m.name;
    document.getElementById("mod-modal-category").value=m.category_override||m.category||"";
    document.getElementById("mod-modal-version").value=m.version||"";
    document.getElementById("mod-modal-link").value=m.link_override||m.link||"";
    document.getElementById("mod-modal-comment").value=m.comment||"";
    document.getElementById("mod-modal-comment2").value=m.comment2||"";
    const currentTags=(m.tags||[]).slice();
    document.getElementById("mod-modal-tags").value=currentTags.join(", ");
    // Llenar selector de etiquetas existentes
    this.populateTagSelector(currentTags);
    this.renderTagChips(currentTags);
    document.getElementById("mod-modal").classList.remove("hidden");
  },
  populateTagSelector(currentTags){
    const sel=document.getElementById("mod-modal-tags-selector");
    sel.innerHTML=`<option value="">${I18n.t("modal.add_tag")}</option>`;
    if(!this.lastState)return;
    const tagSet=new Set();
    for(const m of this.lastState.mods){if(m.tags){for(const t of m.tags){if(t)tagSet.add(t);}}}
    for(const t of Array.from(tagSet).sort()){
      if(!currentTags.includes(t)){
        const o=document.createElement("option");o.value=t;o.textContent=t;sel.appendChild(o);
      }
    }
  },
  renderTagChips(tags){
    const wrap=document.getElementById("mod-modal-tags-chips");
    wrap.innerHTML="";
    for(const t of tags){
      const chip=document.createElement("span");
      chip.style.cssText="background:var(--accent);color:white;padding:2px 8px;border-radius:10px;font-size:11px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;";
      chip.innerHTML=`${escapeHtml(t)} <span style="opacity:0.7;font-size:14px;">&times;</span>`;
      chip.title=I18n.t("modal.remove_tag");
      chip.addEventListener("click",()=>{
        const idx=tags.indexOf(t);
        if(idx>=0){tags.splice(idx,1);document.getElementById("mod-modal-tags").value=tags.join(", ");this.renderTagChips(tags);this.populateTagSelector(tags);}
      });
      wrap.appendChild(chip);
    }
  },
  closeModal(){document.getElementById("mod-modal").classList.add("hidden");this.editingMod=null;},
  async saveMod(){
    if(!this.editingMod)return;
    const o={
      category:document.getElementById("mod-modal-category").value,
      comment:document.getElementById("mod-modal-comment").value,
      comment2:document.getElementById("mod-modal-comment2").value,
      link_override:document.getElementById("mod-modal-link").value,
      tags:document.getElementById("mod-modal-tags").value.split(",").map(s=>s.trim()).filter(Boolean)
    };
    try{await Api.updateMod(this.editingMod.name,o);showToast(I18n.t("modal.saved_ok"),"success");this.closeModal();await this.refresh();}catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async reorderMods(draggedName,targetName){
    // Construir nueva lista de nombres en orden: mover dragged antes de target
    if(!this.lastState)return;
    const allMods=this.lastState.mods;
    const names=[];
    for(const m of allMods){
      if(m.name===draggedName)continue;
      if(m.name===targetName)names.push(draggedName);
      names.push(m.name);
    }
    try{
      await Api.reorderMods(names);
      showToast(I18n.t("modlist.reordered"),"success");
      await this.refresh();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
};
window.ModlistTab=ModlistTab;

// ==================== import_export.js ====================
const ImportExportTab={
  loadedData:null,
  init(){
    document.getElementById("btn-io-export").addEventListener("click",()=>this.exportBackup());
    document.getElementById("btn-io-import").addEventListener("click",()=>this.doImport());
    document.getElementById("btn-io-view").addEventListener("click",()=>this.viewLoaded());
    document.getElementById("btn-io-compare").addEventListener("click",()=>this.compareLoaded());
    document.getElementById("io-import-file").addEventListener("change",()=>this.loadFile());
  },
  async exportBackup(){
    const type=document.getElementById("io-export-type").value;
    let name=document.getElementById("io-export-name").value.trim();
    if(!name)name=`respaldo_${type}_${new Date().toISOString().slice(0,10)}`;
    try{
      let data;
      if(type==="nemesis"){
        const n=await Api.getNemesis();
        data={type:"nemesis",created_at:new Date().toISOString(),profile:AppState.state?AppState.state.profile:"",nemesis:n.stored};
      }else{
        const s=await Api.getState();
        const memory=await Api.getMemory();
        data={type:"modlist",created_at:new Date().toISOString(),profile:s.profile,database:{mods:s.mods},memory:memory};
      }
      downloadTextFile(`${name}.json`,JSON.stringify(data,null,2),"application/json");
      showToast(I18n.t("io.exported"),"success");
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async loadFile(){
    const fileInput=document.getElementById("io-import-file");
    const result=document.getElementById("io-import-result");
    const detail=document.getElementById("io-view-detail");
    detail.innerHTML="";
    document.getElementById("btn-io-view").style.display="none";
    document.getElementById("btn-io-compare").style.display="none";
    document.getElementById("btn-io-import").style.display="none";
    this.loadedData=null;
    if(!fileInput.files||!fileInput.files.length){
      result.textContent="";
      return;
    }
    const file=fileInput.files[0];
    try{
      const text=await file.text();
      const data=JSON.parse(text);
      if(!data.type){
        result.style.color="var(--red)";
        result.textContent=I18n.t("io.invalid_no_type");
        return;
      }
      this.loadedData=data;
      // Mostrar info del archivo sin importar
      let info="";
      if(data.type==="modlist"){
        const mods=(data.database||{}).mods||[];
        const seps=mods.filter(m=>m.is_separator).length;
        info=`${I18n.t("io.type_label")}: ${I18n.t("io.type_modlist")} | ${I18n.t("backups.profile")}: ${data.profile||"?"} | ${I18n.t("modlist.stat_total")}: ${mods.length-seps} | ${I18n.t("modlist.stat_separators")}: ${seps} | ${I18n.t("backups.created")}: ${data.created_at||"?"}`;
      }else if(data.type==="nemesis"){
        const engs=Object.keys((data.nemesis||{}).engines||{});
        info=`${I18n.t("io.type_label")}: ${I18n.t("io.type_nemesis")} | ${I18n.t("backups.profile")}: ${data.profile||"?"} | ${I18n.t("nemesis.engine")}: ${engs.join(", ")||"-"} | ${I18n.t("backups.created")}: ${data.created_at||"?"}`;
      }
      result.style.color="var(--text-dim)";
      result.textContent=info;
      // Mostrar botones ver/comparar/importar
      if(data.type==="modlist"){
        document.getElementById("btn-io-view").style.display="";
        document.getElementById("btn-io-compare").style.display="";
      }
      document.getElementById("btn-io-import").style.display="";
    }catch(e){
      result.style.color="var(--red)";
      result.textContent=I18n.t("io.read_error")+": "+e.message;
    }
  },
  async doImport(){
    if(!this.loadedData){
      showToast(I18n.t("io.load_file_first"),"warning");
      return;
    }
    const result=document.getElementById("io-import-result");
    const data=this.loadedData;
    try{
      if(data.type==="nemesis"){
        const nemesis=data.nemesis||{};
        await Api.saveNemesis(nemesis);
        result.style.color="var(--green)";
        result.textContent=I18n.t("io.imported_count")+": "+Object.keys(nemesis.engines||{}).length+" "+I18n.t("nemesis.engine");
        if(NemesisTab.data)await NemesisTab.refresh();
        showToast(I18n.t("io.imported_ok"),"success");
      }else if(data.type==="modlist"){
        const db=data.database||{};
        if(!db.mods){
          result.style.color="var(--red)";
          result.textContent=I18n.t("io.invalid_no_mods");
          return;
        }
        const restoreComments=confirm(I18n.t("backups.restore_comments"));
        if(restoreComments===false){
          // Usuario cancelo: no importar nada
          result.style.color="var(--orange)";
          result.textContent=I18n.t("io.import_cancelled");
          return;
        }
        await Api.restoreFromJson(db,{restore_memory:restoreComments,memory:data.memory||{}});await new Promise(r=>setTimeout(r,300));
        result.style.color="var(--green)";
        result.textContent=I18n.t("io.imported_count")+": "+db.mods.length;
        await ModlistTab.refresh();
        showToast(I18n.t("io.imported_ok"),"success");
      }else{
        result.style.color="var(--red)";
        result.textContent=I18n.t("io.unknown_type")+": "+data.type;
        return;
      }
      // Limpiar
      document.getElementById("io-import-file").value="";
      document.getElementById("btn-io-view").style.display="none";
      document.getElementById("btn-io-compare").style.display="none";
      document.getElementById("btn-io-import").style.display="none";
      this.loadedData=null;
    }catch(e){
      result.style.color="var(--red)";
      result.textContent="Error: "+e.message;
      showToast(I18n.t("topbar.error")+": "+e.message,"error");
    }
  },
  viewLoaded(){
    if(!this.loadedData)return;
    BackupsTab._viewData(this.loadedData,document.getElementById("io-view-detail"));
  },
  async compareLoaded(){
    if(!this.loadedData)return;
    await BackupsTab._compareData(this.loadedData,document.getElementById("io-view-detail"));
  },
};
window.ImportExportTab=ImportExportTab;

// ==================== editor.js ====================
const BackupsTab={
  currentType:"modlist",
  init(){
    document.getElementById("btn-create-backup").addEventListener("click",()=>this.create());
    document.getElementById("btn-refresh-backups").addEventListener("click",()=>this.refresh());
    document.querySelectorAll("[data-backup-type]").forEach(b=>{
      b.addEventListener("click",()=>{
        document.querySelectorAll("[data-backup-type]").forEach(x=>x.classList.remove("active"));
        b.classList.add("active");
        this.currentType=b.dataset.backupType;
        this.refresh();
      });
    });
  },
  async refresh(){
    try{
      const type=this.currentType;
      // Mostrar ubicacion de respaldos
      if(AppState.state&&AppState.state.store_dir){
        document.getElementById("backups-location").innerHTML=`${I18n.t("backups.location")}: <code>${AppState.state.store_dir}\\backups</code>`;
      }
      // Cargar estado actual segun el tipo
      if(type==="nemesis"){
        const n=await Api.getNemesis();
        const info=document.getElementById("backup-current-info");
        const engines=n.detected.engines;
        const stored=n.stored.engines||{};
        let html=`<strong>${I18n.t("backups.profile")}</strong>: ${AppState.state?AppState.state.profile:"?"}<br>`;
        for(const eng of["nemesis","pandora","custom"]){
          const det=engines[eng]||[];
          const st=stored[eng]||{};
          const enabled=(st.enabled||[]).length;
          const disabled=(st.disabled||[]).length;
          const manual=(st.manual||[]).length;
          html+=`<strong>${eng}</strong>: ${det.length} ${I18n.t("nemesis.detected")}, ${enabled} ${I18n.t("nemesis.enabled")}, ${disabled} ${I18n.t("nemesis.disabled")}, ${manual} ${I18n.t("nemesis.manual")}<br>`;
        }
        info.innerHTML=html;
      }else{
        const s=await Api.getState();
        const info=document.getElementById("backup-current-info");
        info.innerHTML=`<strong>${I18n.t("backups.profile")}</strong>: ${s.profile}<br>
          <strong>${I18n.t("modlist.stat_total")}</strong>: ${s.stats.total}<br>
          <strong>${I18n.t("modlist.stat_active")}</strong>: ${s.stats.active}<br>
          <strong>${I18n.t("modlist.stat_separators")}</strong>: ${s.stats.separators}<br>
          <strong>${I18n.t("modlist.stat_missing")}</strong>: ${s.stats.missing}`;
      }
      // Cargar lista de respaldos del tipo actual
      const backups=await Api.listSnapshots(type);
      const ul=document.getElementById("backups-list");
      ul.innerHTML="";
      if(!backups.length){
        ul.innerHTML=`<li style="text-align:center;color:var(--text-muted);">${I18n.t("backups.none")}</li>`;
        return;
      }
      for(const b of backups){
        const li=document.createElement("li");
        li.style.display="flex";
        li.style.justifyContent="space-between";
        li.style.alignItems="center";
        const stats=b.stats||{};
        let desc="";
        if(type==="nemesis"){
          desc=I18n.t("backups.nemesis_tab");
        }else{
          desc=`${stats.total||0} ${I18n.t("modlist.stat_total")}, ${stats.active||0} ${I18n.t("modlist.stat_active")}, ${stats.separators||0} ${I18n.t("modlist.stat_separators")}`;
        }
        li.innerHTML=`<div><strong>${b.created_at}</strong><br><span style="color:var(--text-dim);font-size:11px;">${desc}</span></div>`;
        const btns=document.createElement("div");
        btns.style.display="flex";btns.style.gap="4px";
        const btnView=document.createElement("button");
        btnView.className="btn btn-sm";btnView.textContent=I18n.t("backups.view");
        btnView.addEventListener("click",()=>this.view(b.file));
        const btnCompare=document.createElement("button");
        btnCompare.className="btn btn-sm";btnCompare.textContent=I18n.t("backups.compare");
        btnCompare.addEventListener("click",()=>this.compare(b.file));
        const btnRestore=document.createElement("button");
        btnRestore.className="btn btn-sm btn-primary";btnRestore.textContent=I18n.t("backups.restore");
        btnRestore.addEventListener("click",()=>this.restore(b.file));
        const btnDelete=document.createElement("button");
        btnDelete.className="btn btn-sm btn-danger";btnDelete.textContent="×";
        btnDelete.title=I18n.t("backups.delete");
        btnDelete.addEventListener("click",()=>this.delete(b.file));
        btns.appendChild(btnView);btns.appendChild(btnCompare);
        btns.appendChild(btnRestore);btns.appendChild(btnDelete);
        li.appendChild(btns);
        ul.appendChild(li);
      }
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async create(){
    try{
      const r=await Api.createSnapshot(this.currentType);
      showToast(I18n.t("backups.created")+": "+r.created_at,"success");
      await this.refresh();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async view(file){
    try{
      const data=await Api.getBackup(file);
      this._viewData(data,document.getElementById("backup-detail"));
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  _viewData(data,d){
    d.innerHTML="";
      const header=document.createElement("div");
      header.style.marginBottom="8px";
      header.innerHTML=`<strong>${I18n.t("backups.created")}</strong>: ${data.created_at||""} | <strong>${I18n.t("backups.profile")}</strong>: ${data.profile||""}`;
      d.appendChild(header);
      if(data.type==="nemesis"){
        // Vista como tabla para nemesis
        const nemesis=data.nemesis||{};
        const engines=nemesis.engines||{};
        const nemComments=this.loadNemCommentsBackup();
        // Combinar todos los mods de todos los engines en una tabla
        const allRows=[];
        for(const eng of["nemesis","pandora","custom"]){
          const st=engines[eng]||{};
          const enabled=new Set(st.enabled||[]);
          const disabled=new Set(st.disabled||[]);
          const manual=st.manual||[];
          // Mods detectados (enabled + disabled)
          for(const modname of[...enabled,...disabled]){
            allRows.push({engine:eng,modname,active:enabled.has(modname),folder:"",comment:nemComments[eng+"|"+modname]||"",manual:false});
          }
          // Mods manuales
          for(const m of manual){
            allRows.push({engine:eng,modname:m.modname,active:m.enabled,folder:m.folder,comment:m.comment||"",manual:true});
          }
        }
        const wrap=document.createElement("div");
        wrap.style.maxHeight="calc(100vh - 280px)";wrap.style.overflow="auto";
        wrap.style.background="var(--bg)";wrap.style.borderRadius="6px";
        const tbl=document.createElement("table");
        tbl.className="nem-table";
        tbl.style.width="100%";
        tbl.innerHTML=`<thead><tr><th>${I18n.t("nemesis.engine")}</th><th>${I18n.t("nemesis.col_active")}</th><th>${I18n.t("nemesis.col_mod")}</th><th>${I18n.t("nemesis.col_folder")}</th><th>${I18n.t("nemesis.col_comment")}</th></tr></thead>`;
        const tb=document.createElement("tbody");
        for(const r of allRows){
          const tr=document.createElement("tr");
          if(r.manual)tr.className="manual-row";
          tr.innerHTML=`<td>${r.engine}</td><td>${r.active?"X":"O"}</td><td>${escapeHtml(r.modname)}</td><td><code>${escapeHtml(r.folder||"")}</code></td><td>${escapeHtml(r.comment||"")}</td>`;
          tb.appendChild(tr);
        }
        tbl.appendChild(tb);
        wrap.appendChild(tbl);
        d.appendChild(wrap);
      }else{
        // Vista como tabla para modlist
        const db=data.database||{};
        let mods=db.mods||[];
        // Filtrar DLCs: empezar desde el primer separador
        const firstSepIdx=mods.findIndex(m=>m.is_separator);
        if(firstSepIdx>=0)mods=mods.slice(firstSepIdx);
        const wrap=document.createElement("div");
        wrap.style.maxHeight="calc(100vh - 280px)";wrap.style.overflow="auto";
        wrap.style.background="var(--bg)";wrap.style.borderRadius="6px";
        const tbl=document.createElement("table");
        tbl.className="mod-table";
        tbl.style.width="100%";
        tbl.innerHTML=`<thead><tr><th class="col-status">${I18n.t("modlist.col_status")}</th><th class="col-priority">${I18n.t("modlist.col_order")}</th><th class="col-name">${I18n.t("modlist.col_name")}</th><th class="col-category">${I18n.t("modlist.col_category")}</th><th class="col-version">${I18n.t("modlist.col_version")}</th><th class="col-comment">${I18n.t("modlist.col_comment")}</th><th class="col-comment2">${I18n.t("modlist.col_comment2")}</th><th class="col-link">${I18n.t("modlist.col_link")}</th></tr></thead>`;
        const tb=document.createElement("tbody");
        for(const m of mods){
          const tr=document.createElement("tr");
          if(m.is_separator){
            tr.className="sep-row";
            tr.innerHTML=`<td colspan="8"><span class="sep-toggle">▼</span> ${escapeHtml(m.display_name||m.name)}</td>`;
          }else{
            if(m.deleted_from_disk)tr.className="missing";
            const link=m.link_override||m.link||"";
            const linkHtml=link?`<a href="${escapeHtml(link)}" target="_blank" rel="noopener" class="mod-link">Abrir</a>`:"";
            tr.innerHTML=`<td class="col-status ${m.active?"status-on":"status-off"}">${m.active?"X":"O"}</td><td class="col-priority">${m.priority!=null?m.priority:"—"}</td><td class="col-name">${escapeHtml(m.display_name||m.name)}</td><td class="col-category">${escapeHtml(m.category||"")}</td><td class="col-version">${escapeHtml(m.version||"")}</td><td class="col-comment">${escapeHtml(m.comment||"")}</td><td class="col-comment2">${escapeHtml(m.comment2||"")}</td><td class="col-link">${linkHtml}</td>`;
          }
          tb.appendChild(tr);
        }
        tbl.appendChild(tb);
        wrap.appendChild(tbl);
        d.appendChild(wrap);
      }
  },
  loadNemCommentsBackup(){try{const r=localStorage.getItem("mlm_nem_comments");return r?JSON.parse(r):{};}catch(e){return {};}},
  async compare(file){
    try{
      const data=await Api.getBackup(file);
      await this._compareData(data,document.getElementById("backup-detail"));
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async _compareData(data,d){
      d.innerHTML="";
      const header=document.createElement("div");
      header.style.marginBottom="8px";
      header.innerHTML=`<strong>${I18n.t("backups.comparing")}</strong>: ${data.created_at||""}`;
      d.appendChild(header);
      // Contenedor split vertical con tablas
      const split=document.createElement("div");
      split.style.display="grid";
      split.style.gridTemplateColumns="1fr 1fr";
      split.style.gap="12px";
      // Columna izquierda: actual
      const left=document.createElement("div");
      left.innerHTML=`<h3 style="color:var(--accent);margin-bottom:6px;">${I18n.t("backups.current")}</h3>`;
      const leftWrap=document.createElement("div");
      leftWrap.style.maxHeight="calc(100vh - 320px)";leftWrap.style.overflow="auto";
      leftWrap.style.background="var(--bg)";leftWrap.style.borderRadius="6px";
      // Columna derecha: respaldo
      const right=document.createElement("div");
      right.innerHTML=`<h3 style="color:var(--accent);margin-bottom:6px;">${I18n.t("backups.backup")}</h3>`;
      const rightWrap=document.createElement("div");
      rightWrap.style.maxHeight="calc(100vh - 320px)";rightWrap.style.overflow="auto";
      rightWrap.style.background="var(--bg)";rightWrap.style.borderRadius="6px";

      if(data.type==="nemesis"){
        // Comparar nemesis con tablas
        const currentNem=await Api.getNemesis();
        const nemComments=this.loadNemCommentsBackup();
        const buildNemTable=(nemData,label)=>{
          const engines=(nemData.engines||nemData.stored?.engines||{});
          const rows=[];
          for(const eng of["nemesis","pandora","custom"]){
            const st=engines[eng]||{};
            const enabled=new Set(st.enabled||[]);
            const disabled=new Set(st.disabled||[]);
            const manual=st.manual||[];
            for(const modname of[...enabled,...disabled]){
              rows.push({engine:eng,modname,active:enabled.has(modname),comment:nemComments[eng+"|"+modname]||""});
            }
            for(const m of manual){
              rows.push({engine:eng,modname:m.modname,active:m.enabled,comment:m.comment||""});
            }
          }
          const tbl=document.createElement("table");
          tbl.className="nem-table";tbl.style.width="100%";tbl.style.fontSize="12px";
          tbl.innerHTML=`<thead><tr><th>${I18n.t("nemesis.engine")}</th><th>${I18n.t("modlist.col_status")}</th><th>${I18n.t("nemesis.col_mod")}</th><th>${I18n.t("nemesis.col_comment")}</th></tr></thead>`;
          const tb=document.createElement("tbody");
          for(const r of rows){
            const tr=document.createElement("tr");
            tr.innerHTML=`<td>${r.engine}</td><td>${r.active?"X":"O"}</td><td>${escapeHtml(r.modname)}</td><td>${escapeHtml(r.comment||"")}</td>`;
            tb.appendChild(tr);
          }
          tbl.appendChild(tb);
          return tbl;
        };
        leftWrap.appendChild(buildNemTable(currentNem.stored,"actual"));
        const bakNem=data.nemesis||{};
        rightWrap.appendChild(buildNemTable(bakNem,"respaldo"));
      }else{
        // Comparar modlist con tablas
        const curState=await Api.getState();
        const curMods=curState.mods;
        const bakModsRaw=(data.database||{}).mods||[];
        // Filtrar DLCs: empezar desde el primer separador
        const filterFromFirstSep=(mods)=>{
          const idx=mods.findIndex(m=>m.is_separator);
          return idx>=0?mods.slice(idx):mods;
        };
        const bakMods=filterFromFirstSep(bakModsRaw);
        const curNames=new Set(curMods.map(m=>m.name));
        const bakNames=new Set(bakMods.map(m=>m.name));
        // Maps por nombre para comparar versiones
        const curVersions={};for(const m of curMods){curVersions[m.name]=m.version||"";}
        const bakVersions={};for(const m of bakMods){bakVersions[m.name]=m.version||"";}
        const buildModTable=(mods,otherNames,isCurrent)=>{
          const tbl=document.createElement("table");
          tbl.className="mod-table";tbl.style.width="100%";tbl.style.fontSize="12px";
          tbl.innerHTML=`<thead><tr><th class="col-status">${I18n.t("modlist.col_status")}</th><th class="col-priority">${I18n.t("modlist.col_order")}</th><th class="col-name">${I18n.t("modlist.col_name")}</th><th class="col-version">${I18n.t("modlist.col_version")}</th><th class="col-comment">${I18n.t("modlist.col_comment")}</th></tr></thead>`;
          const tb=document.createElement("tbody");
          for(const m of mods){
            const tr=document.createElement("tr");
            if(m.is_separator){
              tr.className="sep-row";
              tr.innerHTML=`<td colspan="5"><span class="sep-toggle">▼</span> ${escapeHtml(m.display_name||m.name)}</td>`;
            }else{
              // Prioridad 1: si esta marcado como deleted_from_disk en la actual -> rojo
              if(isCurrent&&m.deleted_from_disk){
                tr.style.background="rgba(239,68,68,0.15)";
                tr.style.textDecoration="line-through";
              // Prioridad 2: mod que solo esta en esta lista (no en la otra)
              }else if(!otherNames.has(m.name)){
                if(isCurrent){
                  tr.style.background="rgba(16,185,129,0.15)";  // verde: nuevo en actual
                }else{
                  tr.style.background="rgba(239,68,68,0.15)";  // rojo: eliminado (solo en respaldo)
                  tr.style.textDecoration="line-through";
                }
              }
              if(m.deleted_from_disk)tr.classList.add("missing");
              // Comparar version: si difiere, marcar celda en amarillo
              let versionStyle="";
              let versionTitle="";
              if(otherNames.has(m.name)){
                const myVer=m.version||"";
                const otherVer=isCurrent?bakVersions[m.name]:curVersions[m.name];
                if(myVer&&otherVer&&myVer!==otherVer){
                  versionStyle="background:rgba(245,158,11,0.25);font-weight:600;";
                  versionTitle=` title="${I18n.t("backups.version_diff")} ${escapeHtml(otherVer)}"`;
                }
              }
              tr.innerHTML=`<td class="col-status ${m.active?"status-on":"status-off"}">${m.active?"X":"O"}</td><td class="col-priority">${m.priority!=null?m.priority:"—"}</td><td class="col-name">${escapeHtml(m.display_name||m.name)}</td><td class="col-version" style="${versionStyle}"${versionTitle}>${escapeHtml(m.version||"")}</td><td class="col-comment">${escapeHtml(m.comment||"")}</td>`;
            }
            tb.appendChild(tr);
          }
          tbl.appendChild(tb);
          return tbl;
        };
        leftWrap.appendChild(buildModTable(curMods,bakNames,true));
        rightWrap.appendChild(buildModTable(bakMods,curNames,false));
      }
      left.appendChild(leftWrap);
      right.appendChild(rightWrap);
      split.appendChild(left);
      split.appendChild(right);
      d.appendChild(split);
      // Sincronizar scroll entre izquierda y derecha (con toggle)
      let syncing=false;
      let scrollSyncOn=true;
      const syncLeft=()=>{
        if(syncing||!scrollSyncOn)return;syncing=true;
        rightWrap.scrollTop=leftWrap.scrollTop;
        setTimeout(()=>syncing=false,10);
      };
      const syncRight=()=>{
        if(syncing||!scrollSyncOn)return;syncing=true;
        leftWrap.scrollTop=rightWrap.scrollTop;
        setTimeout(()=>syncing=false,10);
      };
      leftWrap.addEventListener("scroll",syncLeft);
      rightWrap.addEventListener("scroll",syncRight);
      // Boton toggle para sincronizar scroll
      const syncBtn=document.createElement("button");
      syncBtn.className="btn btn-sm";
      syncBtn.style.marginBottom="8px";
      syncBtn.textContent="🔒 "+I18n.t("backups.scroll_sync_on");
      syncBtn.addEventListener("click",()=>{
        scrollSyncOn=!scrollSyncOn;
        syncBtn.textContent=scrollSyncOn?("🔒 "+I18n.t("backups.scroll_sync_on")):("🔓 "+I18n.t("backups.scroll_sync_off"));
      });
      d.insertBefore(syncBtn,d.firstChild);
      // Leyenda
      const legend=document.createElement("div");
      legend.style.marginTop="8px";
      legend.style.fontSize="11px";
      legend.style.color="var(--text-dim)";
      if(data.type==="modlist"){
        legend.innerHTML=`<span style="color:var(--green);">${I18n.t("backups.legend_new")}</span> | <span style="color:var(--red);">${I18n.t("backups.legend_deleted")}</span> | <span style="background:rgba(245,158,11,0.4);padding:1px 6px;border-radius:3px;">${I18n.t("backups.legend_version")}</span>`;
      }
      d.appendChild(legend);
  },
  async restore(file){
    let backupType="modlist";
    try{
      const data=await Api.getBackup(file);
      backupType=data.type||"modlist";
    }catch(e){}

    let opts={};
    if(backupType==="modlist"){
      const restoreList=confirm(I18n.t("backups.restore_list"));
      if(!restoreList)return;
      const restoreOverrides=confirm(I18n.t("backups.restore_comments"));
      if(restoreOverrides===false){
        // Solo restaurar database, mantener overrides actuales
        opts={restore_database:true,restore_memory:false};
      }else{
        // Restaurar database + overrides del respaldo
        opts={restore_database:true,restore_memory:true};
      }
    }else{
      if(!confirm(I18n.t("backups.confirm_restore")))return;
    }
    try{
      const r=await Api.restoreBackup(file,opts);await new Promise(r=>setTimeout(r,300));
      showToast(I18n.t("backups.restored"),"success");
      if(r.type==="nemesis"){
        if(NemesisTab.data)await NemesisTab.refresh();
      }else{
        await ModlistTab.refresh();
      }
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async delete(file){
    if(!confirm(I18n.t("backups.confirm_delete")))return;
    try{
      await Api.deleteSnapshot(file);
      showToast(I18n.t("backups.deleted"),"success");
      await this.refresh();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
};
window.BackupsTab=BackupsTab;

// ==================== nemesis.js ====================
const NemesisTab={data:null,localState:{},
  init(){
    document.querySelectorAll(".nem-tab").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".nem-tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");AppState.currentNemesisEngine=b.dataset.engine;this.render();}));
    document.getElementById("nem-show-table").addEventListener("change",e=>{document.getElementById("nem-table-wrap").style.display=e.target.checked?"":"none";this.saveSettings();});
    document.getElementById("nem-show-image").addEventListener("change",e=>{document.getElementById("nem-image-wrap").style.display=e.target.checked?"":"none";this.saveSettings();});
    document.getElementById("nem-autodetect").addEventListener("click",()=>this.refresh());
    document.getElementById("nem-add-row").addEventListener("click",()=>this.addRow());
    document.getElementById("nem-image-upload").addEventListener("click",()=>this.uploadImage());
    document.addEventListener("i18n:changed",()=>{if(this.data)this.render();});
  },
  async refresh(){
    try{
      this.data=await Api.getNemesis();
      this.localState=this.data.stored.engines||{};
      for(const e of["nemesis","pandora","custom"]){if(!this.localState[e])this.localState[e]={enabled:[],disabled:[],manual:[]};if(!this.localState[e].manual)this.localState[e].manual=[];}
      const s=await Api.getSettings();const ns=s.nemesis||{};
      document.getElementById("nem-show-table").checked=ns.showTable!==false;
      document.getElementById("nem-show-image").checked=ns.showImage!==false;
      document.getElementById("nem-table-wrap").style.display=ns.showTable!==false?"":"none";
      document.getElementById("nem-image-wrap").style.display=ns.showImage!==false?"":"none";
      this.render();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  addRow(){
    const e=AppState.currentNemesisEngine;
    const st=this.localState[e]||{enabled:[],disabled:[],manual:[]};
    st.manual=st.manual||[];
    st.manual.push({modname:"",folder:"",enabled:false});
    this.localState[e]=st;this.persist();this.render();
    const tb=document.getElementById("nemesis-tbody");const lr=tb.lastElementChild;
    if(lr){const i=lr.querySelector("input[type=text]");if(i)i.focus();}
  },
  render(){
    if(!this.data)return;
    const e=AppState.currentNemesisEngine;
    const det=this.data.detected.engines[e]||[];
    const st=this.localState[e]||{enabled:[],disabled:[],manual:[]};
    const known=new Set([...(st.enabled||[]),...(st.disabled||[]),...(st.manual||[]).map(m=>m.modname)]);
    for(const m of det){if(!known.has(m.modname)){st.disabled=st.disabled||[];st.disabled.push(m.modname);}}
    const info=document.getElementById("nemesis-info");
    const lr=this.data.detected.last_run[e];
    info.innerHTML=`<strong>${I18n.t("nemesis.engine")}</strong>: ${e} &nbsp;|&nbsp; <strong>${I18n.t("nemesis.detected")}</strong>: ${det.length} &nbsp;|&nbsp; <strong>${I18n.t("nemesis.last_run")}</strong>: ${lr||"—"}`;
    const tb=document.getElementById("nemesis-tbody");tb.innerHTML="";
    const es=new Set(st.enabled||[]);
    // Cargar comentarios de mods nemesis desde settings
    const nemComments=this.loadNemComments();
    // Cargar links de mods desde la database (AppState.state.mods)
    const modLinks={};
    if(AppState.state&&AppState.state.mods){
      for(const mod of AppState.state.mods){
        const link=mod.link_override||mod.link||"";
        if(link)modLinks[mod.name]=link;
      }
    }
    for(const m of det){
      const tr=document.createElement("tr");
      const comment=nemComments[e+"|"+m.modname]||"";
      // Buscar link del mod en la database
      const link=modLinks[m.modname]||"";
      const linkHtml=link?`<a href="${escapeHtml(link)}" target="_blank" rel="noopener" class="mod-link">${I18n.t("modlist.open_link")}</a>`:"";
      tr.innerHTML=`<td><input type="checkbox" ${es.has(m.modname)?"checked":""}></td><td>${escapeHtml(m.modname)}</td><td><code>${escapeHtml(m.folder)}</code></td><td><input type="text" class="nem-comment-input" data-engine="${escapeHtml(e)}" data-modname="${escapeHtml(m.modname)}" value="${escapeHtml(comment)}" placeholder="${I18n.t("nemesis.col_comment")}"></td><td>${linkHtml}</td><td></td>`;
      tr.querySelector("input[type=checkbox]").addEventListener("change",ev=>this.toggleMod(e,m.modname,ev.target.checked));
      const commentInput=tr.querySelector(".nem-comment-input");
      commentInput.addEventListener("input",ev=>this.setNemComment(e,m.modname,ev.target.value));
      commentInput.addEventListener("blur",()=>this.saveNemComments());
      tb.appendChild(tr);
    }
    const mm=st.manual||[];
    for(let i=0;i<mm.length;i++){
      const m=mm[i];
      const tr=document.createElement("tr");tr.className="manual-row";
      // Para manuales: si hay link, mostrar clickable; sino, input editable
      let linkHtml="";
      if(m.link){
        linkHtml=`<a href="${escapeHtml(m.link)}" target="_blank" rel="noopener" class="mod-link">${I18n.t("modlist.open_link")}</a>`;
      }
      // Si es custom y no hay link, mostrar input editable
      const linkCell=(e==="custom"&&!m.link)
        ?`<input type="text" data-field="link" value="${escapeHtml(m.link||"")}" placeholder="https://...">`
        :linkHtml;
      tr.innerHTML=`<td><input type="checkbox" ${m.enabled?"checked":""}></td>
        <td><input type="text" data-field="modname" value="${escapeHtml(m.modname||"")}" placeholder="${I18n.t("nemesis.col_mod")}"></td>
        <td><input type="text" data-field="folder" value="${escapeHtml(m.folder||"")}" placeholder="${I18n.t("nemesis.col_folder")}"></td>
        <td><input type="text" data-field="comment" value="${escapeHtml(m.comment||"")}" placeholder="${I18n.t("nemesis.col_comment")}"></td>
        <td>${linkCell}</td>
        <td><button class="btn-delete-manual" title="${I18n.t("nemesis.delete_row")}">&times;</button></td>`;
      tr.querySelector("input[type=checkbox]").addEventListener("change",ev=>{mm[i].enabled=ev.target.checked;this.localState[e].manual=mm;this.persist();});
      tr.querySelectorAll("input[type=text]").forEach(inp=>{inp.addEventListener("input",ev=>{mm[i][ev.target.dataset.field]=ev.target.value;this.localState[e].manual=mm;});inp.addEventListener("blur",()=>this.persist());});
      tr.querySelector(".btn-delete-manual").addEventListener("click",()=>{mm.splice(i,1);this.localState[e].manual=mm;this.persist();this.render();});
      tb.appendChild(tr);
    }
    if(!det.length&&!mm.length){const tr=document.createElement("tr");tr.innerHTML=`<td colspan="6" style="text-align:center;color:var(--text-muted)">${I18n.t("nemesis.no_mods_detected")}</td>`;tb.appendChild(tr);}
    this.renderImages();
  },
  toggleMod(e,n,en){const st=this.localState[e]||{enabled:[],disabled:[]};st.enabled=st.enabled||[];st.disabled=st.disabled||[];if(en){if(!st.enabled.includes(n))st.enabled.push(n);st.disabled=st.disabled.filter(x=>x!==n);}else{if(!st.disabled.includes(n))st.disabled.push(n);st.enabled=st.enabled.filter(x=>x!==n);}this.localState[e]=st;this.persist();},
  async persist(){try{await Api.saveNemesis({engines:this.localState,images:this.data.stored.images||[]});}catch(e){console.error(e);}},
  loadNemComments(){try{const r=localStorage.getItem("mlm_nem_comments");return r?JSON.parse(r):{};}catch(e){return {};}},
  setNemComment(engine,modname,comment){
    const comments=this.loadNemComments();
    const key=engine+"|"+modname;
    if(comment){comments[key]=comment;}else{delete comments[key];}
    // No guardar inmediatamente, se guarda en blur
    this._nemCommentsCache=comments;
  },
  saveNemComments(){
    if(this._nemCommentsCache){
      try{localStorage.setItem("mlm_nem_comments",JSON.stringify(this._nemCommentsCache));}catch(e){}
    }
  },
  async renderImages(){
    const w=document.getElementById("nemesis-images");w.innerHTML="";
    const imgs=this.data.images||[];
    if(!imgs.length){w.innerHTML=`<p style="color:var(--text-muted);grid-column:1/-1">${I18n.t("nemesis.no_images")}</p>`;return;}
    for(const img of imgs){
      const c=document.createElement("div");c.className="nem-image-card";
      c.innerHTML=`<img src="/api/nemesis/image/${encodeURIComponent(img.filename)}" alt="${escapeHtml(img.filename)}"><div class="image-actions"><span>${escapeHtml(img.filename)} (${formatBytes(img.size)})</span><button class="btn-delete-manual">&times;</button></div>`;
      c.querySelector("button").addEventListener("click",async()=>{if(!confirm(I18n.t("nemesis.confirm_delete_image")))return;try{await Api.deleteNemesisImage(img.filename);showToast(I18n.t("nemesis.image_deleted"),"success");await this.refresh();}catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}});
      w.appendChild(c);
    }
  },
  async uploadImage(){
    const i=document.getElementById("nem-image-input");
    if(!i.files||!i.files.length){showToast(I18n.t("nemesis.select_image"),"warning");return;}
    const f=i.files[0];
    try{const b=await fileToBase64(f);await Api.uploadNemesisImage(f.name,b);showToast(I18n.t("nemesis.image_uploaded"),"success");i.value="";await this.refresh();}catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async saveSettings(){const t=document.getElementById("nem-show-table").checked;const i=document.getElementById("nem-show-image").checked;try{await Api.saveSettings({nemesis:{showTable:t,showImage:i}});}catch(e){console.error(e);}},
};
window.NemesisTab=NemesisTab;

// ==================== deleted.js ====================
const DeletedTab={
  data:null,search:"",filterSep:"",filterType:"",lastState:null,_loaded:false,
  init(){
    document.getElementById("btn-deleted-refresh").addEventListener("click",()=>{this._loaded=false;this.refresh();});
    document.getElementById("deleted-search").addEventListener("input",debounce(e=>{this.search=e.target.value.toLowerCase();this.render();},200));
    document.getElementById("deleted-filter-sep").addEventListener("change",e=>{this.filterSep=e.target.value;this.render();});
    document.getElementById("deleted-filter-type").addEventListener("change",e=>{this.filterType=e.target.value;this.render();});
    document.getElementById("btn-forget-all").addEventListener("click",()=>this.forgetAll());
    document.addEventListener("i18n:changed",()=>{if(this.data)this.render();});
  },
  async refresh(){
    // Si ya tenemos datos cargados, no recargar — solo re-renderizar
    // (el boton Actualizar fuerza recarga via _loaded=false)
    if(this._loaded&&this.data){
      this.render();
      return;
    }
    const btn=document.getElementById("btn-deleted-refresh");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("deleted.scanning");
    btn.disabled=true;
    const tb=document.getElementById("deleted-tbody");
    tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--accent);padding:30px;">${I18n.t("deleted.scanning")}</td></tr>`;
    try{
      const s=await Api.getState();
      this.lastState=s;
      // Aplanar la lista de mods eliminados, etiquetando cada uno con su separador
      const deletedMods=[];
      for(const sec of s.sections){
        const sepName=sec.separator?(sec.separator.display_name||sec.separator.name):"";
        const sepKey=sec.separator?sec.separator.name:"";
        for(const m of sec.mods){
          if(m.missing||m.deleted_from_disk){
            deletedMods.push({...m,_sepName:sepName,_sepKey:sepKey});
          }
        }
      }
      this.data=deletedMods;
      this._loaded=true;
      this.populateSepFilter();
      this.render();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  populateSepFilter(){
    const sel=document.getElementById("deleted-filter-sep");
    const cur=sel.value;
    const set=new Set();
    for(const m of (this.data||[])){if(m._sepName)set.add(m._sepName);}
    sel.innerHTML=`<option value="">${I18n.t("deleted.filter_all_sep")}</option>`;
    for(const s of Array.from(set).sort()){const o=document.createElement("option");o.value=s;o.textContent=s;sel.appendChild(o);}
    sel.value=cur;
  },
  render(){
    if(!this.data){
      const tb=document.getElementById("deleted-tbody");
      tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("deleted.none")}</td></tr>`;
      return;
    }
    // Estadisticas
    const total=this.data.length;
    const marked=this.data.filter(m=>m.deleted_from_disk).length;
    const missing=this.data.filter(m=>!m.deleted_from_disk&&m.missing).length;
    const inSep=this.data.filter(m=>m._sepName).length;
    const noSep=total-inSep;
    document.getElementById("stat-deleted-total").textContent=total;
    document.getElementById("stat-deleted-marked").textContent=marked;
    document.getElementById("stat-deleted-missing").textContent=missing;
    document.getElementById("stat-deleted-in-sep").textContent=inSep;
    document.getElementById("stat-deleted-no-sep").textContent=noSep;
    // Filtrar
    let mods=this.data.slice();
    if(this.filterSep){mods=mods.filter(m=>m._sepName===this.filterSep);}
    if(this.filterType==="marked"){mods=mods.filter(m=>m.deleted_from_disk);}
    else if(this.filterType==="missing"){mods=mods.filter(m=>!m.deleted_from_disk&&m.missing);}
    if(this.search){
      const q=this.search;
      mods=mods.filter(m=>(m.name+" "+(m.display_name||"")+" "+(m.category||"")+" "+(m.comment||"")+" "+(m.comment2||"")).toLowerCase().includes(q));
    }
    // Renderizar tabla
    const tb=document.getElementById("deleted-tbody");
    tb.innerHTML="";
    if(!mods.length){
      tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("deleted.none_filtered")}</td></tr>`;
      return;
    }
    for(const m of mods){
      const tr=document.createElement("tr");
      tr.className="mod-row missing";
      tr.dataset.modname=m.name;
      const cat=m.category_override||m.category||"";
      const badge=m.deleted_from_disk
        ?`<span class="badge badge-deleted">${I18n.t("modlist.badge_deleted")}</span>`
        :`<span class="badge badge-folder-missing">${I18n.t("deleted.badge_folder_missing")}</span>`;
      const reason=m.deleted_from_disk
        ?`<span style="color:var(--red);font-size:11px;">${I18n.t("deleted.reason_marked")}</span>`
        :`<span style="color:var(--orange);font-size:11px;">${I18n.t("deleted.reason_missing")}</span>`;
      const orderText=m.order_number!=null?m.order_number:"—";
      const sepText=m._sepName?escapeHtml(m._sepName):`<span style="color:var(--text-muted);">—</span>`;
      tr.innerHTML=`
        <td class="col-status"><button type="button" class="btn-forget-mod" data-modname="${escapeHtml(m.name)}" title="${I18n.t("deleted.forget_row")}">&times;</button></td>
        <td class="col-priority"><span>${orderText}</span></td>
        <td class="col-name">${escapeHtml(m.display_name||m.name)}${badge}</td>
        <td class="col-category">${escapeHtml(cat)}</td>
        <td class="col-version">${escapeHtml(m.version||"")}</td>
        <td class="col-comment">${escapeHtml(m.comment||"")}</td>
        <td class="col-comment2">${escapeHtml(m.comment2||"")}</td>
        <td>${sepText}</td>
        <td>${reason}</td>`;
      // Evento del boton olvidar
      const fbtn=tr.querySelector(".btn-forget-mod");
      fbtn.addEventListener("click",async(e)=>{
        e.stopPropagation();
        await this.forgetOne(m.name);
      });
      tb.appendChild(tr);
    }
  },
  async forgetOne(modname){
    if(!confirm(I18n.t("deleted.confirm_forget_one")))return;
    try{
      await Api.forgetMod(modname);
      showToast(I18n.t("deleted.forgotten_one"),"success");
      this._loaded=false;  // invalidar cache para recargar
      await this.refresh();
      // Tambien refrescar la lista principal
      await ModlistTab.refresh();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async forgetAll(){
    if(!this.data||!this.data.length){
      showToast(I18n.t("deleted.none_to_forget"),"info");
      return;
    }
    // Aplicar los mismos filtros que la vista actual
    let mods=this.data.slice();
    if(this.filterSep){mods=mods.filter(m=>m._sepName===this.filterSep);}
    if(this.filterType==="marked"){mods=mods.filter(m=>m.deleted_from_disk);}
    else if(this.filterType==="missing"){mods=mods.filter(m=>!m.deleted_from_disk&&m.missing);}
    if(this.search){
      const q=this.search;
      mods=mods.filter(m=>(m.name+" "+(m.display_name||"")+" "+(m.category||"")+" "+(m.comment||"")+" "+(m.comment2||"")).toLowerCase().includes(q));
    }
    if(!mods.length){
      showToast(I18n.t("deleted.none_to_forget"),"info");
      return;
    }
    const names=mods.map(m=>m.name);
    const msg=I18n.t("deleted.confirm_forget_all").replace("{count}",names.length);
    if(!confirm(msg))return;
    const btn=document.getElementById("btn-forget-all");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("deleted.forgetting");
    btn.disabled=true;
    try{
      const r=await Api.forgetAllMods(names);
      const forgotten=r.forgotten||0;
      const notFound=(r.not_found||[]).length;
      let toastMsg=I18n.t("deleted.forgotten_all").replace("{count}",forgotten);
      if(notFound>0)toastMsg+=" ("+notFound+" "+I18n.t("deleted.not_found")+")";
      showToast(toastMsg,"success");
      this._loaded=false;  // invalidar cache para recargar
      await this.refresh();
      await ModlistTab.refresh();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
};
window.DeletedTab=DeletedTab;

// ==================== versions.js ====================
const VersionsTab={
  data:null,search:"",filterSep:"",filterType:"",lastState:null,
  activeSubtab:"mods",
  customData:null,customSearch:"",
  backupsData:null,
  init(){
    // Sub-tab switching
    document.querySelectorAll("#versions-subtabs .nem-tab").forEach(btn=>{
      btn.addEventListener("click",()=>this.switchSubtab(btn.dataset.vsubtab));
    });
    // Mods sub-tab
    document.getElementById("btn-versions-refresh").addEventListener("click",()=>this.refresh());
    document.getElementById("versions-search").addEventListener("input",debounce(e=>{this.search=e.target.value.toLowerCase();this.render();},200));
    document.getElementById("versions-filter-sep").addEventListener("change",e=>{this.filterSep=e.target.value;this.render();});
    document.getElementById("versions-filter-type").addEventListener("change",e=>{this.filterType=e.target.value;this.render();});
    // Custom sub-tab
    document.getElementById("btn-cv-add").addEventListener("click",()=>this.addCustomEntry());
    document.getElementById("btn-cv-refresh").addEventListener("click",()=>this.refreshCustom());
    document.getElementById("cv-search").addEventListener("input",debounce(e=>{this.customSearch=e.target.value.toLowerCase();this.renderCustom();},200));
    // Live preview of generated link
    ["cv-mod-id","cv-file-id"].forEach(id=>{
      document.getElementById(id).addEventListener("input",()=>this.updateCvPreview());
    });
    // Backups sub-tab
    document.getElementById("btn-vb-create-mods").addEventListener("click",()=>this.createBackup("mods"));
    document.getElementById("btn-vb-create-custom").addEventListener("click",()=>this.createBackup("custom"));
    document.getElementById("btn-vb-refresh").addEventListener("click",()=>this.refreshBackups());
    document.addEventListener("i18n:changed",()=>{if(this.data)this.render();});
  },
  switchSubtab(name){
    this.activeSubtab=name;
    document.querySelectorAll("#versions-subtabs .nem-tab").forEach(b=>b.classList.toggle("active",b.dataset.vsubtab===name));
    document.querySelectorAll(".versions-subpanel").forEach(p=>p.style.display="none");
    const panel=document.getElementById("vsub-"+name);
    if(panel)panel.style.display="";
    if(name==="mods"&&!this.data)this.refresh();
    if(name==="custom"&&!this.customData)this.refreshCustom();
    if(name==="backups")this.refreshBackups();
  },
  async refresh(){
    const btn=document.getElementById("btn-versions-refresh");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("versions.loading");
    btn.disabled=true;
    const tb=document.getElementById("versions-tbody");
    tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--accent);padding:30px;">${I18n.t("versions.loading")}</td></tr>`;
    try{
      const s=await Api.getState();
      this.lastState=s;
      // Cargar comentarios de version (separados de los de MO2)
      this.versionComments=await Api.getVersionComments();
      const versionMods=[];
      for(const sec of s.sections){
        const sepName=sec.separator?(sec.separator.display_name||sec.separator.name):"";
        for(const m of sec.mods){
          if(m.is_separator)continue;
          if(m.deleted_from_disk)continue;
          versionMods.push({...m,_sepName:sepName});
        }
      }
      this.data=versionMods;
      this.populateSepFilter();
      this.render();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  populateSepFilter(){
    const sel=document.getElementById("versions-filter-sep");
    const cur=sel.value;
    const set=new Set();
    for(const m of (this.data||[])){if(m._sepName)set.add(m._sepName);}
    sel.innerHTML=`<option value="">${I18n.t("versions.filter_all_sep")}</option>`;
    for(const s of Array.from(set).sort()){const o=document.createElement("option");o.value=s;o.textContent=s;sel.appendChild(o);}
    sel.value=cur;
  },
  render(){
    if(!this.data){
      const tb=document.getElementById("versions-tbody");
      tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.none")}</td></tr>`;
      return;
    }
    const total=this.data.length;
    const withLink=this.data.filter(m=>m.version_links&&m.version_links.length>0).length;
    const withoutLink=total-withLink;
    const withNexus=this.data.filter(m=>m.nexus_id&&m.nexus_id!=="0").length;
    const multi=this.data.filter(m=>m.file_ids&&m.file_ids.length>1).length;
    document.getElementById("stat-versions-total").textContent=total;
    document.getElementById("stat-versions-with-link").textContent=withLink;
    document.getElementById("stat-versions-without-link").textContent=withoutLink;
    document.getElementById("stat-versions-with-nexus").textContent=withNexus;
    document.getElementById("stat-versions-multi").textContent=multi;
    let mods=this.data.slice();
    if(this.filterSep){mods=mods.filter(m=>m._sepName===this.filterSep);}
    if(this.filterType==="with_link"){mods=mods.filter(m=>m.version_links&&m.version_links.length>0);}
    else if(this.filterType==="without_link"){mods=mods.filter(m=>!m.version_links||m.version_links.length===0);}
    else if(this.filterType==="multi"){mods=mods.filter(m=>m.file_ids&&m.file_ids.length>1);}
    if(this.search){
      const q=this.search;
      mods=mods.filter(m=>(m.name+" "+(m.display_name||"")+" "+(m.nexus_id||"")+" "+(m.version||"")+" "+(m.file_ids||[]).join(" ")).toLowerCase().includes(q));
    }
    const tb=document.getElementById("versions-tbody");
    tb.innerHTML="";
    if(!mods.length){
      tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.none_filtered")}</td></tr>`;
      return;
    }
    const vComments=this.versionComments||{};
    const CHUNK_SIZE=800;
    const renderChunk=(start)=>{
      const end=Math.min(start+CHUNK_SIZE,mods.length);
      const parts=[];
      for(let i=start;i<end;i++){
        const m=mods[i];
        const statusChar=m.active?"X":"O";
        const statusClass=m.active?"status-on":"status-off";
        const nexusId=m.nexus_id&&m.nexus_id!=="0"?escapeHtml(m.nexus_id):`<span style="color:var(--text-muted);">—</span>`;
        const fileIds=m.file_ids&&m.file_ids.length>0
          ?m.file_ids.map(fid=>escapeHtml(fid)).join(", ")
          :`<span style="color:var(--text-muted);">—</span>`;
        const versionText=m.version?escapeHtml(m.version):`<span style="color:var(--text-muted);">—</span>`;
        let versionLinkHtml="";
        if(m.version_links&&m.version_links.length>0){
          if(m.version_links.length===1){
            versionLinkHtml=`<a href="${escapeHtml(m.version_links[0])}" target="_blank" rel="noopener" class="mod-link">${I18n.t("versions.open_link")}</a>`;
          }else{
            versionLinkHtml=m.version_links.map((vl,idx)=>`<a href="${escapeHtml(vl)}" target="_blank" rel="noopener" class="mod-link" style="display:inline-block;margin:1px 4px;">[${escapeHtml(m.file_ids[idx])}]</a>`).join("");
          }
        }else{
          versionLinkHtml=`<span style="color:var(--text-muted);">—</span>`;
        }
        const sepText=m._sepName?escapeHtml(m._sepName):`<span style="color:var(--text-muted);">—</span>`;
        // Comentario editable (version_comment, NO el de MO2)
        // Toda la celda es clickable para editar
        const vc=vComments[m.name]||"";
        const commentInner=vc?escapeHtml(vc):`<span style="color:var(--text-muted);">—</span>`;
        const commentCell=`<td class="col-comment editable-comment" data-modname="${escapeHtml(m.name)}" title="${I18n.t("versions.comment_placeholder")}" style="cursor:text;">${commentInner}</td>`;
        // Boton copiar a lista personalizada
        const copyBtn=`<button type="button" class="btn btn-sm btn-primary cv-copy-btn" data-modname="${escapeHtml(m.name)}" title="${I18n.t("versions.copy_to_custom_title")}" style="padding:2px 8px;font-size:11px;">↗</button>`;
        parts.push(`<tr class="mod-row"><td class="col-status"><span class="${statusClass}">${statusChar}</span></td><td class="col-name">${escapeHtml(m.display_name||m.name)}</td><td style="font-family:monospace;font-size:12px;">${nexusId}</td><td style="font-family:monospace;font-size:12px;">${fileIds}</td><td class="col-version">${versionText}</td><td>${versionLinkHtml}</td><td>${sepText}</td>${commentCell}<td style="text-align:center;">${copyBtn}</td></tr>`);
      }
      if(start===0){tb.innerHTML=parts.join("");}else{tb.insertAdjacentHTML("beforeend",parts.join(""))}
      if(end<mods.length){requestAnimationFrame(()=>renderChunk(end));}
    };
    renderChunk(0);
    // Event delegation para comentarios editables y boton copiar
    if(!this._modsDelegationInit){
      this._modsDelegationInit=true;
      tb.addEventListener("dblclick",(e)=>{
        const td=e.target.closest(".editable-comment");
        if(td)this.editVersionComment(td);
      });
      tb.addEventListener("click",(e)=>{
        if(e.target.classList.contains("cv-copy-btn")){
          this.copyToCustom(e.target.dataset.modname);
        }
      });
    }
  },
  editVersionComment(td){
    const modName=td.dataset.modname;
    const oldVal=this.versionComments[modName]||"";
    const input=document.createElement("input");
    input.type="text";
    input.value=oldVal;
    input.style.cssText="width:100%;box-sizing:border-box;background:var(--bg);border:1px solid var(--accent);color:var(--text);border-radius:3px;padding:2px 4px;font-size:12px;";
    td.innerHTML="";
    td.appendChild(input);
    input.focus();
    input.select();
    let saved=false;
    const save=async()=>{
      if(saved)return;
      saved=true;
      const newVal=input.value.trim();
      try{
        await Api.saveVersionComment(modName,newVal);
        this.versionComments[modName]=newVal;
        showToast(I18n.t("versions.comment_saved"),"success");
      }catch(e){showToast(I18n.t("versions.comment_save_error"),"error");}
      this.render();
    };
    input.addEventListener("blur",save);
    input.addEventListener("keydown",(e)=>{
      if(e.key==="Enter"){e.preventDefault();input.blur();}
      if(e.key==="Escape"){saved=true;this.render();}
    });
  },
  async copyToCustom(modName){
    if(!this.lastState)return;
    const m=this.lastState.mods.find(x=>x.name===modName);
    if(!m){showToast(I18n.t("topbar.error")+": mod not found","error");return;}
    const modId=m.nexus_id&&m.nexus_id!=="0"?m.nexus_id:"";
    const fileIds=m.file_ids||[];
    const fileId=fileIds.length>0?fileIds[0]:"";
    const version=m.version||"";
    const vc=this.versionComments[modName]||"";
    try{
      await Api.addCustomVersion({
        mod_name:m.display_name||m.name,
        mod_id:modId,
        file_id:fileId,
        version:version,
        comment:vc
      });
      if(!fileId){
        showToast(I18n.t("versions.copy_no_fileid"),"info");
      }else{
        showToast(I18n.t("versions.copied_ok"),"success");
      }
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  // === Custom sub-tab ===
  updateCvPreview(){
    const modId=document.getElementById("cv-mod-id").value.trim();
    const fileId=document.getElementById("cv-file-id").value.trim();
    const preview=document.getElementById("cv-preview");
    if(modId&&fileId){
      preview.innerHTML=`<span style="color:var(--green);">URL: </span><code style="font-size:11px;">https://www.nexusmods.com/skyrimspecialedition/mods/${escapeHtml(modId)}?tab=files&file_id=${escapeHtml(fileId)}</code>`;
    }else{
      preview.textContent="";
    }
  },
  async addCustomEntry(){
    const modName=document.getElementById("cv-mod-name").value.trim();
    const modId=document.getElementById("cv-mod-id").value.trim();
    const fileId=document.getElementById("cv-file-id").value.trim();
    const version=document.getElementById("cv-version").value.trim();
    const comment=document.getElementById("cv-comment").value.trim();
    if(!modName||!modId||!fileId){
      showToast(I18n.t("versions.error_fields_required"),"warning");
      return;
    }
    try{
      await Api.addCustomVersion({mod_name:modName,mod_id:modId,file_id:fileId,version:version,comment:comment});
      showToast(I18n.t("versions.entry_added"),"success");
      document.getElementById("cv-mod-name").value="";
      document.getElementById("cv-mod-id").value="";
      document.getElementById("cv-file-id").value="";
      document.getElementById("cv-version").value="";
      document.getElementById("cv-comment").value="";
      document.getElementById("cv-preview").textContent="";
      await this.refreshCustom();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async refreshCustom(){
    const btn=document.getElementById("btn-cv-refresh");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("versions.loading");
    btn.disabled=true;
    try{
      this.customData=await Api.getCustomVersions();
      this.renderCustom();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  renderCustom(){
    if(!this.customData){
      const tb=document.getElementById("custom-versions-tbody");
      tb.innerHTML=`<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.none")}</td></tr>`;
      return;
    }
    document.getElementById("stat-custom-total").textContent=this.customData.length;
    let entries=this.customData;
    if(this.customSearch){
      const q=this.customSearch;
      entries=entries.filter(e=>(e.mod_name+" "+e.mod_id+" "+e.file_id+" "+e.version+" "+e.comment).toLowerCase().includes(q));
    }
    const tb=document.getElementById("custom-versions-tbody");
    tb.innerHTML="";
    if(!entries.length){
      tb.innerHTML=`<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.none_filtered")}</td></tr>`;
      return;
    }
    entries.forEach((e,idx)=>{
      const tr=document.createElement("tr");
      tr.className="mod-row";
      const linkHtml=e.link?`<a href="${escapeHtml(e.link)}" target="_blank" rel="noopener" class="mod-link">${I18n.t("versions.open_link")}</a>`:"—";
      // File ID editable (toda la celda es clickable)
      const fileIdInner=e.file_id?escapeHtml(e.file_id):`<span style="color:var(--text-muted);">—</span>`;
      const fileIdCell=`<td class="editable-fileid" data-idx="${idx}" title="${I18n.t("versions.comment_placeholder")}" style="font-family:monospace;font-size:12px;cursor:text;">${fileIdInner}</td>`;
      // Comentario editable (toda la celda es clickable)
      const commentInner=e.comment?escapeHtml(e.comment):`<span style="color:var(--text-muted);">—</span>`;
      const commentCell=`<td class="col-comment editable-cvcomment" data-idx="${idx}" title="${I18n.t("versions.comment_placeholder")}" style="cursor:text;">${commentInner}</td>`;
      tr.innerHTML=`<td class="col-name">${escapeHtml(e.mod_name||"")}</td><td style="font-family:monospace;font-size:12px;">${escapeHtml(e.mod_id||"")}</td>${fileIdCell}<td class="col-version">${escapeHtml(e.version||"")}</td><td>${linkHtml}</td>${commentCell}<td class="col-status"><button type="button" class="btn-forget-mod" data-idx="${idx}" title="${I18n.t("versions.delete_entry")}">&times;</button></td>`;
      tr.querySelector(".btn-forget-mod").addEventListener("click",async()=>{
        if(!confirm(I18n.t("versions.confirm_delete_entry")))return;
        try{
          await Api.deleteCustomVersion(idx);
          showToast(I18n.t("versions.entry_deleted"),"success");
          await this.refreshCustom();
        }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
      });
      tb.appendChild(tr);
    });
    // Event delegation para celdas editables (comentario y file_id)
    if(!this._customDelegationInit){
      this._customDelegationInit=true;
      tb.addEventListener("dblclick",(e)=>{
        const td=e.target.closest(".editable-cvcomment");
        if(td){this.editCustomCell(td,"comment");return;}
        const tdFid=e.target.closest(".editable-fileid");
        if(tdFid){this.editCustomCell(tdFid,"file_id");}
      });
    }
  },
  editCustomCell(td,field){
    const idx=parseInt(td.dataset.idx);
    const oldVal=this.customData[idx]?.[field]||"";
    const input=document.createElement("input");
    input.type=field==="file_id"?"number":"text";
    input.value=oldVal;
    input.style.cssText="width:100%;box-sizing:border-box;background:var(--bg);border:1px solid var(--accent);color:var(--text);border-radius:3px;padding:2px 4px;font-size:12px;";
    if(field==="file_id")input.style.fontFamily="monospace";
    td.innerHTML="";
    td.appendChild(input);
    input.focus();
    input.select();
    let saved=false;
    const save=async()=>{
      if(saved)return;
      saved=true;
      const newVal=input.value.trim();
      try{
        const payload={};
        payload[field]=newVal;
        await Api.updateCustomVersion(idx,payload);
        if(this.customData[idx])this.customData[idx][field]=newVal;
        // Si se actualizo file_id, regenerar el link
        if(field==="file_id"&&this.customData[idx]){
          const modId=this.customData[idx].mod_id||"";
          if(modId&&newVal){
            this.customData[idx].link=`https://www.nexusmods.com/skyrimspecialedition/mods/${modId}?tab=files&file_id=${newVal}`;
          }else{
            this.customData[idx].link="";
          }
        }
        showToast(I18n.t("versions.comment_saved"),"success");
      }catch(e){showToast(I18n.t("versions.comment_save_error"),"error");}
      this.renderCustom();
    };
    input.addEventListener("blur",save);
    input.addEventListener("keydown",(e)=>{
      if(e.key==="Enter"){e.preventDefault();input.blur();}
      if(e.key==="Escape"){saved=true;this.renderCustom();}
    });
  },
  // === Backups sub-tab ===
  async refreshBackups(){
    const btn=document.getElementById("btn-vb-refresh");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("versions.loading");
    btn.disabled=true;
    try{
      this.backupsData=await Api.listVersionBackups();
      this.renderBackups();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  renderBackups(){
    const tb=document.getElementById("version-backups-tbody");
    tb.innerHTML="";
    if(!this.backupsData||!this.backupsData.length){
      tb.innerHTML=`<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.no_backups")}</td></tr>`;
      return;
    }
    for(const b of this.backupsData){
      const tr=document.createElement("tr");
      const typeLabel=b.type==="mods"?"Mods":b.type==="custom"?"Personalizada":b.type;
      const typeColor=b.type==="mods"?"var(--blue)":"var(--purple)";
      tr.innerHTML=`<td>${escapeHtml(b.label||b.filename)}</td><td style="color:${typeColor};font-weight:600;">${typeLabel}</td><td style="text-align:center;">${b.entries}</td><td style="font-size:12px;color:var(--text-dim);">${escapeHtml(b.created_at||"")}</td><td></td>`;
      const actionsTd=tr.querySelector("td:last-child");
      const btnView=document.createElement("button");
      btnView.type="button";
      btnView.className="btn btn-sm btn-primary";
      btnView.style.marginRight="4px";
      btnView.textContent=I18n.t("versions.btn_view");
      btnView.addEventListener("click",()=>this.viewBackup(b.filename));
      const btnRestore=document.createElement("button");
      btnRestore.type="button";
      btnRestore.className="btn btn-sm";
      btnRestore.style.marginRight="4px";
      btnRestore.textContent=I18n.t("versions.btn_restore");
      btnRestore.disabled=b.type!=="custom";
      btnRestore.title=b.type!=="custom"?I18n.t("versions.restore_custom_only"):"";
      btnRestore.addEventListener("click",()=>this.restoreBackup(b.filename));
      const btnDelete=document.createElement("button");
      btnDelete.type="button";
      btnDelete.className="btn btn-sm btn-danger";
      btnDelete.textContent="×";
      btnDelete.addEventListener("click",()=>this.deleteBackup(b.filename));
      actionsTd.appendChild(btnView);
      actionsTd.appendChild(btnRestore);
      actionsTd.appendChild(btnDelete);
      tb.appendChild(tr);
    }
  },
  async createBackup(type){
    try{
      const r=await Api.createVersionBackup(type,"");
      showToast(I18n.t("versions.backup_created").replace("{count}",r.entries)+" ("+type+")","success");
      await this.refreshBackups();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async viewBackup(filename){
    try{
      const data=await Api.getVersionBackup(filename);
      // Mostrar en una ventana modal simple
      const entries=data.entries||[];
      const win=window.open("","_blank","width=900,height=600");
      if(!win){showToast(I18n.t("versions.popup_blocked"),"error");return;}
      const typeLabel=data.type==="mods"?"Mods":data.type==="custom"?"Custom":"Unknown";
      let html=`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Backup: ${escapeHtml(filename)}</title><style>body{font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:20px;}table{border-collapse:collapse;width:100%;font-size:13px;}th,td{border:1px solid #333;padding:6px 10px;text-align:left;}th{background:#16213e;}tr:nth-child(even){background:#1a1a2e;}tr:nth-child(odd){background:#16213e;}h2{color:#D9822B;}a{color:#D9822B;}</style></head><body>`;
      html+=`<h2>Backup: ${escapeHtml(filename)}</h2>`;
      html+=`<p>Type: ${typeLabel} | Entries: ${entries.length} | Date: ${escapeHtml(data.created_at||"")}</p>`;
      if(data.type==="mods"){
        html+="<table><tr><th>Name</th><th>Nexus ID</th><th>File IDs</th><th>Version</th><th>Links</th></tr>";
        for(const e of entries){
          const links=(e.version_links||[]).map(l=>`<a href="${escapeHtml(l)}" target="_blank">[${escapeHtml((e.file_ids||[])[0]||"")}]</a>`).join(" ");
          html+=`<tr><td>${escapeHtml(e.name||"")}</td><td>${escapeHtml(e.nexus_id||"")}</td><td>${escapeHtml((e.file_ids||[]).join(", "))}</td><td>${escapeHtml(e.version||"")}</td><td>${links}</td></tr>`;
        }
      }else{
        html+="<table><tr><th>Name</th><th>Mod ID</th><th>File ID</th><th>Version</th><th>Link</th><th>Comment</th></tr>";
        for(const e of entries){
          html+=`<tr><td>${escapeHtml(e.mod_name||"")}</td><td>${escapeHtml(e.mod_id||"")}</td><td>${escapeHtml(e.file_id||"")}</td><td>${escapeHtml(e.version||"")}</td><td>${e.link?`<a href="${escapeHtml(e.link)}" target="_blank">Open</a>`:""}</td><td>${escapeHtml(e.comment||"")}</td></tr>`;
        }
      }
      html+="</table></body></html>";
      win.document.write(html);
      win.document.close();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async restoreBackup(filename){
    if(!confirm(I18n.t("versions.confirm_restore")))return;
    try{
      await Api.restoreVersionBackup(filename);
      showToast(I18n.t("versions.restored_ok"),"success");
      await this.refreshCustom();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async deleteBackup(filename){
    if(!confirm(I18n.t("versions.confirm_delete_backup")))return;
    try{
      await Api.deleteVersionBackup(filename);
      showToast(I18n.t("versions.backup_deleted"),"success");
      await this.refreshBackups();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
};
window.VersionsTab=VersionsTab;

// ==================== plugins.js ====================
const PluginsTab={
  data:null,filter:"",sort:"name",search:"",_loaded:false,
  init(){
    document.getElementById("btn-plugins-refresh").addEventListener("click",()=>{this._loaded=false;this.refresh();});
    document.getElementById("plugins-search").addEventListener("input",debounce(e=>{this.search=e.target.value.toLowerCase();this.render();},200));
    document.getElementById("plugins-filter").addEventListener("change",e=>{this.filter=e.target.value;this.render();});
    document.getElementById("plugins-sort").addEventListener("change",e=>{this.sort=e.target.value;this.render();});
  },
  async refresh(){
    // Si ya tenemos datos cargados, no recargar — solo re-renderizar
    // (el boton Escanear fuerza recarga via _loaded=false)
    if(this._loaded&&this.data){
      this.render();
      return;
    }
    const btn=document.getElementById("btn-plugins-refresh");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("plugins.scanning");
    btn.disabled=true;
    const tb=document.getElementById("plugins-tbody");
    tb.innerHTML=`<tr><td colspan="5" style="text-align:center;color:var(--accent);padding:30px;">${I18n.t("plugins.scanning")}</td></tr>`;
    try{
      const r=await fetch("/api/plugins");
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      this.data=d.data;
      this._loaded=true;
      this.render();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  render(){
    if(!this.data)return;
    const s=this.data.stats;
    document.getElementById("stat-total-active").textContent=s.total_active;
    document.getElementById("stat-esp").textContent=s.total_esp;
    document.getElementById("stat-esl").textContent=s.total_esl;
    document.getElementById("stat-esm").textContent=s.total_esm;
    document.getElementById("stat-plugin-slots").textContent=s.total_slots;
    document.getElementById("stat-remaining-slots").textContent=s.remaining;
    document.getElementById("stat-mods-with-plugins").textContent=s.mods_with;
    document.getElementById("stat-mods-without-plugins").textContent=s.mods_without;
    const tb=document.getElementById("plugins-tbody");
    tb.innerHTML="";
    let mods=this.data.mods||[];
    // Filtros
    if(this.filter==="with"){mods=mods.filter(m=>m.count>0);}
    else if(this.filter==="without"){mods=mods.filter(m=>m.count===0);}
    else if(this.filter==="light"){mods=mods.filter(m=>m.type==="Light"||m.type==="ESPFE"||m.type==="ESPFE + Light"||m.type==="Mixed");}
    else if(this.filter==="esp"){mods=mods.filter(m=>m.files&&m.files.some(f=>(f.type||"esp")==="esp"));}
    else if(this.filter==="standard"){mods=mods.filter(m=>m.type==="Standard");}
    else if(this.filter==="esm"){mods=mods.filter(m=>m.files&&m.files.some(f=>f.type==="esm"));}
    else if(this.filter==="base"){mods=mods.filter(m=>m.type==="Base Game");}
    if(this.search){mods=mods.filter(m=>(m.display_name||m.name).toLowerCase().includes(this.search));}
    // Ordenamiento
    const SORT_ORDER={"Standard":0,"Light":1,"ESPFE":2,"ESPFE + Light":3,"Mixed":4,"Base Game":5,"None":6};
    if(this.sort==="name"){
      mods.sort((a,b)=>(a.display_name||a.name).localeCompare(b.display_name||b.name));
    }else if(this.sort==="count"){
      mods.sort((a,b)=>(b.count||0)-(a.count||0));
    }else if(this.sort==="type"){
      mods.sort((a,b)=>(SORT_ORDER[a.type||"None"]??99)-(SORT_ORDER[b.type||"None"]??99));
    }else if(this.sort==="active"){
      mods.sort((a,b)=>(b.active?1:0)-(a.active?1:0));
    }
    // Color para Standard (azul, igual que ESP en la columna de archivos)
    const STD_COLOR="var(--blue)";
    for(const m of mods){
      const tr=document.createElement("tr");
      if(!m.active)tr.style.opacity="0.5";
      const filesHtml=m.files.map(f=>{
        const t=f.type||"esp";
        // Color: esl/ESPFE = verde, esm = morado, esp estandar = azul (igual que Standard)
        const c=t==="esl"?"var(--green)":t==="esl_flagged"?"var(--green)":t==="esm"?"var(--purple)":STD_COLOR;
        const label=t==="esl_flagged"?" (ESPFE)":t==="esl"?" (ESL)":"";
        return `<code style="display:inline-block;margin:1px 4px;color:${c};">${escapeHtml(f.name)}${label}</code>`;
      }).join("");
      // Color del TYPE: solo None es gris; Standard es azul
      let typeColor;
      if(m.type==="ESPFE"||m.type==="Light"||m.type==="ESPFE + Light")typeColor="var(--green)";
      else if(m.type==="Mixed")typeColor="var(--orange)";
      else if(m.type==="Base Game")typeColor="var(--accent)";
      else if(m.type==="Standard")typeColor=STD_COLOR;
      else typeColor="var(--text-dim)"; // None
      const typeFontWeight=(m.type==="ESPFE"||m.type==="Light"||m.type==="ESPFE + Light"||m.type==="Standard")?"600":"400";
      tr.innerHTML=`<td class="col-status ${m.active?"status-on":"status-off"}">${m.active?"X":"O"}</td><td class="col-name">${escapeHtml(m.display_name||m.name)}</td><td>${filesHtml||"—"}</td><td style="text-align:center;font-weight:600;">${m.count||"—"}</td><td style="color:${typeColor};font-weight:${typeFontWeight};">${m.type||"—"}</td>`;
      tb.appendChild(tr);
    }
    if(!mods.length){const tr=document.createElement("tr");tr.innerHTML=`<td colspan="5" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("plugins.none")}</td>`;tb.appendChild(tr);}
  },
};
window.PluginsTab=PluginsTab;

// ==================== app.js ====================
const App={pollMs:5000,pollTimer:null,
  async init(){
    await I18n.init();
    ModlistTab.init();DeletedTab.init();VersionsTab.init();ImportExportTab.init();NemesisTab.init();BackupsTab.init();PluginsTab.init();
    // Inicializar extensiones si existen
    if(window.Extensions&&Extensions.init)Extensions.init();
    document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>this.switchTab(b.dataset.tab)));
    document.getElementById("btn-refresh").addEventListener("click",()=>this.refreshAll());
    document.getElementById("refresh-toggle").addEventListener("click",()=>this.togglePause());
    document.addEventListener("keydown",e=>{if(e.key==="Escape")document.getElementById("mod-modal").classList.add("hidden");});
    await this.refreshAll();this.startPolling();
  },
  switchTab(n){
    document.querySelectorAll(".tab").forEach(b=>b.classList.remove("active"));
    document.querySelector(`[data-tab="${n}"]`).classList.add("active");
    document.querySelectorAll(".tab-panel").forEach(p=>p.classList.remove("active"));
    document.getElementById(`tab-${n}`).classList.add("active");
    if(n==="nemesis"&&!NemesisTab.data)NemesisTab.refresh();
    if(n==="backups")BackupsTab.refresh();
    if(n==="deleted")DeletedTab.refresh();
    if(n==="versions"&&!VersionsTab.data)VersionsTab.refresh();
    if(n==="plugins")PluginsTab.refresh();  // refresh() usa cache si _loaded=true
    // Notificar a extensiones del cambio de pestana
    if(window.Extensions&&Extensions.switchTab)Extensions.switchTab(n);
  },
  async refreshAll(){
    const p=document.getElementById("profile-name");
    try{
      await ModlistTab.refresh();
      this._fetchErrors=0;  // reset contador de errores
      this.hideReconnectOverlay();
      if(AppState.state)p.textContent=AppState.state.profile;
      // Ajustar intervalo de polling segun tamano de la lista
      // Listas grandes (>1000 mods) usan intervalo mas largo para no sobrecargar
      if(AppState.state&&AppState.state.stats){
        const total=AppState.state.stats.total||0;
        const newPollMs=total>2000?15000:total>1000?10000:5000;
        if(newPollMs!==this.pollMs){
          this.pollMs=newPollMs;
          this.startPolling();  // reiniciar con nuevo intervalo
        }
      }
      if(document.getElementById("tab-nemesis").classList.contains("active"))await NemesisTab.refresh();
    }catch(e){
      p.textContent=I18n.t("topbar.error");
      this._fetchErrors=(this._fetchErrors||0)+1;
      if(this._fetchErrors>=2){
        this.showReconnectOverlay();
      }
    }
  },
  showReconnectOverlay(){
    if(document.getElementById("reconnect-overlay"))return;
    const overlay=document.createElement("div");
    overlay.id="reconnect-overlay";
    overlay.style.cssText="position:fixed;inset:0;background:rgba(15,20,25,0.95);z-index:5000;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:16px;";
    overlay.innerHTML=`
      <div style="font-size:20px;font-weight:700;color:var(--red);">${I18n.t("reconnect.title")}</div>
      <div style="color:var(--text-dim);font-size:14px;text-align:center;max-width:400px;">
        ${I18n.t("reconnect.desc")}
      </div>
      <button class="btn btn-primary" id="btn-reconnect" style="font-size:14px;padding:10px 24px;">${I18n.t("reconnect.retry")}</button>
    `;
    document.body.appendChild(overlay);
    document.getElementById("btn-reconnect").addEventListener("click",async()=>{
      const btn=document.getElementById("btn-reconnect");
      btn.textContent=I18n.t("reconnect.connecting");
      btn.disabled=true;
      try{
        const r=await fetch("/api/state");
        if(r.ok){
          overlay.remove();
          this._fetchErrors=0;
          await this.refreshAll();
        }else{
          btn.textContent=I18n.t("reconnect.retry");
          btn.disabled=false;
        }
      }catch(e){
        btn.textContent=I18n.t("reconnect.retry");
        btn.disabled=false;
      }
    });
  },
  hideReconnectOverlay(){
    const o=document.getElementById("reconnect-overlay");
    if(o)o.remove();
  },
  startPolling(){
    this.stopPolling();
    this.pollTimer=setInterval(()=>{if(!AppState.paused)this.refreshAll();},this.pollMs);
    // Heartbeat: cada 30s enviar ping para mantener el servidor vivo
    this.heartbeatTimer=setInterval(()=>{fetch("/api/state",{method:"GET"}).catch(()=>{});},30000);
  },
  stopPolling(){
    if(this.pollTimer){clearInterval(this.pollTimer);this.pollTimer=null;}
    if(this.heartbeatTimer){clearInterval(this.heartbeatTimer);this.heartbeatTimer=null;}
  },
  togglePause(){
    AppState.paused=!AppState.paused;
    const d=document.getElementById("refresh-dot");const l=document.getElementById("refresh-label");
    if(AppState.paused){d.className="dot off";l.textContent=I18n.t("topbar.autorefresh_off");showToast(I18n.t("topbar.paused"),"warning");}
    else{d.className="dot on";l.textContent=I18n.t("topbar.autorefresh_on");showToast(I18n.t("topbar.resumed"),"success");this.refreshAll();}
  },
};
document.addEventListener("DOMContentLoaded",()=>App.init());
//EXTENSION_JS
</script>
</body>
</html>
'''


# ==================== Core: ModlistReader ====================

# Nombres de mods de DLC que se ocultan automaticamente
DLC_PATTERNS = [
    "dawnguard", "dragonborn", "hearthfires", "hearth fires",
    "skyrim", "update.esm", "skyrim.esm",
    "creation club", "ccbgssse", "ccas", "ccrm", "ccmt", "cctws", "ccffs",
    "anniversary", "ae upgrade",
]


def is_dlc_name(name: str) -> bool:
    """Detecta si un mod es un DLC oficial o contenido del Creation Club."""
    n = name.lower().strip()
    # Si el nombre empieza con "DLC:" o contiene patrones DLC
    if n.startswith("dlc:"):
        return True
    if n.startswith("dlc "):
        return True
    for p in DLC_PATTERNS:
        if p in n:
            return True
    return False


def clean_sep_name(name: str) -> str:
    """Limpia el nombre de un separador removiendo '_separator' y '_' inicial.

    MO2 nombra los separadores como '_Nombre_separator' internamente.
    Esta funcion devuelve solo 'Nombre' para mostrar al usuario.
    """
    if not name:
        return ""
    display = name
    # Remover sufijo _separator (case insensitive)
    if display.lower().endswith("_separator"):
        display = display[:-len("_separator")]
    # Remover prefijo _
    while display.startswith("_"):
        display = display[1:]
    # Limpiar cualquier _separator restante en el medio
    display = display.replace("_separator", "")
    return display.strip()


class ModlistReader:
    """Lee y gestiona la lista de mods usando database.json como fuente de verdad.

    Arquitectura:
        - database.json (en <profile>/ModlistManager/): base de datos principal.
          Contiene TODOS los mods con sus datos completos (nombre, prioridad,
          categoria, version, comentario, link, etc.). Es la fuente de verdad.
        - modlist.txt (en <profile>/): se lee en cada actualizacion para detectar
          mods nuevos (instalados) o eliminados (desinstalados). Solo aporta el
          nombre y el estado activo/inactivo; no sobrescribe los datos guardados.
        - CSV de MO2 (modlist.csv): SOLO se usa para importar/inicializar la base
          de datos la primera vez, o cuando el usuario pulsa "Actualizar desde CSV".
          Aporta datos que modlist.txt no tiene: categoria, version, nexus_id, url.

    Flujo:
        1. Si database.json existe: cargarlo como base.
           - Sincronizar con modlist.txt: anadir mods nuevos, marcar eliminados.
           - NO sobrescribir datos guardados (categoria, comentario, etc.).
        2. Si database.json NO existe:
           - Si CSV existe: importarlo para crear database.json.
           - Si no: generar CSV desde modlist.txt + meta.ini, luego importarlo.
        3. El usuario puede pulsar "Actualizar desde CSV" para forzar la
           re-importacion de datos desde el CSV (version, categoria, etc.).
    """

    def __init__(self, base_path, profile_dir, organizer=None, logger=None):
        self.base_path = Path(base_path)
        self.profile_dir = Path(profile_dir)
        self.mods_dir = self.base_path / "mods"
        self.organizer = organizer
        self.logger = logger
        self.store_dir = self.profile_dir / "ModlistManager"
        self.db_path = self.store_dir / "database.json"

    # ------------------------------------------------------------------ #
    # API publica
    # ------------------------------------------------------------------ #
    def read_modlist(self, force_csv_import=False):
        """Lee la lista de mods desde database.json, sincronizando con modlist.txt.

        Args:
            force_csv_import: si True, re-importa datos desde el CSV (version,
                              categoria, nexus, etc.) sin perder comentarios
                              del usuario ni el orden.
        """
        # Asegurar que existe el directorio del store
        self.store_dir.mkdir(parents=True, exist_ok=True)

        db = self._load_database()

        # Si no hay base de datos: requiere CSV inicial del usuario
        if db is None:
            csv_path = self._find_csv()
            if csv_path is None:
                # No hay DB ni CSV: mostrar aviso pidiendo CSV
                return {
                    "profile": self.profile_dir.name,
                    "mods": [], "separators": [],
                    "stats": {"total":0,"active":0,"inactive":0,"separators":0,"missing":0},
                    "csv_missing": True,
                    "csv_expected_path": str(self.store_dir / "modlist.csv"),
                    "csv_mo2_path": str(self.base_path / "modlist.csv"),
                }
            # Hay CSV: crear DB desde el CSV
            csv_mods = self._parse_csv(csv_path)
            db = {"mods": csv_mods, "created_at": self._now_iso(),
                  "updated_at": self._now_iso()}
            self._save_database(db)

        # Si se fuerza import desde CSV
        if force_csv_import:
            csv_mods = self._read_csv_mods()
            if csv_mods is not None:
                db = self._merge_csv_into_db(db, csv_mods)
                self._save_database(db)

        # Sincronizar con modlist.txt (mods nuevos/eliminados, estado activo)
        db = self._sync_with_modlist_txt(db)

        # Enriquecer comentarios desde meta.ini (el CSV de MO2 no siempre los trae)
        self._enrich_comments_from_meta(db)

        self._save_database(db)

        # Aplicar filtros
        mods = db.get("mods", [])
        mods = self._filter_dlcs(mods)

        active_count = sum(1 for m in mods if m.get("active") and not m.get("is_separator"))
        separators = [m for m in mods if m.get("is_separator")]
        return {
            "profile": self.profile_dir.name,
            "mods": mods,
            "separators": separators,
            "stats": {
                "total": len(mods),
                "active": active_count,
                "inactive": len(mods) - active_count - len(separators),
                "separators": len(separators),
                "missing": sum(1 for m in mods if m.get("missing", False)),
            },
            "db_path": str(self.db_path),
            "csv_path": str(self._find_csv()) if self._find_csv() else None,
        }

    def read_modlist_with_memory(self, memory):
        """Lee mods y aplica overrides del usuario (comentario 2, categoria, etc.)."""
        data = self.read_modlist()
        by_name = {m["name"]: m for m in data["mods"]}

        # Aplicar overrides
        mem_mods = memory.get("mods", {})
        for modname, o in mem_mods.items():
            if modname in by_name:
                m = by_name[modname]
                m["category_override"] = o.get("category")
                m["comment2"] = o.get("comment2", "")
                m["link_override"] = o.get("link_override")
                m["tags"] = o.get("tags", [])

        # Recalcular stats por si se anadieron overrides
        data["stats"] = self._calc_stats(data["mods"])
        return data

    # ------------------------------------------------------------------ #
    # Database.json management
    # ------------------------------------------------------------------ #
    def _load_database(self):
        """Carga database.json. Devuelve None si no existe."""
        if not self.db_path.exists():
            return None
        try:
            return json.loads(self.db_path.read_text(encoding="utf-8"))
        except Exception as e:
            if self.logger:
                self.logger.warning("Error cargando database.json: %s" % e)
            return None

    def _save_database(self, db):
        """Guarda database.json atomicamente."""
        try:
            db["updated_at"] = self._now_iso()
            tmp = self.db_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(str(tmp), str(self.db_path))
        except Exception as e:
            if self.logger:
                self.logger.exception("Error guardando database.json: %s" % e)

    @staticmethod
    def _now_iso():
        return datetime.datetime.now().isoformat(timespec="seconds")

    # ------------------------------------------------------------------ #
    # CSV reading (solo para inicializar o forzar actualizacion)
    # ------------------------------------------------------------------ #
    def _find_csv(self):
        """Busca el CSV de MO2 en varias ubicaciones.

        Orden de busqueda:
        1. <profile>/ModlistManager/modlist.csv (CSV generado por el plugin)
        2. <MO2>/modlist.csv (CSV exportado por MO2 manualmente)
        3. <profile>/modlist.csv
        """
        for c in [self.store_dir / "modlist.csv",
                  self.base_path / "modlist.csv",
                  self.profile_dir / "modlist.csv",
                  self.base_path / "Modlist.csv",
                  self.base_path / "MODLIST.csv"]:
            if c.exists() and c.stat().st_size > 0:
                return c
        return None

    def _read_csv_mods(self):
        """Lee el CSV de MO2 y devuelve lista de mods normalizada. None si no hay CSV."""
        csv_path = self._find_csv()
        if csv_path is None:
            return None
        return self._parse_csv(csv_path)

    def _parse_csv(self, csv_path):
        try:
            text = csv_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return []
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return []
        headers = [h.strip() for h in rows[0]]
        col_map = self._detect_columns(headers)
        mods = []
        for row in rows[1:]:
            if not row or all(not c.strip() for c in row):
                continue
            mod = self._build_mod_from_csv_row(row, col_map)
            if mod:
                mods.append(mod)
        mods.sort(key=lambda m: m["priority"])
        return mods

    def _detect_columns(self, headers):
        col_map = {}
        keywords = {
            "priority": ["prioridad", "priority"],
            "name": ["mod_nombre", "mod_name", "nombre", "name"],
            "state": ["mod_estado", "mod_state", "estado", "state", "status", "active"],
            "notes": ["columna_notas", "notes", "notas", "comment"],
            "category": ["categoria_primaria", "category", "categoria"],
            "nexus_id": ["nexus_id", "nexusid", "modid"],
            "nexus_url": ["nexus_url", "nexusurl", "url"],
            "version": ["mod_version", "version"],
            "install_date": ["fecha_instalacion", "installation", "fecha"],
        }
        for key, words in keywords.items():
            for i, h in enumerate(headers):
                hl = h.lower()
                for w in words:
                    if w in hl:
                        col_map[key] = i
                        break
                if key in col_map:
                    break
        return col_map

    def _build_mod_from_csv_row(self, row, col_map):
        def get(key, default=""):
            idx = col_map.get(key)
            if idx is None or idx >= len(row):
                return default
            val = row[idx]
            # Limpiar comillas envolventes que MO2 anade a campos con espacios
            # El modulo csv de Python ya quita las comillas externas, pero MO2
            # a veces anade comillas dobles escapadas (ej: ""texto"") que quedan
            val = val.strip()
            # Si el valor empieza y termina con comilla, quitarlas
            if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
                val = val[1:-1]
            # Tambien limpiar comillas dobles escapadas ("" -> ")
            val = val.replace('""', '"')
            return val.strip()

        try:
            priority = int(get("priority", "0"))
        except ValueError:
            priority = 0
        name = get("name")
        if not name:
            return None

        state_raw = get("state").lower().strip()
        active = state_raw in ("+","activo","active","checked","yes","true","1","x","on","enabled","v","\u2713")
        if state_raw == "-":
            active = False

        notes = get("notes")
        category = get("category")
        nexus_id = get("nexus_id")
        nexus_url = get("nexus_url")
        if not nexus_url and nexus_id and nexus_id != "0":
            nexus_url = f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}"
        version = get("version")
        install_date = get("install_date")

        is_sep = False
        if name.lower().endswith("_separator"):
            is_sep = True
        elif notes.lower().strip() == "separator":
            is_sep = True
        elif name.startswith("_"):
            is_sep = True

        display_name = name
        if is_sep:
            display_name = clean_sep_name(name)

        mod_dir = self.mods_dir / name
        missing = not mod_dir.exists()

        if is_sep:
            return {
                "name": name, "display_name": display_name, "active": active,
                "priority": priority, "raw_index": priority, "is_separator": True,
                "missing": missing, "deleted_from_disk": False, "category": "",
                "category_id": "", "version": "", "comment": notes, "comment2": "",
                "link": "", "nexus_id": "", "tags": [], "mod_path": str(mod_dir),
            }
        return {
            "name": name, "display_name": display_name, "active": active,
            "priority": priority, "raw_index": priority, "is_separator": False,
            "missing": missing, "deleted_from_disk": False, "category": category,
            "category_id": "", "version": version, "installation": install_date,
            "comment": notes, "comment2": "", "link": nexus_url, "nexus_id": nexus_id,
            "tags": [], "mod_path": str(mod_dir),
        }

    # ------------------------------------------------------------------ #
    # Generar desde modlist.txt + meta.ini (cuando no hay CSV)
    # ------------------------------------------------------------------ #
    def _generate_from_modlist_txt(self):
        """Genera lista de mods leyendo modlist.txt + meta.ini de cada mod."""
        installed = self._read_installed_mod_names()
        if not installed:
            return []
        mods = []
        for name in installed:
            mod_dir = self.mods_dir / name
            meta = self._read_meta_ini(mod_dir)
            try:
                priority = int(meta.get("priority", "999999"))
            except (ValueError, TypeError):
                priority = 999999
            is_sep = self._is_separator(name, meta)
            if is_sep:
                display = clean_sep_name(meta.get("name", "") or name)
                mods.append({
                    "name": name, "display_name": display, "active": True,
                    "priority": priority, "raw_index": priority, "is_separator": True,
                    "missing": not mod_dir.exists(), "deleted_from_disk": False,
                    "category": "", "category_id": "", "version": "",
                    "comment": meta.get("comments", ""), "comment2": "", "link": "",
                    "nexus_id": "", "tags": [], "mod_path": str(mod_dir),
                })
            else:
                nexus_id = meta.get("modid", "")
                if nexus_id == "0":
                    nexus_id = ""
                # Construir link: usar nexus_id si existe, sino usar url del meta.ini
                if nexus_id:
                    link = f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}"
                else:
                    link = meta.get("url", "")
                mods.append({
                    "name": name, "display_name": meta.get("name", name), "active": True,
                    "priority": priority, "raw_index": priority, "is_separator": False,
                    "missing": not mod_dir.exists(), "deleted_from_disk": False,
                    "category": meta.get("category", ""), "category_id": "",
                    "version": meta.get("version", ""), "installation": "",
                    "comment": meta.get("comments", ""), "comment2": "",
                    "link": link, "nexus_id": nexus_id, "tags": [],
                    "mod_path": str(mod_dir),
                })
        mods.sort(key=lambda m: m["priority"])
        return mods

    # ------------------------------------------------------------------ #
    # Sync con modlist.txt (no sobrescribe datos guardados)
    # ------------------------------------------------------------------ #
    def _sync_with_modlist_txt(self, db):
        """Sincroniza database.json con modlist.txt.

        - Mods nuevos en modlist.txt: se anaden a la DB (datos desde meta.ini).
        - Mods eliminados de modlist.txt:
          * Si es un mod normal: se marca deleted_from_disk=True y missing=True,
            pero se mantiene en la DB (con todos sus datos) para referencia.
          * Si es un separador: se ELIMINA completamente de la DB (los separadores
            no tienen datos valiosos que preservar).
        - Mods que siguen: se actualiza el estado activo/inactivo desde modlist.txt.
        - NO se sobrescriben: categoria, comentario, version, link, etc. guardados.
        """
        installed = self._read_installed_mod_names()
        if not installed:
            return db

        mods = db.get("mods", [])

        # Normalizar nombres de separadores para comparar
        def norm(n):
            return n[:-len("_separator")] if n.lower().endswith("_separator") else n
        installed_norm = {norm(n) for n in installed}

        # Construir map de estado activo desde modlist.txt
        active_states = self._read_active_states()

        # Separar mods que siguen de los que se eliminaron
        # Los separadores eliminados se descartan; los mods eliminados se marcan
        kept_mods = []
        for mod in mods:
            name = mod["name"]
            name_norm = norm(name)
            # Si el mod sigue instalado
            if name in installed or name_norm in installed_norm:
                mod["deleted_from_disk"] = False
                mod_dir = self.mods_dir / name
                mod["missing"] = not mod_dir.exists()
                # Actualizar estado activo desde modlist.txt
                if name in active_states:
                    mod["active"] = active_states[name]
                elif name_norm in active_states:
                    mod["active"] = active_states[name_norm]
                # Si el mod existe en disco y NO es separador, leer meta.ini
                # para extraer file_ids y version_links (estos datos no estan
                # en el CSV inicial, solo en el meta.ini de cada mod)
                if not mod.get("is_separator") and mod_dir.exists():
                    meta = self._read_meta_ini(mod_dir)
                    file_ids = meta.get("file_ids", [])
                    mod["file_ids"] = file_ids
                    nexus_id = mod.get("nexus_id", "") or meta.get("modid", "")
                    if nexus_id == "0":
                        nexus_id = ""
                    version_links = []
                    if nexus_id and file_ids:
                        for fid in file_ids:
                            version_links.append(
                                f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}?tab=files&file_id={fid}"
                            )
                    mod["version_links"] = version_links
                kept_mods.append(mod)
            else:
                # Mod fue eliminado
                if mod.get("is_separator"):
                    # Separador eliminado: descartar completamente
                    continue
                else:
                    # Mod eliminado: mantener con marca de deleted_from_disk
                    mod["deleted_from_disk"] = True
                    mod["missing"] = True
                    mod["active"] = False
                    kept_mods.append(mod)

        mods = kept_mods
        db_names = {m["name"] for m in mods}
        db_names_norm = {norm(n) for n in db_names}

        # Anadir mods nuevos (en modlist.txt pero no en DB)
        # Omitir mods que el usuario ha olvidado explicitamente (db["_forgotten"])
        forgotten = set(db.get("_forgotten", []))
        for name in installed:
            name_norm = norm(name)
            if name in db_names or name_norm in db_names_norm:
                continue
            mod_dir = self.mods_dir / name
            # Si el mod fue olvidado por el usuario Y la carpeta no existe en
            # disco, no volver a agregarlo. Si la carpeta existe (el usuario
            # reinstalo el mod), si agregarlo y quitarlo de _forgotten.
            if name in forgotten and not mod_dir.exists():
                continue
            if name in forgotten and mod_dir.exists():
                # El mod fue reinstalado: quitar de forgotten para que vuelva a la normalidad
                forgotten.discard(name)
            meta = self._read_meta_ini(mod_dir)
            try:
                priority = int(meta.get("priority", "999999"))
            except (ValueError, TypeError):
                priority = 999999
            is_sep = self._is_separator(name, meta)
            active = active_states.get(name, True)
            if is_sep:
                display = clean_sep_name(meta.get("name", "") or name)
                mods.append({
                    "name": name, "display_name": display, "active": active,
                    "priority": priority, "raw_index": priority, "is_separator": True,
                    "missing": not mod_dir.exists(), "deleted_from_disk": False,
                    "category": "", "category_id": "", "version": "",
                    "comment": meta.get("comments", ""), "comment2": "", "link": "",
                    "nexus_id": "", "tags": [], "mod_path": str(mod_dir),
                })
            else:
                nexus_id = meta.get("modid", "")
                if nexus_id == "0":
                    nexus_id = ""
                # Construir link: usar nexus_id si existe, sino usar url del meta.ini
                if nexus_id:
                    link = f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}"
                else:
                    link = meta.get("url", "")
                file_ids = meta.get("file_ids", [])
                # Construir enlaces de version especifica si hay file_id y nexus_id
                version_links = []
                if nexus_id and file_ids:
                    for fid in file_ids:
                        version_links.append(
                            f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}?tab=files&file_id={fid}"
                        )
                mods.append({
                    "name": name, "display_name": meta.get("name", name), "active": active,
                    "priority": priority, "raw_index": priority, "is_separator": False,
                    "missing": not mod_dir.exists(), "deleted_from_disk": False,
                    "category": meta.get("category", ""), "category_id": "",
                    "version": meta.get("version", ""), "installation": "",
                    "comment": meta.get("comments", ""), "comment2": "",
                    "link": link, "nexus_id": nexus_id, "tags": [],
                    "mod_path": str(mod_dir),
                    "file_ids": file_ids, "version_links": version_links,
                })

        # Re-ordenar por prioridad
        mods.sort(key=lambda m: m["priority"])
        db["mods"] = mods
        # Guardar la lista de forgotten actualizada (puede haber cambiado si
        # algun mod fue reinstalado)
        db["_forgotten"] = sorted(forgotten)
        return db

    def _read_active_states(self):
        """Lee modlist.txt y devuelve {name: bool_active}."""
        path = self.profile_dir / "modlist.txt"
        if not path.exists():
            return {}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {}
        states = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line[0] in ("+", "-"):
                states[line[1:].strip()] = (line[0] == "+")
        return states

    def _read_installed_mod_names(self):
        """Lee modlist.txt y devuelve un set con los nombres de mods instalados."""
        return set(self._read_active_states().keys())

    # ------------------------------------------------------------------ #
    # Merge CSV into DB (forzar actualizacion de datos sin perder comentarios)
    # ------------------------------------------------------------------ #
    def _merge_csv_into_db(self, db, csv_mods):
        """Merge datos del CSV en la DB existente (actualizacion forzada).

        Actualizar desde CSV = recargar todo desde MO2.
        Sobrescribe: priority, category, version, nexus_id, link, comment, active.
        Mantiene: comment2 (comentario personal del usuario), tags.
        Elimina: mods que estan en la DB pero no en el CSV (mods eliminados de MO2).
        NO mantiene: category_override, link_override (se resetean a los del CSV).
        """
        db_mods = db.get("mods", [])
        csv_by_name = {m["name"]: m for m in csv_mods}

        # Normalizar nombres de separadores
        def norm(n):
            return n[:-len("_separator")] if n.lower().endswith("_separator") else n
        csv_by_name_norm = {norm(n): m for n, m in csv_by_name.items()}

        # Conjunto de nombres del CSV para saber que mantener
        csv_names = set()
        csv_names_norm = set()
        for m in csv_mods:
            csv_names.add(m["name"])
            csv_names_norm.add(norm(m["name"]))

        # Filtrar: solo mantener mods de la DB que esten en el CSV
        # (preservando comment2 y tags del usuario)
        kept_mods = []
        for mod in db_mods:
            name = mod["name"]
            name_norm = norm(name)
            if name in csv_names or name_norm in csv_names_norm:
                # El mod esta en el CSV: actualizar datos forzadamente
                csv_mod = csv_by_name.get(name) or csv_by_name_norm.get(name_norm)
                if csv_mod:
                    mod["priority"] = csv_mod["priority"]
                    mod["raw_index"] = csv_mod["raw_index"]
                    mod["category"] = csv_mod.get("category", "")
                    mod["category_override"] = None
                    mod["version"] = csv_mod.get("version", "")
                    mod["nexus_id"] = csv_mod.get("nexus_id", "")
                    mod["link"] = csv_mod.get("link", "")
                    mod["link_override"] = None
                    mod["comment"] = csv_mod.get("comment", "")
                    mod["_comment_user_edited"] = False
                    mod["active"] = csv_mod.get("active", False)
                    mod["missing"] = csv_mod.get("missing", False)
                    mod["deleted_from_disk"] = False
                    # NO tocar: comment2, tags (esos son del usuario)
                # Leer meta.ini para extraer file_ids y version_links
                # (estos datos no estan en el CSV, solo en el meta.ini)
                if not mod.get("is_separator"):
                    mod_dir = self.mods_dir / name
                    if mod_dir.exists():
                        meta = self._read_meta_ini(mod_dir)
                        file_ids = meta.get("file_ids", [])
                        mod["file_ids"] = file_ids
                        nexus_id = mod.get("nexus_id", "") or meta.get("modid", "")
                        if nexus_id == "0":
                            nexus_id = ""
                        version_links = []
                        if nexus_id and file_ids:
                            for fid in file_ids:
                                version_links.append(
                                    f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}?tab=files&file_id={fid}"
                                )
                        mod["version_links"] = version_links
                kept_mods.append(mod)
            # Si el mod no esta en el CSV, se descarta (eliminado de MO2)

        # Anadir mods del CSV que no estan en la DB (mods nuevos)
        # Si el mod estaba en _forgotten pero ahora esta en el CSV, quitarlo de
        # _forgotten (el usuario esta re-importando intencionalmente)
        db_names = {m["name"] for m in kept_mods}
        db_names_norm = {norm(n) for n in db_names}
        forgotten = set(db.get("_forgotten", []))
        for csv_mod in csv_mods:
            name = csv_mod["name"]
            name_norm = norm(name)
            if name in db_names or name_norm in db_names_norm:
                continue
            # Leer meta.ini para extraer file_ids y version_links
            # (no estan en el CSV, solo en el meta.ini de cada mod)
            if not csv_mod.get("is_separator"):
                mod_dir = self.mods_dir / name
                if mod_dir.exists():
                    meta = self._read_meta_ini(mod_dir)
                    file_ids = meta.get("file_ids", [])
                    csv_mod["file_ids"] = file_ids
                    nexus_id = csv_mod.get("nexus_id", "") or meta.get("modid", "")
                    if nexus_id == "0":
                        nexus_id = ""
                    version_links = []
                    if nexus_id and file_ids:
                        for fid in file_ids:
                            version_links.append(
                                f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}?tab=files&file_id={fid}"
                            )
                    csv_mod["version_links"] = version_links
            kept_mods.append(csv_mod)
            # Quitar de _forgotten si estaba (re-importacion intencional)
            forgotten.discard(name)
            forgotten.discard(name_norm)

        # Re-ordenar
        kept_mods.sort(key=lambda m: m["priority"])
        db["mods"] = kept_mods
        # Guardar _forgotten actualizado
        if "_forgotten" in db or forgotten:
            db["_forgotten"] = sorted(forgotten)
        return db

    # ------------------------------------------------------------------ #
    # Refresh from MO2 (lee meta.ini de todos los mods como MO2 hace)
    # ------------------------------------------------------------------ #
    def refresh_from_mo2(self):
        """Lee meta.ini de todos los mods instalados y actualiza database.json.

        Esto es equivalente a lo que hace MO2 cuando exportas a CSV:
        lee modlist.txt para saber que mods estan instalados y su estado,
        y lee meta.ini de cada mod para obtener prioridad, version, categoria,
        nexus_id, link y comentarios.

        Actualiza database.json SIN perder los overrides del usuario
        (comentario 2, categoria editada, link editado, tags).
        """
        db = self._load_database()
        if db is None:
            # Si no hay DB, crearla desde cero leyendo meta.ini
            db = {"mods": [], "created_at": self._now_iso(), "updated_at": self._now_iso()}

        installed = self._read_installed_mod_names()
        active_states = self._read_active_states()

        def norm(n):
            return n[:-len("_separator")] if n.lower().endswith("_separator") else n

        db_mods = db.get("mods", [])
        db_by_name = {}
        db_by_name_norm = {}
        for m in db_mods:
            db_by_name[m["name"]] = m
            db_by_name_norm[norm(m["name"])] = m

        updated_mods = []
        seen_names = set()

        # Primero: procesar todos los mods instalados (en orden de modlist.txt)
        # Calcular prioridad maxima actual para asignar a mods nuevos
        max_priority = max((m.get("priority", 0) for m in db_mods if not m.get("deleted_from_disk")), default=0)

        # Cargar lista de forgotten para no volver a agregar mods olvidados
        forgotten = set(db.get("_forgotten", []))

        for name in installed:
            name_norm = norm(name)
            mod_dir = self.mods_dir / name
            meta = self._read_meta_ini(mod_dir)

            is_sep = self._is_separator(name, meta)
            active = active_states.get(name, True)

            # Buscar si ya existe en la DB
            existing = db_by_name.get(name) or db_by_name_norm.get(name_norm)

            if existing:
                # NO actualizar prioridad (se mantiene la de la DB para no romper el orden)
                # Solo actualizar: estado activo, version, categoria, nexus, link, comentario
                existing["active"] = active
                existing["deleted_from_disk"] = False
                existing["missing"] = not mod_dir.exists()

                # Version: siempre actualizar desde meta.ini
                existing["version"] = meta.get("version", existing.get("version", ""))

                # Categoria: NO actualizar desde meta.ini en Sincronizar desde MO2
                # (las categorias se mantienen como estan en la DB; solo se actualizan
                # desde el CSV de MO2 con el boton "Actualizar desde CSV")

                # Nexus ID y link: solo si no hay override
                nexus_id = meta.get("modid", "")
                if nexus_id == "0":
                    nexus_id = ""
                if nexus_id:
                    existing["nexus_id"] = nexus_id
                if not existing.get("link_override"):
                    if nexus_id:
                        existing["link"] = f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}"
                    elif meta.get("url", ""):
                        existing["link"] = meta.get("url", "")
                    else:
                        existing["link"] = existing.get("link", "")

                # file_ids y version_links desde [installedFiles] del meta.ini
                file_ids = meta.get("file_ids", [])
                existing["file_ids"] = file_ids
                version_links = []
                if nexus_id and file_ids:
                    for fid in file_ids:
                        version_links.append(
                            f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}?tab=files&file_id={fid}"
                        )
                existing["version_links"] = version_links

                # Comentario: comparar y actualizar si cambio en meta.ini
                meta_comment = (meta.get("comments", "") or "").strip()
                if not existing.get("_comment_user_edited"):
                    # Siempre sincronizar con meta.ini (incluso si se borro)
                    if meta_comment != existing.get("comment", ""):
                        existing["comment"] = meta_comment

                # Display name para separadores
                if is_sep:
                    existing["display_name"] = clean_sep_name(existing.get("display_name", name))

                updated_mods.append(existing)
                seen_names.add(existing["name"])
            else:
                # Mod nuevo: asignar prioridad = max_priority + 1 (al final)
                # Si el mod fue olvidado por el usuario Y la carpeta no existe,
                # no volver a agregarlo. Si la carpeta existe (reinstalado),
                # agregarlo y quitarlo de _forgotten.
                if name in forgotten and not mod_dir.exists():
                    continue
                if name in forgotten and mod_dir.exists():
                    forgotten.discard(name)
                max_priority += 1
                priority = max_priority
                if is_sep:
                    display = clean_sep_name(meta.get("name", "") or name)
                    new_mod = {
                        "name": name, "display_name": display, "active": active,
                        "priority": priority, "raw_index": priority, "is_separator": True,
                        "missing": not mod_dir.exists(), "deleted_from_disk": False,
                        "category": "", "category_id": "", "version": "",
                        "comment": meta.get("comments", ""), "comment2": "", "link": "",
                        "nexus_id": "", "tags": [], "mod_path": str(mod_dir),
                    }
                else:
                    nexus_id = meta.get("modid", "")
                    if nexus_id == "0":
                        nexus_id = ""
                    # Construir link: usar nexus_id si existe, sino usar url del meta.ini
                if nexus_id:
                    link = f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}"
                else:
                    link = meta.get("url", "")
                    file_ids = meta.get("file_ids", [])
                    version_links = []
                    if nexus_id and file_ids:
                        for fid in file_ids:
                            version_links.append(
                                f"https://www.nexusmods.com/skyrimspecialedition/mods/{nexus_id}?tab=files&file_id={fid}"
                            )
                    new_mod = {
                        "name": name, "display_name": meta.get("name", name), "active": active,
                        "priority": priority, "raw_index": priority, "is_separator": False,
                        "missing": not mod_dir.exists(), "deleted_from_disk": False,
                        "category": meta.get("category", ""), "category_id": "",
                        "version": meta.get("version", ""), "installation": "",
                        "comment": meta.get("comments", ""), "comment2": "",
                        "link": link, "nexus_id": nexus_id, "tags": [],
                        "mod_path": str(mod_dir),
                        "file_ids": file_ids, "version_links": version_links,
                    }
                updated_mods.append(new_mod)
                seen_names.add(name)

        # Segundo: mantener mods eliminados (para referencia) y descartar separadores eliminados
        for mod in db_mods:
            name = mod["name"]
            name_norm = norm(name)
            if name in seen_names or name_norm in seen_names:
                continue  # ya procesado arriba
            # Este mod ya no esta instalado
            if mod.get("is_separator"):
                # Separador eliminado: descartar
                continue
            else:
                # Mod eliminado: mantener con marca
                mod["deleted_from_disk"] = True
                mod["missing"] = True
                mod["active"] = False
                updated_mods.append(mod)

        # Ordenar por prioridad
        updated_mods.sort(key=lambda m: m["priority"])
        db["mods"] = updated_mods
        # Guardar _forgotten actualizado (puede haber cambiado si algun mod fue reinstalado)
        if "_forgotten" in db or forgotten:
            db["_forgotten"] = sorted(forgotten)
        self._save_database(db)
        return db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _is_separator(self, name, meta):
        notes = (meta.get("notes") or "").lower().strip()
        if notes == "separator":
            return True
        if name.lower().endswith("_separator"):
            return True
        if name.startswith("_"):
            return True
        return False

    def _read_meta_ini(self, mod_dir):
        meta_path = mod_dir / "meta.ini"
        if not meta_path.exists():
            return {}
        try:
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.read(meta_path, encoding="utf-8")
        except Exception:
            return {}
        out = {}
        if cp.has_section("General"):
            for k in ("modid","name","version","installation","category",
                      "comments","tags","nexusFileStatus","notes","priority","url"):
                if cp.has_option("General", k):
                    out[k] = cp.get("General", k, fallback="").strip()
        # Leer la seccion [installedFiles] para obtener el file_id
        # Estructura tipica:
        #   [installedFiles]
        #   size=1
        #   1\modid=131938
        #   1\fileid=731810
        # Un mod puede tener varios archivos instalados (size=2, 3, ...)
        file_ids = []
        if cp.has_section("installedFiles"):
            try:
                size = cp.getint("installedFiles", "size", fallback=0)
            except Exception:
                size = 0
            for i in range(1, size + 1):
                fid = cp.get("installedFiles", f"{i}\\fileid", fallback="").strip()
                if fid and fid != "0":
                    file_ids.append(fid)
        if file_ids:
            out["file_ids"] = file_ids
            out["file_id"] = file_ids[0]  # primer file_id para compatibilidad
        return out

    def _enrich_comments_from_meta(self, db):
        """Carga comentarios desde meta.ini de cada mod.

        Siempre sincroniza el comentario desde meta.ini (a menos que el usuario
        lo haya editado con _comment_user_edited=True). Esto asegura que:
        - Los respaldos capturen el comentario real de MO2
        - Al restaurar un respaldo, el comentario se actualice desde meta.ini
          si el mod sigue instalado
        """
        mods = db.get("mods", [])
        for mod in mods:
            if mod.get("is_separator"):
                continue
            # Si el usuario edito el comentario, no sobrescribir
            if mod.get("_comment_user_edited"):
                continue
            # Cargar comentario desde meta.ini (siempre, para mantener sincronizado)
            mod_dir = self.mods_dir / mod["name"]
            if mod_dir.exists():
                meta = self._read_meta_ini(mod_dir)
                comments = (meta.get("comments", "") or "").strip()
                if comments:
                    mod["comment"] = comments
                elif not mod.get("comment"):
                    mod["comment"] = ""
            # Si el mod no existe en disco, mantener el comentario del respaldo
            # Tambien enriquecer la version si esta vacia
            if not mod.get("version"):
                mod_dir = self.mods_dir / mod["name"]
                if mod_dir.exists():
                    meta = self._read_meta_ini(mod_dir)
                    if meta.get("version"):
                        mod["version"] = meta["version"]

    def _filter_dlcs(self, mods):
        """Oculta DLCs del juego y todo lo que este antes del primer separador."""
        first_sep_idx = None
        for i, m in enumerate(mods):
            if m.get("is_separator"):
                first_sep_idx = i
                break
        if first_sep_idx is not None:
            return mods[first_sep_idx:]
        return [m for m in mods if not is_dlc_name(m.get("display_name","") or m.get("name",""))]

    def _calc_stats(self, mods):
        active = sum(1 for m in mods if m.get("active") and not m.get("is_separator"))
        missing = sum(1 for m in mods if m.get("missing"))
        seps = sum(1 for m in mods if m.get("is_separator"))
        total = len(mods) - seps
        return {"total": len(mods), "active": active, "inactive": total-active,
                "separators": seps, "missing": missing}


# ==================== Separators helpers ====================

def is_separator(mod):
    return bool(mod.get("is_separator", False))

def group_by_separators(mods):
    sections = []
    current = {"separator": None, "mods": [], "collapsed": False}
    for mod in mods:
        if is_separator(mod):
            sections.append(current)
            current = {"separator": mod, "mods": [], "collapsed": False}
        else:
            current["mods"].append(mod)
    sections.append(current)
    return sections

def apply_collapse_state(sections, state):
    for sec in sections:
        sep = sec.get("separator")
        if sep is None:
            continue
        if sep["name"] in state:
            sec["collapsed"] = bool(state[sep["name"]])
    return sections

def renumber_priority(mods):
    for mod in mods:
        if mod.get("deleted_from_disk") or mod.get("is_separator"):
            mod["order_number"] = None
        else:
            mod["order_number"] = mod.get("priority", 0)
    return mods


# ==================== Nemesis detector ====================

class NemesisDetector:
    ENGINE_NEMESIS = "nemesis"
    ENGINE_PANDORA = "pandora"
    ENGINE_FNIS = "fnis"

    def __init__(self, base_path, profile_dir, mods_dir):
        self.base_path = Path(base_path)
        self.profile_dir = Path(profile_dir)
        self.mods_dir = Path(mods_dir)
        self.overwrite_dir = self.base_path / "overwrite"

    def detect_animation_mods(self):
        return {
            "engines": {
                "nemesis": self._scan(self.ENGINE_NEMESIS),
                "pandora": self._scan(self.ENGINE_PANDORA),
                "custom": [],  # Custom: no auto-deteccion, solo manual
            },
            "last_run": {
                "nemesis": self._last_run(self.ENGINE_NEMESIS),
                "pandora": self._last_run(self.ENGINE_PANDORA),
                "custom": None,  # Custom: sin ultima ejecucion
            },
        }

    def _scan(self, engine):
        results = []
        if not self.mods_dir.exists():
            return results
        for mod_dir in self.mods_dir.iterdir():
            if not mod_dir.is_dir() or mod_dir.name.startswith("_"):
                continue
            anim = self._find_anim_folder(mod_dir, engine)
            if anim:
                try:
                    rel = anim.relative_to(self.base_path)
                    folder = str(rel)
                except ValueError:
                    folder = str(anim)
                results.append({"modname": mod_dir.name, "folder": folder, "has_output": True})
        return results

    def _find_anim_folder(self, mod_dir, engine):
        candidates = []
        if engine == self.ENGINE_NEMESIS:
            candidates = [mod_dir/"Nemesis_Engine", mod_dir/"Meshes"/"actors"/"character"/"animations"/"Nemesis"]
        elif engine == self.ENGINE_PANDORA:
            candidates = [mod_dir/"Pandora_Engine", mod_dir/"Pandora"]
        # Custom: no auto-deteccion
        for c in candidates:
            if c.exists():
                return c
        return None

    def _last_run(self, engine):
        markers = []
        if engine == self.ENGINE_NEMESIS:
            markers = [self.overwrite_dir/"Nemesis_Engine"/"updater.txt", self.overwrite_dir/"Nemesis_Engine"]
        elif engine == self.ENGINE_PANDORA:
            markers = [self.overwrite_dir/"Pandora_Engine", self.overwrite_dir/"Pandora_Output"]
        # Custom: sin ultima ejecucion
        for m in markers:
            if m.exists():
                try:
                    return datetime.datetime.fromtimestamp(m.stat().st_mtime).isoformat()
                except Exception:
                    return None
        return None


# ==================== LoadOrderLibrary ====================

class LoadOrderLibrary:
    def export_modlist_text(self, mods):
        lines = []
        for mod in mods:
            prefix = "+" if mod.get("active") else "-"
            name = mod["name"]
            if mod.get("is_separator"):
                display = mod.get("display_name") or name.lstrip("_")
                # Limpiar sufijo _separator si quedo
                if display.lower().endswith("_separator"):
                    display = display[:-len("_separator")]
                if display.startswith("_"):
                    display = display.lstrip("_")
                lines.append(f"=== {display} ===")
            else:
                lines.append(f"{prefix}{name}")
        return "\n".join(lines) + "\n"

    def export_modlist_csv(self, mods):
        buf = io.StringIO()
        w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["order","active","mod_name","display_name","category","version","comment","comment2","link","is_separator"])
        order = 0
        for mod in mods:
            if mod.get("is_separator"):
                w.writerow(["","","",mod.get("display_name",""),"","","","","","1"])
                continue
            if mod.get("deleted_from_disk"):
                continue
            order += 1
            w.writerow([order, "x" if mod.get("active") else "o", mod["name"],
                        mod.get("display_name",""), mod.get("category_override") or mod.get("category",""),
                        mod.get("version",""), mod.get("comment",""), mod.get("comment2",""),
                        mod.get("link_override") or mod.get("link",""), "0"])
        return buf.getvalue()

    def import_modlist_text(self, text):
        mods = []
        priority = 0
        for raw in text.splitlines():
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith("===") and line.endswith("==="):
                display = line.strip("= ").strip()
                priority += 1
                mods.append({"name":f"_{display}","display_name":display,"active":True,
                             "priority":priority,"is_separator":True,"missing":False,
                             "deleted_from_disk":False,"version":"","category":"",
                             "comment":"","comment2":"","link":"","tags":[]})
                continue
            if line[0] in ("+","-"):
                active = line[0] == "+"
                name = line[1:].strip()
            else:
                active = True
                name = line.strip()
            priority += 1
            mods.append({"name":name,"display_name":name,"active":active,"priority":priority,
                         "is_separator":False,"missing":False,"deleted_from_disk":False,
                         "version":"","category":"","comment":"","comment2":"","link":"","tags":[]})
        return mods

    def import_from_loll_url(self, url):
        url = url.strip().rstrip("/")
        if "/download/" not in url:
            url = url + "/download/text"
        req = urllib.request.Request(url, headers={"User-Agent":"ModlistManager/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return self.import_modlist_text(raw)


# ==================== Snapshot manager ====================

class SnapshotManager:
    MAX_SNAPSHOTS = 2

    def __init__(self, store_dir):
        self.snap_dir = Path(store_dir) / "snapshots"
        self.snap_dir.mkdir(parents=True, exist_ok=True)

    def list_snapshots(self):
        files = sorted(self.snap_dir.glob("snapshot_*.json"), reverse=True)
        out = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                out.append({"file": f.name, "created_at": data.get("created_at"),
                            "profile": data.get("profile"), "stats": data.get("stats",{}), "path": str(f)})
            except Exception:
                continue
        return out

    def create_snapshot(self, modlist_data):
        ts = datetime.datetime.now().isoformat(timespec="milliseconds")
        safe_ts = ts.replace(":","-").replace(" ","_").replace(".","-")
        filename = f"snapshot_{safe_ts}.json"
        path = self.snap_dir / filename
        c = 1
        while path.exists():
            filename = f"snapshot_{safe_ts}_{c}.json"
            path = self.snap_dir / filename
            c += 1
        snapshot = {"created_at": ts, "profile": modlist_data.get("profile",""),
                    "stats": modlist_data.get("stats",{}), "mods": modlist_data.get("mods",[])}
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        self._rotate()
        return {"file": filename, "created_at": ts, "path": str(path)}

    def get_snapshot(self, filename):
        path = self.snap_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Snapshot no encontrado: {filename}")
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_snapshot(self, filename):
        path = self.snap_dir / filename
        if path.exists():
            path.unlink()
            return True
        return False

    def _rotate(self):
        files = sorted(self.snap_dir.glob("snapshot_*.json"))
        while len(files) > self.MAX_SNAPSHOTS:
            try:
                files.pop(0).unlink()
            except Exception:
                pass


# ==================== Store ====================

class Store:
    DEFAULT_MEMORY = {"mods": {}, "deleted": []}

    def __init__(self, store_dir):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        (self.store_dir / "snapshots").mkdir(exist_ok=True)
        (self.store_dir / "images").mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._memory_cache = None

    def memory_path(self): return self.store_dir / "memory.json"
    def load_memory(self):
        with self._lock:
            if self._memory_cache is not None:
                return self._memory_cache
            path = self.memory_path()
            if not path.exists():
                self._memory_cache = dict(self.DEFAULT_MEMORY)
                return self._memory_cache
            try:
                self._memory_cache = json.loads(path.read_text(encoding="utf-8"))
                if "mods" not in self._memory_cache: self._memory_cache["mods"] = {}
                if "deleted" not in self._memory_cache: self._memory_cache["deleted"] = []
            except Exception:
                self._memory_cache = dict(self.DEFAULT_MEMORY)
            return self._memory_cache

    def save_memory(self, memory):
        with self._lock:
            self._memory_cache = memory
            self._atomic_write(self.memory_path(), memory)

    def update_mod_overrides(self, modname, overrides):
        memory = self.load_memory()
        mods = memory.setdefault("mods", {})
        current = mods.get(modname, {})
        current.update(overrides)
        mods[modname] = current
        self.save_memory(memory)
        return current

    def mark_mod_deleted(self, modname, display_name=""):
        memory = self.load_memory()
        deleted = memory.setdefault("deleted", [])
        if modname not in deleted:
            deleted.append(modname)
        mods = memory.setdefault("mods", {})
        if modname not in mods:
            mods[modname] = {"display_name": display_name}
        self.save_memory(memory)

    def forget_mod(self, modname):
        """Elimina un mod completamente de la memoria (mods, deleted, seen_mods)."""
        memory = self.load_memory()
        memory.get("mods", {}).pop(modname, None)
        if modname in memory.get("deleted", []):
            memory["deleted"].remove(modname)
        # Tambien eliminar de seen_mods para que no vuelva a aparecer
        memory.get("seen_mods", {}).pop(modname, None)
        self.save_memory(memory)

    def collapse_path(self): return self.store_dir / "collapse_state.json"
    def load_collapse_state(self):
        path = self.collapse_path()
        if not path.exists(): return {}
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return {}
    def save_collapse_state(self, state): self._atomic_write(self.collapse_path(), state)
    def set_collapse(self, sep_name, collapsed):
        state = self.load_collapse_state()
        state[sep_name] = bool(collapsed)
        self.save_collapse_state(state)

    def nemesis_path(self): return self.store_dir / "nemesis.json"
    def load_nemesis(self):
        path = self.nemesis_path()
        if not path.exists(): return {"engines": {}, "images": []}
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return {"engines": {}, "images": []}
    def save_nemesis(self, data): self._atomic_write(self.nemesis_path(), data)

    def images_dir(self): return self.store_dir / "images"
    def save_image(self, filename, data):
        safe = "".join(c for c in filename if c.isalnum() or c in "._-")
        if not safe: safe = "capture.png"
        path = self.images_dir() / safe
        path.write_bytes(data)
        return path

    def list_images(self):
        out = []
        for p in sorted(self.images_dir().iterdir()):
            if p.is_file() and p.suffix.lower() in (".png",".jpg",".jpeg",".webp",".gif"):
                out.append({"filename": p.name, "size": p.stat().st_size,
                            "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                            "path": str(p)})
        return out

    def delete_image(self, filename):
        path = self.images_dir() / filename
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False

    def settings_path(self): return self.store_dir / "settings.json"
    def load_settings(self):
        path = self.settings_path()
        if not path.exists(): return {}
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return {}
    def save_settings(self, settings): self._atomic_write(self.settings_path(), settings)

    # ------------------------------------------------------------------ #
    # Custom versions (lista personalizada de enlaces de version)
    # ------------------------------------------------------------------ #
    def custom_versions_path(self): return self.store_dir / "custom_versions.json"
    def load_custom_versions(self):
        path = self.custom_versions_path()
        if not path.exists(): return []
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return []
    def save_custom_versions(self, entries):
        self._atomic_write(self.custom_versions_path(), entries)

    # ------------------------------------------------------------------ #
    # Version comments (comentarios editables en la sub-pestaña Mods)
    # ------------------------------------------------------------------ #
    def version_comments_path(self): return self.store_dir / "version_comments.json"
    def load_version_comments(self):
        path = self.version_comments_path()
        if not path.exists(): return {}
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return {}
    def save_version_comments(self, comments):
        self._atomic_write(self.version_comments_path(), comments)
    def set_version_comment(self, mod_name, comment):
        comments = self.load_version_comments()
        if comment:
            comments[mod_name] = comment
        else:
            comments.pop(mod_name, None)
        self.save_version_comments(comments)

    # ------------------------------------------------------------------ #
    # Version backups (respaldos de lista de mods y lista personalizada)
    # ------------------------------------------------------------------ #
    def version_backups_dir(self): return self.store_dir / "version_backups"
    def list_version_backups(self):
        d = self.version_backups_dir()
        if not d.exists(): return []
        result = []
        for f in sorted(d.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "filename": f.name,
                    "type": data.get("type", "unknown"),
                    "entries": len(data.get("entries", [])),
                    "created_at": data.get("created_at", ""),
                    "label": data.get("label", f.stem),
                })
            except Exception:
                pass
        return result
    def save_version_backup(self, backup_type, entries, label=""):
        import datetime as _dt
        d = self.version_backups_dir()
        d.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{backup_type}_{ts}.json"
        data = {
            "type": backup_type,
            "label": label or f"{backup_type}_{ts}",
            "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "entries": entries,
        }
        (d / fname).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return fname
    def load_version_backup(self, filename):
        if "/" in filename or "\\" in filename or ".." in filename:
            return None
        path = self.version_backups_dir() / filename
        if not path.exists(): return None
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return None
    def delete_version_backup(self, filename):
        if "/" in filename or "\\" in filename or ".." in filename:
            return False
        path = self.version_backups_dir() / filename
        if path.exists():
            path.unlink()
            return True
        return False

    def _atomic_write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))


# ==================== API ====================

class Api:
    def __init__(self, reader, store, profile_dir, base_path, translations_dir=None, organizer=None, logger=None):
        self.reader = reader
        self.store = store
        self.profile_dir = Path(profile_dir)
        self.base_path = Path(base_path)
        self.translations_dir = Path(translations_dir) if translations_dir else None
        self.organizer = organizer
        self.logger = logger
        self.nemesis_detector = NemesisDetector(base_path, profile_dir, base_path / "mods")
        self.loll = LoadOrderLibrary()
        self.snapshots = SnapshotManager(store.store_dir)
        self._extension = None  # Referencia a la extension cargada (la asigna ModlistManager)

    def handle(self, method, path, body, query):
        try:
            if path == "/api/state" and method == "GET":
                return self._get_state()
            if path == "/api/plugins" and method == "GET":
                return self._get_plugins()
            if path == "/api/refresh_from_csv" and method == "POST":
                return self._refresh_from_csv()
            if path == "/api/refresh_from_mo2" and method == "POST":
                return self._refresh_from_mo2()
            if path == "/api/generate_csv" and method == "POST":
                return self._generate_csv()
            if path == "/api/reorder" and method == "POST":
                return self._reorder_mods(body)
            if path.startswith("/api/mods/") and path.endswith("/priority") and method == "POST":
                return self._update_priority(path, body)
            if path == "/api/mods" and method == "GET":
                return self._get_mods()
            if path.startswith("/api/mods/") and path.endswith("/forget") and method == "POST":
                return self._forget_mod(path)
            if path == "/api/mods/forget_all" and method == "POST":
                return self._forget_all_mods(body)
            if path.startswith("/api/open_mod_folder/") and method == "POST":
                import subprocess as _subprocess
                import sys as _sys
                modname = urllib.parse.unquote(path[len("/api/open_mod_folder/"):])
                mod_dir = self.reader.mods_dir / modname
                if not mod_dir.exists():
                    return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Carpeta no encontrada"})
                try:
                    if _sys.platform == "win32":
                        _subprocess.Popen(["explorer", str(mod_dir)])
                    elif _sys.platform == "darwin":
                        _subprocess.Popen(["open", str(mod_dir)])
                    else:
                        _subprocess.Popen(["xdg-open", str(mod_dir)])
                    return (HTTPStatus.OK, {"ok": True})
                except Exception as e:
                    return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})
            if path.startswith("/api/mods/") and method == "POST":
                return self._update_mod(path, body)
            if path.startswith("/api/collapse/") and method == "POST":
                return self._set_collapse(path, body)
            # Backups (separados: modlist y nemesis)
            if path == "/api/backups" and method == "GET":
                return self._list_backups(query)
            if path == "/api/backups" and method == "POST":
                return self._create_backup(body, query)
            if path.startswith("/api/backups/") and method == "GET":
                return self._get_backup(path)
            if path.startswith("/api/backups/") and method == "POST":
                return self._restore_backup(path, body)
            if path.startswith("/api/backups/") and method == "DELETE":
                return self._delete_backup(path)
            if path == "/api/restore_json" and method == "POST":
                return self._restore_from_json(body)
            if path == "/api/export" and method == "GET":
                return self._export(query)
            if path == "/api/import" and method == "POST":
                return self._import_text(body)
            if path == "/api/import/url" and method == "POST":
                return self._import_url(body)
            if path == "/api/nemesis" and method == "GET":
                return self._get_nemesis()
            if path == "/api/nemesis" and method == "POST":
                try: payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception: payload = {}
                self.store.save_nemesis(payload)
                return (HTTPStatus.OK, {"ok": True})
            if path == "/api/nemesis/image" and method == "GET":
                return (HTTPStatus.OK, {"ok": True, "data": self.store.list_images()})
            if path == "/api/nemesis/image" and method == "POST":
                return self._upload_nemesis_image(body)
            if path.startswith("/api/nemesis/image/") and method == "GET":
                return self._serve_nemesis_image(path)
            if path.startswith("/api/nemesis/image/") and method == "DELETE":
                filename = urllib.parse.unquote(path[len("/api/nemesis/image/"):])
                if "/" in filename or "\\" in filename or ".." in filename:
                    return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "filename invalido"})
                return (HTTPStatus.OK, {"ok": self.store.delete_image(filename)})
            if path == "/api/settings" and method == "GET":
                return (HTTPStatus.OK, {"ok": True, "data": self.store.load_settings()})
            if path == "/api/memory" and method == "GET":
                return (HTTPStatus.OK, {"ok": True, "data": self.store.load_memory()})
            if path == "/api/settings" and method == "POST":
                try: payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
                cur = self.store.load_settings()
                cur.update(payload)
                self.store.save_settings(cur)
                return (HTTPStatus.OK, {"ok": True, "data": cur})
            # Custom versions (lista personalizada)
            if path == "/api/custom_versions" and method == "GET":
                return (HTTPStatus.OK, {"ok": True, "data": self.store.load_custom_versions()})
            if path == "/api/custom_versions" and method == "POST":
                try: payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
                entries = self.store.load_custom_versions()
                # Agregar nueva entrada
                mod_id = str(payload.get("mod_id", "")).strip()
                file_id = str(payload.get("file_id", "")).strip()
                new_entry = {
                    "mod_name": payload.get("mod_name", ""),
                    "mod_id": mod_id,
                    "file_id": file_id,
                    "version": payload.get("version", ""),
                    "comment": payload.get("comment", ""),
                    "link": f"https://www.nexusmods.com/skyrimspecialedition/mods/{mod_id}?tab=files&file_id={file_id}" if mod_id and file_id else "",
                }
                entries.append(new_entry)
                self.store.save_custom_versions(entries)
                return (HTTPStatus.OK, {"ok": True, "data": new_entry})
            if path.startswith("/api/custom_versions/") and method == "DELETE":
                idx = int(urllib.parse.unquote(path[len("/api/custom_versions/"):]))
                entries = self.store.load_custom_versions()
                if 0 <= idx < len(entries):
                    entries.pop(idx)
                    self.store.save_custom_versions(entries)
                    return (HTTPStatus.OK, {"ok": True})
                return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Indice no encontrado"})
            if path.startswith("/api/custom_versions/") and method == "POST":
                # Actualizar entrada existente (para editar comentarios)
                try: payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
                idx = int(urllib.parse.unquote(path[len("/api/custom_versions/"):]))
                entries = self.store.load_custom_versions()
                if 0 <= idx < len(entries):
                    if "comment" in payload:
                        entries[idx]["comment"] = payload["comment"]
                    if "version" in payload:
                        entries[idx]["version"] = payload["version"]
                    if "file_id" in payload:
                        entries[idx]["file_id"] = str(payload["file_id"]).strip()
                        mod_id = entries[idx].get("mod_id", "")
                        if mod_id and entries[idx]["file_id"]:
                            entries[idx]["link"] = f"https://www.nexusmods.com/skyrimspecialedition/mods/{mod_id}?tab=files&file_id={entries[idx]['file_id']}"
                    self.store.save_custom_versions(entries)
                    return (HTTPStatus.OK, {"ok": True, "data": entries[idx]})
                return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Indice no encontrado"})
            # Version comments (comentarios editables en la sub-pestaña Mods)
            if path == "/api/version_comments" and method == "GET":
                return (HTTPStatus.OK, {"ok": True, "data": self.store.load_version_comments()})
            if path == "/api/version_comments" and method == "POST":
                try: payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
                mod_name = payload.get("mod_name", "")
                comment = payload.get("comment", "")
                if not mod_name:
                    return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "mod_name requerido"})
                self.store.set_version_comment(mod_name, comment)
                return (HTTPStatus.OK, {"ok": True, "data": {"mod_name": mod_name, "comment": comment}})
            # Version backups
            if path == "/api/version_backups" and method == "GET":
                return (HTTPStatus.OK, {"ok": True, "data": self.store.list_version_backups()})
            if path == "/api/version_backups" and method == "POST":
                try: payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
                backup_type = payload.get("type", "mods")
                label = payload.get("label", "")
                if backup_type == "mods":
                    # Respaldar lista de mods con version_links
                    memory = self.store.load_memory()
                    data = self.reader.read_modlist_with_memory(memory)
                    entries = []
                    for m in data.get("mods", []):
                        if m.get("is_separator"): continue
                        if m.get("deleted_from_disk"): continue
                        entries.append({
                            "name": m.get("display_name", m.get("name", "")),
                            "mod_name": m.get("name", ""),
                            "nexus_id": m.get("nexus_id", ""),
                            "file_ids": m.get("file_ids", []),
                            "version_links": m.get("version_links", []),
                            "version": m.get("version", ""),
                        })
                elif backup_type == "custom":
                    entries = self.store.load_custom_versions()
                else:
                    return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Tipo invalido"})
                fname = self.store.save_version_backup(backup_type, entries, label)
                return (HTTPStatus.OK, {"ok": True, "data": {"filename": fname, "entries": len(entries)}})
            if path.startswith("/api/version_backups/") and method == "GET":
                filename = urllib.parse.unquote(path[len("/api/version_backups/"):])
                data = self.store.load_version_backup(filename)
                if data is None:
                    return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Respaldo no encontrado"})
                return (HTTPStatus.OK, {"ok": True, "data": data})
            if path.startswith("/api/version_backups/") and method == "POST":
                filename = urllib.parse.unquote(path[len("/api/version_backups/"):])
                data = self.store.load_version_backup(filename)
                if data is None:
                    return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Respaldo no encontrado"})
                try: payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception: payload = {}
                restore = payload.get("restore", False)
                if restore and data.get("type") == "custom":
                    self.store.save_custom_versions(data.get("entries", []))
                return (HTTPStatus.OK, {"ok": True, "data": data})
            if path.startswith("/api/version_backups/") and method == "DELETE":
                filename = urllib.parse.unquote(path[len("/api/version_backups/"):])
                ok = self.store.delete_version_backup(filename)
                if not ok:
                    return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Respaldo no encontrado"})
                return (HTTPStatus.OK, {"ok": True})
            # Extension API: rutas que empiezan con /api/translation/ se delegan
            # al modulo de extension si esta cargado
            if path.startswith("/api/translation/"):
                if self._extension is not None:
                    try:
                        ext_path = path[len("/api/translation/"):]
                        result = self._extension.handle_api(ext_path, method, body, {
                            "store_dir": str(self.store.store_dir),
                            "mods_dir": str(self.reader.mods_dir),
                            "reader": self.reader,
                            "organizer": self.organizer,
                        })
                        if result is not None:
                            return result
                    except Exception as e:
                        if self.logger: self.logger.exception("Extension API error: %s", e)
                        return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})
                return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Extension no disponible"})
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Ruta no encontrada"})
        except Exception as e:
            if self.logger: self.logger.exception("API error %s %s: %s", method, path, e)
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _get_state(self):
        memory = self.store.load_memory()
        data = self.reader.read_modlist_with_memory(memory)
        data["mods"] = renumber_priority(data["mods"])
        sections = group_by_separators(data["mods"])
        sections = apply_collapse_state(sections, self.store.load_collapse_state())
        data["sections"] = sections
        data["store_dir"] = str(self.store.store_dir)
        data["base_path"] = str(self.base_path)
        return (HTTPStatus.OK, {"ok": True, "data": data})

    def _get_plugins(self):
        """Lee plugins.txt del perfil y mapea plugins a mods instalados.

        Detecta .esp marcados como ESL leyendo el header binario del archivo
        (TES4 record header, flag ESL = bit 9 = 0x00000200). Estos archivos,
        conocidos como ESPFE, ocupan un slot de light plugin (ESL) en lugar de
        un slot estandar de los 255.
        Incluye plugins del juego base (DLCs, Creation Club).
        """
        try:
            import struct
            import os as _os

            # Leer plugins.txt para saber que plugins estan activos
            lo_path = self.profile_dir / "plugins.txt"
            lo_plugins = {}  # {plugin_name_lower: active_bool}
            if lo_path.exists():
                for line in lo_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    active = line.startswith("*")
                    name = line.lstrip("*").strip()
                    if name:
                        lo_plugins[name.lower()] = active

            # Banderas de cabecera TES4 (Record Flags, uint32 little-endian en offset 8)
            ESM_FLAG_BIT = 0x00000001   # Bit 0: Master (Archivo Maestro)
            ESL_FLAG_BIT = 0x00000200   # Bit 9: Light Plugin (ESL / ESPFE)

            # Funcion para leer los flags del header TES4 de un plugin
            # Devuelve (tiene_esm, tiene_esl) o (False, False) si no se pudo leer
            def read_plugin_flags(filepath):
                """Lee el header del plugin y devuelve (esm_flag, esl_flag)."""
                try:
                    with open(str(filepath), "rb") as f:
                        # Cabecera TES4: 4 bytes firma + 4 bytes Data Size + 4 bytes Record Flags
                        header = f.read(24)
                        if len(header) < 12:
                            return (False, False)
                        firma = header[:4]
                        if firma != b'TES4':
                            # Algunos plugins pueden tener cabecera TES5/F4SE/etc; aceptamos TES4
                            return (False, False)
                        # Los flags estan en el byte 8-11 (little-endian uint32)
                        flags = struct.unpack_from("<I", header, 8)[0]
                        return (bool(flags & ESM_FLAG_BIT), bool(flags & ESL_FLAG_BIT))
                except Exception:
                    return (False, False)

            # Funcion para clasificar un plugin segun su extension y flags
            def classify_plugin(filepath, filename):
                """Devuelve 'esm', 'esp', 'esl', o 'esl_flagged' (ESPFE).

                Reglas:
                - .esl nativo -> 'esl' (Light por defecto)
                - .esm con flag ESL -> 'esl_flagged' (ESM maestro ligero, raro)
                - .esm estandar -> 'esm'
                - .esp con flag ESL -> 'esl_flagged' (ESPFE / plugin ligero)
                - .esp estandar -> 'esp' (ocupa slot de los 255)
                """
                _, ext = _os.path.splitext(filename.lower())
                if ext == ".esl":
                    return "esl"
                elif ext == ".esm":
                    _, tiene_esl = read_plugin_flags(filepath)
                    if tiene_esl:
                        return "esl_flagged"
                    return "esm"
                elif ext == ".esp":
                    _, tiene_esl = read_plugin_flags(filepath)
                    if tiene_esl:
                        return "esl_flagged"
                    return "esp"
                return "other"

            # Leer la database
            db = self.reader._load_database()
            db_mods = (db or {}).get("mods", [])
            mods_dir = self.base_path / "mods"

            # Tambien escanear la carpeta Data del juego para plugins base
            game_plugins = []
            try:
                if self.organizer:
                    game_path = Path(self.organizer.managedGame().dataDirectory().canonicalPath())
                else:
                    game_path = self.base_path / "data"
                if game_path.exists():
                    for f in game_path.iterdir():
                        if f.is_file() and f.suffix.lower() in (".esp", ".esm", ".esl"):
                            game_plugins.append(f)
            except Exception:
                pass

            mods_result = []
            # Contadores: esp_normal, esl_native, esl_flagged (esp marcado como esl), esm
            count_esp = 0
            count_esl = 0  # incluye .esl nativos + .esp marcados como esl
            count_esm = 0
            mods_with = 0
            mods_without = 0

            for mod in db_mods:
                if mod.get("is_separator") or mod.get("deleted_from_disk"):
                    continue
                mod_name = mod["name"]
                mod_dir = mods_dir / mod_name
                found_files = []
                mod_type = "None"

                if mod_dir.exists():
                    for f in mod_dir.rglob("*"):
                        if f.is_file() and f.suffix.lower() in (".esp", ".esm", ".esl"):
                            ptype = classify_plugin(f, f.name)
                            found_files.append({"name": f.name, "type": ptype})
                            if lo_plugins.get(f.name.lower(), False):
                                if ptype == "esm":
                                    count_esm += 1
                                elif ptype in ("esl", "esl_flagged"):
                                    count_esl += 1
                                else:
                                    count_esp += 1

                if found_files:
                    mods_with += 1
                    types = set(f["type"] for f in found_files)
                    has_native_esl = "esl" in types          # .esl nativo
                    has_espfe = "esl_flagged" in types        # .esp/.esm marcado como ESL (ESPFE)
                    has_standard = "esp" in types or "esm" in types
                    if has_standard and (has_native_esl or has_espfe):
                        mod_type = "Mixed"
                    elif has_espfe and has_native_esl:
                        mod_type = "ESPFE + Light"
                    elif has_espfe:
                        mod_type = "ESPFE"
                    elif has_native_esl:
                        mod_type = "Light"
                    else:
                        mod_type = "Standard"
                else:
                    mods_without += 1

                active_count = sum(1 for f in found_files if lo_plugins.get(f["name"].lower(), False))

                mods_result.append({
                    "name": mod_name,
                    "display_name": mod.get("display_name", mod_name),
                    "priority": mod.get("priority", 0),
                    "active": mod.get("active", False),
                    "files": [{"name": f["name"], "type": f["type"]} for f in found_files],
                    "count": active_count,
                    "type": mod_type if found_files else "None",
                })

            # Procesar plugins del juego base (DLCs, Creation Club)
            base_plugin_names = set()
            for gp in game_plugins:
                pname = gp.name.lower()
                base_plugin_names.add(pname)
                ptype = classify_plugin(gp, gp.name)
                is_active = lo_plugins.get(pname, False)
                if is_active:
                    if ptype == "esm":
                        count_esm += 1
                    elif ptype in ("esl", "esl_flagged"):
                        count_esl += 1
                    else:
                        count_esp += 1
                # Agregar como entrada en la lista si esta activo
                if is_active:
                    mods_result.append({
                        "name": gp.name,
                        "display_name": gp.name + " (Base Game)",
                        "priority": -1,
                        "active": True,
                        "files": [{"name": gp.name, "type": ptype}],
                        "count": 1,
                        "type": "Base Game",
                    })

            mods_result.sort(key=lambda m: m["priority"])

            total_active = count_esp + count_esl + count_esm
            total_slots = count_esp + count_esm  # ESP + ESM cuentan para 255

            return (HTTPStatus.OK, {"ok": True, "data": {
                "stats": {
                    "total_esp": count_esp,
                    "total_esl": count_esl,
                    "total_esm": count_esm,
                    "total_active": total_active,
                    "total_slots": total_slots,
                    "total_light": count_esl,
                    "remaining": max(0, 255 - total_slots),
                    "mods_with": mods_with,
                    "mods_without": mods_without,
                    "max_slots": 255,
                    "max_light": 4096,
                },
                "mods": mods_result,
            }})
        except Exception as e:
            if self.logger:
                self.logger.exception("Error en _get_plugins: %s" % e)
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _refresh_from_csv(self):
        """Fuerza la re-importacion de datos desde el CSV de MO2.

        Actualizacion forzada: recarga prioridad, categoria, version, comentario MO2,
        link y estado activo desde el CSV. Resetea los overrides (categoria editada,
        link editado) en memory.json. Elimina de memory.json los mods que no estan
        en el CSV. Mantiene: comentarios personales (comment2) y tags de mods que
        si estan en el CSV.
        """
        try:
            # Leer el CSV para saber que mods existen
            csv_mods = self.reader._read_csv_mods()
            if csv_mods is not None:
                def norm(n):
                    return n[:-len("_separator")] if n.lower().endswith("_separator") else n
                csv_names = set()
                csv_names_norm = set()
                for m in csv_mods:
                    csv_names.add(m["name"])
                    csv_names_norm.add(norm(m["name"]))

                # Limpiar memory.json: quitar overrides y eliminar mods no en CSV
                memory = self.store.load_memory()
                mem_mods = memory.get("mods", {})
                for modname in list(mem_mods.keys()):
                    name_norm = norm(modname)
                    if modname not in csv_names and name_norm not in csv_names_norm:
                        del mem_mods[modname]
                    else:
                        mem_mods[modname].pop("category", None)
                        mem_mods[modname].pop("link_override", None)
                self.store.save_memory(memory)

            data = self.reader.read_modlist(force_csv_import=True)
            data["mods"] = renumber_priority(data["mods"])
            return (HTTPStatus.OK, {"ok": True, "data": {"updated": len(data["mods"]), "stats": data["stats"]}})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _refresh_from_mo2(self):
        """Lee meta.ini de todos los mods y actualiza database.json.

        Esto es equivalente a exportar CSV desde MO2 e importarlo, pero sin
        necesidad de hacerlo manualmente. Lee directamente los meta.ini.
        """
        try:
            db = self.reader.refresh_from_mo2()
            mods = db.get("mods", [])
            memory = self.store.load_memory()
            data = self.reader.read_modlist_with_memory(memory)
            data["mods"] = renumber_priority(data["mods"])
            return (HTTPStatus.OK, {"ok": True, "data": {"updated": len(mods), "stats": data["stats"]}})
        except Exception as e:
            if self.logger:
                self.logger.exception("Error refresh_from_mo2: %s" % e)
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _generate_csv(self):
        """Genera un CSV desde la base de datos actual y lo guarda en el perfil.

        El CSV se guarda en <profile>/ModlistManager/modlist.csv con todas las
        columnas que MO2 usa al exportar. Esto permite al usuario "actualizar
        desde CSV" sin tener que exportar manualmente desde MO2.
        """
        try:
            memory = self.store.load_memory()
            data = self.reader.read_modlist_with_memory(memory)
            mods = data["mods"]
            # Generar CSV con las mismas columnas que MO2
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["Mod_Prioridad","Mod_Nombre","Mod_Estado","Columna_Notas",
                        "Categoria_Primaria","Nexus_ID","Mod_Nexus_URL","Mod_Version",
                        "Fecha_Instalacion","Descargar_Nombre_Archivo"])
            for mod in mods:
                if mod.get("deleted_from_disk"):
                    continue  # no incluir eliminados en el CSV
                priority = mod.get("priority", 0)
                name = mod.get("name", "")
                state = "activo" if mod.get("active") else "inactivo"
                notes = mod.get("comment", "")
                if mod.get("is_separator"):
                    notes = "separator"
                category = mod.get("category_override") or mod.get("category", "")
                nexus_id = mod.get("nexus_id", "")
                link = mod.get("link_override") or mod.get("link", "")
                version = mod.get("version", "")
                install_date = mod.get("installation", "")
                w.writerow([priority, name, state, notes, category, nexus_id, link, version, install_date, ""])
            csv_content = buf.getvalue()
            # Guardar en el directorio del store (perfil)
            csv_path = self.store.store_dir / "modlist.csv"
            csv_path.write_text(csv_content, encoding="utf-8")
            return (HTTPStatus.OK, {"ok": True, "data": {"path": str(csv_path), "mods": len(mods)}})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _reorder_mods(self, body):
        """Reordena los mods segun la lista de nombres proporcionada.

        Recibe: {"names": ["mod1", "mod2", ...]}
        Reasigna prioridades secuencialmente segun el orden de la lista,
        PRESERVANDO las prioridades de los mods que no estan en la lista
        (DLCs, mods eliminados, etc.) para que no aparezcan mezclados.

        La prioridad base se calcula como la prioridad MINIMA de los mods
        en la lista, asi los mods reordenados mantienen su rango de prioridades
        y no colisionan con los DLCs.
        """
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            names = payload.get("names", [])
            if not names:
                return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Falta lista de nombres"})
            db = self.reader._load_database()
            if db is None:
                return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "No hay database"})
            db_mods = db.get("mods", [])

            # Separar mods en la lista de los que no estan
            names_set = set(names)
            in_list = [m for m in db_mods if m["name"] in names_set]
            not_in_list = [m for m in db_mods if m["name"] not in names_set]

            # La prioridad base es la del primer mod en la lista (el de menor prioridad)
            # asi preservamos el rango original y no pisamos a los DLCs
            if in_list:
                base_priority = min(m.get("priority", 0) for m in in_list)
            else:
                base_priority = 0

            # Reordenar in_list segun el orden de names
            by_name = {m["name"]: m for m in in_list}
            new_priority = base_priority
            for name in names:
                if name in by_name:
                    by_name[name]["priority"] = new_priority
                    by_name[name]["raw_index"] = new_priority
                    new_priority += 1

            # Combinar y reordenar
            all_mods = not_in_list + in_list
            all_mods.sort(key=lambda m: m.get("priority", 0))
            db["mods"] = all_mods
            self.reader._save_database(db)
            return (HTTPStatus.OK, {"ok": True, "data": {"reordered": len(names)}})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _update_priority(self, path, body):
        """Actualiza la prioridad de un solo mod y reordena."""
        rest = path[len("/api/mods/"):-len("/priority")]
        modname = urllib.parse.unquote(rest)
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}
        try:
            new_priority = int(payload.get("priority", 0))
        except (ValueError, TypeError):
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Prioridad invalida"})
        db = self.reader._load_database()
        if db is None:
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "No hay database"})
        db_mods = db.get("mods", [])
        # Actualizar prioridad del mod
        for mod in db_mods:
            if mod["name"] == modname:
                mod["priority"] = new_priority
                mod["raw_index"] = new_priority
                break
        # Re-ordenar
        db_mods.sort(key=lambda m: m["priority"])
        db["mods"] = db_mods
        self.reader._save_database(db)
        return (HTTPStatus.OK, {"ok": True, "data": {"priority": new_priority}})

    def _get_mods(self):
        memory = self.store.load_memory()
        data = self.reader.read_modlist_with_memory(memory)
        data["mods"] = renumber_priority(data["mods"])
        return (HTTPStatus.OK, {"ok": True, "data": data["mods"]})

    def _update_mod(self, path, body):
        rest = path[len("/api/mods/"):]
        modname = urllib.parse.unquote(rest)
        try: payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception: payload = {}
        # Campos que se guardan directamente en database.json
        db_fields = ("comment", "display_name")
        # Campos que se guardan como overrides en memory.json
        override_fields = ("category", "comment2", "link_override", "tags", "marked_deleted")

        # Actualizar database.json si hay campos directos
        db_updated = False
        if any(k in payload for k in db_fields):
            db = self.reader._load_database()
            if db is not None:
                for mod in db.get("mods", []):
                    if mod["name"] == modname:
                        for k in db_fields:
                            if k in payload:
                                # Comparar: solo guardar si cambio
                                old_val = mod.get(k, "")
                                new_val = payload[k]
                                if old_val != new_val:
                                    mod[k] = new_val
                                    # Si el comentario fue editado por el usuario,
                                    # marcarlo para que no se sobrescriba desde meta.ini
                                    if k == "comment":
                                        mod["_comment_user_edited"] = True
                        db_updated = True
                        break
                if db_updated:
                    self.reader._save_database(db)

        # Actualizar overrides en memory.json
        overrides = {k: payload[k] for k in override_fields if k in payload}
        if overrides:
            saved = self.store.update_mod_overrides(modname, overrides)
        else:
            saved = {}
        if db_updated:
            saved["db_updated"] = True
        return (HTTPStatus.OK, {"ok": True, "data": saved})

    def _forget_mod(self, path):
        rest = path[len("/api/mods/"):-len("/forget")]
        modname = urllib.parse.unquote(rest)
        # 1. Eliminar de memory.json (overrides)
        self.store.forget_mod(modname)
        # 2. Eliminar de database.json y agregar a _forgotten para que el sync
        #    no lo vuelva a agregar desde modlist.txt
        db = self.reader._load_database()
        if db is not None:
            db_mods = db.get("mods", [])
            db["mods"] = [m for m in db_mods if m["name"] != modname]
            forgotten = set(db.get("_forgotten", []))
            forgotten.add(modname)
            db["_forgotten"] = sorted(forgotten)
            self.reader._save_database(db)
        return (HTTPStatus.OK, {"ok": True})

    def _forget_all_mods(self, body):
        """Olvida (elimina de la base de datos) multiples mods a la vez.

        Espera un body JSON: {"names": ["mod1", "mod2", ...]}
        Devuelve {"ok": True, "data": {"forgotten": N, "not_found": [...]}}

        Ademas de eliminar los mods de database.json y memory.json, los agrega
        a db["_forgotten"] para que _sync_with_modlist_txt no los vuelva a
        agregar desde modlist.txt en el proximo refresh.
        """
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
        names = payload.get("names", [])
        if not isinstance(names, list) or not names:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Se requiere una lista de nombres"})
        # Normalizar a strings
        names = [str(n) for n in names if n]
        names_set = set(names)
        forgotten_count = 0
        not_found = []
        # 1. Eliminar de memory.json (overrides, deleted, seen_mods)
        memory = self.store.load_memory()
        changed_mem = False
        for n in list(memory.get("mods", {}).keys()):
            if n in names_set:
                memory["mods"].pop(n, None)
                changed_mem = True
        if memory.get("deleted"):
            memory["deleted"] = [n for n in memory["deleted"] if n not in names_set]
            changed_mem = True
        if memory.get("seen_mods"):
            for n in list(memory["seen_mods"].keys()):
                if n in names_set:
                    memory["seen_mods"].pop(n, None)
                    changed_mem = True
        if changed_mem:
            self.store.save_memory(memory)
        # 2. Eliminar de database.json y agregar a _forgotten
        db = self.reader._load_database()
        if db is not None:
            db_mods = db.get("mods", [])
            before = len(db_mods)
            db["mods"] = [m for m in db_mods if m["name"] not in names_set]
            after = len(db["mods"])
            forgotten_count = before - after
            # Agregar todos los nombres a _forgotten (incluso los que no estaban
            # en la DB, por si acaso aparecen despues desde modlist.txt)
            forgotten = set(db.get("_forgotten", []))
            forgotten.update(names_set)
            db["_forgotten"] = sorted(forgotten)
            # Detectar cuales no se encontraron
            existing_names = {m["name"] for m in db_mods}
            not_found = [n for n in names if n not in existing_names]
            if forgotten_count > 0 or not_found:
                self.reader._save_database(db)
        return (HTTPStatus.OK, {"ok": True, "data": {"forgotten": forgotten_count, "not_found": not_found}})

    def _set_collapse(self, path, body):
        sep_name = urllib.parse.unquote(path[len("/api/collapse/"):])
        try: payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception: payload = {}
        collapsed = bool(payload.get("collapsed", False))
        self.store.set_collapse(sep_name, collapsed)
        return (HTTPStatus.OK, {"ok": True, "data": {"collapsed": collapsed}})

    def _create_snapshot(self):
        memory = self.store.load_memory()
        data = self.reader.read_modlist_with_memory(memory)
        snap = self.snapshots.create_snapshot(data)
        return snap

    # ==================== Backups (database + nemesis) ====================
    def _backups_dir(self):
        d = self.store.store_dir / "backups"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _list_backups(self, query=None):
        """Lista respaldos. type=modlist o type=nemesis para filtrar."""
        btype = (query or {}).get("type", "modlist")
        prefix = f"backup_{btype}_"
        backups_dir = self._backups_dir()
        out = []
        for f in sorted(backups_dir.glob(f"{prefix}*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                out.append({
                    "file": f.name,
                    "type": btype,
                    "created_at": data.get("created_at", ""),
                    "profile": data.get("profile", ""),
                    "stats": data.get("stats", {}),
                    "mods_count": data.get("mods_count", 0),
                    "size": f.stat().st_size,
                })
            except Exception:
                continue
        return (HTTPStatus.OK, {"ok": True, "data": out})

    def _create_backup(self, body=None, query=None):
        """Crea un respaldo. type=modlist o type=nemesis.
        Para modlist, incluye tambien memory.json (comentarios 2, categorias editadas, etc)."""
        btype = (query or {}).get("type", "modlist")
        try:
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            # Formato legible: 2026-08-07_17-27-47
            safe_ts = ts.replace("T", " ").replace(":", "-")
            filename = f"backup_{btype}_{safe_ts}.json"
            path = self._backups_dir() / filename
            c = 1
            while path.exists():
                filename = f"backup_{btype}_{safe_ts}_{c}.json"
                path = self._backups_dir() / filename
                c += 1
            if btype == "nemesis":
                nemesis = self.store.load_nemesis()
                backup = {
                    "created_at": ts,
                    "profile": self.profile_dir.name,
                    "type": "nemesis",
                    "nemesis": nemesis,
                }
            else:
                db = self.reader._load_database() or {"mods": []}
                memory = self.store.load_memory()
                mods = db.get("mods", [])
                active = sum(1 for m in mods if m.get("active") and not m.get("is_separator"))
                seps = sum(1 for m in mods if m.get("is_separator"))
                backup = {
                    "created_at": ts,
                    "profile": self.profile_dir.name,
                    "type": "modlist",
                    "database": db,
                    "memory": memory,
                    "mods_count": len(mods) - seps,
                    "stats": {"total": len(mods), "active": active, "separators": seps},
                }
            path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
            return (HTTPStatus.OK, {"ok": True, "data": {"file": filename, "created_at": ts, "type": btype, "path": str(path)}})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _get_backup(self, path):
        filename = urllib.parse.unquote(path[len("/api/backups/"):])
        if "/" in filename or "\\" in filename or ".." in filename:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "filename invalido"})
        backup_path = self._backups_dir() / filename
        if not backup_path.exists():
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "backup no encontrado"})
        try:
            data = json.loads(backup_path.read_text(encoding="utf-8"))
            return (HTTPStatus.OK, {"ok": True, "data": data})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _restore_backup(self, path, body=None):
        filename = urllib.parse.unquote(path[len("/api/backups/"):])
        if "/" in filename or "\\" in filename or ".." in filename:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "filename invalido"})
        backup_path = self._backups_dir() / filename
        if not backup_path.exists():
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "backup no encontrado"})
        try:
            backup = json.loads(backup_path.read_text(encoding="utf-8"))
            btype = backup.get("type", "modlist")
            # Parsear opciones del body
            restore_memory = True
            restore_database = True
            if body:
                try:
                    opts = json.loads(body.decode("utf-8"))
                    restore_memory = opts.get("restore_memory", True)
                    restore_database = opts.get("restore_database", True)
                except Exception:
                    pass
            if btype == "nemesis":
                nemesis = backup.get("nemesis", {})
                self.store.save_nemesis(nemesis)
            else:
                if restore_database:
                    db = backup.get("database", {})
                    self.reader._save_database(db)
                if restore_memory and backup.get("memory"):
                    self.store.save_memory(backup["memory"])
            return (HTTPStatus.OK, {"ok": True, "data": {"restored": filename, "type": btype}})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _delete_backup(self, path):
        filename = urllib.parse.unquote(path[len("/api/backups/"):])
        if "/" in filename or "\\" in filename or ".." in filename:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "filename invalido"})
        backup_path = self._backups_dir() / filename
        if backup_path.exists():
            backup_path.unlink()
            return (HTTPStatus.OK, {"ok": True})
        return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "backup no encontrado"})

    def _restore_from_json(self, body):
        """Restaura database.json (y opcionalmente memory.json) desde un JSON externo."""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            db = payload.get("database", payload)
            if not db.get("mods"):
                return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido: falta mods"})
            restore_memory = payload.get("restore_memory", True)
            db["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            self.reader._save_database(db)
            if restore_memory and payload.get("memory"):
                self.store.save_memory(payload["memory"])
            return (HTTPStatus.OK, {"ok": True, "data": {"mods": len(db["mods"])}})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    def _export(self, query):
        fmt = query.get("format", "text")
        memory = self.store.load_memory()
        data = self.reader.read_modlist_with_memory(memory)
        if fmt == "csv":
            return (HTTPStatus.OK, {"ok": True, "data": self.loll.export_modlist_csv(data["mods"]), "format": "csv"})
        return (HTTPStatus.OK, {"ok": True, "data": self.loll.export_modlist_text(data["mods"]), "format": "text"})

    def _import_text(self, body):
        try: payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
        mods = self.loll.import_modlist_text(payload.get("text",""))
        return (HTTPStatus.OK, {"ok": True, "data": mods})

    def _import_url(self, body):
        try: payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
        url = payload.get("url","").strip()
        if not url:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Falta url"})
        try:
            mods = self.loll.import_from_loll_url(url)
            return (HTTPStatus.OK, {"ok": True, "data": mods})
        except Exception as e:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(e)})

    def _get_nemesis(self):
        detected = self.nemesis_detector.detect_animation_mods()
        stored = self.store.load_nemesis()
        return (HTTPStatus.OK, {"ok": True, "data": {"detected": detected, "stored": stored, "images": self.store.list_images()}})

    def _upload_nemesis_image(self, body):
        try: payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
        filename = payload.get("filename", "capture.png")
        b64 = payload.get("data_base64", "")
        if not b64:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Falta data_base64"})
        try: data = base64.b64decode(b64)
        except Exception: return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "base64 invalido"})
        path = self.store.save_image(filename, data)
        return (HTTPStatus.OK, {"ok": True, "data": {"filename": path.name, "path": str(path)}})

    def _serve_nemesis_image(self, path):
        filename = urllib.parse.unquote(path[len("/api/nemesis/image/"):])
        if "/" in filename or "\\" in filename or ".." in filename:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "filename invalido"})
        img_path = self.store.images_dir() / filename
        if not img_path.exists():
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "imagen no encontrada"})
        data = img_path.read_bytes()
        ext = img_path.suffix.lower()
        ctype = {".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",
                 ".webp":"image/webp",".gif":"image/gif"}.get(ext, "application/octet-stream")
        return (HTTPStatus.OK, {"_binary": data, "_content_type": ctype})


# ==================== Plugin principal ====================

class ModlistManager(mobase.IPluginTool if mobase else object):
    """Plugin tool que abre una interfaz web para gestionar la lista de mods."""

    def __init__(self):
        mobase.IPluginTool.__init__(self)
        self._organizer = None
        self._server = None
        self._server_thread = None
        self._logger = None
        self._translations = {}
        self._language = "en"
        self._server_port = None
        self._debug_log_path = None
        self._debug_log_date = None
        # Heartbeat para auto-shutdown
        self._last_heartbeat = None
        self._heartbeat_monitor_thread = None
        self._heartbeat_stop = threading.Event()

    # ==================== Settings helpers ====================
    def _get_setting(self, key, default=None):
        if self._organizer is None:
            return default
        try:
            val = self._organizer.pluginSetting(self.name(), key)
            return val if val is not None else default
        except Exception:
            return default

    def _get_bool_setting(self, key, default=False):
        val = self._get_setting(key, default)
        if isinstance(val, bool): return val
        if isinstance(val, str): return val.strip().lower() in ('true','1','yes','on')
        if isinstance(val, (int, float)): return bool(val)
        return default

    def _get_int_setting(self, key, default=0):
        val = self._get_setting(key, default)
        try: return int(val)
        except (ValueError, TypeError): return default

    def _get_string_setting(self, key, default=''):
        val = self._get_setting(key, default)
        return str(val) if val is not None else default

    # ==================== Debug log (con rotacion diaria) ====================
    def _debug_log(self, message):
        if not self._get_bool_setting('debug_enabled', False):
            # Debug desactivado: limpiar archivo residual si existe y esta vacio
            # (puede quedar de una sesion anterior con debug activado)
            if self._debug_log_path is None and self._organizer is not None:
                try:
                    p = Path(self._organizer.basePath()) / "modlist_manager_debug.txt"
                    if p.exists() and p.stat().st_size == 0:
                        p.unlink()
                except Exception:
                    pass
            return
        try:
            if self._debug_log_path is None:
                if self._organizer is not None:
                    self._debug_log_path = Path(self._organizer.basePath()) / "modlist_manager_debug.txt"
                else:
                    return
            rotation = self._get_string_setting('debug_rotation', 'daily').lower().strip()
            if rotation == 'daily':
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                if self._debug_log_date is None:
                    if self._debug_log_path.exists():
                        try:
                            with open(self._debug_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                                first_line = f.readline()
                            m = re.match(r'\[(\d{4}-\d{2}-\d{2})', first_line)
                            if m:
                                self._debug_log_date = m.group(1)
                            else:
                                self._debug_log_date = today
                        except Exception:
                            self._debug_log_date = today
                    else:
                        self._debug_log_date = today
                if today != self._debug_log_date:
                    try:
                        rotated = self._debug_log_path.parent / f"modlist_manager_debug_{self._debug_log_date}.txt"
                        c = 1
                        while rotated.exists():
                            rotated = self._debug_log_path.parent / f"modlist_manager_debug_{self._debug_log_date}_{c}.txt"
                            c += 1
                        self._debug_log_path.rename(rotated)
                    except Exception:
                        pass
                    self._debug_log_date = today
            elif rotation == 'never':
                if self._debug_log_date is None:
                    try:
                        open(self._debug_log_path, 'w', encoding='utf-8').close()
                    except Exception:
                        pass
                    self._debug_log_date = 'session-active'
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with open(self._debug_log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] {message}\n")
        except Exception:
            pass

    # ==================== Lifecycle ====================
    def init(self, organizer):
        self._organizer = organizer
        self._extension = None  # Extension opcional (modlist_manager_traduction.py)
        self._debug_log("=" * 60)
        self._debug_log("[INIT] Modlist Manager init() llamado")
        self._debug_log(f"[INIT] basePath() = {organizer.basePath() if organizer else 'None'}")
        self._debug_log(f"[INIT] cwd() = {Path.cwd()}")
        self._load_translations()
        self._debug_log(f"[INIT] Idioma: {self._language} ({len(self._translations)} traducciones)")
        # Cargar extension opcional si existe
        self._load_extension()
        # Por defecto el servidor NO arranca al iniciar MO2.
        # Solo arranca cuando el usuario abre el plugin (display).
        # Si start_on_mo2_startup esta activado, arrancar el servidor ahora.
        if self._get_bool_setting('start_on_mo2_startup', False):
            self._debug_log("[INIT] start_on_mo2_startup=True — arrancando servidor")
            self._start_server()
            self._start_heartbeat_monitor()
            if self._get_bool_setting('auto_open_browser', False):
                import time
                time.sleep(0.5)
                if self._server_port:
                    try: webbrowser.open(f"http://127.0.0.1:{self._server_port}")
                    except Exception: pass
        else:
            self._debug_log("[INIT] start_on_mo2_startup=False — servidor se arrancara on-demand al abrir el plugin")
        return True

    def _load_extension(self):
        """Detecta y carga la extension modlist_manager_traduction.py si existe.

        Busca en:
        1. La misma carpeta que este plugin (directorio de plugins de MO2)
        2. El directorio base de MO2 / plugins

        Si encuentra el archivo, lo importa y almacena el modulo en
        self._extension. Si no existe, self._extension queda en None y el
        plugin funciona exactamente igual que sin extension.
        """
        import importlib.util
        candidates = []
        # Buscar en el mismo directorio que este archivo
        try:
            this_dir = Path(__file__).parent
            candidates.append(this_dir / "modlist_manager_traduction.py")
        except Exception:
            pass
        # Buscar en <MO2>/plugins/
        if self._organizer is not None:
            try:
                plugins_dir = Path(self._organizer.basePath()) / "plugins"
                candidates.append(plugins_dir / "modlist_manager_traduction.py")
            except Exception:
                pass
        for ext_path in candidates:
            if ext_path.exists() and ext_path.is_file():
                try:
                    self._debug_log(f"[EXT] Cargando extension: {ext_path}")
                    spec = importlib.util.spec_from_file_location("modlist_manager_traduction", str(ext_path))
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    self._extension = mod
                    self._debug_log("[EXT] Extension cargada correctamente")
                    return
                except Exception as e:
                    self._debug_log(f"[EXT] Error cargando extension: {e}")
                    self._extension = None
                    return
        self._debug_log("[EXT] No se encontro modlist_manager_traduction.py — funcionando sin extension")
        self._extension = None

    def _start_heartbeat_monitor(self):
        """Inicia un hilo que monitorea el heartbeat y apaga el servidor tras 60s sin actividad."""
        if self._heartbeat_monitor_thread is not None:
            return  # ya corriendo
        self._heartbeat_stop.clear()
        self._last_heartbeat = datetime.datetime.now()
        def monitor():
            timeout = 300  # 5 minutos sin actividad
            check_interval = 10  # verificar cada 10 segundos
            while not self._heartbeat_stop.is_set():
                self._heartbeat_stop.wait(check_interval)
                if self._heartbeat_stop.is_set():
                    break
                if self._last_heartbeat is None:
                    continue
                elapsed = (datetime.datetime.now() - self._last_heartbeat).total_seconds()
                if elapsed > timeout:
                    self._debug_log(f"[HEARTBEAT] No heartbeat for {elapsed:.0f}s — shutting down server")
                    self._shutdown_server()
                    break
            self._debug_log("[HEARTBEAT] Monitor thread exiting")
        t = threading.Thread(target=monitor, daemon=True, name="ModlistManager-Heartbeat")
        t.start()
        self._heartbeat_monitor_thread = t

    def _shutdown_server(self):
        """Apaga el servidor web."""
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception as e:
                self._debug_log(f"[SERVER] Error al apagar: {e}")
            self._server = None
            self._server_port = None
            self._debug_log("[SERVER] Servidor apagado por inactividad")

    def name(self):
        return "Modlist Manager"

    def localizedName(self):
        return self._tr("Modlist Manager")

    def author(self):
        return "Krou705"

    def description(self):
        return self._tr("Web UI to manage the MO2 mod list: priorities, separators, categories, comments, links. Import/Export from loadorderlibrary.com, list editor, Nemesis/Pandora/Custom panel, multi-language, snapshots.")

    def version(self):
        return mobase.VersionInfo(3, 2, 0)

    def isActive(self):
        return self._organizer is not None

    def settings(self):
        try:
            return [
                mobase.PluginSetting("auto_open_browser",
                    "Automatically open the browser when the plugin starts", True),
                mobase.PluginSetting("start_on_mo2_startup",
                    "Start the web server when MO2 starts (if false, server starts on-demand when you open the plugin)", False),
                mobase.PluginSetting("web_server_port",
                    "Web server port (0 = auto-select from 8765-8775)", 0),
                mobase.PluginSetting("debug_enabled",
                    "Enable debug logging to modlist_manager_debug.txt", False),
                mobase.PluginSetting("debug_rotation",
                    "Debug log rotation: 'daily' (rename old log each day) | 'never' (overwrite on MO2 start) | 'unlimited' (append forever)", "daily"),
            ]
        except Exception:
            return []

    # ==================== IPluginTool ====================
    def displayName(self):
        return self._tr("Modlist Manager")

    def tooltip(self):
        return self._tr("Open the web mod list manager")

    def icon(self):
        """
        Icono vectorial generado en runtime (sin archivos externos).
        Compatible PyQt5 y PyQt6.
        Para personalizar: cambiar ICON_TEXT e ICON_BG_COLOR abajo.
        """
        # === Configuracion del icono (edita estas 2 lineas) ===
        ICON_TEXT = " M "          # texto a mostrar
        ICON_BG_COLOR = "#0982f3" # color de fondo en hex (marron)
        # ========================================================

        try:
            from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon, QFont
            from PyQt5.QtCore import QRect, Qt
            _Antialiasing = QPainter.Antialiasing
            _NoPen        = Qt.NoPen
            _AlignCenter  = Qt.AlignCenter
        except ImportError:
            try:
                from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon, QFont
                from PyQt6.QtCore import QRect, Qt
                _Antialiasing = QPainter.RenderHint.Antialiasing
                _NoPen        = Qt.PenStyle.NoPen
                _AlignCenter  = Qt.AlignmentFlag.AlignCenter
            except ImportError:
                return None

        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        p = QPainter(pix)
        p.setRenderHint(_Antialiasing)
        p.setBrush(QColor(ICON_BG_COLOR))
        p.setPen(_NoPen)
        p.drawRoundedRect(2, 2, 28, 28, 6, 6)
        p.setPen(QColor("#ffffff"))
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        p.drawText(QRect(2, 2, 28, 28), _AlignCenter, ICON_TEXT)
        p.end()
        return QIcon(pix)

    def setParentWidget(self, widget):
        pass

    def display(self):
        self._debug_log("[DISPLAY] display() llamado")
        try:
            if self._server is None:
                self._start_server()
                self._start_heartbeat_monitor()
            # Reset heartbeat para dar tiempo al navegador a cargar
            self._last_heartbeat = datetime.datetime.now()
            if self._server_port is not None:
                url = f"http://127.0.0.1:{self._server_port}/"
                self._debug_log(f"[DISPLAY] Abriendo navegador: {url}")
                try: webbrowser.open(url)
                except Exception as e:
                    self._debug_log(f"[DISPLAY] No se pudo abrir el navegador: {e}")
            else:
                self._debug_log("[DISPLAY] No se pudo arrancar el servidor")
        except Exception as e:
            self._debug_log(f"[DISPLAY] EXCEPTION: {e}")
            import traceback
            self._debug_log(traceback.format_exc())

    def run(self):
        self.display()

    def stop(self):
        # Detener monitor de heartbeat
        self._heartbeat_stop.set()
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None

    # ==================== i18n ====================
    def _tr(self, text):
        if self._translations and text in self._translations:
            return self._translations[text]
        return text

    def _detect_language(self):
        if self._organizer is not None:
            for sn in ['language','locale','Settings\\language']:
                try:
                    val = self._organizer.setting(sn)
                    if val and isinstance(val, str):
                        lang = val.lower()[:2]
                        if len(lang) == 2 and lang.isalpha():
                            return lang
                except Exception:
                    continue
        try:
            if self._organizer is not None:
                ini_path = Path(self._organizer.basePath()) / "ModOrganizer.ini"
                if ini_path.exists():
                    cfg = configparser.ConfigParser()
                    cfg.read(ini_path, encoding='utf-8')
                    for sec in ['Settings','General']:
                        if sec in cfg:
                            for k in ['language','locale']:
                                if k in cfg[sec]:
                                    lang = cfg[sec][k].strip().lower()[:2]
                                    if len(lang) == 2 and lang.isalpha():
                                        return lang
        except Exception:
            pass
        try:
            import locale
            loc = locale.getdefaultlocale()[0] or ''
            if loc:
                lang = loc.split('_')[0].lower()
                if len(lang) == 2 and lang.isalpha():
                    return lang
        except Exception:
            pass
        return "en"

    def _find_translation_file(self, lang):
        filename = f"modlist_manager_{lang}.json"
        candidates = []
        try: candidates.append(Path.cwd() / "translations" / filename)
        except Exception: pass
        try:
            if self._organizer: candidates.append(Path(self._organizer.basePath()) / "translations" / filename)
        except Exception: pass
        try: candidates.append(Path(__file__).resolve().parent / "translations" / filename)
        except Exception: pass
        try: candidates.append(Path(__file__).resolve().parent.parent / "translations" / filename)
        except Exception: pass
        for c in candidates:
            try:
                if c.exists() and c.stat().st_size > 2:
                    return c
            except Exception:
                continue
        return None

    def _load_translations(self):
        lang = self._detect_language()
        tr_file = self._find_translation_file(lang)
        if tr_file is None and lang != "en":
            tr_file = self._find_translation_file("en")
        if tr_file is None:
            self._translations = self._builtin_strings()
            self._language = "en"
            return
        try:
            with open(tr_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged = self._builtin_strings()
                merged.update(data)
                self._translations = merged
                self._language = lang
        except Exception:
            self._translations = self._builtin_strings()
            self._language = "en"

    @staticmethod
    def _builtin_strings():
        return {
            "Modlist Manager": "Modlist Manager",
            "Open the web mod list manager": "Open the web mod list manager",
        }

    # ==================== Server ====================
    def _profile_dir(self):
        try:
            if self._organizer is not None:
                prof = self._organizer.profile()
                if prof is not None:
                    return Path(prof.absolutePath())
        except Exception:
            pass
        try:
            base = Path(self._organizer.basePath()) if self._organizer else Path.cwd()
        except Exception:
            base = Path.cwd()
        return base / "profiles" / "Default"

    def _start_server(self):
        if self._server is not None:
            self._debug_log("[SERVER] Ya corriendo, reusando")
            return
        self._debug_log("[SERVER] _start_server() iniciado")
        try:
            base_path = Path(self._organizer.basePath()) if self._organizer else Path.cwd()
        except Exception:
            base_path = Path.cwd()
        profile_dir = self._profile_dir()
        self._debug_log(f"[SERVER] base_path = {base_path}")
        self._debug_log(f"[SERVER] profile_dir = {profile_dir}")

        try:
            reader = ModlistReader(base_path, profile_dir, self._organizer, self._logger)
            store = Store(profile_dir / "ModlistManager")
        except Exception as e:
            self._debug_log(f"[SERVER] Error creando reader/store: {e}")
            import traceback
            self._debug_log(traceback.format_exc())
            return

        try:
            api = Api(reader=reader, store=store, profile_dir=profile_dir,
                      base_path=base_path, translations_dir=None,
                      organizer=self._organizer, logger=self._logger)
            # Pasar referencia de la extension al API si esta cargada
            api._extension = self._extension
        except Exception as e:
            self._debug_log(f"[SERVER] Error creando API: {e}")
            import traceback
            self._debug_log(traceback.format_exc())
            return

        plugin_self = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *args): pass

            def do_GET(self): self._handle("GET")
            def do_POST(self): self._handle("POST")
            def do_DELETE(self): self._handle("DELETE")

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def _handle(self, method):
                # Actualizar heartbeat en cada request
                if hasattr(plugin_self, '_last_heartbeat'):
                    plugin_self._last_heartbeat = datetime.datetime.now()
                try:
                    parsed = urllib.parse.urlparse(self.path)
                    path = urllib.parse.unquote(parsed.path)
                    query = dict(urllib.parse.parse_qsl(parsed.query))
                    length = int(self.headers.get("Content-Length", 0) or 0)
                    body = self.rfile.read(length) if length > 0 else b""

                    if path in ("/", "/index.html", "") and method == "GET":
                        self.send_response(200)
                        self.send_header("Content-type", "text/html; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        html = HTML_CONTENT
                        # Inyectar contenido de la extension si existe
                        plugin_self._debug_log(f"[EXT] Sirviendo HTML, _extension is None: {plugin_self._extension is None}")
                        if plugin_self._extension is not None:
                            try:
                                ext = plugin_self._extension
                                plugin_self._debug_log(f"[EXT] get_tab_html: {hasattr(ext, 'get_tab_html')}")
                                plugin_self._debug_log(f"[EXT] get_panel_html: {hasattr(ext, 'get_panel_html')}")
                                plugin_self._debug_log(f"[EXT] get_css: {hasattr(ext, 'get_css')}")
                                plugin_self._debug_log(f"[EXT] get_js: {hasattr(ext, 'get_js')}")
                                if hasattr(ext, 'get_tab_html'):
                                    tab_html = ext.get_tab_html()
                                    html = html.replace("<!--EXTENSION_TAB-->", tab_html)
                                    plugin_self._debug_log(f"[EXT] Tab HTML inyectado ({len(tab_html)} chars)")
                                if hasattr(ext, 'get_panel_html'):
                                    panel_html = ext.get_panel_html()
                                    html = html.replace("<!--EXTENSION_PANEL-->", panel_html)
                                    plugin_self._debug_log(f"[EXT] Panel HTML inyectado ({len(panel_html)} chars)")
                                if hasattr(ext, 'get_css'):
                                    css = ext.get_css()
                                    html = html.replace("/*EXTENSION_CSS*/", css)
                                    plugin_self._debug_log(f"[EXT] CSS inyectado ({len(css)} chars)")
                                if hasattr(ext, 'get_js'):
                                    js = ext.get_js()
                                    html = html.replace("//EXTENSION_JS", js)
                                    plugin_self._debug_log(f"[EXT] JS inyectado ({len(js)} chars)")
                                # Verificar que los marcadores fueron reemplazados
                                remaining = []
                                if "<!--EXTENSION_TAB-->" in html: remaining.append("TAB")
                                if "<!--EXTENSION_PANEL-->" in html: remaining.append("PANEL")
                                if "/*EXTENSION_CSS*/" in html: remaining.append("CSS")
                                if "//EXTENSION_JS" in html: remaining.append("JS")
                                if remaining:
                                    plugin_self._debug_log(f"[EXT] WARNING: Marcadores no reemplazados: {remaining}")
                                else:
                                    plugin_self._debug_log("[EXT] Todos los marcadores reemplazados correctamente")
                            except Exception as e:
                                plugin_self._debug_log(f"[EXT] Error inyectando HTML: {e}")
                                import traceback
                                plugin_self._debug_log(traceback.format_exc())
                        self.wfile.write(html.encode("utf-8"))
                        plugin_self._debug_log(f"[EXT] HTML servido ({len(html)} bytes)")
                        return

                    if path == "/i18n.json" and method == "GET":
                        self.send_response(200)
                        self.send_header("Content-type", "application/json; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        # Fusionar traducciones del plugin principal con las de la extension
                        merged_strings = dict(plugin_self._translations)
                        if plugin_self._extension is not None:
                            try:
                                ext_strings = plugin_self._extension.get_translations(plugin_self._language, plugin_self._organizer)
                                if isinstance(ext_strings, dict):
                                    merged_strings.update(ext_strings)
                            except Exception as e:
                                plugin_self._debug_log(f"[EXT] Error cargando traducciones: {e}")
                        self.wfile.write(json.dumps({"language": plugin_self._language,
                            "strings": merged_strings}, ensure_ascii=False).encode("utf-8"))
                        return

                    if path.startswith("/api/"):
                        status, payload = api.handle(method, path, body, query)
                        if isinstance(payload, dict) and "_binary" in payload:
                            data = payload["_binary"]
                            ctype = payload.get("_content_type", "application/octet-stream")
                            self.send_response(status)
                            self.send_header("Content-Type", ctype)
                            self.send_header("Content-Length", str(len(data)))
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.end_headers()
                            self.wfile.write(data)
                            return
                        body_out = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                        self.send_response(status)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(body_out)))
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(body_out)
                        return

                    self.send_response(404)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"404 Not Found")
                except BrokenPipeError:
                    pass
                except ConnectionError:
                    pass  # conexion cerrada por el cliente, normal
                except Exception as e:
                    # Silenciar errores de conexion (WinError 10053, etc)
                    err_str = str(e)
                    if "10053" in err_str or "10054" in err_str or "Connection" in err_str:
                        pass
                    else:
                        try: plugin_self._debug_log(f"[HTTP] Error: {e}")
                        except Exception: pass
                    try:
                        self.send_response(500)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
                    except Exception:
                        pass

        # Puerto: 0 = auto (8765-8775)
        configured_port = self._get_int_setting('web_server_port', 0)
        chosen_port = None
        if configured_port and 1 <= configured_port <= 65535:
            try:
                class RS(socketserver.ThreadingTCPServer):
                    allow_reuse_address = True
                    daemon_threads = True
                httpd = RS(("127.0.0.1", configured_port), Handler)
                chosen_port = configured_port
                self._debug_log(f"[SERVER] Usando puerto configurado {configured_port}")
            except OSError as e:
                self._debug_log(f"[SERVER] Puerto configurado {configured_port} ocupado: {e}")
        if chosen_port is None:
            for port in range(8765, 8776):
                try:
                    class RS(socketserver.ThreadingTCPServer):
                        allow_reuse_address = True
                        daemon_threads = True
                    httpd = RS(("127.0.0.1", port), Handler)
                    chosen_port = port
                    break
                except OSError as e:
                    continue
        if chosen_port is None:
            self._debug_log("[SERVER] ERROR: No se encontro puerto libre 8765-8775")
            return

        self._server = httpd
        self._server_port = chosen_port

        def run_server():
            try: httpd.serve_forever()
            except Exception as e: plugin_self._debug_log(f"[SERVER] serve_forever exception: {e}")

        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        self._server_thread = t
        self._debug_log(f"[SERVER] Servidor arrancado OK en puerto {chosen_port}")
        self._debug_log(f"[SERVER] URL: http://127.0.0.1:{chosen_port}/")


def createPlugin():
    return ModlistManager()
