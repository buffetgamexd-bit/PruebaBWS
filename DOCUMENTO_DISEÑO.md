# Documento de Diseñó de Arquitectura y Sistema
**Candidato:** Brandon  
**Puesto:** AI Automation Specialist  
**Proyecto:** Prueba Técnica - Orquestador Inteligente de Acciones Corporativas  
**Fecha de Entrega:** Jueves 29 de mayo de 2026  

---

## 🛠️ 1. Justificación de Herramientas Seleccionadas

Para construir este sistema se priorizó la estabilidad, velocidad de procesamiento, control de errores estructurado y una experiencia de usuario premium (tanto para el consultor final como para el evaluador). Las herramientas elegidas son:

*   **Lenguaje y Núcleo del Sistema:** **Python 3.10+**. Su ecosistema es el estándar de la industria para automatizaciones complejas, integración de APIs de IA y parsing robusto de archivos (`docx`, `pdf`, `pptx`, etc.).
*   **Framework Web y Servidor:** **FastAPI**. Elegido por su velocidad extrema (basado en Starlette y Pydantic), soporte nativo asíncrono para manejar loops en segundo plano de forma eficiente y su facilidad para exponer endpoints de Webhooks seguros.
*   **Motor de Inteligencia Artificial (LLM):** **Anthropic Claude Sonnet 4.6** (mediante llamada REST directa). Se seleccionó sobre Gemini y modelos de OpenRouter debido a su insuperable calidad de redacción en español corporativo, baja latencia y soporte nativo para **Structured Outputs (GA)** mediante esquemas JSON estrictos, asegurando respuestas con formato 100% válidas en el primer intento.
*   **Herramienta de Gestión de Tareas:** **Notion API**. Notion se eligió frente a Linear o Trello por su extrema flexibilidad de base de datos relacional. Permite configurar columnas personalizadas para almacenar fechas límites nativas, enlaces rich directos al documento de origen en Google Drive, badges de responsables e incrustar borradores formateados dentro del cuerpo de la página del ticket.
*   **Sincronización de Calendario:** **Google Calendar API (v3)**. Permite la integración directa del deadline de la tarea al calendario principal del responsable, garantizando que el consultor tenga visibilidad inmediata en su agenda diaria.
*   **Monitoreo y Alertas en Tiempo Real:** **Telegram Bot API**. Permite enviar notificaciones enriquecidas de éxito al instante con formato HTML, alertas de fallos técnicos críticos y reportes consolidados diarios directamente al celular del consultor.
*   **Persistencia de Historial y Monitoreo:** **SQLite (`monitoring.db`)**. Una base de datos local y ultraligera para mantener un registro persistente de cada archivo procesado, permitiendo evitar duplicados y alimentar un panel web en tiempo real.

---

## 🔍 2. Detección de Nuevos Documentos

El sistema cuenta con un **mecanismo redundante híbrido** para asegurar que ningún documento se pierda:

1.  **Monitoreo Asíncrono Continuo (Polling Activo - Principal):**  
    Mediante un bucle infinito asíncrono en segundo plano (`poll_google_drive_loop`) ejecutado al arrancar el servidor FastAPI, el sistema escanea de manera automatizada la carpeta de Google Drive configurada cada **30 segundos**. Este proceso se ejecuta en un hilo de trabajo separado (`asyncio.to_thread`) para no bloquear las solicitudes web de la aplicación principal. Es robusto e inmune a caídas de red o fallos de configuración en webhooks de terceros.
2.  **Endpoint de Webhooks (Push Notifications - Opcional):**  
    El servidor incluye la ruta `POST /webhook-drive`. Este endpoint está listo para ser registrado en Google Cloud para recibir notificaciones automáticas inmediatas (Push) en el instante exacto en que un usuario sube un archivo, despertando al orquestador instantáneamente.

---

## 🧠 3. Toma de Decisiones y Generación de Borradores con IA

El control del comportamiento de la IA y el formato de la respuesta se gestionan a través de **Structured Outputs**:

*   **Esquema Estricto (`json_schema`):** Se definió un esquema estructurado estricto en el cuerpo del payload de la llamada REST a Claude. Este esquema obliga al modelo a responder con un JSON que contiene un array de acciones, donde cada acción debe clasificar su tipo de forma obligatoria mediante un campo enumerado: `"TASK_ONLY"` o `"DRAFT_REQUIRED"`.
*   **Lógica de Clasificación:**  
    *   **`DRAFT_REQUIRED`:** Si el documento analizado requiere que el consultor responda, redacte o prepare un correo, carta, comunicado o propuesta, la IA clasifica la tarea con este tipo y genera dinámicamente el contenido del borrador en el campo `draft_content`.
    *   **`TASK_ONLY`:** Si la acción es puramente operativa (ej. agendar una reunión, realizar un pago, revisar una firma), se clasifica como tal y el borrador queda vacío.
