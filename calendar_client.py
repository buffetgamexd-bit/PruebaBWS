import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Intentar importaciones de la API de Google, silenciando advertencias si no están instaladas aún
# (Ya que el modo simulación no las requiere, y permite ejecutar el script de inmediato)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    service_account = None
    build = None

GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")

def is_calendar_configured() -> bool:
    """Verifica si las librerías y las credenciales físicas de Google Calendar están disponibles."""
    if not GOOGLE_LIBS_AVAILABLE:
        return False
    if not GOOGLE_CREDENTIALS_FILE or not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        return False
    return True

def create_calendar_event(task_title: str, deadline_str: str, notion_url: str) -> str:
    """
    Agenda un evento de fecha límite en Google Calendar.
    Soporta modo simulación (si no hay credenciales) y modo real (si las credenciales físicas existen).
    Retorna el ID del evento de calendario creado (real o simulado).
    """
    if not deadline_str or deadline_str == "No especificada":
        print(f"[Calendar] Omitiendo agendado de evento para '{task_title}' (No tiene fecha límite).")
        return "No_Deadline"
        
    if not is_calendar_configured():
        # MODO SIMULACIÓN LOCAL (Perfecto para demostraciones y pruebas rápidas)
        print(f"[Calendar - SIMULACIÓN] Agendando evento: '{task_title}' para la fecha {deadline_str}")
        print(f"[Calendar - SIMULACIÓN] Contexto incrustado (Notion Link): {notion_url}")
        # Generar un ID hexadecimal simulado único basado en el hash del título
        import hashlib
        simulated_event_id = hashlib.md5(task_title.encode('utf-8')).hexdigest()[:26]
        print(f"[Calendar - SIMULACIÓN] Evento creado con ID: {simulated_event_id}")
        return simulated_event_id
        
    # MODO REAL (Sincronización con la API de Google Calendar v3)
    print(f"[Calendar] Conectando con Google Calendar API...")
    try:
        # Cargar credenciales de Service Account
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        service = build('calendar', 'v3', credentials=creds)
        
        # Google Calendar requiere fechas en formato ISO 8601 (con hora y zona horaria)
        # Seteamos el evento para durar todo el día o un bloque de 1 hora
        event_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        
        event_body = {
            'summary': f"⏰ Límite: {task_title}",
            'description': f"Tarea automatizada extraída de los documentos.\n\n🔗 Enlace Notion:\n{notion_url}",
            'start': {
                'date': event_date.isoformat(),
                'timeZone': 'America/Mexico_City',
            },
            'end': {
                'date': (event_date + timedelta(days=1)).isoformat(), # Todo el día
                'timeZone': 'America/Mexico_City',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60}, # 1 día antes
                    {'method': 'popup', 'minutes': 60},      # 1 hora antes
                ],
            },
        }
        
        event = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body).execute()
        event_id = event.get('id')
        event_link = event.get('htmlLink')
        print(f"[Calendar] ¡Evento agendado exitosamente!: {event_link}")
        return event_id
        
    except Exception as e:
        raise RuntimeError(f"Error al conectar o insertar en Google Calendar: {e}")

if __name__ == "__main__":
    # Prueba rápida del componente de Google Calendar en modo simulación
    print("Probando conector de Google Calendar...")
    task_name = "Actualizar proyecciones financieras y deck"
    limit = "2026-05-23"
    notion_link = "https://notion.so/test-page-xyz"
    
    event_id = create_calendar_event(task_name, limit, notion_link)
    print(f"ID del evento resultante: {event_id}")
