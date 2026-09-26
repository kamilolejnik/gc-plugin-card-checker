from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from core.plugins import MenuItem


class DiscountsConfig(AppConfig):
    name = "gc_plugins.discounts"
    label = "discounts"
    verbose_name = "Discounts"  # shown only in the admin, which is always in English
    menu = [
        MenuItem(_("Discounts"), "discounts:index", "ni ni-credit-card text-primary", "discounts.apply_discount"),
        MenuItem(_("Discount history"), "discounts:history", "ni ni-tag text-warning", "discounts.view_discountusage"),
    ]
