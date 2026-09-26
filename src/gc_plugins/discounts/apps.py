from django.apps import AppConfig


class DiscountsConfig(AppConfig):
    name = "gc_plugins.discounts"
    label = "discounts"
    verbose_name = "Discounts"  # shown only in the admin, which is always in English
