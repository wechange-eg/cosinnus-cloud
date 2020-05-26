# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import wraps
from time import sleep

from django.dispatch.dispatcher import receiver

from cosinnus.conf import settings
from cosinnus.core import signals
from cosinnus.templatetags.cosinnus_tags import full_name

from .utils import nextcloud
import re
from cosinnus.utils.functions import is_number
from cosinnus.utils.group import get_cosinnus_group_model
from django.db.models.signals import post_save
from cosinnus_cloud.utils.nextcloud import rename_group_and_group_folder
from cosinnus.models.group_extra import CosinnusProject, CosinnusSociety

logger = logging.getLogger("cosinnus")


executor = ThreadPoolExecutor(max_workers=64, thread_name_prefix="nextcloud-req-")


def submit_with_retry(fn, *args, **kwargs):
    @wraps(fn)
    def exec_with_retry():
        # seconds to wait before retrying.
        retry_wait = [2, 5, 10, 30, 60, 300]
        while True:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                try:
                    delay = retry_wait.pop(0)
                    logger.warning(
                        "Nextcloud call %s(%s, %s) failed. Retrying in %ds (%d tries left)",
                        fn.__name__,
                        args,
                        kwargs,
                        delay,
                        len(retry_wait),
                        exc_info=True,
                    )
                    sleep(delay)
                    continue
                except IndexError:
                    logger.warning(
                        "Nextcloud call %s(%s, %s) failed. Giving up",
                        fn.__name__,
                        args,
                        kwargs,
                        exc_info=True,
                    )
                    raise e

    executor.submit(exec_with_retry).add_done_callback(nc_req_callback)


def get_nc_user_id(user):
    return f"wechange-{user.id}"


def nc_req_callback(future: Future):
    try:
        res = future.result()
    except Exception:
        logger.exception("Nextcloud remote call resulted in an exception")
    else:
        logger.debug("Nextcloud call finished with result %r", res)


@receiver(signals.user_joined_group)
def user_joined_group_receiver_sub(sender, user, group, **kwargs):
    """ Triggers when a user properly joined (not only requested to join) a group """
    # only initialize if the cosinnus-app is actually activated
    if 'cosinnus_cloud' not in group.get_deactivated_apps():
        if group.nextcloud_group_id is not None:
            logger.debug(
                "User [%s] joined group [%s], adding him/her to Nextcloud",
                full_name(user),
                group.name,
            )
            submit_with_retry(
                nextcloud.add_user_to_group, get_nc_user_id(user), group.nextcloud_group_id
            )


@receiver(signals.user_left_group)
def user_left_group_receiver_sub(sender, user, group, **kwargs):
    """ Triggers when a user left a group.  
        Note: this can trigger on groups that do not have the cloud app activated, 
              so that it removes users properly while the app is just disabled for 
              a short period of time. """
    if group.nextcloud_group_id is not None:
        logger.debug(
            "User [%s] left group [%s], removing him from Nextcloud",
            full_name(user),
            group.name,
        )
        submit_with_retry(
            nextcloud.remove_user_from_group,
            get_nc_user_id(user),
            group.nextcloud_group_id,
        )


# TODO: replace with _created once core PR#23 is merged
@receiver(signals.userprofile_created)
def userprofile_created_sub(sender, profile, **kwargs):
    user = profile.user
    logger.debug(
        "User profile created, adding user [%s] to nextcloud ", full_name(user)
    )
    submit_with_retry(create_user_from_obj, user)


def create_user_from_obj(user):
    """ Create a nextcloud user from a django auth User object """
    return nextcloud.create_user(
        get_nc_user_id(user),
        full_name(user),
        user.email,
    )


def generate_group_nextcloud_id(group, save=True, force_generate=False):
    """ See `generate_group_nextcloud_field` """
    return generate_group_nextcloud_field(group, 'nextcloud_group_id', save=save, force_generate=force_generate)


def generate_group_nextcloud_groupfolder_name(group, save=True, force_generate=False):
    """ See `generate_group_nextcloud_field` """
    return generate_group_nextcloud_field(group, 'nextcloud_groupfolder_name', save=save, force_generate=force_generate)


def generate_group_nextcloud_field(group, field, save=True, force_generate=False):
    """ If one doesn't yet exist, generates, saves and returns 
        a unique file-system-valid id that is used for both the 
        nextcloud group and group folder for this group. 
        Remove leading and trailing spaces; leave other spaces intact and remove 
        anything that is not an alphanumeric.
        @param field: The field for which a unique nextcloud name should be generated. Usually
            either `nextcloud_group_id` or `nextcloud_groupfolder_name`
        @param save: If True, the group will be saved to DB after generation
        @param force_generate: Generates a new id, even if one already exists
          """
    if hasattr(group, field) and getattr(group, field) and not force_generate:
        return getattr(group, field)

    filtered_name = str(group.name).strip().replace(" ", "-----")
    filtered_name = re.sub(r"(?u)[^\w-]", "", filtered_name)
    filtered_name = filtered_name.replace("-----", " ").strip()
    if getattr(settings, "COSINNUS_CLOUD_PREFIX_GROUP_FOLDERS", False):
        filtered_name = "%s %s" % (
            "G - "
            if group.type == get_cosinnus_group_model().TYPE_SOCIETY
            else "P - ",
            filtered_name,
        )
    elif not filtered_name or is_number(filtered_name):
        filtered_name = "Folder" + filtered_name
    # max length for nextcloud groups (group folders could be longer, but lets keep it like that)
    filtered_name = filtered_name[:64]  

    # uniquify the id-name in case it clashes
    all_names = list(set(
        get_cosinnus_group_model()
        .objects.filter(**{field + '__istartswith': filtered_name})
        .exclude(id=group.id)  # exclude self
        .values_list(field, flat=True)
    ))
    all_names = [name.lower() for name in all_names]
    all_names += [
        "admin"
    ]  # the admin group is a protected system group, so never assign it!

    counter = 2
    unique_name = filtered_name
    while unique_name.lower() in all_names:
        unique_name = "%s %d" % (filtered_name, counter)
        counter += 1
    
    setattr(group, field, unique_name)
    if save == True:
        group.save(update_fields=[field])
    return unique_name


