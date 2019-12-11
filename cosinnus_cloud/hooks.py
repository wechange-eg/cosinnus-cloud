# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from concurrent.futures import ThreadPoolExecutor

from django.dispatch.dispatcher import receiver

from cosinnus.conf import settings
from cosinnus.core import signals
from cosinnus.templatetags.cosinnus_tags import full_name
from .utils import nextcloud

logger = logging.getLogger('cosinnus')

executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="nextcloud-req-")


def submit(fn, *args, **kwargs):
    executor.submit(fn, *args, **kwargs).add_done_callback(nc_req_callback)


def nc_req_callback(future):
    try:
        res = future.result()
    except Exception as e:
        logger.error("Nextcloud remote call resulted in an exception", exc_info=True)
    else:
        logger.debug("Nextcloud call finished with result %r", res)


# TODO: Race condition when a group was just created. Either use locking or retry
@receiver(signals.user_joined_group)
def user_joined_group_receiver_sub(sender, user, group, **kwargs):
    """ Triggers when a user properly joined (not only requested to join) a group """
    logger.debug('User "%s" joined group "%s", adding him/her to Nextcloud', full_name(user), group.name)
    submit(nextcloud.add_user_to_group, user.username, group.slug)
    

@receiver(signals.user_left_group)
def user_left_group_receiver_sub(sender, user, group, **kwargs):
    """ Triggers when a user properly joined (not only requested to join) a group """
    logger.debug('Stub: User "%s" left group "%s", removing him from Nextcloud', full_name(user), group.name)
    submit(nextcloud.remove_user_from_group, user.username, group.slug)
    
    
# TODO: replace with _created once core PR#23 is merged
@receiver(signals.group_object_ceated)
def group_created_sub(sender, group, **kwargs):
    logger.debug("Creating new group [%s] in Nextcloud", group.slug)

    submit(nextcloud.create_group, group.slug)
