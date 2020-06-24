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
from cosinnus_cloud.hooks import create_user_from_obj
from cosinnus_cloud.utils.nextcloud import OCSException
from cosinnus.utils.user import filter_active_users, filter_portal_users


logger = logging.getLogger("cosinnus")


class Command(BaseCommand):
    help = "Checks all active users to create any missing nextcloud user accounts"

    def handle(self, *args, **options):
        try:
            initialize_cosinnus_after_startup()
            self.stdout.write(
                "Checking active users and creating any missing nextcloud user accounts."
            )
            counter = 0
            created = 0
            errors = 0
            all_users = filter_active_users(filter_portal_users(get_user_model().objects.all()))
            
            # TODO: search nextcloud for all exiting user IDs!
            non_existant_users = all_users
            total_users = len(non_existant_users)
            for user in non_existant_users:
                counter += 1
                try:
                    create_user_from_obj(user)
                    created += 1
                except OCSException as e:
                    if not e.statuscode == 102:  # 102: user already exists
                        errors += 1
                        self.stdout.write(
                            f"Error: OCSException: '{e.message}' ({e.statuscode})"
                        )
                except Exception as e:
                    if settings.DEBUG:
                        raise
                    errors += 1
                    self.stdout.write("Error: Exception: " + str(e))
                self.stdout.write(
                    f"{counter}/{total_users} users checked, {created} nextcloud users created ({errors} Errors)",
                    ending="\r",
                )
                self.stdout.flush()
            self.stdout.write(
                f"Done! {counter}/{total_users} users checked, {created} nextcloud users created ({errors} Errors)."
            )
        except Exception as e:
            if settings.DEBUG:
                raise
