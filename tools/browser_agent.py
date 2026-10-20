from tools.models import Job


def prepare_submission(job: Job, cv_path: str, cover_letter_path: str, auto_submit: bool = False) -> tuple[str, str]:
    """Prepara una candidatura; nunca envía sin activar explícitamente el modo automático."""
    if not auto_submit:
        return "Pendiente de confirmación", "Revisar documentos y enviar manualmente desde la URL"
    # El envío real debe implementarse por sitio y requiere Playwright/browser-use.
    return "Lista para automatización", "Adaptador de navegador no configurado para este sitio"
