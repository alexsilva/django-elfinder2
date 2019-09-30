# -*- coding: utf-8 -*-
from django.core.exceptions import ImproperlyConfigured

from elfinder.conf import settings as elfinder_settings
from elfinder.helpers import get_module_class


def get_volume_driver(name='default', **options):
    volume = elfinder_settings.ELFINDER_VOLUME_DRIVERS.get(name)
    if volume is None:
        raise ImproperlyConfigured(u"volume driver name '{0!s}' not found!".format(name))
    driver = volume.get('BACKEND')
    driver_options = volume.get('OPTIONS', {})
    options['volume_driver_name'] = name
    driver_options.update(options)
    return get_module_class(driver)(**driver_options)
