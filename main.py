import os
import hashlib
import traceback
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
import uvicorn

# Importar componentes locales
from document_parser import parse_document
from ai_processor import process_document_with_ai
from notion_client import create_task_ticket
from calendar_client import create_calendar_event
from telegram_client import (
    send_success_notification,
    send_rejection_notification,
    send_error_notification,
    send_telegram_message
)
from logger import register_transaction, log_error, get_daily_summary

# Cargar variables de entorno del archivo .env
load_dotenv()

# Inicializar FastAPI
app = FastAPI(title="AI Automation Specialist Webhook Server")

# Diccionario simple en memoria para evitar procesamientos duplicados en esta sesión
PROCESSED_HASHES = set()

def calculate_file_hash(file_path: str) -> str:
    """Calcula el hash SHA-256 de un archivo para deduplicación."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except Exception:
        # Fallback simple si hay problemas de lectura física
        return hashlib.sha256(file_path.encode('utf-8')).hexdigest()

def process_single_file(file_path: str) -> bool:
    """Orquesta la transacción completa de procesamiento para un solo documento."""
    file_name = os.path.basename(file_path)
    print(f"\n=========================================")
    print(f"[ORQUESTADOR] Iniciando procesamiento de: {file_name}")
    print(f"=========================================\n")
    
    # 1. Deduplicación por hash
    file_hash = calculate_file_hash(file_path)
    if file_hash in PROCESSED_HASHES:
        print(f"[ORQUESTADOR] Omitiendo '{file_name}' (Ya fue procesado en esta sesión).")
        return False
    
    try:
        # 2. Extracción de texto
        print(f"[PASO 1/5] Extrayendo texto de '{file_name}'...")
        document_text = parse_document(file_path)
        print(f"[PASO 1/5] ¡Éxito! Texto extraído: {len(document_text)} caracteres.")
        
        # Truncar el texto si excede límites razonables de prompt
        if len(document_text) > 40000:
            document_text = document_text[:40000] + "\n\n[...Texto truncado por el Orquestador...]"
            
        # 3. Procesamiento de IA (Doble Paso: Generación + Crítico)
        print(f"[PASO 2/5] Enviando a Inteligencia Artificial (Doble Paso)...")
        ai_result = process_document_with_ai(document_text)
        proposal = ai_result["proposal"]
        audit = ai_result["audit"]
        
        # 4. Evaluación del Crítico de Calidad
        aprobado = audit.get("aprobado", False)
        motivo_auditoria = audit.get("motivo", "No se proporcionó explicación.")
        
        if not aprobado:
            # CASO RECHAZADO: Calidad insuficiente o discrepancias
            print(f"[PASO 3/5] [RECHAZADO] RECHAZADO por el Crítico de IA. Motivo: {motivo_auditoria}")
            register_transaction(file_name, "REJECTED_BY_CRITIC", error_msg=motivo_auditoria)
            send_rejection_notification(file_name, motivo_auditoria)
            print(f"[ORQUESTADOR] Proceso finalizado (Calidad Desaprobada) para '{file_name}'.")
            PROCESSED_HASHES.add(file_hash)
            return True
            
        # CASO APROBADO: Continuar a integraciones Notion & Calendar
        print(f"[PASO 3/5] [APROBADO] APROBADO por el Crítico de IA. Iniciando registro...")
        summary = proposal.get("document_summary", "No summary generated.")
        raw_actions = proposal.get("actions", [])
        
        if not raw_actions:
            print(f"[ORQUESTADOR] Advertencia: No se extrajeron tareas accionables en '{file_name}'.")
            register_transaction(file_name, "SUCCESS", error_msg="No se extrajeron tareas accionables.")
            send_telegram_message(f"ℹ️ <b>[SISTEMA]</b> El documento <code>{file_name}</code> fue aprobado pero no contenía acciones implícitas.")
            PROCESSED_HASHES.add(file_hash)
            return True
            
        # 5. Registrar en Notion y Google Calendar (Secuencia transaccional con rollback)
        acciones_procesadas = []
        for action in raw_actions:
            # Crear ticket en Notion (Devuelve URL real o simulada)
            print(f"[PASO 4/5] Creando ticket en Notion: '{action.get('title')}'...")
            notion_url = create_task_ticket(file_name, action)
            action["notion_page_url"] = notion_url
            
            # Crear evento en Google Calendar (Devuelve ID de evento real o simulado)
            print(f"[PASO 5/5] Sincronizando en Google Calendar...")
            event_id = create_calendar_event(action.get("title"), action.get("deadline"), notion_url)
            action["calendar_event_id"] = event_id
            
            acciones_procesadas.append(action)
            
        # 6. Registrar en Base de Datos de Monitoreo SQLite
        # Vinculamos la transacción al primer ticket en Notion para fines de trazabilidad rápida
        notion_principal_url = acciones_procesadas[0].get("notion_page_url", "")
        register_transaction(file_name, "SUCCESS", notion_url=notion_principal_url)
        
        # 7. Enviar Notificación de Éxito Enriquecida por Telegram
        print(f"[ORQUESTADOR] Enviando notificación de éxito enriquecida a Telegram...")
        send_success_notification(file_name, summary, acciones_procesadas)
        
        # Registrar hash en la sesión
        PROCESSED_HASHES.add(file_hash)
        print(f"[ORQUESTADOR] Processing completado con éxito para '{file_name}'.\n")
        return True
        
    except Exception as e:
        # MANEJO GLOBAL DE ERRORES: No interrumpe el orquestador
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"\n[ERROR] [ORQUESTADOR] Falló el procesamiento de '{file_name}': {error_msg}")
        
        # Registrar fallo en base de datos local y archivo JSON de errores físicos
        register_transaction(file_name, "FAILED", error_msg=error_msg)
        log_error(file_name, "ORCHESTRATOR_RUN", error_msg, traceback_str)
        
        # Enviar alerta en tiempo real a Telegram
        send_error_notification(file_name, "ORCHESTRATOR_RUN", error_msg)
        return True

# ==========================================
# BUILT-IN GOOGLE DRIVE POLLING LOOP (Evita problemas de Webhooks)
# ==========================================
async def poll_google_drive_loop():
    """Bucle infinito en segundo plano que busca nuevos archivos en Google Drive cada 60 segundos."""
    print("[POLLING] Iniciando bucle de monitoreo de Google Drive...")
    # Esperar unos segundos antes de la primera ejecución para dar tiempo al servidor de estar "Live"
    await asyncio.sleep(5)
    while True:
        try:
            print("[POLLING] Escaneando Google Drive de forma automatica...")
            # Correr en un hilo separado para no bloquear el loop asincrono principal de FastAPI
            await asyncio.to_thread(run_google_drive_processing)
        except Exception as e:
            print(f"[POLLING] Error en el bucle de Google Drive: {str(e)}")
        # Esperar 60 segundos antes de volver a escanear
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    """Evento que se ejecuta al arrancar el servidor FastAPI."""
    # Iniciar la tarea de escaneo continuo en segundo plano
    asyncio.create_task(poll_google_drive_loop())

# ==========================================
# INTERFAZ WEB DE MONITOREO (ROOT DASHBOARD)
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def dashboard_index():
    """Muestra un panel visual premium con el estado del servidor de automatizaciones."""
    drive_folder = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "No configurado")
    notion_db = os.getenv("NOTION_DATABASE_ID", "No configurado")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Automation Specialist | Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-color: #0b0f19;
                --card-bg: rgba(255, 255, 255, 0.03);
                --border-color: rgba(255, 255, 255, 0.08);
                --primary: #4f46e5;
                --primary-glow: rgba(79, 70, 229, 0.4);
                --success: #10b981;
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
            }}
            body {{
                font-family: 'Outfit', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-main);
                margin: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                background-image: 
                    radial-gradient(circle at 10% 20%, rgba(79, 70, 229, 0.15) 0%, transparent 40%),
                    radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.1) 0%, transparent 40%);
            }}
            .container {{
                width: 100%;
                max-width: 600px;
                padding: 2rem;
                box-sizing: border-box;
            }}
            .card {{
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 24px;
                padding: 2.5rem;
                backdrop-filter: blur(16px);
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                text-align: center;
                position: relative;
                overflow: hidden;
            }}
            .card::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(90deg, var(--primary), var(--success));
            }}
            h1 {{
                font-size: 2.2rem;
                font-weight: 800;
                margin-top: 0;
                margin-bottom: 0.5rem;
                background: linear-gradient(135deg, #fff 40%, var(--text-muted));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .subtitle {{
                color: var(--text-muted);
                font-size: 1rem;
                margin-bottom: 2rem;
            }}
            .status-badge {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: rgba(16, 185, 129, 0.1);
                color: var(--success);
                padding: 8px 16px;
                border-radius: 100px;
                font-weight: 600;
                font-size: 0.9rem;
                margin-bottom: 2.5rem;
                border: 1px solid rgba(16, 185, 129, 0.2);
                box-shadow: 0 0 20px rgba(16, 185, 129, 0.1);
            }}
            .pulse {{
                width: 10px;
                height: 10px;
                background-color: var(--success);
                border-radius: 50%;
                animation: pulse-animation 2s infinite;
            }}
            @keyframes pulse-animation {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
                70% {{ transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 16px;
                text-align: left;
                margin-bottom: 2rem;
            }}
            .stat-item {{
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 1rem 1.25rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .stat-label {{
                color: var(--text-muted);
                font-weight: 500;
                font-size: 0.9rem;
            }}
            .stat-value {{
                font-weight: 600;
                font-size: 0.9rem;
                color: #fff;
                max-width: 60%;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .footer {{
                font-size: 0.8rem;
                color: var(--text-muted);
                margin-top: 1.5rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h1>AI Specialist Activo</h1>
                <p class="subtitle">Orquestador de Automatizaciones en la Nube</p>
                
                <div class="status-badge">
                    <span class="pulse"></span>
                    Monitoreando Google Drive de forma activa
                </div>
                
                <div class="stats-grid">
                    <div class="stat-item">
                        <span class="stat-label">Google Drive Folder ID</span>
                        <span class="stat-value">{drive_folder}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Notion Database ID</span>
                        <span class="stat-value">{notion_db}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Telegram Status</span>
                        <span class="stat-value" style="color: #10b981;">Conectado</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Model LLM</span>
                        <span class="stat-value">DeepSeek v4 Flash</span>
                    </div>
                </div>
                
                <div class="footer">
                    Proyecto desarrollado para Prueba Tecnica BWS &copy; 2026
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

# ==========================================
# ENDPOINT WEBHOOK (FastAPI)
# ==========================================
@app.post("/webhook-drive")
async def drive_webhook_receiver(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint del Webhook que recibe las notificaciones de Google Drive.
    """
    headers = request.headers
    resource_state = headers.get("x-goog-resource-state")
    channel_id = headers.get("x-goog-channel-id")
    
    print(f"\n[WEBHOOK] Recibida notificacion de Drive. State: {resource_state}, Channel: {channel_id}")
    
    # Disparar la descarga y procesamiento real desde Google Drive en segundo plano
    background_tasks.add_task(run_google_drive_processing)
    
    return {"status": "accepted", "message": "Notification queued for processing."}

