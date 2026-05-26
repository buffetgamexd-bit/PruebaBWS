import os
import hashlib
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
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

def process_single_file(file_path: str):
    """Orquesta la transacción completa de procesamiento para un solo documento."""
    file_name = os.path.basename(file_path)
    print(f"\n=========================================")
    print(f"[ORQUESTADOR] Iniciando procesamiento de: {file_name}")
    print(f"=========================================\n")
    
    # 1. Deduplicación por hash
    file_hash = calculate_file_hash(file_path)
    if file_hash in PROCESSED_HASHES:
        print(f"[ORQUESTADOR] Omitiendo '{file_name}' (Ya fue procesado en esta sesión).")
        return
    
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
            return
            
        # CASO APROBADO: Continuar a integraciones Notion & Calendar
        print(f"[PASO 3/5] [APROBADO] APROBADO por el Crítico de IA. Iniciando registro...")
        summary = proposal.get("document_summary", "No summary generated.")
        raw_actions = proposal.get("actions", [])
        
        if not raw_actions:
            print(f"[ORQUESTADOR] Advertencia: No se extrajeron tareas accionables en '{file_name}'.")
            register_transaction(file_name, "SUCCESS", error_msg="No se extrajeron tareas accionables.")
            send_telegram_message(f"ℹ️ <b>[SISTEMA]</b> El documento <code>{file_name}</code> fue aprobado pero no contenía acciones implícitas.")
            PROCESSED_HASHES.add(file_hash)
            return
            
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
    
    print(f"\n[WEBHOOK] Recibida notificación de Drive. State: {resource_state}, Channel: {channel_id}")
    
    # En producción, consultaríamos la API de Google Drive para obtener los nuevos archivos agregados.
    # En este prototipo, disparamos el escaneo de los archivos nuevos en la carpeta de prueba en segundo plano.
    background_tasks.add_task(run_offline_batch_processing)
    
    return {"status": "accepted", "message": "Notification queued for processing."}

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
        print(f"Error: La carpeta de pruebas no existe en {dir_prueba}")
        return
        
    print("\n=========================================")
    print("INICIANDO ESCANEO DE DOCUMENTOS DE PRUEBA")
    print("=========================================\n")
    
    # Extensiones de documentos soportadas
    valid_extensions = {'.txt', '.md', '.docx', '.pdf', '.pptx'}
    
    archivos = [
        os.path.join(dir_prueba, f) for f in os.listdir(dir_prueba)
        if os.path.splitext(f.lower())[1] in valid_extensions
    ]
    
    print(f"Se encontraron {len(archivos)} documentos listos para procesar.")
    
    # Procesar secuencialmente (Evita concurrencia en la API que causaría 429 adicionales)
    for archivo_path in archivos:
        process_single_file(archivo_path)
        
    # Al terminar, enviar el Reporte Consolidado Diario por Telegram
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
    else:
        # Por defecto, ejecutamos en Modo Batch offline procesando los archivos locales
        run_offline_batch_processing()
