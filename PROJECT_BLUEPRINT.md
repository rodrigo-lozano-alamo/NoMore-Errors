# NoMore Errors - Blueprint del proyecto

## 1. Objetivo

NoMore Errors será una aplicación web/desktop que ayude a personas no técnicas a entender y resolver errores de Windows. El producto debe convertir una captura de pantalla o un código de error en una explicación clara, una guía paso a paso y una forma simple de indicar si la solución funcionó.

Principios del producto:

- Explicar primero el problema y después la solución.
- Evitar jerga técnica o explicar cada término técnico que sea imprescindible.
- Mostrar advertencias antes de acciones potencialmente destructivas.
- Separar la información encontrada de las recomendaciones generadas por IA.
- Registrar la efectividad de cada solución sin almacenar más datos personales de los necesarios.

## 2. Arquitectura propuesta

La primera versión seguirá una arquitectura modular con un backend HTTP y un cliente desacoplado:

```text
Cliente web/desktop
        |
        v
API FastAPI (contratos, validación y orquestación)
        |
        +--> Servicio OCR
        +--> Conectores de fuentes (Windows DB, Reddit)
        +--> Servicio de síntesis IA
        +--> Base de datos de errores, soluciones y feedback
        +--> Almacenamiento temporal de imágenes
```

### Módulos principales

1. **Captura e identificación**
   - Aceptar código manual, imagen y posteriormente captura de pantalla.
   - Validar tamaño y tipo de archivo.
   - Extraer texto con OCR y normalizar códigos como `0x80070005` o `KERNEL_SECURITY_CHECK_FAILURE`.

2. **Búsqueda y síntesis**
   - Consultar una base de conocimiento propia de Windows.
   - Consultar Reddit mediante un conector con límites, caché y trazabilidad de la fuente.
   - Enviar a la IA únicamente el contexto necesario.
   - Generar pasos numerados, dificultad, riesgo, requisitos y fuentes.

3. **Feedback y analítica**
   - Registrar `Sí` o `No` para cada solución mostrada.
   - Calcular efectividad por solución y por familia de errores.
   - Evitar interpretar una muestra pequeña como una métrica fiable: mostrar también el número de respuestas.

4. **Interfaz**
   - Flujo corto: identificar error, entenderlo, seguir pasos y dar feedback.
   - Estados explícitos para carga, falta de resultados, error de fuente y solución no verificada.
   - Diseño accesible, responsive y con lenguaje orientado a acciones.

## 3. Tecnologías sugeridas

### Backend

- **Python 3.12+ y FastAPI** para endpoints tipados, documentación OpenAPI y validación con Pydantic.
- **Uvicorn** como servidor ASGI local y de despliegue detrás de un proxy.
- **PostgreSQL** para errores normalizados, soluciones, fuentes y feedback.
- **SQLAlchemy 2 + Alembic** para persistencia y migraciones.
- **Redis** opcional para caché, rate limiting y trabajos breves.
- **Celery/RQ** opcional para OCR, consultas externas y generación IA asíncronas.

Node.js con NestJS/Express también sería válido, pero FastAPI encaja mejor con futuras herramientas de OCR, procesamiento de imágenes y evaluación de texto en Python.

### Cliente

- **React + TypeScript + Vite** para la interfaz web.
- **Tauri** si se necesita empaquetar la interfaz como aplicación desktop ligera.
- Cliente HTTP generado o validado a partir del contrato OpenAPI del backend.

### Calidad y operación

- **pytest** para pruebas unitarias y de API.
- **Ruff** y **mypy** para calidad y tipos en Python.
- **Docker Compose** para desarrollo local con PostgreSQL y Redis.
- Variables de entorno para claves de IA, Reddit y conexión a base de datos; nunca incluir secretos en el repositorio.
- Logs estructurados, identificadores de correlación y métricas básicas desde el primer endpoint real.

## 4. Estructura de carpetas

La estructura propuesta separa el backend del proyecto .NET existente y permite añadir el cliente sin mezclar responsabilidades:

