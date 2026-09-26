# -*- coding: utf-8 -*-
"""
Modlist Manager - Extension de Traducciones
===========================================

Extension opcional para el plugin Modlist Manager que anade una pestaña
de gestion de traducciones de mods.

Esta extension se carga automaticamente si el archivo
modlist_manager_traduction.py esta presente en la carpeta de plugins de MO2.
Si no esta, el plugin principal funciona exactamente igual que sin extension.

Caracteristicas:
  - Nueva pestana "Traducciones" con 2 sub-pestanas:
    1. Lista: tabla de mods con tipo de traduccion (T/D/M/S)
    2. Respaldos: crear/restaurar/eliminar respaldos de datos de traduccion
  - Clasificacion de mods por tipo de traduccion:
    T = Traduccion (azul)
    D = DSD (verde)
    M = MCM (naranja)
    S = Script (gris)
  - Campo "A que mod traduce" con autocompletado
  - Comentarios de traduccion almacenados en translation_data.json
  - Respaldo/restauracion de datos de traduccion

Autor: Krou705
Version: 3.0.0
"""

import json
import os
import datetime
from pathlib import Path
from http import HTTPStatus


# ==================== Traducciones de la extension ====================

def _find_ext_translation(language, organizer=None):
    """Busca el archivo de traduccion de la extension en varias ubicaciones."""
    filename = f"modlist_manager_traduction_{language}.json"
    candidates = []
    # 1. Junto al .py de la extension
    try:
        p = Path(__file__).resolve().parent / filename
        candidates.append(p)
    except Exception:
        pass
    # 2. <plugin_dir>/translations/
    try:
        p = Path(__file__).resolve().parent / "translations" / filename
        candidates.append(p)
    except Exception:
        pass
    # 3. <cwd>/translations/
    try:
        p = Path.cwd() / "translations" / filename
        candidates.append(p)
    except Exception:
        pass
    # 4. <MO2_base>/translations/
    if organizer is not None:
        try:
            p = Path(organizer.basePath()) / "translations" / filename
            candidates.append(p)
        except Exception:
            pass
    for c in candidates:
        try:
            if c.exists() and c.stat().st_size > 2:
                return c
            # Debug: log si no existe
        except Exception:
            continue
    return None

def get_translations(language, organizer=None):
    """Devuelve las traducciones de la extension para el idioma dado.

    Busca modlist_manager_traduction_<language>.json en varias ubicaciones.
    Si no existe, usa 'en' como fallback (antes era 'es').
    Si tampoco existe, devuelve un dict vacio.
    """
    for lang in [language, "en"]:
        p = _find_ext_translation(lang, organizer)
        if p is not None:
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


# ==================== Almacenamiento ====================

def _tracker_dir(ctx):
    """Directorio 'Translations Tracker' dentro de la carpeta del plugin principal."""
    return Path(ctx["store_dir"]) / "Translations Tracker"

def _data_path(ctx):
    """Ruta al archivo translations.json dentro de Translations Tracker."""
    return _tracker_dir(ctx) / "translations.json"

def _backups_dir(ctx):
    """Directorio de respaldos dentro de Translations Tracker."""
    return _tracker_dir(ctx) / "backups"

def _load_data(ctx):
    """Carga los datos de traduccion desde translation_data.json."""
    p = _data_path(ctx)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_data(ctx, data):
    """Guarda los datos de traduccion en translation_data.json."""
    p = _data_path(ctx)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(p))


# ==================== Deteccion automatica ====================

# Palabras clave de idioma en el nombre del mod (con variantes de sufijo)
LANG_SUFFIXES = [
    " - spanish", " - espanol", " - español", " - castellano",
    " - traducion spanish", " - traduccion spanish", " - traduccion español",
    " - traducción spanish", " - traducción español",
    " - italian", " - italiano", " - french", " - francais", " - german",
    " - deutsch", " - russian", " - portuguese", " - polish", " - japanese",
    " - chinese", " - korean", " - latam", " - latin",
    " spanish", " espanol", " español", " castellano",
    " traducion spanish", " traduccion spanish",
    " traducción spanish", " traducción español",
    " italian", " italiano", " french", " german",
    " russian", " portuguese", " polish", " japanese",
    " -es", " -en", " -it", " -fr", " -de", " -ru", " -pt", " -pl",
    " _es", " _en", " _it", " _fr",
]

def _guess_original_mod(display_name):
    """Intenta adivinar el nombre del mod original eliminando sufijos de idioma."""
    name = display_name.strip()
    name_lower = name.lower()
    for suffix in sorted(LANG_SUFFIXES, key=len, reverse=True):
        if name_lower.endswith(suffix):
            return name[:len(name)-len(suffix)].strip()
    return ""
LANG_KEYWORDS = [
    "spanish", "español", "espanol", "castellano", " es ", "-es", "_es",
    " italian", "italiano", " it ", "-it", "_it",
    " russian", "russky", " ru ", "-ru", "_ru",
    " french", "francais", "française", " fr ", "-fr", "_fr",
    " german", "deutsch", " de ", "-de", "_de",
    " portuguese", "portugues", " pt ", "-pt", "_pt", "br ",
    " polish", "polski", " pl ", "-pl", "_pl",
    " japanese", " jp ", "-jp", "_jp",
    " chinese", " cn ", "-cn", "_cn",
    " korean", " kr ", "-kr", "_kr",
    "latam", "latin",
]

