import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def is_notion_configured() -> bool:
    """Verifica si las credenciales de Notion están provistas."""
    return bool(NOTION_API_KEY and NOTION_DATABASE_ID)

def create_task_ticket(file_name: str, task: dict, file_url: str = None) -> str:
    """
    Crea un ticket de tarea en Notion.
    Soporta modo simulación (si no hay API Keys) y modo real (si están configuradas).
    Retorna el URL del ticket creado (real o simulado).
    """
    title = task.get("title", "Tarea sin título")
    description = task.get("description", "Sin descripción")
    responsible = task.get("responsible", "No especificado")
    deadline = task.get("deadline", "No especificada")
    task_type = task.get("type", "TASK_ONLY")
    draft_content = task.get("draft_content", "")
    
    if not is_notion_configured():
        # MODO SIMULACIÓN LOCAL (Perfecto para probar sin configurar APIs inmediatamente)
        print(f"[Notion - SIMULACIÓN] Creando ticket: '{title}' asignado a {responsible}")
        # Generar un ID hexadecimal simulado único basado en el hash del título
        import hashlib
        simulated_id = hashlib.md5(title.encode('utf-8')).hexdigest()[:32]
        simulated_url = f"https://notion.so/simulated-workspace/{simulated_id}"
        print(f"[Notion - SIMULACIÓN] Ticket simulado creado con éxito: {simulated_url}")
        return simulated_url
        
    # MODO REAL (Sincronización con la API oficial de Notion)
    print(f"[Notion] Sincronizando ticket real: '{title}'...")
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    # Resolver la URL del archivo de Drive. Si no viene, usamos una URL de Drive por defecto
    valid_file_url = file_url if file_url else "https://drive.google.com"
    
    # Propiedades básicas del ticket (Omitimos 'Estado' para que Notion use el valor por defecto de tu idioma y evitar errores 400)
    # Formateamos 'Documento de Origen' como Files & Media para que guarde el archivo adjunto real.
    properties = {
        "Tarea": {
            "title": [{"text": {"content": title}}]
        },
        "Responsable": {
            "rich_text": [{"text": {"content": responsible}}]
        },
        "Documento de Origen": {
            "files": [
                {
                    "name": file_name,
                    "type": "external",
                    "external": {"url": valid_file_url}
                }
            ]
        },
        "Tipo": {
            "select": {"name": task_type}
        }
    }
    
    # Agregar fecha límite si es válida
    if deadline and deadline != "No especificada":
        properties["Fecha Límite"] = {
            "date": {"start": deadline}
        }
        
    # Construir contenido interno (cuerpo de la página con descripción y borrador de IA)
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": "📋 Descripción de la Tarea"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": description}}]
            }
        }
    ]
    
    # Inyectar el borrador enriquecido redactado por la IA si corresponde
    if task_type == "DRAFT_REQUIRED" and draft_content:
        children.extend([
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "🤖 Borrador Generado por IA"}}]
                }
            },
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"text": {"content": draft_content}}],
                    "icon": {"emoji": "📝"},
                    "color": "gray_background"
                }
            }
        ])
        
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
        "children": children
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code != 200 and response.status_code != 201:
            print(f"[Notion API Error Response] {response.text}")
        response.raise_for_status()
        result = response.json()
        notion_url = result.get("public_url") or result.get("url") or "https://notion.so"
        print(f"[Notion] ¡Ticket creado con éxito en Notion!: {notion_url}")
        return notion_url
    except requests.exceptions.HTTPError as e:
        error_details = response.text if 'response' in locals() else str(e)
        raise RuntimeError(f"Detalle de error Notion: {error_details}")
    except Exception as e:
        raise RuntimeError(f"Error inesperado al conectar con la API de Notion: {e}")

if __name__ == "__main__":
    # Prueba rápida en modo simulación
    print("Probando conector de Notion...")
    tarea_test = {
        "title": "Enviar term sheet a revisión legal",
        "description": "Enviar term sheet al despacho jurídico para revisar la cláusula de liquidación de Grupo Inversión.",
        "responsible": "Ana Sofía Campos",
        "deadline": "2026-05-15",
        "type": "DRAFT_REQUIRED",
        "draft_content": "Estimados licenciados, adjunto compartimos el term sheet para su revisión urgente..."
    }
    
    url = create_task_ticket("doc minuta startup.docx", tarea_test)
    print(f"URL resultante: {url}")
