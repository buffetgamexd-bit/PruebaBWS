import os
import json
import sqlite3
from datetime import datetime

ERROR_LOG_PATH = "error_logs.json"
DB_PATH = "monitoring.db"

def init_db():
    """Inicializa la base de datos SQLite de monitoreo."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            status TEXT,          -- 'SUCCESS', 'REJECTED_BY_CRITIC', 'FAILED'
            error_message TEXT,
            notion_page_url TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_error(file_name: str, phase: str, error_msg: str, traceback_str: str = ""):
    """Escribe un log de error estructurado en el archivo error_logs.json."""
    error_entry = {
        "timestamp": datetime.now().isoformat(),
        "file_name": file_name,
        "phase": phase,
        "error_type": error_msg.split(":")[0] if ":" in error_msg else "Exception",
        "message": error_msg,
        "stack_trace": traceback_str
    }
    
    # Leer logs anteriores
    logs = []
    if os.path.exists(ERROR_LOG_PATH):
        try:
            with open(ERROR_LOG_PATH, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    logs = json.loads(content)
        except Exception as e:
            print(f"[Logger] Advertencia al leer error_logs.json: {e}")
            
    # Añadir nuevo log
    logs.append(error_entry)
    
    # Escribir de vuelta
    try:
        with open(ERROR_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Logger] Error al escribir en error_logs.json: {e}")

def register_transaction(file_name: str, status: str, error_msg: str = "", notion_url: str = ""):
    """Registra una transacción completa en la base de datos de monitoreo SQLite."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transactions (file_name, status, error_message, notion_page_url, timestamp) VALUES (?, ?, ?, ?, ?)",
            (file_name, status, error_msg, notion_url, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Logger] Error al registrar transacción en SQLite: {e}")
        # Intentar resguardar en logs de texto si falla la base de datos
        log_error(file_name, "SQLITE_LOG", f"Fallo al guardar en SQLite: {e}")

def is_file_already_processed(file_name: str) -> bool:
    """Consulta la base de datos SQLite para verificar si el archivo ya se procesó con éxito."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE file_name = ? AND status = 'SUCCESS'",
            (file_name,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        print(f"[Logger] Error al consultar historial en SQLite: {e}")
        return False

def get_recent_transactions(limit=10):
    """Devuelve la lista de las últimas transacciones registradas en SQLite."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_name, status, error_message, notion_page_url, timestamp FROM transactions ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        transactions = []
        for row in rows:
            transactions.append(dict(row))
        conn.close()
        return transactions
    except Exception as e:
        print(f"[Logger] Error al obtener transacciones recientes: {e}")
        return []

def get_daily_summary() -> str:
    """Genera un reporte consolidado en Markdown/HTML de la ejecución diaria."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Obtener estadísticas básicas del día actual (hoy)
        hoy = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute(
            "SELECT status, COUNT(*) FROM transactions WHERE timestamp LIKE ? GROUP BY status",
            (f"{hoy}%",)
        )
        stats = dict(cursor.fetchall())
        
        total_exito = stats.get("SUCCESS", 0)
        total_rechazos = stats.get("REJECTED_BY_CRITIC", 0)
        total_fallos = stats.get("FAILED", 0)
        total_procesados = total_exito + total_rechazos + total_fallos
        
        # Obtener los últimos fallos o rechazos para el reporte
        cursor.execute(
            "SELECT file_name, status, error_message FROM transactions WHERE timestamp LIKE ? AND status != 'SUCCESS' ORDER BY timestamp DESC LIMIT 5",
            (f"{hoy}%",)
        )
        detalles_fallos = cursor.fetchall()
        
        conn.close()
        
        summary = (
            "📊 <b>[REPORTE CONSOLIDADO DIARIO]</b>\n\n"
            f"📅 <b>Fecha:</b> <code>{hoy}</code>\n"
            f"🔄 <b>Total de Documentos Procesados:</b> <code>{total_procesados}</code>\n\n"
            f"✅ <i>Exitosos:</i> <code>{total_exito}</code>\n"
            f"⚠️ <i>Rechazados por Calidad:</i> <code>{total_rechazos}</code>\n"
            f"🚨 <i>Fallidos Técnicamente:</i> <code>{total_fallos}</code>\n\n"
        )
        
        if detalles_fallos:
            summary += "🔍 <b>Detalles de Incidencias a Revisar:</b>\n"
            for file, status, error in detalles_fallos:
                icono = "❌" if status == "REJECTED_BY_CRITIC" else "💥"
                motivo = error[:120] + "..." if len(error) > 120 else error
                summary += f"  {icono} <code>{file}</code> ({status}): <i>{motivo}</i>\n"
        else:
            summary += "🎉 <b>¡Excelente! Cero incidencias técnicas o de calidad registradas hoy.</b>"
            
        return summary
    except Exception as e:
        return f"Error al generar reporte diario: {e}"

if __name__ == "__main__":
    # Prueba del logger
    print("Probando inicialización y funciones del Logger...")
    init_db()
    
    # Registrar transacciones simuladas
    register_transaction("doc_prueba1.pdf", "SUCCESS", notion_url="https://notion.so/prueba1")
    register_transaction("doc_prueba2.docx", "REJECTED_BY_CRITIC", error_msg="Alucinación detectada en plazos de entrega.")
    register_transaction("doc_prueba3.docx", "FAILED", error_msg="Notion API 400 Bad Request.")
    
    # Escribir log de error de prueba
    log_error("doc_prueba3.docx", "NOTION_SYNC", "Notion API 400 Bad Request: Invalid page property 'Responsable'.", "Traceback...")
    
    # Imprimir reporte consolidado
    print("\n=========================================")
    print("REPORTE CONSOLIDADO DIARIO SIMULADO:")
    print("=========================================\n")
    try:
        print(get_daily_summary())
    except UnicodeEncodeError:
        print(get_daily_summary().encode('ascii', errors='replace').decode('ascii'))
    print("\n=========================================")