def _detect_translations(ctx):
    """Detecta mods que posiblemente sean traducciones.

    Criterios:
    1. Nombre del mod contiene palabras clave de idioma
    2. Estructura de carpetas:
       - DSD: SKSE/Plugins/DynamicStringDistributor/
       - SKSE: SKSE/Plugins/translations/
       - ESP: tiene .esp/.esm (reemplazo)
       - Script: tiene scripts/ pero no .esp
       - MCM: tiene interface/ o mcm/ con .swf
    """
    mods_dir = Path(ctx["mods_dir"])
    reader = ctx.get("reader")
    if reader is None:
        return []
    # Obtener lista de mods desde el reader
    try:
        db = reader._load_database()
    except Exception:
        return []
    if db is None:
        return []
    db_mods = db.get("mods", [])
    results = []
    for mod in db_mods:
        if mod.get("is_separator") or mod.get("deleted_from_disk"):
            continue
        mod_name = mod["name"]
        mod_dir = mods_dir / mod_name
        if not mod_dir.exists():
            continue
        display_name = mod.get("display_name", mod_name)
        name_lower = (display_name + " " + mod_name).lower()
        # 1. Verificar si el nombre tiene palabras clave de idioma
        has_lang = any(kw in name_lower for kw in LANG_KEYWORDS)
        if not has_lang:
            continue  # No es traduccion probable
        # 2. Escanear estructura de carpetas
        has_esp = False
        has_esm = False
        has_scripts = False
        has_dsd = False
        has_skse_translations = False
        has_mcm = False
        has_mcm_config = False
        has_interface_translations = False
        has_other = False
        esp_files = []
        mcm_config_files = []
        interface_trans_files = []
        try:
            for f in mod_dir.rglob("*"):
                if f.is_file():
                    rel = str(f.relative_to(mod_dir)).lower().replace("\\", "/")
                    ext = f.suffix.lower()
                    fname_lower = f.name.lower()
                    if ext == ".esp":
                        has_esp = True
                        esp_files.append(f.name)
                    elif ext == ".esm":
                        has_esm = True
                        esp_files.append(f.name)
                    elif ext == ".swf" and ("interface" in rel or "mcm" in rel):
                        has_mcm = True
                    # DSD: SKSE/Plugins/DynamicStringDistributor/
                    if "skse/plugins/dynamicstringdistributor" in rel:
                        has_dsd = True
                    # SKSE translations: SKSE/Plugins/translations/
                    if "skse/plugins/translations" in rel:
                        has_skse_translations = True
                    # Scripts folder
                    if rel.startswith("scripts/") or "/scripts/" in rel:
                        if ext in (".pex",):
                            has_scripts = True
                    # MCM Config: MCM/Config/[modname]/config.json
                    if "mcm/config/" in rel and ext == ".json":
                        has_mcm_config = True
                        mcm_config_files.append(f.name)
                    # Interface translations: Interface/Translations/*.txt
                    # que NO sean _english.txt
                    if "interface/translations" in rel and ext == ".txt":
                        if "_english" not in fname_lower:
                            has_interface_translations = True
                            interface_trans_files.append(f.name)
                    # Interface tweenoptions (mods de interfaz)
                    if "interface/tweenoptions" in rel:
                        has_other = True
                    # Sound folder (mods de audio traduccion)
                    if rel.startswith("sound/") or "/sound/" in rel:
                        if ext in (".fuz", ".xwm", ".wav", ".lip"):
                            has_other = True
        except Exception:
            pass
        # 3. Determinar tipo de traduccion
        detected_type = None
        reason = ""
        if has_dsd:
            detected_type = "D"
            reason = "Carpeta DSD detectada (SKSE/Plugins/DynamicStringDistributor)"
        elif has_esp or has_esm:
            detected_type = "T"
            reason = f"Reemplaza ESP/ESM: {', '.join(esp_files[:3])}"
        elif has_skse_translations:
            detected_type = "O"
            reason = "SKSE/Plugins/translations detectado"
        elif has_scripts:
            detected_type = "S"
            reason = "Solo scripts (.pex) sin ESP/ESM"
        elif has_mcm or has_mcm_config or has_interface_translations:
            detected_type = "M"
            # Detallar la razon segun lo encontrado
            reasons = []
            if has_mcm:
                reasons.append(".swf en interface/mcm")
            if has_mcm_config:
                reasons.append(f"MCM/Config ({', '.join(mcm_config_files[:2])})")
            if has_interface_translations:
                reasons.append(f"Interface/Translations no-English ({', '.join(interface_trans_files[:2])})")
            reason = "MCM: " + " + ".join(reasons)
        elif has_other:
            detected_type = "OT"
            reason = "Otros: estructura de interfaz detectada (tweenoptions)"
        else:
            # Tiene palabra de idioma pero no estructura clara -> OT
            detected_type = "OT"
            reason = "Otros: nombre sugiere traduccion pero estructura no coincide con tipos conocidos"
        # Solo incluir si se detecto algo
        if detected_type or has_lang:
            guessed_original = _guess_original_mod(display_name)
            results.append({
                "mod_name": mod_name,
                "display_name": display_name,
                "guessed_original": guessed_original,
                "detected_type": detected_type,
                "reason": reason,
                "has_esp": has_esp,
                "has_esm": has_esm,
                "has_scripts": has_scripts,
                "has_dsd": has_dsd,
                "has_skse_translations": has_skse_translations,
                "has_mcm": has_mcm,
                "has_mcm_config": has_mcm_config,
                "has_interface_translations": has_interface_translations,
                "has_other": has_other,
            })
    return results


# ==================== API Handler ====================

