"""Applying discounts to parking cards. Independent of the panel, so the kiosk plugin can reuse it.

Checks run in the order the users know from the Card Checker, each refusal with its own message:
monthly limits, chosen minutes, the card lookup, the card's zone or access, one use per card.
"""

import logging
import re
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from core.parking_api import ParkingApiError, ParkingUnreachable

from .models import Discount, DiscountUsage

logger = logging.getLogger(__name__)

DYNAMIC_MINUTES = range(10, 1441, 10)


class DiscountRefused(Exception):
    """The discount cannot be applied; str(error) is the message for the user."""


def month_start():
    """Start of the current calendar month, Warsaw time."""
    return timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def check_limits(discount, user=None, user_limit=0):
    """Monthly limits of the discount and of the user (0 means no limit); pending uses count too."""
    this_month = DiscountUsage.unscoped.filter(applied_at__gte=month_start())
    if discount.monthly_limit and this_month.filter(discount=discount).count() >= discount.monthly_limit:
        raise DiscountRefused(
            _("The monthly limit of this discount has been reached: %(limit)s.") % {"limit": discount.monthly_limit}
        )
    # Every use by the user counts, also at parkings they no longer work with.
    if user_limit and this_month.filter(applied_by=user).count() >= user_limit:
        raise DiscountRefused(_("Your monthly discount limit has been reached: %(limit)s.") % {"limit": user_limit})


def parse_minutes(discount, value):
    """Minutes chosen for a dynamic discount; None for the other kinds."""
    if discount.kind != Discount.Kind.DYNAMIC:
        return None
    if value in (None, ""):
        raise DiscountRefused(_("No number of minutes chosen."))
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        raise DiscountRefused(_("Invalid number of minutes.")) from None
    if minutes not in DYNAMIC_MINUTES:
        raise DiscountRefused(_("Minutes must be between 10 and 1440, in steps of 10."))
    return minutes


def find_card(api, card_number="", plate=""):
    """The card with this number, or else with this plate, if it may get a discount at all."""
    card_number = re.sub(r"\D", "", card_number or "")
    plate = re.sub(r"\s", "", plate or "").upper()
    if not card_number and not plate:
        raise DiscountRefused(_("Enter the card number or the plate"))
    try:
        card = api.find_card(number=card_number) if card_number else api.find_card(lpn=plate)
    except ParkingApiError:
        logger.warning("%s: card lookup failed", api.parking, exc_info=True)
        raise DiscountRefused(_("There was a problem fetching the card.")) from None
    if card is None:
        raise DiscountRefused(_("Card not found."))
    if card.valid is not True:
        raise DiscountRefused(_("Card is inactive."))
    if card.blocked:
        raise DiscountRefused(_("Card is blocked."))
    return card


def check_eligible(discount, card):
    """The card's zone and access allow the discount, and the discount was not used on the card yet.

    Chosen zones or accesses restrict the discount; none chosen allows any. Every kind but the access
    change needs zones, and the access change needs the accesses it changes.
    """
    zones = set(discount.zones.values_list("external_id", flat=True))
    accesses = set(discount.accesses.values_list("external_id", flat=True))
    if discount.kind == Discount.Kind.ACCESS_CHANGE:
        if discount.to_access is None:
            raise DiscountRefused(_("Discount misconfigured (no new access)."))
        if not accesses:
            raise DiscountRefused(_("Discount misconfigured (no allowed accesses)."))
        if card.access_id not in accesses:
            raise DiscountRefused(_("The card does not have the access required for the change."))
    elif accesses and card.access_id not in accesses:
        raise DiscountRefused(_("The card is not eligible for this discount."))
    if (zones or discount.kind != Discount.Kind.ACCESS_CHANGE) and card.zone_id not in zones:
        raise DiscountRefused(_("The card is not eligible for this discount."))
    if DiscountUsage.unscoped.filter(discount=discount, card_id=card.id).exists():
        raise DiscountRefused(_("This discount has already been used for this card."))


def prepare(api, discount, *, card_number="", plate="", minutes=None, user=None, user_limit=0):
    """Run every check before applying; returns the card and the chosen minutes."""
    check_limits(discount, user, user_limit)
    minutes = parse_minutes(discount, minutes)
    card = find_card(api, card_number, plate)
    check_eligible(discount, card)
    return card, minutes


def apply(api, discount, card, *, station_id, payment_kind_id, minutes=None, user=None, user_limit=0, label=""):
    """Apply a prepared discount to the card; returns the card as updated by the parking system.

    The use is reserved before the parking system is called, so a second click or a parallel
    request cannot pay twice. If the parking refuses, the reservation is removed; if it does not
    answer (it may still have taken the payment), the reservation stays pending for Green to check.
    """
    usage = reserve(discount, card, user=user, user_limit=user_limit, label=label)
    try:
        updated = call_parking(api, discount, card, station_id, payment_kind_id, minutes)
    except ParkingUnreachable:
        logger.error("%s: no answer while applying discount %s to card %s; left pending", api.parking, discount.pk, card.id)
        raise DiscountRefused(_("There was a problem on the parking server's side.")) from None
    except ParkingApiError:
        logger.warning("%s: discount %s refused for card %s", api.parking, discount.pk, card.id, exc_info=True)
        usage.delete()
        raise DiscountRefused(_("There was a problem on the parking server's side.")) from None
    usage.status = DiscountUsage.Status.APPLIED
    usage.save(update_fields=["status"])
    logger.info("%s: discount %s applied to card %s by %s", api.parking, discount.pk, card.id, label)
    return updated


def reserve(discount, card, *, user, user_limit, label):
    try:
        with transaction.atomic():
            Discount.unscoped.select_for_update().get(pk=discount.pk)  # one limit check at a time
            check_limits(discount, user, user_limit)
            return DiscountUsage.unscoped.create(
                discount=discount,
                card_id=card.id,
                card_number=card.number,
                plates=", ".join(card.lpns),
                applied_by=user,
                applied_by_label=label,
            )
    except IntegrityError:
        raise DiscountRefused(_("This discount has already been used for this card.")) from None


def call_parking(api, discount, card, station_id, payment_kind_id, minutes):
    if discount.kind == Discount.Kind.ACCESS_CHANGE:
        return api.set_card_access(card.id, discount.to_access.external_id)
    payment = {"station_id": station_id, "payment_kind_id": payment_kind_id, "description": receipt_description()}
    if discount.kind == Discount.Kind.PERCENTAGE:
        # The discount pays its share of the card's fee up to now.
        quote = api.payment_quote(card.id)
        share = discount.percentage / 100
        price = (quote.price_with_vat * share).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return api.pay(card, quote=quote, price=price, credit=int(quote.add_credit * share), **payment)
    added = discount.minutes if discount.kind == Discount.Kind.MINUTES else minutes
    return api.pay(card, quote=api.payment_quote(card.id, add_credit=added), **payment)


def receipt_description():
    """The receipt line printed by the parking system: in the deployment's language, not the user's."""
    with translation.override(settings.LANGUAGE_CODE):
        return _("parking with a discount")
