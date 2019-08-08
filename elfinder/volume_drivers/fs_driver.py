# -#- coding: utf-8 -*-
import hashlib
import mimetypes as mimes
import os
import re
import shutil
from datetime import datetime

from django.conf import settings
from django.core.files import File

from elfinder.conf import settings as elfinder_settings
from elfinder.volume_drivers.base import BaseVolumeDriver

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib


class FileExists(IOError):
    pass


class WrapperBase(object):
    def __init__(self, root):
        self.root = root

    def rename(self, new_name):
        new_abs_path = self.root.joinpath(self.path.parent, new_name)
        if not new_abs_path.exists():
            self.path.rename(new_abs_path)
            self.path = new_abs_path
        else:
            raise FileExists(new_abs_path.name)

    def is_dir(self):
        return False

    def is_file(self):
        return False

    def get_hash(self):
        return '%s_%s' % (self._real_hash(self.root)[0:2], self._real_hash(self.path))

    def get_parent_hash(self):
        if self.path.resolve() == self.root.resolve():
            return ''
        return DirectoryWrapper(self.path.parent, self.root).get_hash()

    def _real_hash(self, path):
        enc_path = str(path)
        m = hashlib.md5(enc_path)
        return str(m.hexdigest())


class FileWrapper(WrapperBase):
    def __init__(self, file_path, root, fs_driver_url):
        if not file_path.is_file():
            raise ValueError("'%s' is not a valid file path" % file_path)
        self._file = self._file_path = None
        self.path = file_path
        self.fs_driver_url = fs_driver_url
        super(FileWrapper, self).__init__(root)

    def is_file(self):
        return self.path.is_file()

    @property
    def path(self):
        return self._file_path

    @path.setter
    def path(self, path):
        self._file_path = path
        if self._file is not None:
            self._file.close()
            self._file = None

    @property
    def name(self):
        return self._file.name

    def get_chunks(self):
        if self._file is None:
            self._file = File(self.path.open('rb'))
        return self._file.chunks()

    def get_contents(self):
        if self._file is None:
            self._file = File(self.path.open())
        self._file.seek(0)
        return self._file.read()

    def set_contents(self, data):
        if self._file is not None:
            self._file.close()
            self._file = None
        _file = File(self.path.open("ab"))
        _file.write(data)
        _file.close()

    contents = property(get_contents, set_contents)

    def get_info(self):
        path = self.path
        spath = str(path)
        info = {
            'name': path.name,
            'hash': self.get_hash(),
            'date': datetime.fromtimestamp(path.stat().st_mtime).strftime("%d %b %Y %H:%M"),
            'size': self.get_size(),
            'read': os.access(spath, os.R_OK),
            'write': os.access(spath, os.W_OK),
            'rm': os.access(spath, os.W_OK),
            'url': self.get_url(),
            'phash': self.get_parent_hash() or '',
        }
        if settings.DEBUG:
            info['abs_path'] = str(path.resolve())

        mime, is_image = self.get_mime(spath)
        # if is_image and self.imglib and False:
        #     try:
        #         import Image
        #         l['tmb'] = self.get_thumb_url(f)
        #     except ImportError:
        #         pass
        #     except Exception:
        #         raise

        info['mime'] = mime

        return info

    def get_size(self):
        return self.path.lstat().st_size

    def get_url(self):
        rel_path = self.path.relative_to(self.root).as_posix()
        user_path = '%s/' % (self.root.parts[-1],)
        fs_driver_url = self.fs_driver_url
        if not re.search("(?:%s)$" % re.escape(user_path), fs_driver_url, re.U):
            fs_driver_url += user_path
        if not fs_driver_url.endswith("/") and not rel_path.startswith("/"):
            fs_driver_url += '/'
        return fs_driver_url + rel_path

    def get_mime(self, path):
        mime = mimes.guess_type(path)[0] or 'Unknown'
        if mime.startswith('image/'):
            return mime, True
        else:
            return mime, False

    def remove(self):
        self.path.unlink()

    @classmethod
    def mkfile(cls, file_path, root, fs_driver_url):
        if not file_path.is_file():
            with file_path.open("w"):
                return cls(file_path, root, fs_driver_url=fs_driver_url)
        else:
            raise Exception("File '%s' already exists" % file_path.name)


