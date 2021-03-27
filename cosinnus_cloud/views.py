# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.http.response import JsonResponse, HttpResponseBadRequest
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
from cosinnus.utils.permissions import check_ug_membership
from django.core.exceptions import PermissionDenied
from django_select2.views import Select2View, NO_ERR_RESP
from django.template.loader import render_to_string

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


    """
class AttachableObjectSelect2View(RequireReadMixin, Select2View):
        This view is used as API backend to serve the suggestions for the message recipient field.
        
        For each model type use the search terms to both search in the attachable model types 
        (that is, their configured type aliases (see settings.COSINNUS_ATTACHABLE_OBJECTS_SUGGEST_ALIASES))
        and their title for good matches.
        
        Examples (assumed that 'event' is configured as an alias for [cosinnus_event.Event]: 
            term: 'even Heilig' would return an [Event] with title 'Heiligabendfeier'
            term: 'even Heilig' would not find a [File] with title 'Einladung zum Heiligabend'
            term  'even Heilig' would (!) return a [File] with title 'Invitiation: Heiligabend-Event.pdf'
    """
    """
    def check_all_permissions(self, request, *args, **kwargs):
        user = request.user 
        group = self.kwargs.get('group', None)
        # Check if cloud is enabled for group
        if not user.is_authenticated or not check_ug_membership(user, group):
            raise PermissionDenied('User is not a member of this group!')
        # Check if current user is member of this group
        if 'cosinnus_cloud' in group.get_deactivated_apps() or \
                not group.nextcloud_group_id or \
                not group.nextcloud_groupfolder_name:
            raise PermissionDenied('Cloud is not enabled for this group!')
    """
        
def get_attachable_cloud_files_results(group, request, term, page):
    # Check if cloud is enabled for group
    if 'cosinnus_cloud' in group.get_deactivated_apps() or \
            not group.nextcloud_group_id or \
            not group.nextcloud_groupfolder_name:
        return []
    simple_cloud_files = query_group_files_for_user(request.user, group, term, page=page)
    return simple_cloud_files



def query_group_files_for_user(user, group, name_query, limit=10, page=1):
    """ Returns a list of `SimpleCloudFile` for a given user and a given group with a given search query.
        Will NOT do any permission checks (i.e. if the user is a group member) """
    simple_cloud_files = nextcloud.get_groupfiles_match_list(
        userid=get_nc_user_id(user), 
        folder=group.nextcloud_groupfolder_name,
        name_query=name_query,
        page=1,
        page_size=limit,
    )
    return simple_cloud_files


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

