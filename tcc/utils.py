from django.contrib.contenttypes.models import ContentType

from tcc.settings import CONTENT_TYPES

_CONTENT_TYPES = None


def get_content_types():
    global _CONTENT_TYPES
    if not _CONTENT_TYPES:
        _CONTENT_TYPES = []
        for label in CONTENT_TYPES:
            ct = ContentType.objects.get_by_natural_key(*label.split("."))
            _CONTENT_TYPES.append(ct.id)
    return _CONTENT_TYPES
