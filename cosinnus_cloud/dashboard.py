# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from cosinnus.utils.dashboard import DashboardWidget, DashboardWidgetForm

from cosinnus.models.widget import WidgetConfig
from cosinnus.utils.urls import group_aware_reverse
from cosinnus_cloud.models import CloudFile


class LatestCloudFilesForm(DashboardWidgetForm):
    amount = forms.IntegerField(label="Amount", initial=5, min_value=0,
        help_text="0 means unlimited", required=False)


class Latest(DashboardWidget):

    app_name = 'cloud'
    form_class = LatestCloudFilesForm
    model = None
    title = _('Latest Cloud files')
    user_model_attr = None  # No filtering on user page
    widget_name = 'latest'

    def get_data(self, offset=0):
        """ Returns a tuple (data, rows_returned, has_more) of the rendered data and how many items were returned.
            if has_more == False, the receiving widget will assume no further data can be loaded.
         """
        count = int(self.config['amount'])
        
        # TODO: get data from nextcloud
        newest_group_files = [CloudFile('File aa'), CloudFile('File b')]
        
        
        if count != 0:
            newest_group_files = newest_group_files[offset:offset+count]
            
        data = {
            'rows': newest_group_files,
            'no_data': _('No cloud files yet'),
            'group': self.config.group,
        }
        return (render_to_string('cosinnus_cloud/widgets/latest.html', data), len(newest_group_files), len(newest_group_files) >= count)
    
    
    @property
    def title_url(self):
        if self.config.type == WidgetConfig.TYPE_MICROSITE:
            return ''
        if self.config.group:
            return group_aware_reverse('cosinnus:cloud:index', kwargs={'group': self.config.group})
        return ''
    