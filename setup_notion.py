import os
import sys
import requests
import json
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

ENV_PATH = ".env"
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

if not NOTION_API_KEY:
    print("[Config] NOTION_API_KEY no encontrada en .env.")
    NOTION_API_KEY = input("Introduce tu Token de Notion (ntn_... o secret_...): ").strip()
    if not NOTION_API_KEY:
        print("❌ Error: Se requiere un token de Notion para continuar.")
        sys.exit(1)

def update_env_file(key: str, value: str):
    """Actualiza o añade una variable de entorno en el archivo .env."""
    lines = []
    key_exists = False
    
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            key_exists = True
            break
            
    if not key_exists:
        lines.append(f"{key}={value}\n")
        
    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"[Config] Actualizado .env: {key}={value}")

def search_shared_pages():
    """Busca las páginas que han sido compartidas con esta integración."""
    url = "https://api.notion.com/v1/search"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {
        "filter": {
            "property": "object",
            "value": "page"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        results = response.json().get("results", [])
        return results
    except Exception as e:
        print(f"[Error] No se pudo buscar en Notion: {e}")
        return []

def create_database(parent_page_id: str):
    """Crea la base de datos de tareas programáticamente en Notion."""
    url = "https://api.notion.com/v1/databases"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    payload = {
        "parent": {
            "type": "page_id",
            "page_id": parent_page_id
        },
        "title": [
            {
                "type": "text",
                "text": {
                    "content": "Tablero de Tareas Extraídas por IA"
                }
            }
        ],
        "properties": {
            "Tarea": {
                "title": {}
            },
            "Responsable": {
                "rich_text": {}
            },
            "Fecha Límite": {
                "date": {}
            },
            "Tipo": {
                "select": {
                    "options": [
                        {"name": "TASK_ONLY", "color": "blue"},
                        {"name": "DRAFT_REQUIRED", "color": "purple"}
                    ]
                }
            },
            "Documento de Origen": {
                "rich_text": {}
            },
            "Estado": {
                "status": {}
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        response.raise_for_status()
        result = response.json()
        db_id = result.get("id")
        db_url = result.get("url")
        print(f"\n=========================================")
        print(f"🎉 ¡BASE DE DATOS CREADA EN NOTION CON ÉXITO!")
        print(f"=========================================")
        print(f"ID de la Base de Datos: {db_id}")
        print(f"Enlace de la Base de Datos: {db_url}")
        print(f"=========================================\n")
        return db_id
    except Exception as e:
        print(f"[Error] Falló la creación de la base de datos: {e}")
        if 'response' in locals() and response is not None:
            print(f"Respuesta de la API: {response.text}")
        return None

def main():
    print("=========================================")
    print("CONFIGURADOR AUTOMÁTICO DE NOTION")
    print("=========================================\n")
    
    # 1. Actualizar el token de Notion en el archivo .env
    update_env_file("NOTION_API_KEY", NOTION_API_KEY)
    
    # 2. Buscar páginas compartidas
    print("[Notion] Buscando páginas que compartiste con el bot...")
    pages = search_shared_pages()
    
    if not pages:
        print("\n❌ [NOTION] ¡No se encontraron páginas compartidas!")
        print("----------------------------------------------------------------")
        print("Instrucciones de configuración obligatorias:")
        print("1. Abre tu espacio de trabajo de Notion en el navegador.")
        print("2. Ve a la página (o crea una nueva) donde quieres crear la base de datos.")
        print("3. Haz clic en los tres puntos (...) en la esquina superior derecha.")
        print("4. Selecciona '+ Add connections' (o Agregar conexiones).")
        print("5. Busca y selecciona tu bot/integración con el token proporcionado.")
        print("6. Haz clic en 'Confirm' para darle acceso a la página.")
        print("7. Vuelve a ejecutar este configurador: 'python setup_notion.py'")
        print("----------------------------------------------------------------\n")
        sys.exit(1)
        
    # 3. Utilizar la primera página encontrada como padre
    parent_page = pages[0]
    parent_id = parent_page.get("id")
    parent_title = "Página de Notion"
    try:
        parent_title = parent_page.get("properties", {}).get("title", {}).get("title", [{}])[0].get("text", {}).get("content", "Página de Notion")
    except Exception:
        pass
        
    print(f"[Notion] Encontrada página compartida: '{parent_title}' (ID: {parent_id})")
    print(f"[Notion] Creando la base de datos estructurada con las columnas requeridas...")
    
    db_id = create_database(parent_id)
    
    if db_id:
        # 4. Registrar el Database ID en el archivo .env
        update_env_file("NOTION_DATABASE_ID", db_id)
        print("🏁 ¡Configuración completada con éxito! Notion ahora está en MODO REAL.")
    else:
        print("❌ Falló la configuración de la base de datos.")

if __name__ == "__main__":
    main()
