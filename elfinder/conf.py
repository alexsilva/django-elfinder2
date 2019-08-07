# -*- coding: utf-8 -*-
from django.conf import settings as user_settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import LazyObject


class Settings(object):
    pass


class LazySettings(LazyObject):
    def _setup(self):
        self._wrapped = Settings()

        self.ELFINDER_VOLUME_DRIVERS = getattr(
            user_settings, "ELFINDER_VOLUME_DRIVERS", {
                "default": {
                    "BACKEND": "elfinder.volume_drivers.model_driver.ModelVolumeDriver",
                },
                "fs": {
                    "BACKEND": "elfinder.volume_drivers.fs_driver.FileSystemVolumeDriver",
                    "OPTIONS": {"fs_root": user_settings.MEDIA_ROOT}
                }
            })
        if not isinstance(self.ELFINDER_VOLUME_DRIVERS, dict):
            raise ImproperlyConfigured('ELFINDER_VOLUME_DRIVERS is not a dict!')

        self.ELFINDER_FS_DRIVER_URL = getattr(
            user_settings, "ELFINDER_FS_DRIVER_URL",
            user_settings.MEDIA_URL
        )

        # special settings for TinyMCE connector
        self.ELFINDER_TINYMCE_PATH_TO_POPUP_JS = getattr(
            user_settings, "ELFINDER_TINYMCE_PATH_TO_POPUP_JS",
            None
        )


settings = LazySettings()
