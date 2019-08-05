# -*- coding: utf-8 -*-
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import render

from elfinder.conf import settings


def tinymce_filebrowser_script_view(request):
    """
    View for rendering JS with TnyMCE file browser callback function.
    """
    return render(request, "elfinder/tinymce_filebrowser_script.html", content_type="text/javascript")


def tinymce_filebrowser_dialog_view(request):
    """
    View for rendering elfinder with TinyMCE popup bindings.
    """
    tinymce_popup_js = settings.ELFINDER_TINYMCE_PATH_TO_POPUP_JS
    if tinymce_popup_js is None:
        raise ImproperlyConfigured("ELFINDER_TINYMCE_PATH_TO_POPUP_JS must be specified in settings")

    return render(request, "elfinder/tinymce_filebrowser_dialog.html", {"tinymce_popup_js": tinymce_popup_js})