```text
NoMore Errors/
|-- PROJECT_BLUEPRINT.md
|-- backend/
|   |-- main.py                  # Arranque FastAPI, análisis y OCR
|   |-- requirements.txt
|   |-- data/
|   |   |-- errors_catalog.json   # Fichas técnicas locales de errores Windows
|   |-- app/
|   |   |-- api/
|   |   |   |-- routes_errors.py # Endpoints de identificación y análisis
|   |   |   |-- routes_feedback.py
|   |   |-- core/
|   |   |   |-- config.py        # Configuración desde entorno
|   |   |   |-- logging.py
|   |   |-- domain/
|   |   |   |-- models.py        # Entidades y reglas de negocio
|   |   |-- schemas/
|   |   |   |-- errors.py        # DTOs de entrada y salida
|   |   |-- services/
|   |   |   |-- ocr_service.py
|   |   |   |-- search_service.py
|   |   |   |-- synthesis_service.py
|   |   |   |-- knowledge_service.py
|   |   |   |-- ai_service.py
|   |   |   |-- solution_service.py
|   |   |   |-- feedback_service.py
|   |   |-- integrations/
|   |       |-- windows_database.py
|   |       |-- reddit_client.py
|   |-- tests/
|       |-- test_health.py
|       |-- test_errors_api.py
|-- frontend/
|   |-- index.html               # Interfaz inicial de captura
|   |-- styles.css
|   |-- app.js                   # Integración con la API
|-- NoMore Errors/
|   |-- NoMore Errors.csproj     # Proyecto existente, sin cambios en esta fase
|   |-- Program.cs
```

El módulo OCR está temporalmente en `main.py` para mantener la Fase 2 fácil de ejecutar. En la siguiente refactorización deberá trasladarse a `app/services/ocr_service.py`, dejando en `main.py` únicamente el registro de rutas.

## 5. Contrato inicial de la API

### `GET /health`

Devuelve el estado mínimo del proceso para comprobar que el servidor está disponible.

### `POST /api/v1/errors/analyze`

Entrada:

```json
{
  "error_code": "0x80070005"
}
```

Salida simulada:

```json
{
  "error_code": "0x80070005",
  "title": "Permiso insuficiente",
  "summary": "Windows bloqueó la acción porque faltan permisos.",
  "confidence": 0.72,
  "steps": [
    "Cierra la aplicación que muestra el error.",
    "Vuelve a intentarlo con una cuenta administradora solo si confías en el programa."
  ],
  "sources": [],
  "simulated": true
}
```

La propiedad `simulated` evita confundir esta respuesta de demostración con una recomendación verificada. En fases posteriores el contrato deberá versionarse y documentar códigos de error, límites, autenticación y errores con RFC 7807.

### `POST /api/v1/errors/ocr`

Recibe `multipart/form-data` con un campo `file`. Solo acepta imágenes de hasta 5 MB y devuelve el texto normalizado por OCR junto a los códigos hexadecimales o nombres de pantallazo azul reconocidos:

```json
{
   "extracted_text": "STOP CODE CRITICAL_PROCESS_DIED 0x000000EF",
   "detected_errors": ["0X000000EF", "CRITICAL_PROCESS_DIED"],
   "simulated": false
}
```

El OCR usa `pytesseract`, que requiere instalar el paquete Python y el ejecutable Tesseract OCR en Windows. La API responde `503` si Tesseract no está disponible, `415` para archivos que no sean imágenes y `413` si superan el límite.

## 6. Arquitectura de la Fase 3

El motor de soluciones está separado en tres responsabilidades para poder sustituir cada proveedor sin cambiar el contrato del frontend:

```text
POST /api/v1/solutions/search
                   |
                   v
         solution_service
            /           \
          v             v
knowledge_service  ai_service
    /       \           |
   v         v          v
Windows DB  Reddit  OpenAI opcional
 (simulada)  JSON    o fallback local
```

### Flujo de búsqueda

1. Normalizar el código recibido y limitar el texto contextual procedente de OCR.
2. Consultar primero `backend/data/errors_catalog.json`, con fichas técnicas y pasos estructurados para errores conocidos.
3. Si el código no existe en el catálogo, consultar la búsqueda JSON pública de Reddit con `User-Agent`, timeout de 8 segundos y un máximo de cinco publicaciones.
4. Tratar títulos y textos de Reddit como datos no confiables: no se ejecutan instrucciones encontradas allí y se delimitan antes de enviarlos a la IA.
5. Para códigos desconocidos, sintetizar mediante Claude (Anthropic) cuando existe `ANTHROPIC_API_KEY`, exigiendo causas, rutas de menú, comandos y tipos de paso.
6. Usar un fallback técnico local si no hay clave, la IA falla o Reddit no está disponible. El frontend nunca muestra la marca interna `simulated`.

### Contrato `POST /api/v1/solutions/search`

Entrada:

```json
{
   "error_code": "0x80070005",
   "error_text": "Access denied al abrir una aplicación"
}
```

Salida:

