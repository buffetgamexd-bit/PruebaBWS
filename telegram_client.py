import os
import requests
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8774600944:AAEzEQzDMeLJpuZMbk7wv4LblG_osVP2hdY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5479231410")

def send_telegram_message(message: str) -> bool:
    """Envia un mensaje enriquecido (soporta HTML) al chat de Telegram configurado."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Error: Credenciales de Telegram no configuradas.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] Error al enviar mensaje: {e}")
        return False

def send_success_notification(file_name: str, summary: str, actions: list) -> bool:
    """Envía un reporte de éxito súper enriquecido y con un diseño estético impecable."""
    msg = (
        "🚀 <b>[SISTEMA AUTOMÁTICO] ¡Procesamiento Exitoso!</b>\n\n"
        f"📄 <b>Documento:</b> <code>{file_name}</code>\n"
        f"💡 <b>Resumen:</b> <i>{summary}</i>\n\n"
        "📋 <b>Tareas Registradas en Notion:</b>\n"
    )
    
    for i, action in enumerate(actions, 1):
        responsible = action.get("responsible", "No asignado")
        deadline = action.get("deadline", "No especificada")
        title = action.get("title", "Tarea sin título")
        notion_url = action.get("notion_page_url", "#")
        
        msg += (
            f"  {i}. <b>{title}</b>\n"
            f"     👤 <i>Responsable:</i> {responsible}\n"
            f"     📅 <i>Fecha Límite:</i> {deadline}\n"
        )
        if notion_url and notion_url != "#":
            msg += f"     🔗 <a href='{notion_url}'>Abrir Ticket en Notion</a>\n"
        else:
            msg += "     🔗 <i>Notion: Sincronizado correctamente</i>\n"
        msg += "\n"
        
    msg += "✨ <i>Los plazos ya se han programado en Google Calendar.</i>"
    return send_telegram_message(msg)

def send_rejection_notification(file_name: str, audit_reason: str) -> bool:
    """Envía una alerta visual e inmediata cuando el Crítico de la IA desaprueba la propuesta."""
    msg = (
        "⚠️ <b>[CALIDAD IA] Tareas Rechazadas por el Auditor</b>\n\n"
        f"📄 <b>Documento:</b> <code>{file_name}</code>\n"
        "❌ <b>Resultado de Auditoría:</b> RECHAZADO\n\n"
        f"🗣️ <b>Motivo del Auditor:</b>\n{audit_reason}\n\n"
        "🛑 <i>La tarea ha sido descartada para proteger la integridad de Notion. Se requiere revisión manual.</i>"
    )
    return send_telegram_message(msg)

def send_error_notification(file_name: str, phase: str, error_msg: str) -> bool:
    """Envía una alerta urgente en caso de fallo técnico de infraestructura o de red."""
    msg = (
        "🚨 <b>[SISTEMA] Alerta de Fallo Técnico Crítico</b>\n\n"
        f"📄 <b>Documento:</b> <code>{file_name}</code>\n"
        f"⚙️ <b>Fase del Flujo:</b> <code>{phase}</code>\n"
        f"💥 <b>Mensaje de Error:</b>\n<code>{error_msg}</code>\n\n"
        "📁 <i>Los detalles técnicos y stack trace se han registrado en <b>error_logs.json</b>.</i>"
    )
    return send_telegram_message(msg)

if __name__ == "__main__":
    # Prueba rápida del notificador de Telegram
    print("Probando envío de notificaciones de Telegram...")
    
    # Probar mensaje de prueba básico
    send_telegram_message("🔌 <b>Prueba de conexión:</b> Bot de Telegram activo y respondiendo.")
    
    # Probar mensaje de éxito simulado
    acciones_ejemplo = [
        {
            "title": "Enviar term sheet a revisión legal",
            "responsible": "Ana Sofía Campos",
            "deadline": "2026-05-15",
            "notion_page_url": "https://notion.so/test-page-id-1"
        },
        {
            "title": "Preparar acceso a data room para Grupo Inversión",
            "responsible": "Martín Espinoza",
            "deadline": "2026-05-21",
            "notion_page_url": "https://notion.so/test-page-id-2"
        }
    ]
    
    exito = send_success_notification(
        "doc minuta startup.docx", 
        "Minuta de NovaTech Solutions sobre Serie A y due diligence.", 
        acciones_ejemplo
    )
    
    if exito:
        print("¡Prueba de Telegram completada con éxito!")
    else:
        print("Falló el envío de prueba de Telegram.")
