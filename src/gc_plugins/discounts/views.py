from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import Access, ParkingAssignment, Zone

from . import services
from .models import Discount
from .services import DiscountRefused

APPLY_PERMISSION = "discounts.apply_discount"


def allowed_discounts(request):
    """Active discounts of the user's parkings they may apply: the ones given to them, all for Green staff."""
    discounts = Discount.scoped(request).filter(is_active=True).select_related("parking", "to_access")
    if request.user.project_id:
        discounts = discounts.filter(users__user=request.user)
    return discounts


@permission_required(APPLY_PERMISSION, raise_exception=True)
def index(request):
    discounts = allowed_discounts(request)
    parking = request.parking
    if parking is None and (first := discounts.first()):
        parking = first.parking
    texts = {
        "chosen": _("Chosen discount:"),
        "processing": _("Processing..."),
        "missing": _("Please enter the card number or the plate number."),
        "failed": _("An error occurred while applying the discount."),
        "session": _("Your session has expired. Log in again."),
    }
    context = {"parking": parking, "discounts": discounts.filter(parking=parking) if parking else [], "texts": texts}
    return render(request, "discounts/index.html", context)


@require_POST
@permission_required(APPLY_PERMISSION, raise_exception=True)
def check(request):
    """Look the card up and run every check, without applying anything."""
    try:
        discount, _assignment, card, _minutes = prepare(request)
    except DiscountRefused as refusal:
        return JsonResponse({"message": str(refusal)}, status=400)
    return JsonResponse(card_data(request, discount, card))


@require_POST
@permission_required(APPLY_PERMISSION, raise_exception=True)
def apply(request):
    try:
        discount, assignment, card, minutes = prepare(request)
        updated = services.apply(
            discount.parking.api(),
            discount,
            card,
            station_id=assignment.station_id,
            payment_kind_id=assignment.payment_kind_id,
            minutes=minutes,
            user=request.user,
            user_limit=user_limit(request),
            label=request.user.get_username(),
        )
    except DiscountRefused as refusal:
        return JsonResponse({"message": str(refusal)}, status=400)
    added_minutes = minutes or (discount.minutes if discount.kind == Discount.Kind.MINUTES else None)
    return JsonResponse({"discount": discount.name, "added_minutes": added_minutes, **card_data(request, discount, updated)})


def prepare(request):
    discount_id = request.POST.get("discount", "")
    discount = allowed_discounts(request).filter(pk=discount_id).first() if discount_id.isdigit() else None
    if discount is None:
        raise DiscountRefused(_("You do not have access to this discount."))
    assignment = ParkingAssignment.scoped(request).filter(user=request.user, parking=discount.parking).first()
    if assignment is None:
        raise DiscountRefused(_("No station_id/paymentKindId configured for this parking."))
    card, minutes = services.prepare(
        discount.parking.api(),
        discount,
        card_number=request.POST.get("card_number", ""),
        plate=request.POST.get("plate", ""),
        minutes=request.POST.get("minutes"),
        user=request.user,
        user_limit=user_limit(request),
    )
    return discount, assignment, card, minutes


def user_limit(request):
    settings = getattr(request.user, "discount_settings", None) if request.user.project_id else None
    return settings.monthly_limit if settings else 0


def card_data(request, discount, card):
    """What the panel shows about a card, times in local time."""
    zone = Zone.scoped(request).filter(parking=discount.parking, external_id=card.zone_id).first()
    access = Access.scoped(request).filter(parking=discount.parking, external_id=card.access_id).first()
    return {
        "card_number": card.number,
        "plates": ", ".join(card.lpns),
        "entry_time": local_time(card.entry_time),
        "exit_time": local_time(card.exit_time),
        "exit_ok": card.exit_time > timezone.now() if card.exit_time else None,
        "zone": described(card.zone_id, zone),
        "access": described(card.access_id, access),
    }


def local_time(value):
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S") if value else None


def described(external_id, item):
    if external_id is None:
        return None
    return f"{external_id} – {item.name}" if item else str(external_id)
