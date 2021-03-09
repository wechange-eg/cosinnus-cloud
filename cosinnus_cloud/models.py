# -*- coding: utf-8 -*-

from dataclasses import dataclass
from cosinnus.conf import settings

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


@dataclass
class SimpleCloudFile:
    """Similar to CloudFile, but doesn't provide download links, only id and name"""
    id: int
    filename: str
    dirname: str