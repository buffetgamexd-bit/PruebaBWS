import os
import json
import requests
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# Obtener la API de Claude desde las variables de entorno
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

if not CLAUDE_API_KEY:
    print("[ERROR CONFIGURACIÓN] La variable CLAUDE_API_KEY no está configurada.")

def _call_claude_api(system_prompt: str, user_content: str) -> str:
    """Llama de forma directa a la API REST oficial de Anthropic Claude usando claude-sonnet-4-6."""
    if not CLAUDE_API_KEY:
        raise ValueError("CLAUDE_API_KEY no está configurada en las variables de entorno o archivo .env. Por favor, agrega una clave válida de Anthropic.")
        
    url = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    # Definición de esquema compatible con Claude (requiere additionalProperties: False)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "document_summary": {
                "type": "string",
                "description": "Un resumen corto y ejecutivo del documento de maximo 2 lineas."
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string", "description": "Titulo corto, accionable y profesional para el ticket."},
                        "description": {"type": "string", "description": "Descripcion exhaustiva del contexto de la tarea."},
                        "type": {
                            "type": "string", 
                            "enum": ["TASK_ONLY", "DRAFT_REQUIRED"],
                            "description": "Usa DRAFT_REQUIRED si el texto pide responder, redactar o preparar un correo/carta/comunicado. Si no, TASK_ONLY."
                        },
                        "responsible": {"type": "string", "description": "Nombre de la persona responsable. Si no hay, pon 'No asignado'."},
                        "deadline": {"type": "string", "description": "Plazo en formato YYYY-MM-DD. Si no hay ni se deduce, pon 'No especificada'."},
                        "draft_content": {"type": "string", "description": "Borrador completo, profesional, pulido y en español. SIN placeholders (ej: no usar [Nombre]). Si es TASK_ONLY, dejar vacio."}
                    },
                    "required": ["title", "description", "type", "responsible", "deadline", "draft_content"]
                }
            }
        },
        "required": ["document_summary", "actions"]
    }
    
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4000,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_content}
        ],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": schema
            }
        },
        "temperature": 0.15
    }
    
    try:
        print("[IA - Claude] Solicitando estructuracion de tareas a Claude Sonnet 4.6...")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            print(f"[IA - Claude Error Response] {response.text}")
            
        response.raise_for_status()
        result = response.json()
        
        # Extraer el texto devuelto en structured outputs
        content = result['content'][0]['text']
        return content
    except Exception as e:
        print(f"[IA - Claude] Error al contactar con la API de Claude: {str(e)}")
        raise e

def generate_tasks_proposal(document_text: str) -> dict:
    """Llamada (Generador): Analiza el documento y propone tareas estructuradas en JSON usando Claude."""
    system_prompt = (
        "Eres un Extractor de Acciones Corporativas de élite. Tu objetivo es analizar el documento adjunto "
        "y extraer TODAS las obligaciones o tareas accionables, plazos de entrega y responsables de manera muy rigurosa.\n\n"
        "Reglas estrictas:\n"
        "1. Identifica las acciones claras que deben ejecutarse a partir del texto.\n"
        "2. Para cada tarea identificada, si implica redactar algo (un correo de respuesta, una carta formal, un comunicado, etc.), "
        "debes clasificar el tipo como 'DRAFT_REQUIRED' y escribir un borrador profesional, formal, completo, pulido "
        "y en español en la propiedad 'draft_content'. No utilices placeholders genéricos (ej. '[Nombre del cliente]'); "
        "deduce o infiere la información del documento original. Si es una tarea puramente operativa, clasifícala como 'TASK_ONLY'.\n"
        "3. Infiere la fecha límite en formato YYYY-MM-DD basándote en los datos del documento (ej. si el documento tiene "
        "fecha de mayo de 2026 y dice 'entrega antes del 16 de mayo', la fecha es 2026-05-16). Si no hay fecha mencionada "
        "ni se puede deducir, pon 'No especificada'.\n"
        "4. Asigna el responsable real mencionado. Si no se menciona a nadie específico, pon 'No asignado'.\n\n"
        "Debes responder en el formato JSON estructurado segun la definicion provista."
    )
    
    user_content = f"DOCUMENTO A ANALIZAR:\n\n{document_text}"
    
    response_content = _call_claude_api(system_prompt, user_content)
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        raise ValueError(f"La API de Claude no devolvió un JSON válido:\n{response_content}")

def process_document_with_ai(document_text: str) -> dict:
    """Orquesta el flujo: Generación directa de tareas con Claude Sonnet 4.6 (Verificador desactivado)."""
    print("[IA] Procesando documento con Anthropic Claude...")
    proposal = generate_tasks_proposal(document_text)
    
    # Auditoría automática pre-aprobada
    audit = {
        "aprobado": True,
        "motivo": "Aprobado automáticamente mediante el motor oficial de Claude Sonnet 4.6."
    }
    
    return {
        "proposal": proposal,
        "audit": audit
    }

if __name__ == "__main__":
    # Prueba rápida local
    test_text = "Reunión de logística. Brandon debe entregar los reportes financieros antes del 30 de mayo de 2026."
    print("Probando cliente de Claude REST API...")
    try:
        res = process_document_with_ai(test_text)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error en prueba: {e}")
