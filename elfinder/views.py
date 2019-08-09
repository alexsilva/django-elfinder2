import json

from django.contrib.auth.decorators import user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.functional import cached_property
from django.views.decorators.csrf import ensure_csrf_cookie

from elfinder.connector import ElFinderConnector
from elfinder.volume_drivers import get_volume_driver


class VolumeDriver(object):
    def __init__(self, request, json_response=False, **options):
        self.request = request
        self.options = options
        self.json_response = json_response

    @cached_property
    def name(self):
        request_method = getattr(self.request, self.request.method)
        return request_method.get('volume', 'default')

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
        return self.access_view is True
    __nonzero__ = __bool__

    @cached_property
    def access_view(self):
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
def index(request, coll_id=None):
    """ Displays the elFinder file browser template for the specified
        collection.
    """
    volume = VolumeDriver(request, collection_id=coll_id)

    if not volume: # not has access
        return volume.access_view

    return render_to_response("elfinder/index.html",
                              {'coll_id': coll_id,
                               'volume': volume},
                              RequestContext(request))


@ensure_csrf_cookie
def connector_view(request, coll_id=None):
    """ Handles requests for the elFinder connector.
    """
    volume_driver = VolumeDriver(request,
                                 json_response=True,
                                 collection_id=coll_id)

    if not volume_driver:  # not has access
        return volume_driver.access_view

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
    return render_to_response(template,
                              {'file': file_hash},
                              RequestContext(request))
