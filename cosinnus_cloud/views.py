# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import TemplateView, RedirectView

from cosinnus.utils.urls import group_aware_reverse
from cosinnus.views.mixins.group import RequireReadMixin

logger = logging.getLogger('cosinnus')


class CloudIndexView(RequireReadMixin, RedirectView):
    permanent = False

    def get_redirect_url(self, **kwargs):
        return group_aware_reverse('cosinnus:cloud:stub', kwargs={'group': self.group})

cloud_index_view = CloudIndexView.as_view()


class CloudStubView(RequireReadMixin, TemplateView):
    
    template_name = 'cosinnus_cloud/cloud_stub.html'
    
    def get_context_data(self, *args, **kwargs):
        context = super(CloudStubView, self).get_context_data(*args, **kwargs)
        context.update({
            'iframe_url': 'http://neverssl.com',
        })
        return context

cloud_stub_view = CloudStubView.as_view()

