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
- `CV_PATH=data/master_cv.md`: CV base utilizado para evaluar y adaptar documentos.
- `NOTION_TOKEN`: token de integración de Notion, si se configura un CRM Notion.
- `NOTION_DATABASE_ID`: ID de la base de datos de Notion, si se configura un CRM Notion.

Para JSearch instala `requests`, define `JSEARCH_API_KEY` y usa `JOB_SOURCE=jsearch`. Las credenciales no deben entrar en el repositorio.

## Evolución

- Implementar adaptadores específicos de Greenhouse/Lever con Playwright o browser-use.
- Sustituir el evaluador por un proveedor LLM con salida estructurada y trazabilidad.
- Cambiar el logger CSV por Notion/Airtable manteniendo `ApplicationRecord`.
- Añadir Telegram para la solicitud de confirmación.

El envío automático está intencionadamente protegido: el MVP no presenta una candidatura sin una integración de sitio configurada y una confirmación explícita.

Los CV en PDF se conservan como documentos originales. Para este MVP, el CV seleccionado por `CV_PATH` debe ser `.md` o texto plano, porque el evaluador y el generador leen el archivo directamente. El texto extraído de cada PDF puede convertirse a `.md` para usarlo como CV base.
