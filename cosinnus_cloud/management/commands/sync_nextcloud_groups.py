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
from cosinnus_cloud.hooks import (
    create_user_from_obj,
    generate_group_nextcloud_id,
    get_nc_user_id,
)
from cosinnus_cloud.utils.nextcloud import OCSException
from cosinnus.utils.group import get_cosinnus_group_model
from cosinnus_cloud.utils import nextcloud


logger = logging.getLogger("cosinnus")


class Command(BaseCommand):
    help = "Checks all active groups to create any missing nextcloud groups and group folders"

    def handle(self, *args, **options):
        try:
            initialize_cosinnus_after_startup()
            self.stdout.write(
                "Checking active users and creating any missing nextcloud user accounts."
            )
            counter = 0
            created = 0
            folders_created = 0
            users_added = 0
            errors = 0

            # TODO: only run the actual API calls for entries that are not yet set!

            portal_groups = get_cosinnus_group_model().objects.all_in_portal()
            total_groups = len(portal_groups)
            for group in portal_groups:
                counter += 1
                # only run this for groups that have the cloud app activated
                if not 'cosinnus_cloud' in group.get_deactivated_apps():
                    
                    current_group_created = False
                    if not group.nextcloud_group_id:
                        generate_group_nextcloud_id(group)
    
                    # create group
                    try:
                        nextcloud.create_group(group.nextcloud_group_id)
                        created += 1
                        current_group_created = True
                    except OCSException as e:
                        if not e.statuscode == 102:  # 102: group already exists
                            errors += 1
                            self.stdout.write(
                                f"Error (group create): OCSException: '{e.message}' ({e.statuscode})"
                            )
                    except Exception as e:
                        if settings.DEBUG:
                            raise
                        errors += 1
                        self.stdout.write("Error (group create): Exception: " + str(e))
    
                    # WARNING: Creating a group folder in a group with an existing one will ERASE the old group folder!
                    # So never create a group folder on a group that already has one!
                    if current_group_created:
                        # create group folder
                        try:
                            nextcloud.create_group_folder(
                                group.nextcloud_group_id, group.nextcloud_group_id, raise_on_existing_name=False,
                            )
                            folders_created += 1
                        except OCSException as e:
                            errors += 1
                            self.stdout.write(
                                f"Error (group folder create): OCSException: '{e.message}' ({e.statuscode})"
                            )
                        except Exception as e:
                            if settings.DEBUG:
                                raise
                            errors += 1
                            self.stdout.write(
                                "Error (group folder create): Exception: " + str(e)
                            )
    
                    # add members to group
                    nextcloud_user_ids = [get_nc_user_id(member) for member in group.actual_members]
                    # always add admin to groups
                    nextcloud_user_ids.append(settings.COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME) 
                    for nc_uid in nextcloud_user_ids:
                        try:
                            nextcloud.add_user_to_group(
                                nc_uid, group.nextcloud_group_id
                            )
                            users_added += 1
                        except OCSException as e:
                            errors += 1
                            self.stdout.write(
                                f"Error (add user to group): OCSException: '{e.message}' ({e.statuscode})"
                            )
                        except Exception as e:
                            if settings.DEBUG:
                                raise
                            errors += 1
                            self.stdout.write(
                                "Error (add user to group): Exception: " + str(e)
                            )
                self.stdout.write(
                    f"{counter}/{total_groups} groups processed, {created} groups created, {folders_created} group folders created, {users_added} groups members added ({errors} Errors)",
                )
                
            self.stdout.write(
                f"Done! {counter}/{total_groups} groups processed, {created} groups created, {folders_created} group folders created, {users_added} groups members added ({errors} Errors)."
            )
        except Exception as e:
            if settings.DEBUG:
                raise
