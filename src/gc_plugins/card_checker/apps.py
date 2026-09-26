from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from core.plugins import MenuItem


class CardCheckerConfig(AppConfig):
    name = "gc_plugins.card_checker"
    label = "card_checker"
    verbose_name = "Card checker"  # shown only in the admin, which is always in English
    menu = [
        MenuItem(_("Discounts"), "card_checker:index", "ni ni-credit-card text-primary", "card_checker.apply_discount"),
        MenuItem(_("Discount history"), "card_checker:history", "ni ni-tag text-warning", "card_checker.view_discountusage"),
    ]
