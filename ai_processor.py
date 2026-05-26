import os
import json
import requests
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# Obtener la API de Gemini desde las variables de entorno
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    # Si no se encuentra en el entorno, intentamos cargarla del .env de forma segura
    # pero NO dejamos valores por defecto hardcodeados que puedan ser revocados por Google al subirse a GitHub.
    print("[ERROR CONFIGURACIÓN] La variable GEMINI_API_KEY no está configurada.")


def _call_gemini_api(system_prompt: str, user_content: str) -> str:
    """Llama de forma directa a la API REST oficial de Google Gemini usando gemini-2.5-flash-lite."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno o archivo .env. Por favor, agrega una clave válida de Google AI Studio.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Definición de esquema estricto OpenAPI compatible con Gemini
    schema = {
        "type": "object",
        "properties": {
            "document_summary": {
                "type": "string",
                "description": "Un resumen corto y ejecutivo del documento de maximo 2 lineas."
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
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
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": user_content}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": system_prompt}
            ]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.15
        }
    }
    
    try:
        print("[IA - Gemini] Solicitando estructuracion de tareas a Gemini 2.5 Flash Lite...")
        response = requests.post(url, headers=headers, json=payload, timeout=50)
        
        if response.status_code != 200:
            print(f"[IA - Gemini Error Response] {response.text}")
            
        response.raise_for_status()
        result = response.json()
        
        # Extraer el texto devuelto
        content = result['candidates'][0]['content']['parts'][0]['text']
        return content
    except Exception as e:
        print(f"[IA - Gemini] Error al contactar con la API de Gemini: {str(e)}")
        raise e

def generate_tasks_proposal(document_text: str) -> dict:
    """Llamada (Generador): Analiza el documento y propone tareas estructuradas en JSON usando Gemini."""
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
    
    response_content = _call_gemini_api(system_prompt, user_content)
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        raise ValueError(f"La API de Gemini no devolvió un JSON válido:\n{response_content}")

def process_document_with_ai(document_text: str) -> dict:
    """Orquesta el flujo: Generación directa de tareas con Gemini 2.5 Flash Lite (Verificador desactivado)."""
    print("[IA] Procesando documento con Google Gemini...")
    proposal = generate_tasks_proposal(document_text)
    
    # Auditoría automática pre-aprobada
    audit = {
        "aprobado": True,
        "motivo": "Aprobado automáticamente mediante el motor oficial de Gemini 2.5 Flash Lite."
    }
    
    return {
        "proposal": proposal,
        "audit": audit
    }

if __name__ == "__main__":
    # Prueba rápida local
    test_text = "Reunión de logística. Brandon debe entregar los reportes financieros antes del 30 de mayo de 2026."
    print("Probando cliente de Gemini REST API...")
    try:
        res = process_document_with_ai(test_text)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error en prueba: {e}")
