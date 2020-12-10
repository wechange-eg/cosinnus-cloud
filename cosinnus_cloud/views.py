# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.http.response import JsonResponse
from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import TemplateView, RedirectView
from rest_framework.views import APIView

from cosinnus_cloud.hooks import get_nc_user_id
from cosinnus.utils.urls import group_aware_reverse
from cosinnus.views.mixins.group import RequireReadMixin
from cosinnus.models.group import CosinnusGroup
from cosinnus.conf import settings

import urllib.parse
from cosinnus.views.user_dashboard import BasePagedOffsetWidgetView
from cosinnus_cloud.utils import nextcloud
from cosinnus.models.user_dashboard import DashboardItem
from django.utils.html import escape

logger = logging.getLogger("cosinnus")


def get_nextcloud_group_folder_url(group):
    """ Returns the direct link to a groupfolder in nextcloud for a given group """
    if group.nextcloud_group_id and group.nextcloud_groupfolder_name:
        relative_url = settings.COSINNUS_CLOUD_GROUP_FOLDER_IFRAME_URL % {
            "group_folder_name": urllib.parse.quote(group.nextcloud_groupfolder_name),
        }
    else:
        relative_url = ""
    return settings.COSINNUS_CLOUD_NEXTCLOUD_URL + relative_url


class CloudIndexView(RequireReadMixin, RedirectView):
    permanent = False

    def get_redirect_url(self, **kwargs):
        # return group_aware_reverse("cosinnus:cloud:stub", kwargs={"group": self.group})
        return get_nextcloud_group_folder_url(self.group)


cloud_index_view = CloudIndexView.as_view()


class CloudStubView(RequireReadMixin, TemplateView):

    template_name = "cosinnus_cloud/cloud_stub.html"

    def get_context_data(self, *args, **kwargs):
        context = super(CloudStubView, self).get_context_data(*args, **kwargs)
        context.update(
            {"iframe_url": get_nextcloud_group_folder_url(self.group),}
        )
        return context


cloud_stub_view = CloudStubView.as_view()


#  ---
class OAuthView(APIView):
    """
    Used by Oauth2 authentication of Nextcloud to retrieve user details
    """

    def get(self, request, **kwargs):
        if request.user.is_authenticated:
            user = request.user
            return JsonResponse(
                {
                    "success": True,
                    "id": user.id,
                    "email": user.email,
                    "displayName": f"{user.first_name} {user.last_name}",
                    "groups": [
                        group.name for group in CosinnusGroup.objects.get_for_user(user)
                    ],
                }
            )
        else:
            return JsonResponse({"success": False,})


oauth_view = OAuthView.as_view()



class CloudFilesContentWidgetView(BasePagedOffsetWidgetView):
    """ Shows Nextcloud files retrieved via Webdav for the user """

    model = None
    # if True: will show only content that the user has recently visited
    # if False: will show all of the users content, sorted by creation date
    show_recent = False
    
    def get(self, request, *args, **kwargs):
        self.show_recent = kwargs.pop('show_recent', False)
        if self.show_recent:
            self.offset_model_field = 'visited'
        else:
            self.offset_model_field = 'created'
        return super(CloudFilesContentWidgetView, self).get(request, *args, **kwargs)
    
    
    def get_data(self, **kwargs):

        
        # we do not use timestamps, but instead just simple paging offsets
        # because Elasticsearch gives that to us for free
        page = 1
        if self.offset_timestamp:
            page = int(self.offset_timestamp)

        dataset = nextcloud.find_newest_files(userid=get_nc_user_id(self.request.user), page=page, page_size=self.page_size)

        items = self.get_items_from_dataset(dataset)
        return {
            'items': items,
            'widget_title': _('Cloud Files'),
            'has_more': page*self.page_size < dataset['meta']['total'],
            'offset_timestamp': page + 1,
        }
    
        return dataset
    
    def get_items_from_dataset(self, dataset):
        """ Returns a list of converted item data from the ES result"""
        items = []
        for doc in dataset['documents']:
            item = DashboardItem()
            item['icon'] = 'fa-file-text'
            try:
                item['text'] = escape(doc['info']['file'])
                item['subtext'] = escape(doc['info']['dir'])
            except KeyError:
                continue
            # cloud_file.download_url for a direct download or cloud_file.url for a link into Nextcloud
            item['url'] = f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}{doc['link']}"
            items.append(item)
        return items
        
    
api_user_cloud_files_content = CloudFilesContentWidgetView.as_view()

