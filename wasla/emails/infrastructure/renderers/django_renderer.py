from __future__ import annotations

from typing import Mapping

from django.template.loader import render_to_string

from emails.domain.ports import RenderedEmail, TemplateRendererPort


class DjangoTemplateRendererAdapter(TemplateRendererPort):
    """
    Template convention:
    - templates/emails/<template_key>.subject.txt
    - templates/emails/<template_key>.html
    - templates/emails/<template_key>.txt (optional)
    """

    def render(self, *, template_key: str, context: Mapping[str, object]) -> RenderedEmail:
        subject = render_to_string(f"emails/{template_key}.subject.txt", context).strip()
        html = ""
        text = ""
        try:
            html = render_to_string(f"emails/{template_key}.html", context)
        except Exception:
            html = ""
        try:
            text = render_to_string(f"emails/{template_key}.txt", context)
        except Exception:
            text = ""
        return RenderedEmail(subject=subject, html=html, text=text, headers={})

