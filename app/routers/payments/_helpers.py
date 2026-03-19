"""Sdílené helper funkce pro modul plateb."""

import logging

from fastapi.templating import Jinja2Templates

from app.utils import setup_jinja_filters

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")
setup_jinja_filters(templates)