# ==========================================
# PROCESAMIENTO REAL DESDE GOOGLE DRIVE
# ==========================================
def run_google_drive_processing():
    """
    Se conecta a Google Drive, obtiene la lista de archivos de GOOGLE_DRIVE_FOLDER_ID,
    los descarga temporalmente y los procesa uno por uno.
    """
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id or folder_id == "AQUI_PON_EL_ID_DE_LA_CARPETA_DE_DRIVE" or "AQUI" in folder_id:
        print("[Aviso] GOOGLE_DRIVE_FOLDER_ID no configurado. Iniciando escaneo local en su lugar.")
        run_offline_batch_processing()
        return
        
    print("\n=========================================")
    print("INICIANDO PROCESAMIENTO DESDE GOOGLE DRIVE")
    print("=========================================\n")
    
    # Asegurar que exista una carpeta temporal de descargas
    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(base_dir, "temp_downloads")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Importación diferida para no requerir librerías si se corre offline local simple
        from drive_client import list_files_in_folder, download_file
        
        # 1. Listar archivos de la carpeta
        files = list_files_in_folder(folder_id)
        valid_extensions = {'.txt', '.md', '.docx', '.pdf', '.pptx'}
        
        # Filtrar solo archivos con extensiones válidas
        valid_files = []
        for f in files:
            name = f.get("name", "")
            ext = os.path.splitext(name.lower())[1]
            if ext in valid_extensions:
                valid_files.append(f)
                
        print(f"[ORQUESTADOR] Encontrados {len(valid_files)} archivos validos para procesar en Google Drive.")
        
        # 2. Procesar secuencialmente
        processed_any_new = False
        for gfile in valid_files:
            file_id = gfile["id"]
            file_name = gfile["name"]
            
            # Usar el hash del archivo de Google Drive (md5Checksum) o su file_id como deduplicación
            file_hash = gfile.get("md5Checksum", file_id)
            
            if file_hash in PROCESSED_HASHES:
                print(f"[ORQUESTADOR] Omitiendo '{file_name}' (Ya procesado en esta sesion).")
                continue
                
            dest_path = os.path.join(temp_dir, file_name)
            
            # Descargar archivo de Drive
            if download_file(file_id, dest_path):
                # Procesar archivo descargado
                was_processed = process_single_file(dest_path)
                if was_processed:
                    processed_any_new = True
                
                # Intentar borrar el archivo temporal para ahorrar espacio
                try:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                except Exception as e:
                    print(f"[Advertencia] No se pudo eliminar el archivo temporal {file_name}: {str(e)}")
                    
        # 3. Reporte Consolidado
        if processed_any_new:
            print("\n[ORQUESTADOR] Generando reporte diario consolidado de monitoreo...")
            reporte = get_daily_summary()
            send_telegram_message(reporte)
        
    except Exception as e:
        print(f"[ERROR CRITICO] Error durante el procesamiento de Google Drive: {str(e)}")
        send_error_notification("GOOGLE_DRIVE_SYNC", "GOOGLE_DRIVE_RUN", str(e))
        
    print("=========================================")
    print("PROCESAMIENTO DE GOOGLE DRIVE COMPLETADO")
    print("=========================================\n")