class DirectoryWrapper(WrapperBase):
    def __init__(self, dir_path, root):
        if not dir_path.is_dir():
            raise ValueError("'%s' is not a valid dir path" % dir_path)
        self._dir_path = None
        self.path = dir_path
        super(DirectoryWrapper, self).__init__(root)

    def is_dir(self):
        return self.path.is_dir()

    @property
    def path(self):
        return self._dir_path

    @path.setter
    def path(self, path):
        self._dir_path = path

    def get_info(self):
        path = self.path
        spath = str(path)
        info = {
            'name': path.name,
            'hash': self.get_hash(),
            'date': datetime.fromtimestamp(path.stat().st_mtime).strftime("%d %b %Y %H:%M"),
            'mime': 'directory',
            'size': self.get_size(),
            'read': os.access(spath, os.R_OK),
            'write': os.access(spath, os.W_OK),
            'rm': os.access(spath, os.W_OK),
            'dirs': self.has_dirs(),
            'phash': self.get_parent_hash() or ''
        }
        if settings.DEBUG:
            info['abs_path'] = str(path.resolve())
        return info

    def get_size(self):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(str(self.path)):
            for filename in filenames:
                fp = self.root.joinpath(dirpath, filename)
                if fp.exists():
                    total_size += fp.stat().st_size
        return total_size

    def has_dirs(self):
        for path in self.path.iterdir():
            if path.is_dir():
                return True
        return False

    def remove(self):
        shutil.rmtree(str(self.path))

    @classmethod
    def mkdir(cls, dir_path, root):
        if not dir_path.exists():
            dir_path.mkdir(parents=True,
                           exist_ok=True)
            return cls(dir_path, root)
        else:
            raise Exception("Directory '%s' already exists" % os.path.basename(dir_path))


