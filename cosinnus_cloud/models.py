# -*- coding: utf-8 -*-

from dataclasses import dataclass
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from cosinnus.conf import settings
from cosinnus.models.tagged import BaseTaggableObjectModel
from annoying.functions import get_object_or_None
from django.utils.crypto import get_random_string


class CloudFile(object):
    """ A wrapper object for API-retrieved nextcloud file infos """
    
    # uses the internal id to redirect https://<cloud-root>/f/1085
    title = None # str
    url = None
    download_url = None
    type = None # ??? 
    folder = None
    root_folder = None
    path = None
    icon = 'fa-cloud'
    
    def __init__(self, title=None, url=None, download_url=None, type=None, folder=None, root_folder=None, path=None, user=None):
        """ Supply a `user` to make download links work for users! """
        self.title = title
        self.url = url
        self.type = type
        self.folder = folder
        self.root_folder = root_folder
        self.path = path
        if user:
            from cosinnus_cloud.hooks import get_nc_user_id
            self.download_url = download_url.replace(
                settings.COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME,
                get_nc_user_id(user),
                1
            )
        else:
            self.download_url = download_url
    
    def get_icon(self):
        return self.icon

@dataclass
class SimpleCloudFile:
    """Similar to CloudFile, but doesn't provide download links, only id and name"""
    id: str # an int from NC, but prepended for use in the attached object view
    filename: str
    dirname: str
    
    @property
    def title(self):
        """ Proxy for `build_attachment_field_result()` """
        return self.filename
    


@python_2_unicode_compatible
class LinkedCloudFile(BaseTaggableObjectModel):

    nextcloud_file_id = models.IntegerField('Nextcloud File ID', unique=True, blank=False, null=False)
    path = models.CharField(_('Path'), blank=True, null=True, max_length=255)
    url = models.URLField(_('URL'), blank=True, null=True)
    
    class Meta(BaseTaggableObjectModel.Meta):
        verbose_name = _('Linked Cloud File')
        verbose_name_plural = _('Linked Cloud Files')
    
    @classmethod
    def get_for_nextcloud_file_id(cls, nextcloud_file_id, group):
        """ Creates or retrieves a LinkedCloudFile for the given nextcloud file id.
            If the file link existed already, the data is re-synced. """
        existing_linked_file = get_object_or_None(cls, nextcloud_file_id=nextcloud_file_id)
        linked_file = existing_linked_file or LinkedCloudFile(nextcloud_file_id=nextcloud_file_id, group=group)
        # populate or if existed, refresh from NC
        try:
            linked_file.sync_from_nextcloud_for_id(linked_file.nextcloud_file_id)
            linked_file.save()
        except Exception as e:
            # if there was an error retrieving the NC info, we return the existing linked file or nothing
            if settings.DEBUG:
                raise
            return existing_linked_file or None
        return linked_file
        
    def sync_from_nextcloud_for_id(self, nextcloud_file_id):
        """ Stub, this fills the file infos `path` and `url` from nextcloud for the given id.
            TODO: Requires an API-call!
            TODO: From the search-endpoint, return a "nc-xxx" id, and and only then do the retrieve loop
                    to prevent retrieving on a saved ao object! """
            
        self.nextcloud_file_id = nextcloud_file_id
        if not self.title:
            self.title = 'STUBBED-FILENAME-' + get_random_string(4)
        self.path = '/STUBBED-PATH/'
        from cosinnus_cloud.utils import nextcloud
        self.url = nextcloud.get_permalink_for_file_id(nextcloud_file_id)
    
    def __str__(self):
        return f'LinkedCloudFile (nc-id: {self.nextcloud_file_id})'
    
    def get_icon(self):
        """ Returns the font-awesome icon specific to this object type """
        return 'fa-cloud'
    
    def save(self, *args, **kwargs):
        return super(LinkedCloudFile, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return self.url
    
    def to_cloud_file(self, request=None):
        """ Converts this to a CloudFile, that is used in templates """
        return CloudFile(
            title=self.title,
            url=self.url,
            download_url=f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}{self.path}",
            type=None,
            folder=self.path,
            root_folder=self.path.split("/")[1],
            path=self.path,
            user=request.user if request and request.user and request.user.is_authenticated else None,
        )
    
    @classmethod
    def get_attachable_objects_query_results(cls, group, request, term, page=1):
        """ A droping for `cosinnus.view.attached_object.AttachableObjectSelect2View` to get attachable
            objects in a non-DB-based query. """
        # Check if cloud is enabled for group
        if 'cosinnus_cloud' in group.get_deactivated_apps() or \
                not group.nextcloud_group_id or \
                not group.nextcloud_groupfolder_name:
            return []
        from cosinnus_cloud.utils import nextcloud
        from cosinnus_cloud.hooks import get_nc_user_id
        simple_cloud_files = nextcloud.get_groupfiles_match_list(
            userid=get_nc_user_id(request.user), 
            folder=group.nextcloud_groupfolder_name,
            name_query=term,
            page=page,
            page_size=10,
        )
        # add a prefix to the ID to signify that the ID doesn't belong to the actual model, 
        # but needs to be resolved
        for simple_cloud_file in simple_cloud_files:
            simple_cloud_file.id = f'_unresolved_{simple_cloud_file.id}'
        return simple_cloud_files
    
    @classmethod
    def resolve_attachable_object_id(cls, object_id, group):
        """ For _unresolved_ IDs of an attachable object, get an attachable object 
            that belongs to that ID (usually an external object's ID is given, and
            we return the local DB object that is attachable and is pointing to it) """
        return cls.get_for_nextcloud_file_id(object_id, group)
        
    