@receiver(signals.group_object_created)
def group_created_sub(sender, group, **kwargs):
    # only initialize if the cosinnus-app is actually activated
    if 'cosinnus_cloud' not in group.get_deactivated_apps():
        submit_with_retry(
            initialize_nextcloud_for_group,
            group
        )
    
    
@receiver(signals.group_apps_activated)
def group_cloud_app_activated_sub(sender, group, apps, **kwargs):
    """ Listen for the cloud app being activated """
    if 'cosinnus_cloud' in apps:
        def _conurrent_wrap():
            initialize_nextcloud_for_group(group)
            for user in group.actual_members:
                submit_with_retry(
                    nextcloud.add_user_to_group, get_nc_user_id(user), group.nextcloud_group_id
                )
                # we don't need to remove users who have left the group while the app was deactivated here,
                # because that listener is always active
        submit_with_retry(_conurrent_wrap)

@receiver(signals.group_apps_deactivated)
def group_cloud_app_deactivated_sub(sender, group, apps, **kwargs):
    #logger.warn('DEact apps: %s' % str(apps))
    pass


def rename_nextcloud_groupfolder_on_group_rename(sender, created, **kwargs):
    """ Tries to rename the nextcloud group folder to reflect a Group's naming change """
    if not created:
        group = kwargs.get('instance')
        if not 'cosinnus_cloud' in group.get_deactivated_apps() and \
                group.nextcloud_group_id and group.nextcloud_groupfolder_name and group.nextcloud_groupfolder_id:
            # just softly generate a new folder name first, and see if it has to be changed (because of a group rename)
            old_nextcloud_groupfolder_name = group.nextcloud_groupfolder_name
            generate_group_nextcloud_groupfolder_name(group, save=False, force_generate=True)
            new_nextcloud_groupfolder_name = group.nextcloud_groupfolder_name
            # rename the folder if the name would be a different one
            if new_nextcloud_groupfolder_name != old_nextcloud_groupfolder_name:
                result = rename_group_and_group_folder(group.nextcloud_groupfolder_id, new_nextcloud_groupfolder_name)
                # if the rename was successful, save the group. 
                # otherwise, reload it to discard the newly generated folder name on the object
                if result is True:
                    group.save(update_fields=['nextcloud_groupfolder_name'])
                    return 
            group.refresh_from_db()
        
post_save.connect(rename_nextcloud_groupfolder_on_group_rename, sender=get_cosinnus_group_model())
post_save.connect(rename_nextcloud_groupfolder_on_group_rename, sender=CosinnusProject)
post_save.connect(rename_nextcloud_groupfolder_on_group_rename, sender=CosinnusSociety)

    
def initialize_nextcloud_for_group(group):
    # generate group and groupfolder name
    generate_group_nextcloud_id(group, save=False)
    generate_group_nextcloud_groupfolder_name(group, save=False)
    group.save(update_fields=['nextcloud_group_id', 'nextcloud_groupfolder_name'])
    
    logger.debug(
        "Creating new group [%s] in Nextcloud (wechange group name [%s])",
        group.nextcloud_groupfolder_name,
        group.nextcloud_group_id,
    )

    # create nextcloud group
    nextcloud.create_group(group.nextcloud_group_id)
    # create nextcloud group folder
    nextcloud.create_group_folder(
        group.nextcloud_groupfolder_name,
        group.nextcloud_group_id,
        group,
        raise_on_existing_name=False,
    )
    # add admin user to group
    nextcloud.add_user_to_group(
        settings.COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME,
        group.nextcloud_group_id
    )


# maybe listen to user_logged_in and user_logged_out too?
# https://docs.djangoproject.com/en/3.0/ref/contrib/auth/#django.contrib.auth.signals.user_logged_in


@receiver(signals.user_deactivated)
def user_deactivated(sender, user, **kwargs):
    submit_with_retry(
        nextcloud.disable_user, 
        get_nc_user_id(user)
    )

@receiver(signals.user_activated)
def user_activated(sender, user, **kwargs):
    submit_with_retry(
        nextcloud.enable_user, 
        get_nc_user_id(user)
    )

@receiver(signals.group_deactivated)
def group_deactivated(sender, group, **kwargs):
    #logger.warning('Group "%s" was deactivated' % group.slug)
    pass

@receiver(signals.group_reactivated)
def group_reactivated(sender, group, **kwargs):
    #logger.warning('Group "%s" was reactivated' % group.slug)
    pass
