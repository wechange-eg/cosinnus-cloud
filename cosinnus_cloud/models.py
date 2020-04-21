# -*- coding: utf-8 -*-

class CloudFile(object):
    """ A wrapper object for API-retrieved nextcloud file infos """
    
    # uses the internal id to redirect https://<cloud-root>/f/1085
    title = None # str
    url = None 
    type = None # ??? 
    
    def __init__(self, title=None, url=None, type=None):
        self.title = title
        self.url = url
        self.type = type
