# Job Agent

MVP local para buscar, evaluar, adaptar y registrar candidaturas. El flujo usa adaptadores reemplazables para scraper, documentos, navegador y CRM.

## Ejecución local

```bash
python3 main.py
```

La ejecución de ejemplo lee `data/jobs.json` y `data/master_cv.md`, genera documentos para ofertas con compatibilidad >= 70 y escribe `data/applications.csv`. Los documentos adaptados aparecen en `output/`.

Cada línea de salida es un registro JSON con `paso`, `empresa`, `compatibilidad` y `estado`.

## Configuración

Copia `config.example.env` a `.env`. Por defecto:

- `JOB_SOURCE=local`: usa el JSON local.
- `MIN_COMPATIBILITY=70`: umbral de aprobación.
- `AUTO_SUBMIT=false`: exige revisión humana.
- `CRM_PATH=data/applications.csv`: exportación CSV compatible; SQLite es la fuente principal cuando `STORAGE_BACKEND=sqlite`.
- `CV_PATH=data/master_cv.md`: archivo de referencia; el evaluador selecciona dinámicamente otro `.md` de `data/` usando Ollama.
- `OLLAMA_MODEL=llama3.2`: modelo local usado para elegir el CV más adecuado. Si Ollama no está disponible, se usa una selección local por coincidencia de términos.
- `OLLAMA_HOST=http://127.0.0.1:11434`: dirección del servidor local de Ollama.
- `OLLAMA_TIMEOUT_SECONDS=90`: tiempo máximo de espera de una selección antes de activar el fallback local.
- `OLLAMA_GENERATOR_TIMEOUT_SECONDS=30`: tiempo máximo separado para refinar perfil y bullets; si vence, conserva el contenido original.
- `NOTION_TOKEN`: token de integración de Notion, si se configura un CRM Notion.
- `NOTION_DATABASE_ID`: ID de la base de datos de Notion, si se configura un CRM Notion.
- `NOTION_ENABLED=false`: activa el envío opcional de cada auditoría a Notion.
- `NOTION_VERSION=2022-06-28`: versión de la API de Notion utilizada.

### Trazabilidad de documentos

La tabla SQLite `applications` conserva la auditoría por candidatura. `data/applications.csv`
es una exportación compatible regenerada desde SQLite:
empresa, rol, score, estado, CV base seleccionado, ruta del PDF generado, enlace
`file://` explícito, SHA-256 del CV base y SHA-256 del PDF. La huella permite
demostrar que el documento no cambió después de la generación. SQLite se escribe antes
de sincronizar con Notion, por lo que Notion no es un punto único de fallo. El histórico
existente del CSV se importa automáticamente una sola vez cuando la tabla está vacía.

Para activar Notion, crea una base de datos con estas propiedades exactas:
`Name` (title), `Empresa`, `Rol`, `Estado`, `CV base`, `CV SHA256`, `PDF SHA256`
(rich text), `Score` (number), `PDF` y `Oferta` (URL). Comparte la base de datos
con la integración y configura:

```env
NOTION_ENABLED=true
NOTION_TOKEN=
NOTION_DATABASE_ID=
```

El PDF local se registra como enlace `file://`; es accesible en el mismo equipo,
pero no es un enlace público. Para compartirlo externamente, usa una carpeta
sincronizada o almacenamiento con URL HTTPS y reemplaza `PDF` por esa URL.

