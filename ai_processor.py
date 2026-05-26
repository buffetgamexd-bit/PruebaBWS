import os
import json
import requests
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash:free")

if not OPENROUTER_API_KEY:
    raise ValueError("Error: OPENROUTER_API_KEY no está configurada en el archivo .env")

import time

def _call_openrouter(messages, json_mode=True):
    """Llama a la API de OpenRouter con soporte de reintentos y failover/fallback robusto ante errores 429."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/brandon/ai-automation-test",
        "X-Title": "AI Automation Specialist Test"
    }
    
    # Cola de modelos gratuitos a intentar si el principal está ocupado o arroja 429
    modelos_a_intentar = [
        "liquid/lfm-2.5-1.2b-instruct:free",
        OPENROUTER_MODEL,
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free"
    ]
    
    # Eliminar duplicados manteniendo el orden
    modelos_a_intentar = list(dict.fromkeys([m for m in modelos_a_intentar if m]))
    
    ultimo_error = None
    for modelo in modelos_a_intentar:
        max_reintentos = 3
        for intento in range(max_reintentos):
            print(f"[IA] Intentando llamada con: {modelo} (Intento {intento + 1}/{max_reintentos})...")
            payload = {
                "model": modelo,
                "messages": messages,
                "temperature": 0.2
            }
            
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
                
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=45)
                
                if response.status_code == 429:
                    segundos_espera = 4
                    try:
                        err_json = response.json()
                        metadata = err_json.get("error", {}).get("metadata", {})
                        # Intentar leer el tiempo recomendado por OpenRouter, por defecto 4
                        segundos_espera = int(float(metadata.get("retry_after_seconds", segundos_espera)))
                    except Exception:
                        pass
                    
                    print(f"[IA] Advertencia: '{modelo}' rate-limited (429). Esperando {segundos_espera}s para reintentar...")
                    time.sleep(segundos_espera)
                    ultimo_error = f"429 Client Error para {modelo}"
                    continue # Reintentar en el mismo modelo
                    
                response.raise_for_status()
                result = response.json()
                content = result['choices'][0]['message']['content']
                return content
            except Exception as e:
                print(f"[IA] Error al usar '{modelo}': {e}")
                ultimo_error = e
                # Ante excepciones o fallos de red, saltamos directamente al siguiente modelo
                break
            
    raise RuntimeError(f"Todos los modelos gratuitos de OpenRouter fallaron. Último error: {ultimo_error}")

def generate_tasks_proposal(document_text):
    """Llamada 1 (Generador): Analiza el documento y propone tareas estructuradas en JSON."""
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
        "Debes responder EXCLUSIVAMENTE en formato JSON con el siguiente esquema:\n"
        "{\n"
        "  \"document_summary\": \"Resumen ejecutivo del documento de 2 líneas.\",\n"
        "  \"actions\": [\n"
        "    {\n"
        "      \"title\": \"Título corto y descriptivo de la tarea\",\n"
        "      \"description\": \"Descripción detallada del contexto y de lo que debe realizarse\",\n"
        "      \"type\": \"TASK_ONLY\" o \"DRAFT_REQUIRED\",\n"
        "      \"responsible\": \"Nombre del responsable\",\n"
        "      \"deadline\": \"YYYY-MM-DD\",\n"
        "      \"draft_content\": \"Borrador profesional completo redactado (solo si type es DRAFT_REQUIRED, si no, string vacío)\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"DOCUMENTO A ANALIZAR:\n\n{document_text}"}
    ]
    
    response_content = _call_openrouter(messages, json_mode=True)
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        raise ValueError(f"La IA no devolvió un JSON válido en la llamada del Generador:\n{response_content}")

def audit_tasks_proposal(document_text, proposal_json):
    """Llamada 2 (Crítico): Toma el texto original y la propuesta, y emite un veredicto de calidad."""
    system_prompt = (
        "Eres un Auditor de Calidad de IA de élite. Tu trabajo es verificar críticamente si las tareas extraídas "
        "por el primer modelo (el Generador) a partir del documento original son 100% correctas, completas y libres de alucinaciones (inventos o exageraciones).\n\n"
        "Debes realizar un análisis comparativo estricto e identificar quién está cometiendo un error o alucinando (el Generador es quien alucina si inventa datos que NO están en el Documento Original, ya que el Documento Original es la Verdad Absoluta).\n\n"
        "Criterios de Auditoría obligatorios:\n"
        "1. ANÁLISIS DE ALUCINACIONES: Revisa cada tarea propuesta. Si el Generador incluyó plazos, nombres o tareas que NO se mencionan ni se infieren de manera lógica en el Documento, detállalo como una alucinación del Generador.\n"
        "2. ANÁLISIS DE DISCREPANCIAS: Si hay una discrepancia (ej. el Generador dice que la fecha es el 30 de mayo pero el Documento dice el 15 de mayo), explica explícitamente: 'El Generador alucinó la fecha [Fecha Propuesta] cuando el Documento original dice claramente [Fecha Real]'.\n"
        "3. FIDELIDAD: ¿Las tareas corresponden de verdad a obligaciones reales mencionadas en el texto? (Falso = No aprobado)\n"
        "4. RESPONSABLES: ¿Los responsables asignados coinciden exactamente con los mencionados en el texto?\n"
        "5. CALIDAD DEL BORRADOR: ¿El borrador en 'draft_content' es profesional, útil, formal y en español?\n\n"
        "Debes responder EXCLUSIVAMENTE en formato JSON con el siguiente esquema:\n"
        "{\n"
        "  \"aprobado\": true o false,\n"
        "  \"motivo\": \"Explicación extremadamente específica y comparativa. Detalla paso a paso qué tareas fueron correctas, cuáles fueron alucinadas por el Generador, y qué dice exactamente el Documento Original para desmentir al Generador en cada discrepancia.\"\n"
        "}"
    )
    
    user_content = (
        f"DOCUMENTO ORIGINAL:\n\n{document_text}\n\n"
        f"PROPUESTA DE TAREAS EXTRAÍDAS:\n\n{json.dumps(proposal_json, indent=2, ensure_ascii=False)}"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    response_content = _call_openrouter(messages, json_mode=True)
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        raise ValueError(f"La IA no devolvió un JSON válido en la llamada del Crítico:\n{response_content}")

def process_document_with_ai(document_text):
    """Orquesta el flujo: Generacion directa de tareas con DeepSeek (Verificador desactivado)."""
    print("[IA] Generando propuesta de tareas con DeepSeek...")
    proposal = generate_tasks_proposal(document_text)
    
    # Verificador desactivado a solicitud del usuario para evitar rechazos
    audit = {
        "aprobado": True,
        "motivo": "Aprobado automaticamente (Verificador de Calidad desactivado)."
    }
    
    return {
        "proposal": proposal,
        "audit": audit
    }

if __name__ == "__main__":
    # Prueba rápida del componente con el documento correo legal
    from document_parser import parse_document
    
    test_file = r"c:\Users\brand\Desktop\PruebaBrandon\Documentos Prueba\doc correo_legal.txt"
    if os.path.exists(test_file):
        print(f"Probando ai_processor con: {os.path.basename(test_file)}")
        texto = parse_document(test_file)
        try:
            resultado = process_document_with_ai(texto)
            print("\n=========================================")
            print("PROPUESTA GENERADA:")
            print(json.dumps(resultado["proposal"], indent=2, ensure_ascii=False))
            print("\n=========================================")
            print("VEREDICTO DEL CRÍTICO:")
            print(json.dumps(resultado["audit"], indent=2, ensure_ascii=False))
            print("=========================================\n")
        except Exception as e:
            print(f"Error en el procesamiento de IA: {e}")
    else:
        print(f"No se encontró el archivo de prueba en {test_file}")