def handle_api(path, method, body, ctx):
    """Maneja las peticiones API de la extension.

    Args:
        path: ruta relativa (sin /api/translation/)
        method: metodo HTTP (GET, POST, DELETE)
        body: cuerpo de la peticion (bytes)
        ctx: contexto con store_dir, mods_dir, reader, organizer

    Returns:
        (status_code, response_dict) o None si no se maneja
    """
    # GET /data - obtener todos los datos de traduccion
    if path == "data" and method == "GET":
        return (HTTPStatus.OK, {"ok": True, "data": _load_data(ctx)})

    # GET /detect - detectar traducciones automaticamente
    if path == "detect" and method == "GET":
        results = _detect_translations(ctx)
        return (HTTPStatus.OK, {"ok": True, "data": results})

    # POST /open_folder - abrir carpeta de un mod en el explorador
    if path == "open_folder" and method == "POST":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
        modname = payload.get("mod_name", "")
        if not modname:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "mod_name requerido"})
        mod_dir = Path(ctx["mods_dir"]) / modname
        if not mod_dir.exists():
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Carpeta no encontrada"})
        try:
            import subprocess
            import sys as _sys
            if _sys.platform == "win32":
                # Usar subprocess.Popen con explorer para traer la ventana al frente
                subprocess.Popen(["explorer", str(mod_dir)])
            elif _sys.platform == "darwin":
                subprocess.Popen(["open", str(mod_dir)])
            else:
                subprocess.Popen(["xdg-open", str(mod_dir)])
            return (HTTPStatus.OK, {"ok": True})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    # POST /apply_detected - aplicar traducciones detectadas (aceptadas)
    # NO sobrescribe mods que ya tienen tipo en la lista (la lista siempre gana)
    if path == "apply_detected" and method == "POST":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
        entries = payload.get("entries", [])
        if not isinstance(entries, list):
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "entries debe ser una lista"})
        data = _load_data(ctx)
        applied = 0
        skipped = 0
        for entry in entries:
            modname = entry.get("mod_name", "")
            ttype = entry.get("detected_type", "")
            if modname and ttype:
                # Si ya tiene tipo en la lista, NO sobrescribir (la lista siempre gana)
                existing = data.get(modname, {})
                if existing.get("translation_type"):
                    skipped += 1
                    continue
                data[modname] = {
                    "translation_type": ttype,
                    "translates_mod": existing.get("translates_mod", ""),
                    "translation_comment": existing.get("translation_comment", ""),
                }
                applied += 1
        _save_data(ctx, data)
        return (HTTPStatus.OK, {"ok": True, "data": {"applied": applied, "skipped": skipped}})

    # POST /data/<modname> - guardar datos de traduccion para un mod
    if path.startswith("data/") and method == "POST":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON invalido"})
        # El modname viene codificado en la URL
        import urllib.parse
        modname = urllib.parse.unquote(path[len("data/"):])
        if not modname:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Nombre de mod requerido"})
        data = _load_data(ctx)
        entry = {
            "translation_type": payload.get("translation_type", ""),
            "translates_mod": payload.get("translates_mod", ""),
            "translation_comment": payload.get("translation_comment", ""),
        }
        # Si todos los campos estan vacios, eliminar la entrada
        if not any(entry.values()):
            data.pop(modname, None)
        else:
            data[modname] = entry
        _save_data(ctx, data)
        return (HTTPStatus.OK, {"ok": True, "data": entry})

    # DELETE /data/<modname> - eliminar datos de traduccion de un mod
    if path.startswith("data/") and method == "DELETE":
        import urllib.parse
        modname = urllib.parse.unquote(path[len("data/"):])
        data = _load_data(ctx)
        if modname in data:
            del data[modname]
            _save_data(ctx, data)
            return (HTTPStatus.OK, {"ok": True})
        return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Mod no encontrado en datos de traduccion"})

    # GET /backups - listar respaldos
    if path == "backups" and method == "GET":
        d = _backups_dir(ctx)
        if not d.exists():
            return (HTTPStatus.OK, {"ok": True, "data": []})
        result = []
        for f in sorted(d.glob("*.json"), reverse=True):
            try:
                bdata = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "filename": f.name,
                    "entries": len(bdata.get("entries", {})),
                    "created_at": bdata.get("created_at", ""),
                    "label": bdata.get("label", f.stem),
                })
            except Exception:
                pass
        return (HTTPStatus.OK, {"ok": True, "data": result})

    # POST /backups - crear respaldo
    if path == "backups" and method == "POST":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}
        label = payload.get("label", "")
        d = _backups_dir(ctx)
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"translation_{ts}.json"
        data = _load_data(ctx)
        bdata = {
            "type": "translation",
            "label": label or f"translation_{ts}",
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "entries": data,
        }
        (d / fname).write_text(json.dumps(bdata, ensure_ascii=False, indent=2), encoding="utf-8")
        return (HTTPStatus.OK, {"ok": True, "data": {"filename": fname, "entries": len(data)}})

    # GET /backups/<filename> - ver contenido de un respaldo
    if path.startswith("backups/") and method == "GET":
        import urllib.parse
        filename = urllib.parse.unquote(path[len("backups/"):])
        if "/" in filename or "\\" in filename or ".." in filename:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Filename invalido"})
        p = _backups_dir(ctx) / filename
        if not p.exists():
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Respaldo no encontrado"})
        try:
            return (HTTPStatus.OK, {"ok": True, "data": json.loads(p.read_text(encoding="utf-8"))})
        except Exception:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "Error leyendo respaldo"})

    # POST /backups/<filename> - restaurar respaldo
    if path.startswith("backups/") and method == "POST":
        import urllib.parse
        filename = urllib.parse.unquote(path[len("backups/"):])
        if "/" in filename or "\\" in filename or ".." in filename:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Filename invalido"})
        p = _backups_dir(ctx) / filename
        if not p.exists():
            return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Respaldo no encontrado"})
        try:
            bdata = json.loads(p.read_text(encoding="utf-8"))
            entries = bdata.get("entries", {})
            _save_data(ctx, entries)
            return (HTTPStatus.OK, {"ok": True, "data": {"restored": len(entries)}})
        except Exception as e:
            return (HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})

    # DELETE /backups/<filename> - eliminar respaldo
    if path.startswith("backups/") and method == "DELETE":
        import urllib.parse
        filename = urllib.parse.unquote(path[len("backups/"):])
        if "/" in filename or "\\" in filename or ".." in filename:
            return (HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Filename invalido"})
        p = _backups_dir(ctx) / filename
        if p.exists():
            p.unlink()
            return (HTTPStatus.OK, {"ok": True})
        return (HTTPStatus.NOT_FOUND, {"ok": False, "error": "Respaldo no encontrado"})

    return None


# ==================== HTML / CSS / JS Injection ====================

def get_tab_html():
    """HTML para el boton de la pestana."""
    return '<button class="tab" data-tab="traduction" data-i18n="tabs.traduction">Traducciones</button>'

def get_panel_html():
    """HTML para el panel de contenido de la pestana."""
    return '''
  <!-- Tab: Traducciones (Extension) -->
  <section id="tab-traduction" class="tab-panel">
    <div class="panel">
      <h2 data-i18n="trad.title">Traducciones de mods <span style="font-size:14px;font-weight:400;color:var(--text-dim);float:right;">V2.6</span></h2>
      <!-- Sub-tabs -->
      <div class="nem-tabs" id="trad-subtabs">
        <button class="nem-tab active" data-tsubtab="list" data-i18n="trad.subtab_list">Lista</button>
        <button class="nem-tab" data-tsubtab="detect" data-i18n="trad.subtab_detect">Deteccion</button>
        <button class="nem-tab" data-tsubtab="backups" data-i18n="trad.subtab_backups">Respaldos</button>
      </div>

      <!-- Sub-tab: Lista -->
      <div class="trad-subpanel" id="tsub-list">
        <p data-i18n="trad.desc">Clasifica tus mods de traduccion por tipo. Doble clic en una fila para editar.&#10;TR = Reemplaza ESP/ESM | DSD = Dynamic String Distributor | MCM = Solo menu | SC = Solo Scripts | SK = SKSE | OT = Otros | NO = No requiere traduccion</p>
        <div class="stats-grid" id="trad-stats">
          <div class="stat-box"><div class="stat-label" data-i18n="trad.total">Total mods</div><div class="stat-value" style="color:var(--accent);font-size:24px;" id="stat-trad-total">0</div></div>
          <div class="stat-box"><div class="stat-label" data-i18n="trad.stat_reemplazo">Reemplazo ESP/ESM</div><div class="stat-value blue" id="stat-trad-t">0</div></div>
          <div class="stat-box"><div class="stat-label">DSD</div><div class="stat-value green" id="stat-trad-d">0</div></div>
          <div class="stat-box"><div class="stat-label">MCM</div><div class="stat-value orange" id="stat-trad-m">0</div></div>
          <div class="stat-box"><div class="stat-label">Scripts</div><div class="stat-value purple" id="stat-trad-s">0</div></div>
          <div class="stat-box"><div class="stat-label">SKSE</div><div class="stat-value" style="color:#E91E63;" id="stat-trad-o">0</div></div>
          <div class="stat-box"><div class="stat-label" data-i18n="trad.stat_otros">Otros</div><div class="stat-value" style="color:#00BCD4;" id="stat-trad-ot">0</div></div>
          <div class="stat-box"><div class="stat-label" data-i18n="trad.stat_no_requiere">No requiere</div><div class="stat-value" style="color:var(--text-muted);" id="stat-trad-no">0</div></div>
        </div>
        <div class="controls">
          <input type="text" class="search-input" id="trad-search" data-i18n-placeholder="modlist.search_placeholder" placeholder="Buscar mod...">
          <select class="select" id="trad-filter-type">
            <option value="" data-i18n="trad.filter_all">Todos</option>
            <option value="T" data-i18n="trad.filter_trad">Traduccion (Reemplaza ESP)</option>
            <option value="D" data-i18n="trad.filter_dsd">DSD (Dynamic String Distributor)</option>
            <option value="M" data-i18n="trad.filter_mcm">MCM (Solo menu)</option>
            <option value="S" data-i18n="trad.filter_script">Script (Solo scripts)</option>
            <option value="O" data-i18n="trad.filter_skse">SKSE (Plugins SKSE)</option>
            <option value="OT" data-i18n="trad.filter_otros">Otros (Interfaz u otros)</option>
            <option value="NO" data-i18n="trad.filter_no_requiere">No requiere traduccion</option>
            <option value="none" data-i18n="trad.filter_none">Sin clasificar</option>
          </select>
          <select class="select" id="trad-filter-sep">
            <option value="" data-i18n="trad.filter_all_sep">Todos los separadores</option>
          </select>
          <button class="btn btn-sm" id="btn-trad-refresh" data-i18n="trad.refresh">Actualizar</button>
        </div>
        <div class="table-wrap">
          <table class="mod-table" id="trad-table">
            <thead><tr>
              <th class="col-status" data-i18n="trad.col_on">ON</th>
              <th class="col-status" style="width:50px;" data-i18n="trad.col_trad">Trad</th>
              <th class="col-priority" data-i18n="modlist.col_order">N°</th>
              <th class="col-name" data-i18n="modlist.col_name">Nombre Mod</th>
              <th class="col-category" data-i18n="modlist.col_category">Categoria</th>
              <th class="col-version" data-i18n="modlist.col_version">Version</th>
              <th data-i18n="trad.col_translates" style="min-width:160px;">A que mod traduce</th>
              <th class="col-comment" data-i18n="trad.col_comment" style="min-width:140px;">Comentario Traduccion</th>
              <th data-i18n="trad.col_link" style="width:80px;">Link</th>
              <th style="width:50px;">📂</th>
            </tr></thead>
            <tbody id="trad-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- Sub-tab: Deteccion automatica -->
      <div class="trad-subpanel" id="tsub-detect" style="display:none;">
        <p data-i18n="trad.detect_desc">Deteccion automatica de mods de traduccion basada en nombre y estructura de carpetas. Los cambios no se aplican automaticamente — revisalos y acepta los que quieras.</p>
        <div class="controls">
          <button type="button" class="btn btn-primary btn-sm" id="btn-trad-detect" data-i18n="trad.detect_btn">Detectar traducciones</button>
          <button type="button" class="btn btn-sm" id="btn-trad-select-all" data-i18n="trad.detect_select_all" style="display:none;">Marcar todo</button>
          <button type="button" class="btn btn-sm" id="btn-trad-deselect-all" data-i18n="trad.detect_deselect_all" style="display:none;">Desmarcar todo</button>
          <button type="button" class="btn btn-primary btn-sm" id="btn-trad-apply-all" data-i18n="trad.apply_all" style="display:none;">Aplicar seleccionados</button>
          <span id="trad-detect-count" style="font-size:12px;color:var(--text-dim);"></span>
        </div>
        <div class="controls" id="trad-detect-controls" style="display:none;">
          <input type="text" class="search-input" id="trad-detect-search" data-i18n-placeholder="modlist.search_placeholder" placeholder="Buscar...">
          <select class="select" id="trad-detect-filter-type">
            <option value="" data-i18n="trad.detect_all_types">Todos los tipos</option>
            <option value="T" data-i18n="trad.detect_filter_tr">TR (Reemplazo ESP)</option>
            <option value="D" data-i18n="trad.detect_filter_dsd">DSD</option>
            <option value="M" data-i18n="trad.detect_filter_mcm">MCM</option>
            <option value="S" data-i18n="trad.detect_filter_sc">SC (Scripts)</option>
            <option value="O" data-i18n="trad.detect_filter_sk">SK (SKSE)</option>
            <option value="OT" data-i18n="trad.detect_filter_ot">OT (Otros)</option>
            <option value="none" data-i18n="trad.detect_no_type">Sin tipo</option>
          </select>
          <select class="select" id="trad-detect-sort">
            <option value="name" data-i18n="trad.sort_name">Ordenar: Nombre</option>
            <option value="type" data-i18n="trad.sort_type">Ordenar: Tipo</option>
          </select>
        </div>
        <div class="table-wrap" style="margin-top:10px;">
          <table class="mod-table" id="trad-detect-table">
            <thead><tr>
              <th style="width:40px;text-align:center;">✓</th>
              <th style="text-align:center;" data-i18n="modlist.col_name">Mod</th>
              <th style="width:80px;text-align:center;" data-i18n="trad.col_trad">Tipo</th>
              <th style="min-width:160px;text-align:center;" data-i18n="trad.col_translates">Mod Original</th>
              <th style="min-width:200px;text-align:center;" data-i18n="trad.col_reason">Razon</th>
              <th style="width:180px;text-align:center;" data-i18n="trad.backup_actions">Acciones</th>
            </tr></thead>
            <tbody id="trad-detect-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- Sub-tab: Respaldos -->
      <div class="trad-subpanel" id="tsub-backups" style="display:none;">
        <p data-i18n="trad.backups_desc">Crea y restaura respaldos de los datos de traduccion (tipo y comentario). Los datos del mod se guardan en otros respaldos.</p>
        <div class="controls">
          <button type="button" class="btn btn-primary btn-sm" id="btn-trad-backup-create" data-i18n="trad.create_backup">Crear respaldo</button>
          <button type="button" class="btn btn-sm" id="btn-trad-backup-refresh" data-i18n="trad.refresh">Actualizar</button>
        </div>
        <div class="table-wrap" style="margin-top:10px;">
          <table class="mod-table" id="trad-backups-table">
            <thead><tr>
              <th data-i18n="trad.backup_name" style="min-width:200px;">Nombre</th>
              <th data-i18n="trad.backup_entries" style="width:80px;">Entradas</th>
              <th data-i18n="trad.backup_date" style="width:160px;">Fecha</th>
              <th data-i18n="trad.backup_actions" style="width:200px;">Acciones</th>
            </tr></thead>
            <tbody id="trad-backups-tbody"></tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- Modal de edicion de traduccion -->
  <div class="modal hidden" id="trad-edit-modal">
    <div class="modal-backdrop"></div>
    <div class="modal-content" style="width:500px;">
      <div class="modal-header">
        <h3 id="trad-edit-title" data-i18n="trad.edit_title">Editar traduccion</h3>
        <button type="button" class="btn btn-sm" id="trad-edit-close">×</button>
      </div>
      <div style="padding:16px;">
        <div style="margin-bottom:12px;">
          <label style="font-size:12px;color:var(--text-dim);" data-i18n="trad.field_type">Tipo de traduccion</label><br>
          <select id="trad-edit-type" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:13px;margin-top:4px;">
            <option value="" data-i18n="trad.type_none">Sin clasificar</option>
            <option value="T" data-i18n="trad.modal_type_trad">Traduccion (Reemplaza ESP/ESM y otros)</option>
            <option value="D" data-i18n="trad.modal_type_dsd">DSD (Dynamic String Distributor + MCM/scripts)</option>
            <option value="M" data-i18n="trad.modal_type_mcm">MCM (Solo menu MCM traducido)</option>
            <option value="S" data-i18n="trad.modal_type_script">Script (Solo scripts traducidos)</option>
            <option value="O" data-i18n="trad.modal_type_skse">SKSE (Solo plugins SKSE traducidos)</option>
            <option value="OT" data-i18n="trad.modal_type_otros">Otros (Interfaz u otros archivos)</option>
            <option value="NO" data-i18n="trad.modal_type_no">No requiere traduccion</option>
          </select>
        </div>
        <div style="margin-bottom:12px;">
          <label style="font-size:12px;color:var(--text-dim);" data-i18n="trad.field_translates">A que mod traduce</label><br>
          <input type="text" id="trad-edit-translates" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:13px;margin-top:4px;" data-i18n-placeholder="trad.field_translates_ph" placeholder="Escribe para buscar...">
          <div id="trad-autocomplete-list" style="position:relative;display:none;"></div>
        </div>
        <div style="margin-bottom:12px;">
          <label style="font-size:12px;color:var(--text-dim);" data-i18n="trad.field_comment">Comentario de traduccion</label><br>
          <textarea id="trad-edit-comment" rows="3" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:13px;margin-top:4px;resize:vertical;" data-i18n-placeholder="trad.field_comment_ph" placeholder="Notas sobre esta traduccion..."></textarea>
        </div>
      </div>
      <div style="text-align:right;padding:0 16px 16px;">
        <button type="button" class="btn" id="trad-edit-cancel" data-i18n="modal.cancel">Cancelar</button>
        <button type="button" class="btn btn-primary" id="trad-edit-save" data-i18n="modal.save">Guardar</button>
      </div>
    </div>
  </div>
'''

def get_css():
    """CSS para la extension."""
    return '''
/* === Extension Traducciones === */
.trad-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 22px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 12px;
  line-height: 1;
}
.trad-badge-T { background: #2196F3; color: white; }
.trad-badge-D { background: #4CAF50; color: white; }
.trad-badge-M { background: #FF9800; color: white; }
.trad-badge-S { background: #9C27B0; color: white; }
.trad-badge-O { background: #E91E63; color: white; }
.trad-badge-OT { background: #00BCD4; color: white; }
.trad-badge-NO { background: #607D8B; color: white; }
.trad-badge-none { background: transparent; color: var(--text-muted); border: 1px dashed var(--border); }
.trad-row-T { border-left: 3px solid #2196F3; }
.trad-row-D { border-left: 3px solid #4CAF50; }
.trad-row-M { border-left: 3px solid #FF9800; }
.trad-row-S { border-left: 3px solid #9C27B0; }
.trad-row-O { border-left: 3px solid #E91E63; }
.trad-row-OT { border-left: 3px solid #00BCD4; }
.trad-row-NO { border-left: 3px solid #607D8B; }
#trad-autocomplete-list {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 100;
  margin-top: 2px;
}
#trad-autocomplete-list .ac-item {
  padding: 6px 10px;
  cursor: pointer;
  font-size: 13px;
}
#trad-autocomplete-list .ac-item:hover {
  background: var(--card-hover);
}
'''

def get_js():
    """JavaScript para la extension."""
    return '''
// ==================== Extension: Traducciones ====================
console.log("[EXT-TRAD] Cargando extension Traducciones V2.6...");
window.TraductionTab={
  data:null,tradData:null,search:"",filterType:"",filterSep:"",editingMod:null,
  backupsData:null,activeSubtab:"list",
  detectData:null,detectSearch:"",detectFilterType:"",detectSort:"name",detectEditingFromDetect:false,
  init(){
    console.log("[EXT-TRAD] TraductionTab.init() llamado");
    try{
    // Cargar tradData inmediatamente para que la columna Trad se muestre
    fetch("/api/translation/data").then(r=>r.json()).then(d=>{
      if(d.ok){
        this.tradData=d.data||{};
        window._tradData=this.tradData;
        const thTrad=document.getElementById("th-trad");
        if(thTrad)thTrad.style.display="";
        // Forzar re-render de la lista principal si ya tiene datos
        if(window.ModlistTab&&ModlistTab.lastState){
          ModlistTab._lastStateHash=""; // invalidar hash para forzar render
          ModlistTab.render();
        }
      }
    }).catch(()=>{});
    // Sub-tab switching
    document.querySelectorAll("#trad-subtabs .nem-tab").forEach(btn=>{
      btn.addEventListener("click",()=>this.switchSubtab(btn.dataset.tsubtab));
    });
    // Botones
    document.getElementById("btn-trad-refresh").addEventListener("click",()=>this.refresh());
    document.getElementById("trad-search").addEventListener("input",debounce(e=>{this.search=e.target.value.toLowerCase();this.render();},200));
    document.getElementById("trad-filter-type").addEventListener("change",e=>{this.filterType=e.target.value;this.render();});
    document.getElementById("trad-filter-sep").addEventListener("change",e=>{this.filterSep=e.target.value;this.render();});
    // Backups
    document.getElementById("btn-trad-backup-create").addEventListener("click",()=>this.createBackup());
    document.getElementById("btn-trad-backup-refresh").addEventListener("click",()=>this.refreshBackups());
    // Detect
    document.getElementById("btn-trad-detect").addEventListener("click",()=>this.runDetection());
    document.getElementById("btn-trad-apply-all").addEventListener("click",()=>this.applyAllDetected());
    document.getElementById("btn-trad-select-all").addEventListener("click",()=>this.selectAllDetect(true));
    document.getElementById("btn-trad-deselect-all").addEventListener("click",()=>this.selectAllDetect(false));
    document.getElementById("trad-detect-search").addEventListener("input",debounce(e=>{this.detectSearch=e.target.value.toLowerCase();this.renderDetection();},200));
    document.getElementById("trad-detect-filter-type").addEventListener("change",e=>{this.detectFilterType=e.target.value;this.renderDetection();});
    document.getElementById("trad-detect-sort").addEventListener("change",e=>{this.detectSort=e.target.value;this.renderDetection();});
    // Modal
    document.getElementById("trad-edit-close").addEventListener("click",()=>this.closeModal());
    document.getElementById("trad-edit-cancel").addEventListener("click",()=>this.closeModal());
    document.getElementById("trad-edit-save").addEventListener("click",()=>this.saveMod());
    document.querySelector("#trad-edit-modal .modal-backdrop").addEventListener("click",()=>this.closeModal());
    // Autocomplete
    const translatesInput=document.getElementById("trad-edit-translates");
    translatesInput.addEventListener("input",()=>this.updateAutocomplete());
    translatesInput.addEventListener("blur",()=>setTimeout(()=>{document.getElementById("trad-autocomplete-list").style.display="none";},200));
    console.log("[EXT-TRAD] TraductionTab.init() OK");
    }catch(e){console.error("[EXT-TRAD] Error en init():",e);}
  },
  switchSubtab(name){
    this.activeSubtab=name;
    document.querySelectorAll("#trad-subtabs .nem-tab").forEach(b=>b.classList.toggle("active",b.dataset.tsubtab===name));
    document.querySelectorAll(".trad-subpanel").forEach(p=>p.style.display="none");
    const panel=document.getElementById("tsub-"+name);
    if(panel)panel.style.display="";
    if(name==="list"&&!this.data)this.refresh();
    if(name==="backups")this.refreshBackups();
    // Detect: no auto-run, user clicks button
  },
  async refresh(){
    console.log("[EXT-TRAD] refresh() llamado");
    const btn=document.getElementById("btn-trad-refresh");
    if(!btn){console.error("[EXT-TRAD] btn-trad-refresh no encontrado!");return;}
    const oldText=btn.textContent;
    btn.textContent=I18n.t("versions.loading");
    btn.disabled=true;
    const tb=document.getElementById("trad-tbody");
    tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--accent);padding:30px;">${I18n.t("versions.loading")}</td></tr>`;
    try{
      console.log("[EXT-TRAD] Llamando Api.getState()...");
      const s=await Api.getState();
      console.log("[EXT-TRAD] getState OK, sections:",s.sections?s.sections.length:0);
      console.log("[EXT-TRAD] Llamando /api/translation/data...");
      const td=await fetch("/api/translation/data").then(r=>r.json());
      console.log("[EXT-TRAD] translation/data OK, ok="+td.ok);
      this.tradData=td.ok?td.data:{};
      // Exportar tradData a window para que el plugin principal pueda usarlo
      window._tradData=this.tradData;
      // Mostrar la columna Trad en la lista principal
      const thTrad=document.getElementById("th-trad");
      if(thTrad)thTrad.style.display="";
      const mods=[];
      for(const sec of s.sections){
        const sepName=sec.separator?(sec.separator.display_name||sec.separator.name):"";
        for(const m of sec.mods){
          if(m.is_separator)continue;
          if(m.deleted_from_disk)continue;
          mods.push({...m,_sepName:sepName});
        }
      }
      this.data=mods;
      this.populateSepFilter();
      this.render();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  populateSepFilter(){
    const sel=document.getElementById("trad-filter-sep");
    const cur=sel.value;
    const set=new Set();
    for(const m of (this.data||[])){if(m._sepName)set.add(m._sepName);}
    sel.innerHTML=`<option value="">${I18n.t("trad.filter_all_sep")}</option>`;
    for(const s of Array.from(set).sort()){const o=document.createElement("option");o.value=s;o.textContent=s;sel.appendChild(o);}
    sel.value=cur;
  },
  render(){
    if(!this.data){
      const tb=document.getElementById("trad-tbody");
      tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.none")}</td></tr>`;
      return;
    }
    // Stats
    const tCount=this.data.filter(m=>(this.tradData[m.name]||{}).translation_type==="T").length;
    const dCount=this.data.filter(m=>(this.tradData[m.name]||{}).translation_type==="D").length;
    const mCount=this.data.filter(m=>(this.tradData[m.name]||{}).translation_type==="M").length;
    const sCount=this.data.filter(m=>(this.tradData[m.name]||{}).translation_type==="S").length;
    const oCount=this.data.filter(m=>(this.tradData[m.name]||{}).translation_type==="O").length;
    const otCount=this.data.filter(m=>(this.tradData[m.name]||{}).translation_type==="OT").length;
    const noCount=this.data.filter(m=>(this.tradData[m.name]||{}).translation_type==="NO").length;
    document.getElementById("stat-trad-total").textContent=this.data.length;
    document.getElementById("stat-trad-t").textContent=tCount;
    document.getElementById("stat-trad-d").textContent=dCount;
    document.getElementById("stat-trad-m").textContent=mCount;
    document.getElementById("stat-trad-s").textContent=sCount;
    document.getElementById("stat-trad-o").textContent=oCount;
    document.getElementById("stat-trad-ot").textContent=otCount;
    document.getElementById("stat-trad-no").textContent=noCount;
    // Filter
    let mods=this.data.slice();
    if(this.filterSep){mods=mods.filter(m=>m._sepName===this.filterSep);}
    if(this.filterType==="none"){mods=mods.filter(m=>!(this.tradData[m.name]||{}).translation_type);}
    else if(this.filterType){mods=mods.filter(m=>(this.tradData[m.name]||{}).translation_type===this.filterType);}
    if(this.search){
      const q=this.search;
      mods=mods.filter(m=>(m.name+" "+(m.display_name||"")+" "+(m.category||"")+" "+(m.version||"")).toLowerCase().includes(q));
    }
    const tb=document.getElementById("trad-tbody");
    tb.innerHTML="";
    if(!mods.length){
      tb.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.none_filtered")}</td></tr>`;
      return;
    }
    // Event delegation for dblclick
    if(!this._delegationInit){
      this._delegationInit=true;
      tb.addEventListener("dblclick",(e)=>{
        const tr=e.target.closest("tr[data-modname]");
        if(tr)this.openModal(tr.dataset.modname);
      });
    }
    // Render
    const CHUNK=800;
    const renderChunk=(start)=>{
      const end=Math.min(start+CHUNK,mods.length);
      const parts=[];
      for(let i=start;i<end;i++){
        const m=mods[i];
        const td=(this.tradData[m.name]||{});
        const tType=td.translation_type||"";
        const tMod=td.translates_mod||"";
        const tComment=td.translation_comment||"";
        const statusChar=m.active?"X":"O";
        const statusClass=m.active?"status-on":"status-off";
        const orderText=m.order_number!=null?m.order_number:"—";
        const cat=m.category_override||m.category||"";
        // Badge
        // Badge: show 2-3 letter code instead of single letter
        const BADGE_LABELS={T:"TR",D:"DSD",M:"MCM",S:"SC",O:"SK",OT:"OT",NO:"NO"};
        const badge=tType?`<span class="trad-badge trad-badge-${tType}">${BADGE_LABELS[tType]||tType}</span>`:`<span class="trad-badge trad-badge-none">—</span>`;
        const rowClass=tType?("trad-row-"+tType):"";
        // Version: clickable to file download link (version_links[0])
        let versionHtml;
        if(m.version&&m.version_links&&m.version_links.length>0){
          versionHtml=`<a href="${escapeHtml(m.version_links[0])}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none;" title="${escapeHtml(m.version_links[0])}">${escapeHtml(m.version)}</a>`;
        }else{
          versionHtml=m.version?escapeHtml(m.version):`<span style="color:var(--text-muted);">—</span>`;
        }
        // Link: go to mod page (not file-specific)
        // Link: usar nexus_id si existe, sino usar m.link (del meta.ini nexus_url)
        let linkHtml="—";
        if(m.nexus_id&&m.nexus_id!=="0"&&m.nexus_id!==""){
          const modUrl=`https://www.nexusmods.com/skyrimspecialedition/mods/${escapeHtml(m.nexus_id)}`;
          linkHtml=`<a href="${modUrl}" target="_blank" rel="noopener" class="mod-link">Link</a>`;
        }else if(m.link){
          linkHtml=`<a href="${escapeHtml(m.link)}" target="_blank" rel="noopener" class="mod-link">Link</a>`;
        }
        const translatesText=tMod?escapeHtml(tMod):`<span style="color:var(--text-muted);">—</span>`;
        const commentText=tComment?escapeHtml(tComment):`<span style="color:var(--text-muted);">—</span>`;
        const folderBtnList=`<button type="button" class="btn btn-sm list-folder-btn" data-modname="${escapeHtml(m.name)}" title="${I18n.t("trad.detect_open_folder")}" style="padding:2px 6px;font-size:11px;">📂</button>`;
        parts.push(`<tr class="mod-row ${rowClass}" data-modname="${escapeHtml(m.name)}"><td class="col-status"><span class="${statusClass}">${statusChar}</span></td><td style="text-align:center;">${badge}</td><td class="col-priority">${orderText}</td><td class="col-name">${escapeHtml(m.display_name||m.name)}</td><td class="col-category">${escapeHtml(cat)}</td><td class="col-version">${versionHtml}</td><td>${translatesText}</td><td class="col-comment">${commentText}</td><td>${linkHtml}</td><td style="text-align:center;">${folderBtnList}</td></tr>`);
      }
      if(start===0)tb.innerHTML=parts.join("");
      else tb.insertAdjacentHTML("beforeend",parts.join(""));
      if(end<mods.length)requestAnimationFrame(()=>renderChunk(end));
    };
    renderChunk(0);
    // Event delegation para boton carpeta en lista
    if(!this._listFolderDelegationInit){
      this._listFolderDelegationInit=true;
      tb.addEventListener("click",async(e)=>{
        if(e.target.classList.contains("list-folder-btn")){
          await this.openFolder(e.target.dataset.modname);
        }
      });
    }
  },
  openModal(modname){
    const m=(this.data||[]).find(x=>x.name===modname);
    if(!m)return;
    this.editingMod=m;
    const td=(this.tradData[modname]||{});
    document.getElementById("trad-edit-title").textContent=(m.display_name||m.name);
    document.getElementById("trad-edit-type").value=td.translation_type||"";
    document.getElementById("trad-edit-translates").value=td.translates_mod||"";
    document.getElementById("trad-edit-comment").value=td.translation_comment||"";
    document.getElementById("trad-edit-modal").classList.remove("hidden");
  },
  closeModal(){
    document.getElementById("trad-edit-modal").classList.add("hidden");
    this.editingMod=null;
    document.getElementById("trad-autocomplete-list").style.display="none";
  },
  updateAutocomplete(){
    const q=document.getElementById("trad-edit-translates").value.toLowerCase();
    const list=document.getElementById("trad-autocomplete-list");
    if(!q||!this.data){list.style.display="none";return;}
    const matches=this.data.filter(m=>(m.display_name||m.name).toLowerCase().includes(q)).slice(0,10);
    if(!matches.length){list.style.display="none";return;}
    list.style.display="block";
    list.innerHTML=matches.map(m=>`<div class="ac-item" data-val="${escapeHtml(m.name)}">${escapeHtml(m.display_name||m.name)}</div>`).join("");
    list.querySelectorAll(".ac-item").forEach(item=>{
      item.addEventListener("mousedown",(e)=>{
        e.preventDefault();
        document.getElementById("trad-edit-translates").value=item.dataset.val;
        list.style.display="none";
      });
    });
  },
  async saveMod(){
    if(!this.editingMod)return;
    const modname=this.editingMod.name;
    const payload={
      translation_type:document.getElementById("trad-edit-type").value,
      translates_mod:document.getElementById("trad-edit-translates").value.trim(),
      translation_comment:document.getElementById("trad-edit-comment").value.trim(),
    };
    try{
      const r=await fetch("/api/translation/data/"+encodeURIComponent(modname),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      this.tradData[modname]=d.data;
      // Sincronizar window._tradData y forzar re-render de la lista principal
      window._tradData=this.tradData;
      if(window.ModlistTab&&ModlistTab.lastState){ModlistTab._lastStateHash="";ModlistTab.render();}
      // Si se edito desde la deteccion, actualizar la fila
      if(this.detectEditingFromDetect){
        const item=this.detectData.find(i=>i.mod_name===modname);
        if(item){
          item.detected_type=payload.translation_type;
          item.guessed_original=payload.translates_mod||item.guessed_original;
          item._checked=true;
        }
        this.detectEditingFromDetect=false;
        showToast(I18n.t("versions.comment_saved"),"success");
        this.closeModal();
        this.renderDetection();
      }else{
        showToast(I18n.t("versions.comment_saved"),"success");
        this.closeModal();
        this.render();
      }
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  // === Detection ===
  async runDetection(){
    const btn=document.getElementById("btn-trad-detect");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("trad.detect_scanning");
    btn.disabled=true;
    const tb=document.getElementById("trad-detect-tbody");
    tb.innerHTML=`<tr><td colspan="5" style="text-align:center;color:var(--accent);padding:30px;">${I18n.t("trad.detect_scanning")}</td></tr>`;
    try{
      const r=await fetch("/api/translation/detect");
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      this.detectData=d.data||[];
      // Mostrar controles
      document.getElementById("btn-trad-select-all").style.display="";
      document.getElementById("btn-trad-deselect-all").style.display="";
      document.getElementById("btn-trad-apply-all").style.display="";
      document.getElementById("trad-detect-controls").style.display="";
      this.renderDetection();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  renderDetection(){
    const tb=document.getElementById("trad-detect-tbody");
    const countSpan=document.getElementById("trad-detect-count");
    if(!this.detectData||!this.detectData.length){
      tb.innerHTML=`<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("trad.detect_no_results")}</td></tr>`;
      countSpan.textContent="";
      return;
    }
    // Filtrar y ordenar
    let items=this.detectData.slice();
    if(this.detectFilterType==="none"){items=items.filter(i=>!i.detected_type);}
    else if(this.detectFilterType){items=items.filter(i=>i.detected_type===this.detectFilterType);}
    if(this.detectSearch){
      const q=this.detectSearch;
      items=items.filter(i=>(i.display_name+" "+i.mod_name+" "+i.reason+" "+(i.guessed_original||"")).toLowerCase().includes(q));
    }
    const TYPE_ORDER={"T":0,"D":1,"M":2,"S":3,"O":4,"OT":5,"NO":6,"":7};
    if(this.detectSort==="name"){
      items.sort((a,b)=>(a.display_name||a.mod_name).localeCompare(b.display_name||b.mod_name));
    }else if(this.detectSort==="type"){
      items.sort((a,b)=>(TYPE_ORDER[a.detected_type||""]??99)-(TYPE_ORDER[b.detected_type||""]??99));
    }
    const checkedCount=items.filter(i=>i._checked).length;
    countSpan.textContent=items.length+" "+I18n.t("trad.detect_detected")+" ("+checkedCount+" "+I18n.t("trad.detect_selected")+")";
    tb.innerHTML="";
    if(!items.length){
      tb.innerHTML=`<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("trad.detect_no_match")}</td></tr>`;
      return;
    }
    const BADGE_LABELS={T:"TR",D:"DSD",M:"MCM",S:"SC",O:"SK",OT:"OT",NO:"NO"};
    const BADGE_COLORS={T:"#2196F3",D:"#4CAF50",M:"#FF9800",S:"#9C27B0",O:"#E91E63",OT:"#00BCD4",NO:"#607D8B"};
    for(const item of items){
      const tr=document.createElement("tr");
      // Si ya tiene tipo en la lista (tradData), usar ese tipo y marcar como checked
      const existingTd=(this.tradData||{})[item.mod_name]||{};
      const existingType=existingTd.translation_type||"";
      // El tipo mostrado es el de la lista si existe, sino el detectado
      const displayType=existingType||item.detected_type||"";
      const hasExisting=!!existingType;
      // Marcar como checked si ya tiene tipo en la lista
      if(hasExisting)item._checked=true;
      const checked=item._checked?"checked":"";
      const t=displayType;
      const badge=t?`<span class="trad-badge" style="background:${BADGE_COLORS[t]||"#999"};color:white;">${BADGE_LABELS[t]||t}</span>`:`<span style="color:var(--text-muted);font-size:11px;">?</span>`;
      // Mod Original: usar translates_mod de la lista si existe, sino guessed_original
      const origValue=existingTd.translates_mod||item.guessed_original||"";
      const origText=origValue?escapeHtml(origValue):`<span style="color:var(--text-muted);">—</span>`;
      const editBtn=`<button type="button" class="btn btn-sm" data-action="edit" data-modname="${escapeHtml(item.mod_name)}" title="${I18n.t("trad.detect_edit")}" style="padding:2px 6px;font-size:11px;">✎</button>`;
      const applyBtn=`<button type="button" class="btn btn-sm btn-primary" data-action="apply" data-modname="${escapeHtml(item.mod_name)}" title="${I18n.t("trad.detect_apply_row")}" style="padding:2px 6px;font-size:11px;">↗</button>`;
      const folderBtn=`<button type="button" class="btn btn-sm" data-action="folder" data-modname="${escapeHtml(item.mod_name)}" title="${I18n.t("trad.detect_open_folder")}" style="padding:2px 6px;font-size:11px;">📂</button>`;
      // Indicador de que ya esta en la lista
      const listIndicator=hasExisting?` <span style="color:var(--green);font-size:10px;" title="${I18n.t("trad.detect_already_in_list")}">✓</span>`:"";
      tr.innerHTML=`<td style="text-align:center;"><input type="checkbox" class="detect-accept" data-modname="${escapeHtml(item.mod_name)}" ${checked}></td><td>${escapeHtml(item.display_name||item.mod_name)}${listIndicator}</td><td style="text-align:center;">${badge}</td><td style="font-size:12px;">${origText}</td><td style="font-size:11px;color:var(--text-dim);">${escapeHtml(item.reason)}</td><td style="text-align:center;white-space:nowrap;">${editBtn} ${applyBtn} ${folderBtn}</td>`;
      tb.appendChild(tr);
    }
    // Event delegation para botones de accion
    if(!this._detectDelegationInit){
      this._detectDelegationInit=true;
      tb.addEventListener("click",async(e)=>{
        const btn=e.target.closest("button[data-action]");
        if(!btn)return;
        const action=btn.dataset.action;
        const modname=btn.dataset.modname;
        if(action==="edit"){
          this.openModalFromDetect(modname);
        }else if(action==="apply"){
          await this.applyOneDetected(modname);
        }else if(action==="folder"){
          await this.openFolder(modname);
        }
      });
    }
  },
  selectAllDetect(checked){
    if(!this.detectData)return;
    for(const item of this.detectData){
      item._checked=checked;
    }
    this.renderDetection();
  },
  async openFolder(modname){
    try{
      const r=await fetch("/api/translation/open_folder",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mod_name:modname})});
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  openModalFromDetect(modname){
    // Buscar el mod en detectData y abrir el modal de edicion
    const item=this.detectData.find(d=>d.mod_name===modname);
    if(!item)return;
    this.detectEditingFromDetect=true;
    // Crear un mod temporal para el modal
    this.editingMod={name:modname,display_name:item.display_name||item.mod_name};
    const td=(this.tradData[modname]||{});
    document.getElementById("trad-edit-title").textContent=item.display_name||item.mod_name;
    document.getElementById("trad-edit-type").value=item.detected_type||td.translation_type||"";
    document.getElementById("trad-edit-translates").value=td.translates_mod||"";
    document.getElementById("trad-edit-comment").value=td.translation_comment||"";
    document.getElementById("trad-edit-modal").classList.remove("hidden");
  },
  async applyOneDetected(modname){
    const item=this.detectData.find(d=>d.mod_name===modname);
    if(!item||!item.detected_type){
      showToast(I18n.t("trad.detect_no_type_to_apply"),"warning");
      return;
    }
    try{
      const r=await fetch("/api/translation/apply_detected",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({entries:[{mod_name:modname,detected_type:item.detected_type}]})
      });
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      showToast(`"${item.display_name||modname}" ${I18n.t("trad.detect_applied_one")}`,"success");
      // Marcar el checkbox de la fila
      item._checked=true;
      const cb=document.querySelector(`.detect-accept[data-modname="${modname}"]`);
      if(cb)cb.checked=true;
      this.data=null; // invalidar cache de la lista
      // Recargar tradData y forzar re-render de la lista principal
      const td=await fetch("/api/translation/data").then(r=>r.json());
      if(td.ok){this.tradData=td.data;window._tradData=this.tradData;if(window.ModlistTab&&ModlistTab.lastState){ModlistTab._lastStateHash="";ModlistTab.render();}}
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async applyAllDetected(){
    if(!this.detectData||!this.detectData.length){
      showToast(I18n.t("trad.detect_nothing_to_apply"),"info");
      return;
    }
    // Recoger entradas aceptadas (checkbox marcado)
    const entries=[];
    document.querySelectorAll(".detect-accept").forEach(cb=>{
      if(cb.checked){
        const modname=cb.dataset.modname;
        const item=this.detectData.find(d=>d.mod_name===modname);
        if(item&&item.detected_type){
          entries.push({mod_name:modname,detected_type:item.detected_type});
        }
      }
    });
    if(!entries.length){
      showToast(I18n.t("trad.detect_none_selected"),"warning");
      return;
    }
    if(!confirm(I18n.t("trad.detect_apply_confirm").replace("{count}",entries.length)))return;
    try{
      const r=await fetch("/api/translation/apply_detected",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({entries:entries})
      });
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      showToast(`${d.data.applied} ${I18n.t("trad.detect_applied_all")}`,"success");
      this.data=null; // invalidar cache de la lista
      // Recargar tradData y forzar re-render de la lista principal
      const td=await fetch("/api/translation/data").then(r=>r.json());
      if(td.ok){this.tradData=td.data;window._tradData=this.tradData;if(window.ModlistTab&&ModlistTab.lastState){ModlistTab._lastStateHash="";ModlistTab.render();}}
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  // === Backups ===
  async refreshBackups(){
    const btn=document.getElementById("btn-trad-backup-refresh");
    const oldText=btn.textContent;
    btn.textContent=I18n.t("versions.loading");
    btn.disabled=true;
    try{
      const r=await fetch("/api/translation/backups");
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      this.backupsData=d.data;
      this.renderBackups();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
    btn.textContent=oldText;
    btn.disabled=false;
  },
  renderBackups(){
    const tb=document.getElementById("trad-backups-tbody");
    tb.innerHTML="";
    if(!this.backupsData||!this.backupsData.length){
      tb.innerHTML=`<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:20px;">${I18n.t("versions.no_backups")}</td></tr>`;
      return;
    }
    for(const b of this.backupsData){
      const tr=document.createElement("tr");
      tr.innerHTML=`<td>${escapeHtml(b.label||b.filename)}</td><td style="text-align:center;">${b.entries}</td><td style="font-size:12px;color:var(--text-dim);">${escapeHtml(b.created_at||"")}</td><td></td>`;
      const actionsTd=tr.querySelector("td:last-child");
      const btnView=document.createElement("button");
      btnView.type="button";btnView.className="btn btn-sm btn-primary";btnView.style.marginRight="4px";
      btnView.textContent=I18n.t("versions.btn_view");
      btnView.addEventListener("click",()=>this.viewBackup(b.filename));
      const btnRestore=document.createElement("button");
      btnRestore.type="button";btnRestore.className="btn btn-sm";btnRestore.style.marginRight="4px";
      btnRestore.textContent=I18n.t("versions.btn_restore");
      btnRestore.addEventListener("click",()=>this.restoreBackup(b.filename));
      const btnDelete=document.createElement("button");
      btnDelete.type="button";btnDelete.className="btn btn-sm btn-danger";btnDelete.textContent="×";
      btnDelete.addEventListener("click",()=>this.deleteBackup(b.filename));
      actionsTd.appendChild(btnView);actionsTd.appendChild(btnRestore);actionsTd.appendChild(btnDelete);
      tb.appendChild(tr);
    }
  },
  async createBackup(){
    try{
      const r=await fetch("/api/translation/backups",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})});
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      showToast(I18n.t("versions.backup_created").replace("{count}",d.data.entries),"success");
      await this.refreshBackups();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async viewBackup(filename){
    try{
      const r=await fetch("/api/translation/backups/"+encodeURIComponent(filename));
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      const entries=d.data.entries||{};
      const win=window.open("","_blank","width=800,height=600");
      if(!win){showToast(I18n.t("versions.popup_blocked"),"error");return;}
      let html=`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Backup: ${escapeHtml(filename)}</title><style>body{font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:20px;}table{border-collapse:collapse;width:100%;font-size:13px;}th,td{border:1px solid #333;padding:6px 10px;text-align:left;}th{background:#16213e;}h2{color:#D9822B;}.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-weight:700;font-size:11px;color:white;}</style></head><body>`;
      html+=`<h2>Backup: ${escapeHtml(filename)}</h2>`;
      html+=`<p>${I18n.t("trad.backup_entries")}: ${Object.keys(entries).length} | ${I18n.t("trad.backup_date")}: ${escapeHtml(d.data.created_at||"")}</p>`;
      html+=`<table><tr><th>${I18n.t("modlist.col_name")}</th><th>${I18n.t("trad.col_trad")}</th><th>${I18n.t("trad.col_translates")}</th><th>${I18n.t("trad.col_comment")}</th></tr>`;
      const BADGE_LABELS={T:"TR",D:"DSD",M:"MCM",S:"SC",O:"SK",OT:"OT",NO:"NO"};
      const BADGE_COLORS={T:"#2196F3",D:"#4CAF50",M:"#FF9800",S:"#9C27B0",O:"#E91E63",OT:"#00BCD4",NO:"#607D8B"};
      for(const [modname,e] of Object.entries(entries)){
        const t=e.translation_type||"";
        const label=t?(BADGE_LABELS[t]||t):"—";
        const color=t?(BADGE_COLORS[t]||"#999"):"transparent";
        const badge=t?`<span class="badge" style="background:${color};">${label}</span>`:"—";
        html+=`<tr><td>${escapeHtml(modname)}</td><td>${badge}</td><td>${escapeHtml(e.translates_mod||"")}</td><td>${escapeHtml(e.translation_comment||"")}</td></tr>`;
      }
      html+="</table></body></html>";
      win.document.write(html);win.document.close();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async restoreBackup(filename){
    if(!confirm(I18n.t("versions.confirm_restore")))return;
    try{
      const r=await fetch("/api/translation/backups/"+encodeURIComponent(filename),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})});
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      showToast(I18n.t("versions.restored_ok"),"success");
      await this.refresh();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
  async deleteBackup(filename){
    if(!confirm(I18n.t("versions.confirm_delete_backup")))return;
    try{
      const r=await fetch("/api/translation/backups/"+encodeURIComponent(filename),{method:"DELETE"});
      const d=await r.json();
      if(!d.ok)throw new Error(d.error);
      showToast(I18n.t("versions.backup_deleted"),"success");
      await this.refreshBackups();
    }catch(e){showToast(I18n.t("topbar.error")+": "+e.message,"error");}
  },
};

// Extension registration
console.log("[EXT-TRAD] Registrando Extensions...");
window.Extensions={
  init(){
    console.log("[EXT-TRAD] Extensions.init() llamado");
    if(window.TraductionTab){
      console.log("[EXT-TRAD] TraductionTab existe, llamando init()");
      window.TraductionTab.init();
    }else{
      console.error("[EXT-TRAD] TraductionTab NO existe!");
    }
  },
  switchTab(n){
    console.log("[EXT-TRAD] Extensions.switchTab("+n+") llamado");
    if(n==="traduction"&&window.TraductionTab){
      console.log("[EXT-TRAD] Activando pestana traduction, data="+!!window.TraductionTab.data);
      if(!window.TraductionTab.data)window.TraductionTab.refresh();
    }
  },
};
console.log("[EXT-TRAD] Extension registrada, Extensions="+!!window.Extensions);
'''
