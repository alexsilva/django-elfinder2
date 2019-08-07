import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.csrf import ensure_csrf_cookie

from elfinder.conf import settings
from elfinder.connector import ElFinderConnector
from elfinder.volume_drivers import get_volume_driver


def login_required_if_configured(view):
    """Forces login to view when configured via settings"""
    if settings.ELFINDER_LOGIN_REQUIRED:
        return login_required(view, login_url=settings.ELFINDER_LOGIN_URL)
    return view


def _get_volume_name(request):
    request_method = getattr(request, request.method)
    return request_method.get('volume', 'default')


@login_required_if_configured
@ensure_csrf_cookie
def index(request, coll_id=None):
    """ Displays the elFinder file browser template for the specified
        collection.
    """

    return render_to_response("elfinder/index.html",
                              {'coll_id': coll_id,
                               'volume_name': _get_volume_name(request)},
                              RequestContext(request))


@login_required_if_configured
@ensure_csrf_cookie
def connector_view(request, coll_id=None):
    """ Handles requests for the elFinder connector.
    """
    volume_name = _get_volume_name(request)

    volume = get_volume_driver(volume_name,
                               request=request,
                               collection_id=coll_id)

    finder = ElFinderConnector([volume])
    finder.run(request)

    # Some commands (e.g. read file) will return a Django View - if it
    # is set, return it directly instead of building a response
    if finder.return_view:
        return finder.return_view

    response = HttpResponse(content_type=finder.httpHeader['Content-type'])
    response.status_code = finder.httpStatusCode
    if finder.httpHeader['Content-type'] == 'application/json':
        response.content = json.dumps(finder.httpResponse)
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
