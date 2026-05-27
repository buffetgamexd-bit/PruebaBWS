# Orquestador Inteligente de Acciones Corporativas 🤖💼

¡Bienvenido! Este es el repositorio de la prueba técnica desarrollada para el puesto de **AI Automation Specialist**. 

El sistema es un orquestador inteligente que monitorea activamente una carpeta de Google Drive, procesa documentos de clientes en tiempo real utilizando la API oficial de **Anthropic Claude Opus 4.6 (Structured Outputs)**, genera borradores contextuales de alta calidad y automatiza la sincronización de tareas estructuradas en **Notion** y plazos en **Google Calendar**, todo monitoreado a través de alertas inmediatas en **Telegram** y un **Dashboard Web Premium** en tiempo real.

---

## 📂 Estructura del Entregable

La prueba técnica consta de dos fases integradas en este repositorio:

1.  **Fase 1 - Documento de Diseño de Arquitectura (Calificación: 30%):**  
    Un desglose técnico exhaustivo de la arquitectura del sistema, justificación detallada de herramientas y respuestas de ingeniería de software a las 8 preguntas críticas planteadas en las pautas.  
    👉 **[Leer el Documento de Diseño Completo (Fase 1)](file:///c:/Users/brand/Desktop/PruebaBrandon/DOCUMENTO_DISE%C3%91O.md)**
2.  **Fase 2 - Prototipo Funcionando en Producción (Calificación: 25%):**  
    Un prototipo funcional integrado de principio a fin, tolerante a fallos, asíncrono y desplegado en la nube de forma estable.

---

## 🛠️ Tecnologías Utilizadas

*   **Núcleo:** Python 3.10+ (Asíncrono con `asyncio`).
*   **Servidor Web:** FastAPI + Uvicorn (con Webhooks y rutas `/health` / `/healthz`).
*   **Base de datos de Monitoreo:** SQLite3 (Persistencia de historial, deduplicación y logs de estados).
*   **Motor de Inteligencia Artificial:** REST API directa a **Anthropic Claude Opus 4.6** (con *Structured Outputs* de una sola vuelta).
*   **Integraciones principales:**
    *   **Google Drive API v3:** Descarga y exportación al vuelo de archivos nativos de Google Docs/Slides.
    *   **Google Calendar API v3:** Sincronización automática de plazos y agendas de responsables.
    *   **Notion API:** Gestión de tareas relacionales con enlaces de origen y borradores listos.
    *   **Telegram Bot API:** Alertas técnicas inmediatas y reportes diarios consolidados.

---

## ⚡ Guía de Inicio Rápido (Local)

Si deseas ejecutar y validar el prototipo localmente en tu computadora, sigue estos pasos:

### 1. Clonar el repositorio e instalar dependencias
```bash
git clone https://github.com/buffetgamexd-bit/PruebaBWS.git
cd PruebaBWS
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno (`.env`)
Crea un archivo `.env` en la raíz del proyecto (este archivo está protegido en `.gitignore` para seguridad de tus credenciales) y configura los siguientes parámetros:

```env
# 1. Inteligencia Artificial (Claude API)
CLAUDE_API_KEY=tu_anthropic_api_key_aqui

# 2. Monitoreo y Alertas (Telegram)
TELEGRAM_BOT_TOKEN=tu_telegram_bot_token_aqui
TELEGRAM_CHAT_ID=tu_telegram_chat_id_aqui

# 3. Integración con Notion
NOTION_API_KEY=tu_notion_api_key_aqui
NOTION_DATABASE_ID=tu_notion_database_id_aqui

# 4. Integración con Google (Drive y Calendar)
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
GOOGLE_DRIVE_FOLDER_ID=id_de_tu_carpeta_de_drive_aqui
GOOGLE_CALENDAR_ID=primary
```

### 3. Ejecutar el Servidor y Monitoreo Asíncrono
Inicia el servidor FastAPI local que levantará el Dashboard interactivo y activará el polling asíncrono continuo de Google Drive (cada 30 segundos):

```bash
python main.py --server
```
*   El servidor se abrirá en `http://localhost:8000`
*   El bot escaneará tu carpeta de Drive automáticamente de fondo buscando archivos nuevos (`.docx`, `.pdf`, `.txt`, `.pptx`, Google Docs, Google Slides).

---

## 🌟 Características Exclusivas del Prototipo

*   **Dashboard Web Premium Integrado:** Panel visual con diseño oscuro moderno y efecto de cristal (glassmorphism) que cuenta con un **cronómetro regresivo interactivo de 30 segundos** y **auto-recarga del navegador** para ver transacciones en tiempo real.
*   **Manejo de Estados de Transacción en Vivo (`En Proceso`):** En el instante exacto en que el bot detecta un archivo en Drive, lo registra en el Dashboard como `En Proceso (PROCESSING)` con una animación de pulso, actualizándose automáticamente a `Exitoso` o `Fallido` una vez concluyen las llamadas a Notion/Calendar/Telegram.
*   **Tratamiento de Fallos y Transaccionalidad:** Si una API (como Notion) experimenta un corte o error temporal, el orquestador captura la excepción, registra el fallo en SQLite y en `error_logs.json`, omite la creación de eventos en Calendar correspondientes a esa tarea para evitar eventos huérfanos, envía una alerta estructurada inmediata por Telegram y **sigue procesando el resto de documentos sin detenerse**.
*   **Redacción de Borradores Impecable:** Claude Opus 4.6 está configurado a baja temperatura (`0.15`) y con instrucciones exhaustivas que impiden el uso de placeholders vacíos, garantizando cartas, correos o comunicados listos para que el consultor trabaje sobre ellos de inmediato.