class FileSystemVolumeDriver(BaseVolumeDriver):
    def __init__(self, fs_root=settings.MEDIA_ROOT, *args, **kwargs):
        super(FileSystemVolumeDriver, self).__init__(*args, **kwargs)
        self.fs_driver_url = self.kwargs.get('fs_driver_url',
                                             elfinder_settings.ELFINDER_FS_DRIVER_URL)
        self.root = pathlib.Path(fs_root).resolve()

    def get_volume_id(self):
        return DirectoryWrapper(self.root, self.root).get_hash().split("_")[0]

    def get_info(self, target):
        path = self._find_path(target)
        return self._get_path_info(path)

    def get_tree(self, target, ancestors=False, siblings=False):
        path = self._find_path(target)

        tree = [self._get_path_info(path)]
        tree.extend([self._get_path_info(self.root / child) for child in path.iterdir()])

        if ancestors:
            proc_path = path
            while proc_path != self.root:
                tree.append(self._get_path_info(proc_path))
                proc_path, head = proc_path.parent, proc_path.name
                for ancestor_sibling in proc_path.iterdir():
                    ancestor_sibling_abs = self.root / proc_path / ancestor_sibling
                    if ancestor_sibling_abs.is_dir():
                        tree.append(self._get_path_info(ancestor_sibling_abs))

        if siblings and not (path == self.root):
            parent_path, curr_dir = path.parent, path.name
            for sibling in parent_path.iterdir():
                if sibling == curr_dir:
                    continue
                sibling_abs = self.root / parent_path / sibling
                tree.append(self._get_path_info(sibling_abs))
        # print
        # print "*******************************************"
        # print
        # for t in tree:
        #     print t
        # print
        return tree

    def read_file_view(self, request, hash):
        file_path = self._find_path(hash)
        from django.http import HttpResponse
        resp = HttpResponse(content_type='application/force-download')
        file = FileWrapper(file_path, self.root,
                           fs_driver_url=self.fs_driver_url)
        for chunk in file.get_chunks():
            resp.write(chunk)

        return resp

    def mkdir(self, name, parent):
        parent_path = self._find_path(parent)
        new_abs_path = self.root / parent_path / name
        return DirectoryWrapper.mkdir(new_abs_path, self.root).get_info()

    def mkfile(self, name, parent):
        parent_path = self._find_path(parent)
        new_abs_path = self.root / parent_path / name
        return FileWrapper.mkfile(new_abs_path, self.root, self.fs_driver_url).get_info()

    def rename(self, name, target):
        obj = self._get_path_object(self._find_path(target))
        obj.rename(name)
        return {
            "added": [obj.get_info()],
            "removed": [target],
        }

    def list(self, target):
        dir_list = []
        for item in self.get_tree(target):
            dir_list.append(item['name'])
        return dir_list

    def paste(self, targets, source, dest, cut):
        """ Moves/copies target files/directories from source to dest. """
        # source_dir = self._get_path_object(source)
        dest_dir = self._get_path_object(self._find_path(dest))
        added = []
        removed = []
        if dest_dir.is_dir():
            for target in targets:
                orig_abs_path = self._find_path(target)
                orig_obj = self._get_path_object(orig_abs_path)
                new_abs_path = self.root / dest_dir.path / orig_abs_path.name
                if cut:
                    _fnc = shutil.move
                    removed.append(orig_obj.get_info()['hash'])
                else:
                    if orig_obj.is_dir():
                        _fnc = shutil.copytree
                    else:
                        _fnc = shutil.copy
                _fnc(str(orig_abs_path), str(new_abs_path))
                added.append(self._get_path_info(new_abs_path))

        return {"added": added,
                "removed": removed}

    def remove(self, target):
        obj = self._get_path_object(self._find_path(target))
        obj.remove()
        return target

    def upload(self, files, parent):
        added = []
        parent = self._get_path_object(self._find_path(parent))
        if parent.is_dir():
            for upload in files.getlist('upload[]'):
                new_abs_path = self.root / parent.path / upload.name
                try:
                    new_file = FileWrapper.mkfile(new_abs_path, self.root, self.fs_driver_url)
                    new_file.contents = upload.read()
                    added.append(new_file.get_info())
                except Exception:
                    pass
        return {"added": added}

    # private methods

    def _find_path(self, fhash, root=None, resolution=False):
        if root is None:
            root = self.root
        final_path = None

        if not fhash:
            return root

        for dirpath, dirnames, filenames in os.walk(str(root)):
            for filename in filenames:
                filepath = self.root.joinpath(dirpath, filename)
                f_obj = FileWrapper(filepath, self.root,
                                    fs_driver_url=self.fs_driver_url)
                if fhash == f_obj.get_hash():
                    final_path = filepath
                    if resolution:
                        try:
                            final_path = pathlib.Path(str(final_path, 'utf8'))
                        except:
                            pass
                    return final_path

            for dirname in dirnames:
                child_dirpath = self.root.joinpath(dirpath, dirname)
                d_obj = DirectoryWrapper(child_dirpath, self.root)
                if fhash == d_obj.get_hash():
                    final_path = child_dirpath
                    if resolution:
                        try:
                            final_path = pathlib.Path(str(final_path, 'utf8'))
                        except:
                            pass
                    return final_path

            dirpath = pathlib.Path(dirpath).resolve()
            d_obj = DirectoryWrapper(dirpath, self.root)
            if fhash == d_obj.get_hash():
                final_path = dirpath
                if resolution:
                    try:
                        final_path = pathlib.Path(str(final_path, 'utf8'))
                    except:
                        pass
                return final_path

        return final_path

    def _get_path_object(self, path):
        if path.is_dir():
            return DirectoryWrapper(path, root=self.root)
        else:
            return FileWrapper(path, root=self.root,
                               fs_driver_url=self.fs_driver_url)

    def _get_path_info(self, path):
        return self._get_path_object(path).get_info()