Para JSearch instala `requests`, define `JSEARCH_API_KEY` y usa `JOB_SOURCE=jsearch`. Las credenciales no deben entrar en el repositorio.
Después de ejecutar `tools.fetch_jobs`, usa `JOB_SOURCE=local` para ejecutar
`main.py` sobre las ofertas ya almacenadas sin volver a consumir cuota de RapidAPI.
Usa `JOB_SOURCE=jsearch` únicamente cuando quieras que `main.py` haga una búsqueda
nueva. El comando `tools.daily_run` sí consulta primero las fuentes configuradas y
después procesa solo las ofertas nuevas.
`JSEARCH_QUERIES` permite indicar roles separados por comas en español e inglés.
`JSEARCH_HOST=jsearch-mega.p.rapidapi.com` y `JSEARCH_ENDPOINT=search` configuran el
producto y endpoint de RapidAPI. Deben coincidir con la suscripción activa en RapidAPI.
`JSEARCH_COUNTRY=co`, `JSEARCH_DATE_POSTED=all` y `JSEARCH_LANGUAGE=es` se envían como
filtros explícitos. La cobertura de Colombia depende del proveedor; una respuesta HTTP 200
con `data: []` significa que la API no encontró resultados para esa combinación, no que
`daily_run` haya fallado.
Los resultados con país distinto al configurado y los puestos con seniority senior,
lead, principal, manager, director o equivalentes se descartan. Puedes ampliar o reducir
la lista con `JSEARCH_EXCLUDE_SENIORITY`. `JSEARCH_CLEAN_CATALOG=true` elimina del
catálogo persistido las ofertas JSearch antiguas que ya no cumplen país o seniority;
déjalo en `false` si quieres conservar el histórico.
`JSEARCH_QUERY_SUFFIX=junior` añade el término al texto de cada búsqueda para priorizar
vacantes iniciales; el filtro de seniority sigue aplicándose después de recibir la respuesta.
`OLLAMA_GENERATOR_TIMEOUT_SECONDS` limita el refinamiento del CV sin afectar la selección
del CV base.
`JOB_RSS_FEEDS` acepta feeds RSS separados por comas y `MAX_OLLAMA_JOBS=50` limita
el número de ofertas que pasan al evaluador y a Ollama.

## API FastAPI

La API usa SQLite como fuente principal y comparte los servicios de evaluación y
generación con la CLI. Para iniciar el backend:

```bash
uvicorn api.main:app --reload
```

Endpoints iniciales:

