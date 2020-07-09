# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import traceback

from django.core.management.base import BaseCommand
from django.utils.encoding import force_text

from cosinnus.conf import settings
from cosinnus.core.middleware.cosinnus_middleware import (
    initialize_cosinnus_after_startup,
)
from django.contrib.auth import get_user_model
from cosinnus_cloud.hooks import create_user_from_obj, get_nc_user_id
from cosinnus_cloud.utils.nextcloud import OCSException, list_all_users,\
    create_social_login_app
from cosinnus.utils.user import filter_active_users, filter_portal_users


logger = logging.getLogger("cosinnus")


class Command(BaseCommand):
    help = "Creates a wechange oauth provider app and a nextcloud social login client app"

    def handle(self, *args, **options):
        create_social_login_apps()
        
    