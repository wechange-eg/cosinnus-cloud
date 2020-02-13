# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from cosinnus.conf import settings


from django.core.signals import request_finished
from django.dispatch import receiver


def register():
    if "cosinnus_cloud" in getattr(settings, "COSINNUS_DISABLED_COSINNUS_APPS", []):
        return

    # Import here to prevent import side effects
    from django.utils.translation import ugettext_lazy as _
    from django.utils.translation import pgettext_lazy

    from cosinnus.core.registries import app_registry, url_registry

    app_registry.register("cosinnus_cloud", "cloud", _("Cloud"), deactivatable=True)
    url_registry.register_urlconf("cosinnus_cloud", "cosinnus_cloud.urls")

    # makemessages replacement protection
    name = pgettext_lazy("the_app", "cloud")

    import cosinnus_cloud.hooks  # noqa
