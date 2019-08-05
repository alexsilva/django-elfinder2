from xadmin.sites import site
from elfinder.adminx.mptt_adminx import MPTTModelAdmin
from elfinder.models import File, Directory, FileCollection


class mMPTTModelAdmin(MPTTModelAdmin):
    list_display = (
        "name",
        "collection"
    )
    search_fields = (
        'name',
    )


site.register(Directory, mMPTTModelAdmin)
site.register(FileCollection)
site.register(File)