```json
{
   "error_code": "0X80070005",
   "causes": [
      "La aplicación necesita permisos elevados.",
      "Una política de seguridad está bloqueando la operación."
   ],
   "simple_explanation": "Windows bloquea la operación porque faltan permisos.",
   "steps": [
      {
         "number": 1,
         "title": "Ejecuta como administrador",
         "detail": "En el Explorador, haz clic derecho en el programa y elige Más > Ejecutar como administrador.",
         "tipo": "configuracion",
         "comando": null,
         "tags": ["configuracion"]
      }
   ],
   "sources_summary": "Consultadas: Reddit r/Windows, Windows knowledge base (simulada).",
   "simulated": true
}
```

La propiedad `simulated` distingue el fallback y la base local de una síntesis IA conectada. Las publicaciones de Reddit sirven como contexto y no como instrucciones autorizadas; antes de producción se deben añadir caché, rate limiting, auditoría de fuentes y una política de privacidad.

El catálogo local contiene 17 fichas iniciales, incluyendo `0x80244007`, `0x800F0922`, `0x80073712`, `0x80070422`, `CRITICAL_PROCESS_DIED`, `SYSTEM_SERVICE_EXCEPTION`, `IRQL_NOT_LESS_OR_EQUAL`, `PAGE_FAULT_IN_NONPAGED_AREA` y `DPC_WATCHDOG_VIOLATION`. Cada ficha se valida con el mismo modelo de pasos que usa la respuesta IA.

El archivo está preparado para crecer a miles de entradas sin modificar Python: cada nuevo objeto dentro de `errors` puede incluir `code`, `title`, `simple_explanation`, `probable_causes` y `steps`. La ruta puede cambiarse con `WINDOWS_ERROR_CATALOG_PATH`, lo que permite montar un JSON generado desde una fuente oficial o una exportación CSV convertida durante el proceso de build.

### Configuración

- `ANTHROPIC_API_KEY`: activa la síntesis remota; nunca se guarda en el repositorio.
- `NOMORE_CLAUDE_MODEL`: modelo opcional, por defecto `claude-opus-5-5`.
- `REDDIT_USER_AGENT`: identificador descriptivo para la consulta pública de Reddit.
- `TESSERACT_CMD`: ruta opcional al ejecutable OCR de Windows.
- `WINDOWS_ERROR_CATALOG_PATH`: ruta opcional a un catálogo JSON ampliado.

El prompt del sistema obliga a devolver JSON con `simple_explanation`, `causes` y pasos con `detail`, `how_to`, `tipo`, `comando`, `command_explanation` y `tags`; exige rutas de menú y comandos solo cuando sean pertinentes, y prohíbe desactivar la seguridad de Windows. La respuesta se valida antes de llegar al frontend; si no tiene la forma esperada se usa el fallback técnico.

## 7. Arquitectura de la Fase 4

El feedback se guarda en SQLite para mantener el entorno local ligero y evitar introducir todavía una infraestructura de base de datos externa. Cada clic genera un registro histórico asociado al código y a la solución exacta que se mostró:

```sql
CREATE TABLE feedback_votes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      error_code TEXT NOT NULL,
      solution_id TEXT NOT NULL,
      success INTEGER NOT NULL CHECK (success IN (0, 1)),
      timestamp TEXT NOT NULL
);
```

El índice `(error_code, solution_id)` acelera la consulta de métricas. `success` se almacena como `0` o `1`, y `timestamp` se registra en UTC ISO 8601. La base se crea automáticamente en `backend/data/feedback.db`; puede cambiarse con `FEEDBACK_DB_PATH`.

### Contrato de feedback

`POST /api/feedback` recibe:

```json
{
   "error_code": "0X80070005",
   "solution_id": "sol_c90a952b21e9b572",
   "success": true
}
```

Devuelve el resultado actualizado:

```json
{
   "solution_id": "sol_c90a952b21e9b572",
   "success": true,
   "effectiveness_percentage": 100.0,
   "total_votes": 1,
   "message": "Gracias por tu respuesta."
}
```

La efectividad se calcula como `(votos Sí / total de votos) * 100`. Cuando todavía no existen votos, el porcentaje es `null` y la interfaz muestra “Todavía no hay votos”. La respuesta de `POST /api/v1/solutions/search` incluye el mismo porcentaje y el total actual para que el frontend pueda mostrar la confiabilidad antes de votar.

El sistema no recoge identidad del usuario en esta fase. Antes de producción deben añadirse controles contra votos automatizados, política de retención, agregación mínima para privacidad y una estrategia de migración de SQLite a PostgreSQL si crece el volumen.

