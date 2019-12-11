# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.dispatch.dispatcher import receiver

from cosinnus.conf import settings
from cosinnus.core import signals
from cosinnus.templatetags.cosinnus_tags import full_name


logger = logging.getLogger('cosinnus')


@receiver(signals.user_joined_group)
def user_joined_group_receiver_sub(sender, user, group, **kwargs):
    """ Triggers when a user properly joined (not only requested to join) a group """
    logger.warn('Stub: User "%s" joined group "%s"' % (full_name(user), group.name))
    

@receiver(signals.user_left_group)
def user_left_group_receiver_sub(sender, user, group, **kwargs):
    """ Triggers when a user properly joined (not only requested to join) a group """
    logger.warn('Stub: User "%s" left group "%s"' % (full_name(user), group.name))
    
    
    