- `GET /health`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/jobs/{id}/evaluate`
- `POST /api/v1/jobs/{id}/documents`
- `GET /api/v1/documents/{filename}`
- `GET /api/v1/applications`
- `GET /api/v1/applications/{id}`
- `PATCH /api/v1/applications/{id}`
- `POST /api/v1/jobs/{id}/evaluate-task`
- `POST /api/v1/jobs/{id}/documents-task`
- `GET /api/v1/tasks/{id}`

Las operaciones lentas de Ollama y generación de documentos pueden encolarse como
tareas persistentes. Devuelven `202 Accepted` y se consultan mediante
`GET /api/v1/tasks/{id}`. Los estados son `queued`, `running`, `completed` o
`failed`. La API no activa envíos automáticos.

`JOB_SOURCES` controla las fuentes activas, separadas por comas:
`jsearch`, `rss`, `computrabajo` y `linkedin-import`. Cada fuente falla de forma
aislada para que una caída no impida consultar las demás; el error se muestra en
la salida del proceso.

Computrabajo se consulta únicamente mediante una URL pública configurada por el
usuario. Define, por ejemplo, `COMPUTRABAJO_SEARCH_URL_TEMPLATE` con los
marcadores `{query}`, `{query_slug}` y `{location}` que admita la URL pública
vigente. El adaptador no inicia sesión, no resuelve CAPTCHA y no intenta evadir
robots.txt o controles anti-bot. Si la estructura del portal cambia, se debe
revisar el adaptador antes de aumentar la frecuencia de consulta.

LinkedIn se integra mediante importación controlada, no mediante scraping o
automatización de login. Exporta o prepara un CSV/JSON con campos `title`,
`company`, `description`, `url`, `location` y opcionalmente `published_at`, y
configura `LINKEDIN_IMPORT_PATH`. Esto permite usar alertas o datos obtenidos
manualmente y mantiene la revisión humana.

También existe un adaptador opcional para proveedores RapidAPI:
`facebook-api` y `linkedin-api`. Como cada suscripción tiene endpoints y esquemas
distintos, copia desde el Playground el endpoint, el campo que contiene la lista
de resultados (`response path`) y los parámetros requeridos:

```env
JOB_SOURCES=jsearch,facebook-api,linkedin-api
FACEBOOK_RAPIDAPI_HOST=facebook-scraper3.p.rapidapi.com
FACEBOOK_RAPIDAPI_ENDPOINT=<ruta-del-playground>
FACEBOOK_RAPIDAPI_RESPONSE_PATH=data
FACEBOOK_RAPIDAPI_PARAMS_JSON={"country":"co"}
LINKEDIN_RAPIDAPI_HOST=<host-del-playground>
LINKEDIN_RAPIDAPI_ENDPOINT=<ruta-del-playground>
LINKEDIN_RAPIDAPI_RESPONSE_PATH=data
LINKEDIN_RAPIDAPI_PARAMS_JSON={"location":"Colombia"}
```

El adaptador reutiliza `JSEARCH_API_KEY` como clave RapidAPI y normaliza campos
comunes (`title`, `company`, `description`, `url`, `location`). No se debe copiar
la clave en `config.example.env`. Si el proveedor usa otra autenticación o una
respuesta anidada, ajusta `*_RAPIDAPI_QUERY_PARAM` y
`*_RAPIDAPI_RESPONSE_PATH` según su documentación.

### Captura automática de vacantes

La captura está separada del procesamiento:

```bash
./venv/bin/python -m tools.fetch_jobs
./venv/bin/python -m tools.daily_run
```

`fetch_jobs` consulta JSearch con roles bilingües de datos, QA, DevOps, Cloud, Full Stack
y desarrollo/programación de software, combina opcionalmente feeds RSS, deduplica por ID o
hash de URL y persiste el catálogo en `data/jobs.json`. El límite se aplica antes de enviar
ofertas al evaluador y nunca supera 50 aunque `MAX_OLLAMA_JOBS` tenga un valor mayor.
`daily_run` procesa únicamente las ofertas nuevas devueltas por `fetch_jobs`; si la captura
devuelve cero, termina sin reevaluar el catálogo histórico.

LinkedIn, Computrabajo y Empleo Colombia pueden aparecer indirectamente mediante la cobertura
de JSearch. Para una fuente que ofrezca RSS se puede añadir su URL a `JOB_RSS_FEEDS`. No se
automatiza el inicio de sesión ni se evaden CAPTCHA, robots.txt o controles anti-bot; para
esas páginas se debe crear un adaptador autorizado y específico.

### Ejecución cada 24 horas con systemd user timer

Para un PC que solo está encendido en ciertos momentos, un timer de usuario es conveniente:
ejecuta la tarea cuando el equipo está encendido y no requiere mantenerlo conectado todo el
día. Si está apagado a la hora exacta, `Persistent=true` permite ejecutar la tarea al volver
a encenderlo.

Crea `~/.config/systemd/user/job-agent.service`:

```ini
[Unit]
Description=Fetch and process job applications

[Service]
Type=oneshot
WorkingDirectory=/home/brandon/Descargas/job
ExecStart=/home/brandon/Descargas/job/venv/bin/python -m tools.daily_run
```

Crea `~/.config/systemd/user/job-agent.timer`:

```ini
[Unit]
Description=Run job agent daily

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true
Unit=job-agent.service

[Install]
WantedBy=timers.target
```

Activa el timer:

```bash
systemctl --user daemon-reload
systemctl --user enable --now job-agent.timer
systemctl --user list-timers job-agent.timer
```

Para probarlo manualmente:

```bash
systemctl --user start job-agent.service
journalctl --user -u job-agent.service -f
```

Ollama debe estar disponible cuando se ejecuta el servicio; configúralo como servicio de
usuario o asegúrate de iniciarlo antes del timer.

### Integración con Ollama

El evaluador usa Ollama únicamente para escoger el CV base. El modelo recibe la descripción
de la oferta y un catálogo resumido de los CV `.md`; no recibe los PDF. La respuesta esperada
es JSON y el nombre de archivo se valida contra el catálogo antes de continuar.

1. Instala Ollama desde [ollama.com](https://ollama.com).
2. Inicia el servicio:

   ```bash
   ollama serve
   ```

3. Descarga un modelo:

   ```bash
   ollama pull llama3.2
   ```

4. Configura el nombre si quieres usar otro modelo:

   ```env
   OLLAMA_MODEL=llama3.2
   ```

5. Ejecuta el flujo:

   ```bash
   python3 main.py
   ```

La librería Python se conecta por defecto al servicio local de Ollama en
`http://127.0.0.1:11434`. Si el servicio está apagado, el modelo no existe o devuelve
una respuesta inválida, el sistema registra `local-fallback` y selecciona el perfil por
coincidencia de habilidades. Esto permite probar el proyecto sin depender del LLM.

