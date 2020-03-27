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
from cosinnus.models.group import CosinnusGroup

from .utils import nextcloud

logger = logging.getLogger("cosinnus")


executor = ThreadPoolExecutor(max_workers=64, thread_name_prefix="nextcloud-req-")


def submit_with_retry(fn, *args, **kwargs):
    @wraps(fn)
    def exec_with_retry():
        # seconds to wait before retrying.
        retry_wait = [5, 10, 60, 60, 600]
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
    """ Triggers when a user left a group """
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
@receiver(signals.userprofile_ceated)
def userprofile_created_sub(sender, profile, **kwargs):
    user = profile.user
    logger.debug(
        "User profile created, adding user [%s] to nextcloud ", full_name(user)
    )
    submit_with_retry(
        nextcloud.create_user,
        get_nc_user_id(user),
        full_name(user),
        user.email,
        [
            group.nextcloud_group_id
            for group in CosinnusGroup.objects.get_for_user(user)
        ],
    )


@receiver(signals.group_object_ceated)
def group_created_sub(sender, group, **kwargs):

    # For now, just use the group name, we might do something different in later versions
    group.nextcloud_group_id = group.name

    group.save(update_fields=["nextcloud_group_id"])

    logger.debug(
        "Creating new group [%s] in Nextcloud (wechange group name [%s])",
        group.nextcloud_group_id,
        group.name,
    )

    submit_with_retry(nextcloud.create_group, group.nextcloud_group_id)
    submit_with_retry(nextcloud.create_group_folder, group.name, group.nextcloud_group_id)


# maybe listen to user_logged_in and user_logged_out too?
# https://docs.djangoproject.com/en/3.0/ref/contrib/auth/#django.contrib.auth.signals.user_logged_in


@receiver(signals.user_deactivated)
def user_deactivated(sender, user, **kwargs):
    logger.warning("User %s was deactivated" % user.username)


@receiver(signals.user_activated)
def user_activated(sender, user, **kwargs):
    logger.warning("User %s was activated" % user.username)


@receiver(signals.group_deactivated)
def group_deactivated(sender, group, **kwargs):
    logger.warning('Group "%s" was deactivated' % group.slug)


@receiver(signals.group_reactivated)
def group_reactivated(sender, group, **kwargs):
    logger.warning('Group "%s" was reactivated' % group.slug)
