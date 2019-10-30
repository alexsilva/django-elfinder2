from xadmin.sites import site
from elfinder.adminx.mptt_adminx import MPTTModelAdmin
from elfinder.models import File, Directory, FileCollection
from elfinder.conf import settings


class mMPTTModelAdmin(MPTTModelAdmin):
    list_display = (
        "name",
        "collection"
    )
    search_fields = (
        'name',
    )


if settings.ELFINDER_XADMIN_REGISTER:
    site.register(Directory, mMPTTModelAdmin)
    site.register(FileCollection)
    site.register(File)