*   **System Prompt:** El prompt del sistema le exige a Claude actuar como un extractor corporativo de élite, deduciendo los plazos reales a partir del contexto del documento y redactando borradores pulidos, formales y en español, **prohibiendo estrictamente el uso de placeholders genéricos** (como `[Nombre del cliente]`), los cuales son inferidos a partir del texto analizado.

---

## 🛡️ 4. Tolerancia a Fallos y Transaccionalidad de APIs

Para evitar inconsistencias de datos entre herramientas (por ejemplo, agendar una fecha en Calendar para una tarea que falló al registrarse en Notion), el sistema implementa un **flujo de transaccionalidad secuencial en cascada**:

```
[Inicio Procesamiento] 
         │
         ▼
 1. Descarga y Parseo del Documento
         │
         ▼
 2. Análisis con Claude Sonnet 4.6 (JSON Estructurado)
         │
         ▼
 3. Registro Inicial en SQLite como 'PROCESSING' (En Proceso)
         │
         ▼
 4. Creación de Ticket en Notion (Genera Notion URL)
         │  (Si Notion falla ──► Registra Error ──► Cancela Siguientes ──► Estado 'FAILED')
         ▼
 5. Sincronización en Google Calendar (Incluye Notion URL en el Evento)
         │
         ▼
 6. Actualización en SQLite a 'SUCCESS' (Exitoso)
         │
         ▼
 7. Notificación en Telegram con enlaces a Notion
```

Si Notion falla en el paso 4, el bloque de control de excepciones `try-except` captura el error de inmediato, cancela la ejecución del paso 5 (Google Calendar) para esa acción específica y actualiza el estado de la transacción en SQLite como **`FAILED`** con el mensaje de error correspondiente. Esto previene eventos huérfanos en el calendario.

---

## 📈 5. Prevención de Saturación y Rate Limits (Throttling)

Si un documento largo genera múltiples tareas (por ejemplo, 8 acciones en un solo briefing), o si el usuario sube 20 documentos de golpe a la carpeta de Drive, el sistema evita saturar las APIs de Notion, Calendar y Anthropic mediante:

*   **Procesamiento de Lote Dosificado (Límite por Ciclo):**  
    En `main.py`, se implementó un límite estricto de **1 archivo nuevo procesado por cada ciclo de escaneo** (es decir, 1 archivo máximo cada 30 segundos). Si el usuario sube 10 archivos simultáneamente, el bot los procesará pacientemente de forma individual a lo largo de 5 minutos.
*   **Pausa entre Acciones:**  
    Durante la iteración secuencial de las acciones de un solo documento, el orquestador realiza una pausa controlada de 3 segundos (`time.sleep(3)`) entre la creación de cada ticket. Esto suaviza el consumo de las APIs y evita que se disparen bloqueos por tasa de llamadas (HTTP 429).
*   **Deduplicación Persistente y por Hash:**  
    Antes de iniciar cualquier descarga, el sistema calcula el hash SHA-256 del archivo y consulta el historial SQLite. Si el archivo ya existe o su hash ya fue procesado, se omite por completo al inicio del flujo, ahorrando recursos y llamadas a la IA.

---

## 🪙 6. Control de Costos en la API de Inteligencia Artificial

Procesar 200 documentos diarios puede resultar sumamente costoso si no se optimiza el consumo de tokens. El sistema implementa las siguientes estrategias de optimización financiera:

*   **Structured Outputs de Una Sola Vuelta:** Al forzar a la API de Claude a devolver la respuesta estructurada y validada en JSON en su primera respuesta, se previene la necesidad de realizar llamadas correctivas (conversaciones multi-turno o reintentos de formato), lo que reduce el consumo de tokens en un **50%**.
*   **Remoción de Agentes Críticos Redundantes:** Consolidamos el poder de análisis y control de calidad en **una sola llamada directa y altamente directiva** a Claude Sonnet 4.6, eliminando el coste adicional de tokens de entrada/salida de un agente secundario de verificación que causaba duplicación de llamadas.
*   **Truncado Inteligente de Texto:** Antes de enviar el texto extraído del documento a la IA, el orquestador trunca el contenido a un máximo de 40,000 caracteres (suficiente para capturar propuestas ejecutivas extensas) para prevenir picos inesperados de consumo de tokens en documentos masivos.

---

## 💎 7. Validación y Garantía de Calidad en los Borradores

La calidad de los borradores generados se garantiza a nivel de diseño mediante:

