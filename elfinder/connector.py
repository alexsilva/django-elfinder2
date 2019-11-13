""" Connector class for Django/elFinder integration.

TODO

Permissions checks when viewing/modifying objects - users can currently
create files in other people's file collections, or delete files they
do not own. This needs to be implemented in an extendable way, rather
than being tied to one method of permissions checking.
"""

import logging
import os

import collections
import patoolib

logger = logging.getLogger(__name__)


class ElFinderConnector(object):
    _version = '2.1'

    def __init__(self, volumes=None):
        if volumes is None:
            volumes = {}
        self.httpResponse = {}
        self.httpStatusCode = 200
        self.httpHeader = {'Content-type': 'application/json'}
        self.data = {}
        self.response = {}
        self.return_view = None
        self.is_return_view = False

        # Populate the volumes dict, using volume_id as the key
        self.volumes = {}
        for volume in volumes:
            self.volumes[volume.get_volume_id()] = volume

    def get_commands(self):
        """ Returns a dict which maps command names to functions.

            The dict key is the command name. The value is a tuple containing
            the name of a function on this class, and a dict specifying which
            GET variables must be set/unset. This lets us do validation of the
            given arguments, so the command functions can assume the correct
            values are set. Used by check_command_functions.
        """
        return {
            'open': {'method': '__open', 'options': ['target']},
            'tree': {'method': '__tree', 'options': ['target']},
            'file': {'method': '__file', 'options': ['target']},
            'parents': {'method': '__parents', 'options': ['target']},
            'mkdir': [
                {'method': '__mkdir', 'options': ['target', 'name']},
                {'method': '__mkdirs', 'options': ['target', 'dirs']},
            ],
            'mkfile': {'method': '__mkfile', 'options': ['target', 'name']},
            'rename': {'method': '__rename', 'options': ['target', 'name']},
            'ls': {'method': '__list', 'options': ['target']},
            'paste': {'method': '__paste',
                      'options': ['targets[]', 'dst', 'cut', 'suffix'],
                      'defaults': {'renames[]': []}},
            'rm': {'method': '__remove', 'options': ['targets[]']},
            'upload': [
                {'method': '__upload',
                 'options': ['target'],
                 'defaults': {'overwrite': True, 'suffix': '~', 'renames[]': []},
                 'exclude': ['chunk', 'range', 'cid', 'upload[]']},
                {'method': '__upload_chunked', 'options': ['target', 'range', 'chunk', 'cid']},
                {'method': '__upload_chunked_req',
                 'options': ['target', 'upload[]', 'chunk'],
                 'defaults': {'suffix': '~', 'renames[]': [],
                              'mimes': None, 'cid': None, 'overwrite': True}},
            ],
            'duplicate': {'method': '__duplicate', 'options': ['targets[]']},
            'extract': {'method': '__extract', 'options': ['target']},
            'archive': {'method': '__archive',
                        'options': ['target', 'targets[]', 'name', 'type']},
            'search': {'method': '__search', 'options': ['target', 'q']},
            'zipdl': {'method': '__zip_download', 'options': ['targets[]']}
        }

    def get_init_params(self):
        """ Returns a dict which is used in response to a client init request.

            The returned dict will be merged with response during the __open
            command.
        """
        return {'api': self._version}

    def get_allowed_http_params(self):
        """ Returns a list of parameters allowed during GET/POST requests.
        """
        return ['cmd', 'target', 'targets[]', 'current', 'tree',
                'name', 'content', 'src', 'dst', 'cut', 'init',
                'type', 'width', 'height', 'upload[]', 'dirs[]',
                'q', 'download', 'suffix', 'overwrite', 'renames[]',
                'chunk', 'cid', 'range', 'mimes']

    def get_volume(self, hash):
        """ Returns the volume which contains the file/dir represented by the
            hash.
        """
        try:
            volume_id, target = hash.split('_')
        except ValueError:
            raise Exception('Invalid target hash: %s' % hash)

        return self.volumes[volume_id]

    def check_command_variables(self, options, exclude):
        """ Checks the GET variables to ensure they are valid for this command.
            _commands controls which commands must or must not be set.

            This means command functions do not need to check for the presence
            of GET vars manually - they can assume that required items exist.
        """
        for field in options:
            if field not in self.data:
                return False
        for field in exclude:
            if field in self.data:
                return False
        return True

    def run_command(self, func_name, **defaults):
        """ Attempts to run the given command.

            If the command does not execute, or there are any problems
            validating the given GET vars, an error message is set.

            func: the name of the function to run (e.g. __open)
            command_variables: a list of 'name':True/False tuples specifying
            which GET variables must be present or empty for this command.
        """
        func = getattr(self, '_' + self.__class__.__name__ + func_name, None)
        if not isinstance(func, collections.Callable):
            self.response['error'] = 'Command failed'
            return

        try:
            return func(**defaults)
        except Exception as e:
            self.response['error'] = '%s' % e
            logger.exception(e)

    @staticmethod
    def _convert_bool(v):
        return bool(int(v))

    def _get_defaults(self, **defaults):
        for field in defaults:
            if field in self.data:
                method_name = '_convert_{0.__name__}'.format(type(defaults[field]))
                method = getattr(self, method_name, lambda value: value)
                defaults[field] = method(self.data[field])
        return defaults

    def run(self, request):
        """ Main entry point for running commands. Attemps to run a command
            function based on info in request.GET.

            The command function will complete in one of two ways. It can
            set response, which will be turned in to an HttpResponse and
            returned to the client.

            Or it can set return_view, a Django View function which will
            be rendered and returned to the client.
        """

        self.request = request

        # Is this a POST or a GET?
        data_source = getattr(request, request.method)

        # Copy allowed parameters from the given request's GET to self.data
        for field in self.get_allowed_http_params():
            if field in data_source:
                if field in ["targets[]", "dirs[]", "renames[]", "upload[]"]:
                    self.data[field] = data_source.getlist(field)
                else:
                    self.data[field] = data_source[field]

        # If a valid command has been specified, try and run it. Otherwise set
        # the relevant error message.
        commands = self.get_commands()
        if 'cmd' in self.data:
            if self.data['cmd'] in commands:
                cmd = commands[self.data['cmd']]
                if isinstance(cmd, list):
                    for command in cmd:
                        if self.check_command_variables(command['options'], command.get('exclude', ())):
                            defaults = self._get_defaults(**command.get('defaults', {}))
                            self.run_command(command['method'], **defaults)
                            break
                    else:
                        self.response['error'] = 'Invalid arguments'
                elif self.check_command_variables(cmd['options'], cmd.get('exclude', ())):
                    defaults = self._get_defaults(**cmd.get('defaults', {}))
                    self.run_command(cmd['method'], **defaults)
                else:
                    self.response['error'] = 'Invalid arguments'
            else:
                self.response['error'] = 'Unknown command'
        else:
            self.response['error'] = 'No command specified'

        self.httpResponse = self.response
        return self.httpStatusCode, self.httpHeader, self.httpResponse

    def __zip_download(self):
        """pack files in temp zip file"""
        targets = self.data["targets[]"]
        download = bool(int(self.data.get('download', 0)))
        volume = self.get_volume(targets[0])
        result = volume.zip_download(targets, download)
        if not download:
            self.response['zipdl'] = result
        else:
            self.is_return_view = True
            self.return_view = result

    def __search(self):
        """Do search"""
        target = self.data['target']
        query = self.data['q']
        volume = self.get_volume(target)
        self.response['files'] = volume.search(query, target)

    def __parents(self):
        """ Handles the parent command.

            Sets response['tree'], which contains a list of dicts representing
            the ancestors/siblings of the target object.

            The tree is not a tree in the traditional hierarchial sense, but
            rather a flat list of dicts which have hash and parent_hash (phash)
            values so the client can draw the tree.
        """
        target = self.data['target']
        volume = self.get_volume(target)
        self.response['tree'] = volume.get_tree(target,
                                                ancestors=True,
                                                siblings=True)

    def __tree(self):
        """ Handles the 'tree' command.

            Sets response['tree'] - a list of children of the specified
            target Directory.
        """
        target = self.data['target']
        volume = self.get_volume(target)
        self.response['tree'] = volume.get_tree(target)

    def __file(self):
        """ Handles the 'file' command.

            Sets return_view, which will cause read_file_view to be rendered
            as the response. A custom read_file_view can be given when
            initialising the connector.
        """
        target = self.data['target']
        volume = self.get_volume(target)

        # A file was requested, so set return_view to the read_file view.
        # self.return_view = self.read_file_view(self.request, volume, target)
        self.return_view = volume.read_file_view(self.request, target)
        self.is_return_view = True

    def __open(self):
        """ Handles the 'open' command.

            Sets response['files'] and response['cwd'].

            If 'tree' is requested, 'files' contains information about all
            ancestors, siblings and children of the target. Otherwise, 'files'
            only contains info about the target's immediate children.

            'cwd' contains info about the currently selected directory.

            If 'target' is blank, information about the root dirs of all
            currently-opened volumes is returned. The root of the first
            volume is considered to be the current directory.
        """
        if 'tree' in self.data and self.data['tree'] == '1':
            inc_ancestors = True
            inc_siblings = True
        else:
            inc_ancestors = False
            inc_siblings = False

        target = self.data['target']
        if target == '':
            # No target was specified, which means the client is being opened
            # for the first time and requires information about all currently
            # opened volumes.

            # Assume the first volume's root is the currently open directory.
            volume = next(iter(self.volumes.values()))
            self.response.update(volume.get_options())
            self.response['cwd'] = volume.get_info('')

            # Add relevant tree information for each volume
            for volume_id in self.volumes:
                volume = self.volumes[volume_id]
                self.response['files'] = volume.get_tree('',
                                                         inc_ancestors,
                                                         inc_siblings)
        else:
            # A target was specified, so we only need to return info about
            # that directory.
            volume = self.get_volume(target)
            self.response.update(volume.get_options())
            self.response['cwd'] = volume.get_info(target)
            self.response['files'] = volume.get_tree(target,
                                                     inc_ancestors,
                                                     inc_siblings)

        # If the request includes 'init', add some client initialisation
        # data to the response.
        if 'init' in self.data:
            self.response.update(self.get_init_params())

    def __mkdir(self):
        target = self.data['target']
        volume = self.get_volume(target)
        self.response['added'] = [volume.mkdir(self.data['name'], target)]

    def __mkdirs(self):
        target = self.data['target']
        volume = self.get_volume(target)
        added = []
        for dirname in self.data['dirs']:
            added.append(volume.mkdir(dirname, target))
        self.response['added'] = added

    def __mkfile(self):
        target = self.data['target']
        volume = self.get_volume(target)
        self.response['added'] = [volume.mkfile(self.data['name'], target)]

    def __rename(self):
        target = self.data['target']
        volume = self.get_volume(target)
        self.response.update(volume.rename(self.data['name'], target))

    def __list(self):
        target = self.data['target']
        volume = self.get_volume(target)
        self.response['list'] = volume.list(target)

    def __paste(self, **kwargs):
        targets = self.data['targets[]']
        dest = self.data['dst']
        cut = (self.data['cut'] == '1')
        source_volume = self.get_volume(targets[0])
        dest_volume = self.get_volume(dest)
        if source_volume != dest_volume:
            raise Exception('Moving between volumes is not supported.')
        self.response.update(dest_volume.paste(targets, dest, cut, **kwargs))

    def __archive(self):
        target = self.data['target']
        targets = self.data['targets[]']
        name = self.data['name']
        type = self.data['type']
        source_volume = self.get_volume(target)
        abs_path = source_volume._find_path(target)
        type_map = {
            "application/x-tar": 'tar',
            "application/zip": 'zip',
        }
        added = []
        zipfile = None
        if abs_path:
            zipfile = os.path.join(abs_path, "{}.{}".format(name, type_map[type]))
            files = []
            for trg in targets:
                orig_abs_path = source_volume._find_path(trg)
                files.append(orig_abs_path)

            patoolib.create_archive(zipfile, files)
        for node in source_volume.get_tree(target):
            if source_volume._find_path(node['hash']) == zipfile:
                added.append(node)
        self.response.update({"added": added})

    def __extract(self):
        target = self.data['target']
        source_volume = self.get_volume(target)
        archive_file = source_volume.get_info(target)
        archive_file_path = source_volume._find_path(target)
        archive_name = archive_file_path.split('/')[-1].split('.')[0]
        folder_path = os.path.join(
            source_volume._find_path(archive_file.get('phash')),
            archive_name
        )
        self.get_volume(archive_file.get('phash')).mkdir(archive_name, archive_file.get('phash'))
        patoolib.extract_archive(archive_file_path, outdir=folder_path, interactive=False)
        added = []
        for node in source_volume.get_tree(archive_file.get('phash')):
            if source_volume._find_path(node['hash']) == folder_path:
                added.append(node)

        self.response.update({"added": added})

    def __remove(self):
        targets = self.data['targets[]']
        self.response['removed'] = []
        warnings = []
        # Because the targets might not all belong to the same volume, we need
        # to lookup the volume and call the remove() function for every target.
        for target in targets:
            volume = self.get_volume(target)
            warning = volume.remove(target)
            if warning:
                warnings.extend(warning)
                continue
            self.response['removed'].append(target)
        # Errors caused when removing files in directories.
        if warnings:
            self.response['warning'] = warnings

    def __upload(self, **kwargs):
        parent = self.data['target']
        volume = self.get_volume(parent)
        self.response.update(volume.upload(self.request.FILES, parent, **kwargs))

    def __upload_chunked(self, **kwargs):
        parent = self.data['target']

        cid = self.data['cid']
        chunk = self.data['chunk']
        bytes_range = self.data['range']

        volume = self.get_volume(parent)
        data = volume.upload_chunked(self.request.FILES,
                                     parent, cid, chunk,
                                     bytes_range,
                                     **kwargs)
        self.response.update(data)

    def __upload_chunked_req(self, **kwargs):
        parent = self.data['target']
        volume = self.get_volume(parent)
        chunk = self.data['chunk']
        files = self.data['upload[]']
        data = volume.upload_chunked_req(files, parent, chunk, **kwargs)
        self.response.update(data)

    def __duplicate(self):
        """Duplicate files and dirs"""
        targets = self.data['targets[]']
        volume = self.get_volume(targets[0])
        self.response.update(volume.duplicate(targets))