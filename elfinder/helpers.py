# -*- coding: utf-8 -*-
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


def get_module_class(class_path):
    """
    imports and returns module class from ``path.to.module.Class``
    argument
    """
    try:
        klass = import_string(class_path)
    except ImportError as exc:
        raise ImproperlyConfigured('Error importing class path: "%s"' % exc)
    return klass