# ==========================================
# PROCESAMIENTO OFFLINE POR LOTES (Batch Mode)
# ==========================================
def run_offline_batch_processing():
    """
    Escanea la carpeta 'Documentos Prueba' local y procesa de forma secuencial todos los archivos.
    """
    # Usar ruta relativa para que funcione tanto en tu PC como en Render
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dir_prueba = os.path.join(base_dir, "Documentos Prueba")
    
    if not os.path.exists(dir_prueba):
        print(f"[Aviso] La carpeta de pruebas no existia en {dir_prueba}. Se creara automaticamente.")
        os.makedirs(dir_prueba, exist_ok=True)
        
    print("\n=========================================")
    print("INICIANDO ESCANEO DE DOCUMENTOS DE PRUEBA LOCAL")
    print("=========================================\n")
    
    # Extensiones de documentos soportadas
    valid_extensions = {'.txt', '.md', '.docx', '.pdf', '.pptx'}
    
    archivos = [
        os.path.join(dir_prueba, f) for f in os.listdir(dir_prueba)
        if os.path.splitext(f.lower())[1] in valid_extensions
    ]
    
    print(f"Se encontraron {len(archivos)} documentos listos para procesar.")
    
    # Procesar secuencialmente (Evita concurrencia en la API que causaria 429 adicionales)
    processed_any_new = False
    for archivo_path in archivos:
        was_processed = process_single_file(archivo_path)
        if was_processed:
            processed_any_new = True
        
    # Al terminar, enviar el Reporte Consolidado Diario por Telegram (Solo si se procesaron nuevos)
    if processed_any_new:
        print("\n[ORQUESTADOR] Generando reporte diario final de monitoreo...")
        reporte = get_daily_summary()
        send_telegram_message(reporte)
    print("=========================================")
    print("PROCESAMIENTO POR LOTES COMPLETADO")
    print("=========================================\n")

if __name__ == "__main__":
    import sys
    # Si se pasa el argumento '--server', levantamos FastAPI en Uvicorn para escuchar Webhooks reales
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        print("Iniciando Servidor Webhook FastAPI en el puerto 8000...")
        print("Recuerda exponer este puerto a internet usando: ngrok http 8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    elif len(sys.argv) > 1 and sys.argv[1] == "--local":
        # Ejecutar en Modo Batch local offline forzado
        run_offline_batch_processing()
    else:
        # Por defecto, intenta procesar desde Google Drive si el ID esta configurado
        run_google_drive_processing()
