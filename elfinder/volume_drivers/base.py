from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.six import string_types


class BaseVolumeDriver(object):
    def __init__(self, request=None, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.request = request

    def get_volume_id(self):
        """ Returns the volume ID for the volume, which is used as a prefix
            for client hashes.
        """
        raise NotImplementedError

    def _get_connector_url(self):
        """:return url of driver connector"""
        view_name = self.kwargs.get('connector_url_view_name',
                                    'elfinder_connector')
        collection_id = self.kwargs.get('collection_id')
        if collection_id:
            url = reverse(view_name, kwargs={'coll_id': collection_id})
        else:
            url = reverse(view_name)
        return url

    connector_url = cached_property(_get_connector_url)

    @cached_property
    def login_required(self):
        return bool(self.kwargs.get('login_required'))

    @cached_property
    def login_url(self):
        return self.kwargs.get('login_url')

    @cached_property
    def login_test_func(self):
        test_func = self.kwargs.get('login_test_func')
        if isinstance(test_func, string_types):
            test_func = import_string(test_func)
        else:
            test_func = lambda u: u.is_authenticated
        return test_func

    def get_options(self):
        """Volume config defaults"""
        options = {
            'uplMaxSize': '128M',
            'options': {'separator': '/',
                        'disabled': [],
                        'copyOverwrite': 1}
        }
        options.update(self.kwargs.get('js_api_options', {}))
        return options

    def get_index_template(self, template):
        """Template that render the index view."""
        return self.kwargs.get('index_template', template)

    def get_info(self, target):
        """ Returns a dict containing information about the target directory
            or file. This data is used in response to 'open' commands to
            populates the 'cwd' response var.

            :param target: The hash of the directory for which we want info.
            If this is '', return information about the root directory.
            :returns: dict -- A dict describing the directory.
        """
        raise NotImplementedError

    def zip_download(self, targets, dl=False):
        """ Prepare files for download

            :param targets[]: array of hashed paths of the nodes
            :returns: dict -- A dict describing the zip file.
        """
        raise NotImplementedError

    def get_tree(self, target, ancestors=False, siblings=False):
        """ Gets a list of dicts describing children/ancestors/siblings of the
            target.

            :param target: The hash of the directory the tree starts from.
            :param ancestors: Include ancestors of the target.
            :param siblings: Include siblings of the target.
            :param children: Include children of the target.
            :returns: list -- a list of dicts describing directories.
        """
        raise NotImplementedError

    def read_file_view(self, request, hash):
        """ Django view function, used to display files in response to the
            'file' command.

            :param request: The original HTTP request.
            :param hash: The hash of the target file.
            :returns: dict -- a dict describing the new directory.
        """
        raise NotImplementedError

    def search(self, text, target):
        """ Search for file/directory

            :param query: search string.
            :param hash: The hash of the parent directory.
            :returns: mimes
        """
        raise NotImplementedError

    def mkdir(self, name, parent):
        """ Creates a directory.

            :param name: The name of the new directory.
            :param parent: The hash of the parent directory.
            :returns: dict -- a dict describing the new directory.
        """
        raise NotImplementedError

    def mkfile(self, name, parent):
        """ Creates a directory.

            :param name: The name of the new file.
            :param parent: The hash of the parent directory.
            :returns: dict -- a dict describing the new file.
        """
        raise NotImplementedError

    def rename(self, name, target):
        """ Renames a file or directory.

            :param name: The new name of the file/directory.
            :param target: The hash of the target file/directory.
            :returns: dict -- a dict describing which objects were added and
            removed.
        """
        raise NotImplementedError

    def duplicate(self, targets):
        """Creates a copy of the directory / file. Copy name is generated as follows:
        basedir_name_filecopy+serialnumber.extension (if any)
        """

    def list(self, target):
        """ Lists the contents of a directory.

            :param target: The hash of the target directory.
            :returns: list -- a list containing the names of files/directories
            in this directory.
        """
        raise NotImplementedError

    def paste(self, targets, dest, cut):
        """ Moves/copies target files/directories from source to dest.

            If a file with the same name already exists in the dest directory
            it should be overwritten (the client asks the user to confirm this
            before sending the request).

            :param targets: A list of hashes of files/dirs to move/copy.
            :param source: The current parent of the targets.
            :param dest: The new parent of the targets.
            :param cut: Boolean. If true, move the targets. If false, copy the
            targets.
            :returns: dict -- a dict describing which targets were moved/copied.
        """
        raise NotImplementedError

    def size(self, targets):
        """ Returns the size of a directory or file.

            size: The total size for all the supplied targets.
            fileCnt: The total counts of the file for all the supplied targets. (Optional to API >= 2.1025)
            dirCnt: The total counts of the directory for all the supplied targets. (Optional to API >= 2.1025)
            sizes: An object of each target size infomation. (Optional to API >= 2.1030)
        """
        raise NotImplementedError

    def remove(self, target):
        """ Deletes the target files/directories.

            The 'rm' command takes a list of targets - this function is called
            for each target, so should only delete one file/directory.

            :param targets: A list of hashes of files/dirs to delete.
            :returns: list -- warnings generated when trying to remove a file or directory.
        """
        raise NotImplementedError

    def upload(self, files, parent):
        """ Uploads one or more files in to the parent directory.

            :param files: A list of uploaded file objects, as described here:
            https://docs.djangoproject.com/en/dev/topics/http/file-uploads/
            :param parent: The hash of the directory in which to create the
            new files.
            :returns: TODO
        """

    def upload_chunked(self, files, target, cid, chunk, bytes_range):
        """
        Chunking arguments:
        chunk : chunk name "filename.[NUMBER]_[TOTAL].part"
        cid : unique id of chunked uploading file
        range : Bytes range of file "Start byte,Chunk length,Total bytes
        """

    def upload_chunked_req(self, files, parent, chunk):
        """Chunk merge request (When receive _chunkmerged, _name)"""
