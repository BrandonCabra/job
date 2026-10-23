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
- `CRM_PATH=data/applications.csv`: CRM local.
- `CV_PATH=data/master_cv.md`: archivo de referencia; el evaluador selecciona dinámicamente otro `.md` de `data/` usando Ollama.
- `OLLAMA_MODEL=llama3.2`: modelo local usado para elegir el CV más adecuado. Si Ollama no está disponible, se usa una selección local por coincidencia de términos.
- `OLLAMA_HOST=http://127.0.0.1:11434`: dirección del servidor local de Ollama.
- `OLLAMA_TIMEOUT_SECONDS=90`: tiempo máximo de espera de una selección antes de activar el fallback local.
- `NOTION_TOKEN`: token de integración de Notion, si se configura un CRM Notion.
- `NOTION_DATABASE_ID`: ID de la base de datos de Notion, si se configura un CRM Notion.

Para JSearch instala `requests`, define `JSEARCH_API_KEY` y usa `JOB_SOURCE=jsearch`. Las credenciales no deben entrar en el repositorio.

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