El generador usa Ollama para adaptar de forma conservadora el perfil profesional y los bullets
de experiencia. El modelo recibe el perfil o los bullets seleccionados, la oferta y las brechas detectadas.
La respuesta debe conservar la cantidad de bullets y cada tecnología nueva se valida contra
el CV fuente; si no supera esas validaciones, se conservan los bullets originales.
Además, se genera un `.md`, un `.html` y un `.pdf` limpio en `output/`. El PDF se renderiza
desde HTML/CSS con Playwright para controlar tipografía, márgenes, jerarquía y saltos de página.
Si el navegador de Playwright no está disponible, se usa ReportLab como fallback; el contenido
no se inventa ni se extrae de fuentes externas.

El documento final conserva también encabezado, educación, experiencia completa, habilidades,
cursos e idiomas del CV seleccionado. Las experiencias no relevantes no se eliminan: solo se
priorizan los bullets relacionados con la oferta para la adaptación y los demás se mantienen.

Para validar únicamente la selección:

```bash
python3 -m unittest discover -s tests -v
```

## Evolución

- Implementar adaptadores específicos de Greenhouse/Lever con Playwright o browser-use.
- Sustituir el evaluador por un proveedor LLM con salida estructurada y trazabilidad.
- Cambiar el logger CSV por Notion/Airtable manteniendo `ApplicationRecord`.
- Añadir Telegram para la solicitud de confirmación.

El envío automático está intencionadamente protegido: el MVP no presenta una candidatura sin una integración de sitio configurada y una confirmación explícita.

Los CV en PDF se conservan como documentos originales. El evaluador construye un catálogo con los CV `.md` de la misma carpeta que `CV_PATH`, excluyendo `master_cv.md`, y selecciona uno antes de evaluar y generar documentos. El texto extraído de cada PDF puede convertirse a `.md` para añadirlo al catálogo.
## Ejecución segura y reproducible

El catálogo puede ejecutarse con SQLite para evitar sobrescrituras concurrentes:

```env
STORAGE_BACKEND=sqlite
JOB_DB_PATH=data/jobs.db
ALLOW_REMOTE_LLM=false
```

Con `STORAGE_BACKEND=sqlite`, la primera ejecución importa las ofertas existentes de
`data/jobs.json` y escribe las nuevas en `data/jobs.db`. El CSV de postulaciones se
protege con bloqueo de archivo durante la transición.

Las descripciones obtenidas de APIs, RSS o páginas públicas se tratan como datos no
confiables en los prompts. No se siguen instrucciones incluidas en una oferta. El
modelo remoto está bloqueado por defecto; solo se puede habilitar explícitamente con
`ALLOW_REMOTE_LLM=true` después de revisar la política de privacidad del proveedor.

Para un entorno reproducible con Playwright/Chromium y ReportLab:

```bash
docker build -t job-agent .
docker run --rm --env-file .env -v "$PWD/data:/app/data" -v "$PWD/output:/app/output" job-agent
```

El scraping reintenta errores transitorios (`429`, `5xx`) con backoff y respeta
`Retry-After`. Un `403` no se evade ni se reintenta automáticamente.

## Frontend React

El frontend independiente está en [`frontend/`](./frontend) y consume la API
FastAPI mediante el proxy de Vite.

En una terminal inicia el backend:

```bash
.venv/bin/uvicorn api.main:app --reload
```

En otra terminal instala y ejecuta el frontend:

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173`. El panel permite consultar ofertas y candidaturas,
encolar evaluaciones o generación de documentos, consultar el progreso de las
tareas y actualizar el estado de una candidatura. El envío automático permanece
desactivado.

Para validar el bundle de producción:

```bash
cd frontend
npm run build
```