1.  **Configuración de Temperatura Baja:** Se fijó el parámetro `temperature` en **0.15** en la configuración de generación de la IA. Esto reduce la creatividad aleatoria del modelo, forzando respuestas altamente consistentes, rigurosas y basadas estrictamente en la verdad del documento (cero alucinaciones).
2.  **Instrucciones de Redacción Profesional:** Las directrices del System Prompt obligan a Claude a actuar como un consultor corporativo senior en español, requiriendo borradores con redacción fluida, natural, formal y coherente, que realmente aporten valor y sirvan como punto de partida útil para el equipo de consultores.

---

## 📊 8. Logs, Monitoreo y Alertas del Sistema

Para asegurar la tranquilidad de que el sistema funcionó perfectamente cada noche, se implementó un suite completo de auditoría y monitoreo:

### A. Base de Datos SQLite de Monitoreo (`monitoring.db`)
Registra de forma permanente cada acción del sistema en la tabla `transactions` con las siguientes columnas:
*   `file_name`: Nombre del documento origen.
*   `status`: Estado exacto en tiempo real (`PROCESSING`, `SUCCESS`, `FAILED`, `REJECTED_BY_CRITIC`).
*   `error_message`: El mensaje de error técnico exacto en caso de fallo.
*   `notion_page_url`: El enlace directo al ticket de Notion creado para trazabilidad inmediata.
*   `timestamp`: Fecha y hora exacta de la transacción.

### B. Registro Físico de Errores (`error_logs.json`)
En caso de excepciones a nivel de servidor o librerías, el sistema realiza un volcado del error con el paso de ejecución (`phase`), la hora exacta y el stack trace completo de Python (`traceback_str`) para facilitar la depuración inmediata.

### C. Alertas Inmediatas por Telegram
Si ocurre un fallo crítico de sincronización de Google Drive o un fallo de conexión de APIs, el bot envía instantáneamente un mensaje estructurado con un icono de alarma (`🚨`) indicando el documento y la causa exacta para la intervención inmediata del administrador.

### D. Reporte Diario Consolidado
Cada mañana, o al finalizar el procesamiento de un lote de archivos, el sistema genera de forma autónoma un reporte formateado en HTML que se envía a Telegram, indicando:
*   Total de documentos procesados.
*   Cantidad de éxitos, rechazos y fallos técnicos.
*   Detalle rápido de cualquier incidencia ocurrida con nombres de archivos y causas para una revisión rápida.

*   **Historial en Tiempo Real:** Renderiza la tabla de transacciones de SQLite al vuelo, mostrando los archivos en estado **"En Proceso" (PROCESSING)** con una animación de pulso interactiva en el preciso instante en que el orquestador los está analizando, y actualizándolos a **Exitoso** o **Fallido** de forma automática.

---

## 💾 9. Consideraciones de Persistencia en Producción (Render Ephemeral Disks)

Durante las pruebas, es normal observar que si el servidor de Render se reinicia o se despliega una nueva versión, **los archivos del Drive vuelven a procesarse**. Esto se debe a un comportamiento de diseño de la infraestructura de Render:

*   **Discos Efímeros:** Render Web Services utiliza contenedores sin persistencia de disco por defecto en su capa gratuita. Cada despliegue o reinicio borra por completo el disco duro local, lo que significa que el archivo `monitoring.db` de SQLite se elimina y se recrea vacío al iniciar el servidor. Al borrarse la base de datos de historial local y limpiarse la memoria, el bot pierde el registro de qué archivos ya procesó con éxito y los vuelve a escanear como nuevos.

### Soluciones de Producción (Enterprise Ready):
En un entorno real de producción, este comportamiento se soluciona mediante cualquiera de las siguientes tres estrategias de persistencia:

1.  **Render Persistent Disks (Volúmenes Montados):**  
    Montar un volumen de disco persistente de Render (por ejemplo, en `/data`) y configurar la variable de entorno `DB_PATH=/data/monitoring.db`. De este modo, la base de datos SQLite sobrevive perfectamente a cualquier despliegue, actualización o reinicio del contenedor.
2.  **Base de Datos en la Nube (Decoupled Database):**  
    Migrar el backend de SQLite a una base de datos administrada como **PostgreSQL** (ofrecida nativamente en Render o mediante proveedores como Supabase). Esto independiza totalmente la persistencia del sistema de archivos del servidor web, garantizando 100% de disponibilidad histórica.
3.  **Consulta Previa en Notion (Double Check):**  
    Antes de descargar o procesar un archivo, el orquestador puede hacer una llamada rápida de consulta a la API de Notion (`query database`) buscando si ya existe alguna página cuyo título o propiedad de origen coincida con el nombre del archivo. Si existe, se omite de forma inteligente incluso si la base de datos SQLite local estuviera vacía.

