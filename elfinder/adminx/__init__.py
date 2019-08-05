from xadmin.sites import site
from elfinder.adminx.mptt_adminx import MPTTModelAdmin
from elfinder.models import File, Directory, FileCollection

site.register(Directory, MPTTModelAdmin)
site.register(FileCollection)
site.register(File)