## 8. Siguientes pasos detallados

1. Instalar Tesseract OCR y configurar `TESSERACT_CMD` si el ejecutable no está en PATH.
2. Añadir pruebas de contrato para `/health`, OCR y `/api/v1/solutions/search` con Reddit/IA simulados.
3. Sustituir la base local de Windows por un conector oficial versionado y con caché.
4. Añadir caché, rate limiting, reintentos y observabilidad al conector de Reddit.
5. Evaluar respuestas IA con casos fijos, validación de seguridad y revisión humana de recomendaciones.
6. Diseñar el modelo de datos para errores, soluciones, fuentes, consultas y feedback.
7. Mejorar la normalización OCR con preprocesado de contraste, rotación y catálogo de errores.
8. Migrar el frontend estático a React/Tauri cuando el contrato esté estable.
9. Instrumentar feedback, métricas de éxito y panel de calidad con intervalos de confianza.
10. Preparar despliegue, copias de seguridad, control de costes, privacidad y eliminación de imágenes temporales.

## 9. Criterios de aceptación de la Fase 4

- La base SQLite se crea automáticamente con votos, timestamps e índice por solución.
- `/api/feedback` guarda respuestas `Sí` y `No` y devuelve la métrica recalculada.
- `/api/v1/solutions/search` incluye `solution_id`, porcentaje de efectividad y total de votos.
- El frontend muestra botones interactivos y actualiza la métrica tras registrar el voto.
- La documentación cubre el flujo completo: OCR, conocimiento, síntesis IA, feedback y analítica.

## 10. Despliegue y Ejecución

### Ejecución local en Windows

1. Instala Python 3.12 o superior y Tesseract OCR. Si Tesseract no está en `PATH`, usa la variable `TESSERACT_CMD`.
2. Crea y activa el entorno virtual desde la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instala las dependencias del backend:

```powershell
Set-Location backend
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

4. Edita `backend/.env` y añade solo las variables necesarias:

```dotenv
ANTHROPIC_API_KEY=tu_clave_de_anthropic
NOMORE_CLAUDE_MODEL=claude-opus-5-5
REDDIT_USER_AGENT=NoMoreErrors/0.1 (contacto: tu-email@example.com)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

El conector actual usa la búsqueda pública JSON de Reddit y no necesita credenciales. Si se cambia a OAuth o a la API oficial, añade las credenciales correspondientes al `.env`, nunca al código ni al frontend.

5. Levanta la API:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

La documentación OpenAPI queda disponible en `http://127.0.0.1:8000/docs`. Si el puerto está ocupado, usa otro y actualiza `API_URL` en `frontend/app.js`.

6. En otra terminal, sirve el frontend estático:

```powershell
Set-Location frontend
..\.venv\Scripts\python.exe -m http.server 5500
```

Abre `http://127.0.0.1:5500`. No abras `index.html` directamente como `file://`: el navegador puede bloquear la comunicación o enviar un origen `null`. Durante desarrollo, FastAPI acepta cualquier puerto HTTP de `localhost` o `127.0.0.1`; en producción debe sustituirse por una lista de dominios explícita.

### Comprobaciones rápidas

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/solutions/search `
   -Method Post -ContentType application/json `
   -Body '{"error_code":"0x80070005","error_text":"Access denied"}'
```

### Seguridad antes de producción

- No subas `.env`, claves, la base SQLite ni imágenes de usuarios al repositorio.
- Cambia CORS desde los puertos locales a una lista explícita de dominios HTTPS.
- Añade autenticación, rate limiting y protección contra votos automatizados.
- Mantén límites de tamaño, formato y tiempo de OCR; elimina las imágenes temporales después de procesarlas.
- Trata Reddit y cualquier contenido externo como datos no confiables; no ejecutes comandos sugeridos automáticamente.
- Registra errores técnicos en el servidor, pero muestra mensajes genéricos al usuario para no filtrar rutas, claves o trazas.
- En producción usa HTTPS, backups cifrados y PostgreSQL si SQLite deja de ser suficiente.

### Empaquetado futuro

- **Tauri** es la opción preferida para un desktop ligero: puede servir el frontend y arrancar el backend local como proceso controlado, con menor consumo que Electron.
- **Electron** facilita integrar un frontend web y procesos Node/Python, pero requiere más memoria y una política estricta para no exponer APIs del sistema al contenido web.
- **Docker** permite empaquetar FastAPI y sus dependencias. La imagen debe instalar Tesseract, recibir secretos mediante variables del entorno y montar un volumen para `backend/data`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```