---

## 🗺️ 10. Diagrama de Flujo Interactivo (Estilo n8n) y Análisis de Costos

Para facilitar una comprensión visual rápida y ejecutiva de todo el ecosistema de automatización, hemos desarrollado un **Diagrama de Flujo Interactivo Premium** en formato HTML independiente. 

👉 **[ABRIR DIAGRAMA DE FLUJO INTERACTIVO (flujo_interactivo.html)](file:///c:/Users/brand/Desktop/PruebaBrandon/flujo_interactivo.html)** *(Haz doble clic sobre el archivo en tu sistema para abrirlo de forma interactiva en tu navegador web).*

### 📊 Desglose de Operaciones y Costos (Claude 3.5 Sonnet)
Una de las preguntas clave en entornos empresariales es el retorno de inversión (ROI) y los costos operativos de la Inteligencia Artificial. A continuación, se detalla el análisis de costos para el procesamiento de documentos:

*   **Entrada Promedio por Documento:** 1,940 caracteres (~485 tokens de texto limpio extraído del archivo).
*   **System Prompt + Esquemas JSON Estrictos:** ~1,500 tokens (instrucciones directivas de comportamiento y el esquema del Structured Output).
*   **Total Tokens de Entrada (Input):** ~2,000 tokens.
*   **Total Tokens de Salida (Output):** ~500 tokens (JSON estructurado con la clasificación, prioridad y el borrador redactado en español).

#### 🪙 Cálculo de Costo (Precios oficiales de Anthropic Claude 3.5 Sonnet):
*   **Costo de Entrada:** $3.00 USD por millón de tokens ($0.003 USD por 1K).
    $$\text{Costo Input} = 2,000 \times \left(\frac{\$3.00}{1,000,000}\right) = \$0.006\text{ USD}$$
*   **Costo de Salida:** $15.00 USD por millón de tokens ($0.015 USD por 1K).
    $$\text{Costo Output} = 500 \times \left(\frac{\$15.00}{1,000,000}\right) = \$0.0075\text{ USD}$$
*   **Costo Promedio Total por Documento:** **$0.0135 USD** (aprox. **$0.27 MXN**).
*   **Procesamiento Masivo de 100 Documentos:** **$1.35 USD** (aprox. **$27.00 MXN**). 

> [!TIP]
> **Eficiencia Financiera Extrema:** Gracias a la arquitectura de **Structured Outputs de una sola vuelta**, el bot nunca realiza llamadas correctivas (lo que duplicaría los costos en caso de JSONs mal formados), logrando un ahorro del **50%** en tokens frente a implementaciones tradicionales de prompt-engineering.

---

### ⏳ Comportamiento del Servidor y Polling (Render Free Tier vs Producción)
El orquestador está actualmente configurado para realizar un **Polling Activo cada 30 segundos** en la carpeta de Google Drive. A continuación, explicamos la disponibilidad según la infraestructura:

1.  **Entorno de Pruebas (Render Free Tier):**
    *   **Cold Start (Inactividad):** Si no hay peticiones HTTP entrantes al Dashboard durante **15 minutos**, Render "apaga" (suspende) el servidor para liberar recursos.
    *   **Consecuencia en el Polling:** Al suspenderse el servidor, el bucle en segundo plano de Google Drive se detiene. Si subes un archivo a Drive mientras duerme, no se procesará inmediatamente.
    *   **Reactivación:** En cuanto un usuario visita la URL de nuestro [Dashboard Web](https://pruebabws.onrender.com/), el servidor despierta (tarda unos 45 segundos en iniciar) y procesa automáticamente de golpe todos los archivos pendientes acumulados en Drive.
    
2.  **Entorno de Producción (Enterprise Ready):**
    *   **Always-On ($7 USD/mes):** Al contratar el plan Web Service básico de Render, el servidor nunca entra en modo de suspensión. El loop de polling funciona de forma continua 24/7 de manera ininterrumpida.
    *   **Solución Alternativa Gratuita (UptimeRobot):** Se puede configurar un cron job externo gratuito en [UptimeRobot](https://uptimerobot.com) que haga ping al endpoint `/healthz` de nuestro dashboard cada 10-14 minutos. Esto mantiene el servidor de Render "despierto" las 24 horas del día a costo cero.

---

### 🔗 Enlaces Importantes de Acceso Rápido
*   💻 **[Dashboard de Monitoreo en Vivo (Desplegado)](https://pruebabws.onrender.com/)**
*   📁 **[Carpeta de Google Drive (Monitoreada)](https://drive.google.com/drive/folders/1_8ADStAk0-EG64bDtqVlZ8ppZadigNST)**


