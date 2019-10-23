import json

from django.contrib.auth.decorators import user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.functional import cached_property
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from elfinder.conf import settings
from elfinder.connector import ElFinderConnector
from elfinder.volume_drivers import get_volume_driver


class VolumeDriver(object):
    def __init__(self, request, json_response=False, name=None, **options):
        self.request = request
        self.options = options
        self.json_response = json_response
        self._name = name

    @cached_property
    def name(self):
        if self._name is None:
            request_method = getattr(self.request, self.request.method)
            return request_method.get('volume', 'default')
        else:
            return self._name

    @cached_property
    def volume(self):
        volume = get_volume_driver(self.name,
                                   request=self.request,
                                   **self.options)
        return volume

    @staticmethod
    def _access_view(req):
        return True

    def __bool__(self):
        return self.login_view is True

    __nonzero__ = __bool__

    @cached_property
    def login_view(self):
        """Checks if volume is project by authentication.
        (redirect to view accordingly)"""
        if self.volume.login_required:
            decorator = user_passes_test(test_func=self.volume.login_test_func,
                                         login_url=self.volume.login_url)
            response = decorator(self._access_view)(self.request)
            if response is not True:
                if self.json_response:
                    return JsonResponse({'error': "Login required!"})
                else:
                    return response
        return True


@ensure_csrf_cookie
@never_cache
def index(request, coll_id=None):
    """ Displays the elFinder file browser template for the specified
        collection.
    """
    volume_driver = VolumeDriver(request, collection_id=coll_id)

    if not volume_driver:  # not has access
        return volume_driver.login_view
    context = {
        'coll_id': coll_id,
        'volume_driver': volume_driver
    }
    return render(request, "elfinder/index.html",
                  context=context,
                  using=settings.ELFINDER_TEMPLATE_ENGINE)


@ensure_csrf_cookie
def connector_view(request, coll_id=None):
    """ Handles requests for the elFinder connector.
    """
    volume_driver = VolumeDriver(request,
                                 json_response=True,
                                 collection_id=coll_id)

    if not volume_driver:  # not has access
        return volume_driver.login_view

    finder = ElFinderConnector([volume_driver.volume])
    finder.run(request)

    # Some commands (e.g. read file) will return a Django View - if it
    # is set, return it directly instead of building a response
    if finder.return_view:
        return finder.return_view

    response = HttpResponse(content_type=finder.httpHeader['Content-type'])
    response.status_code = finder.httpStatusCode
    if finder.httpHeader['Content-type'] == 'application/json':
        response.content = json.dumps(finder.httpResponse,
                                      cls=DjangoJSONEncoder,
                                      ensure_ascii=False)
    else:
        response.content = finder.httpResponse

    return response


def read_file(request, volume, file_hash, template="elfinder/read_file.html"):
    """ Default view for responding to "open file" requests.

        coll: FileCollection this File belongs to
        file: The requested File object
    """
    return render(request, template,
                  context={'file': file_hash},
                  using=settings.ELFINDER_TEMPLATE_ENGINE)
