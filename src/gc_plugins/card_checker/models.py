from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.scoping.models import ParkingScopedModel, ScopedModel


class Discount(ParkingScopedModel):
    """A discount that users of a parking may apply to parking cards."""

    class Kind(models.TextChoices):
        PERCENTAGE = "percentage", _("Percentage")
        MINUTES = "minutes", _("Minutes")
        DYNAMIC = "dynamic", _("Minutes chosen on the spot")
        ACCESS_CHANGE = "access_change", _("Access change")

    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    kind = models.CharField(_("kind"), max_length=20, choices=Kind)
    percentage = models.DecimalField(
        _("percentage"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Share of the card's current parking fee that this discount pays.",
    )
    minutes = models.PositiveIntegerField(_("minutes"), null=True, blank=True, help_text="Free minutes added to the card.")
    zones = models.ManyToManyField(
        "core.Zone",
        blank=True,
        related_name="+",
        verbose_name=_("zones"),
        help_text="The card must be in one of these zones. Required, except for an access change (empty: any zone).",
    )
    accesses = models.ManyToManyField(
        "core.Access",
        blank=True,
        related_name="+",
        verbose_name=_("accesses"),
        help_text="The card must have one of these accesses (empty: any). Required for an access change.",
    )
    to_access = models.ForeignKey(
        "core.Access",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("new access"),
        help_text="Access the card gets (access change).",
    )
    monthly_limit = models.PositiveIntegerField(
        _("monthly limit"), default=0, help_text="Uses per calendar month for all users, 0 for no limit."
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("discount")
        verbose_name_plural = _("discounts")
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(kind="percentage") | Q(percentage__isnull=False, percentage__gt=0, percentage__lte=100),
                name="discount_percentage_in_range",
                violation_error_message="A percentage discount needs a percentage above 0 and at most 100.",
            ),
            models.CheckConstraint(
                condition=~Q(kind="minutes") | Q(minutes__isnull=False, minutes__gt=0),
                name="discount_minutes_set",
                violation_error_message="A minutes discount needs the number of minutes.",
            ),
            models.CheckConstraint(
                condition=~Q(kind="access_change") | Q(to_access__isnull=False),
                name="discount_new_access_set",
                violation_error_message="An access change needs the new access.",
            ),
        ]

    def __str__(self):
        return self.name


class DiscountUser(ScopedModel):
    """Which discounts a project user may apply, and how many per month."""

    SCOPE = "user__project"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="discount_settings", verbose_name=_("user")
    )
    discounts = models.ManyToManyField(Discount, blank=True, related_name="users", verbose_name=_("discounts"))
    monthly_limit = models.PositiveIntegerField(
        _("monthly limit"), default=0, help_text="Discounts this user may apply per calendar month, 0 for no limit."
    )

    class Meta:
        verbose_name = _("discount user")
        verbose_name_plural = _("discount users")
        ordering = ["user__username"]

    def __str__(self):
        return str(self.user)

    def clean(self):
        super().clean()
        if self.user_id and not self.user.project_id:
            raise ValidationError("Only project users get discount settings; Green staff may apply every discount.")


class DiscountUsage(ScopedModel):
    """A discount applied to a card. A card gets each discount at most once."""

    SCOPE = "discount__parking"

    class Status(models.TextChoices):
        PENDING = "pending", _("pending")
        APPLIED = "applied", _("applied")

    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, related_name="usages", verbose_name=_("discount"))
    card_id = models.BigIntegerField(_("card ID"))
    card_number = models.CharField(_("card number"), max_length=32, blank=True)
    plates = models.CharField(_("plates"), max_length=100, blank=True)
    status = models.CharField(_("status"), max_length=10, choices=Status, default=Status.PENDING)
    applied_at = models.DateTimeField(_("applied at"), default=timezone.now)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    applied_by_label = models.CharField(_("applied by"), max_length=150, blank=True)

    class Meta:
        verbose_name = _("discount usage")
        verbose_name_plural = _("discount usages")
        ordering = ["-applied_at"]
        default_permissions = ("view", "delete")
        permissions = [("apply_discount", "Can apply discounts")]
        constraints = [
            models.UniqueConstraint(fields=["card_id", "discount"], name="discount_once_per_card"),
        ]
        indexes = [
            models.Index(fields=["discount", "applied_at"]),
            models.Index(fields=["applied_by", "applied_at"]),
        ]

    def __str__(self):
        return f"{self.discount} @ {self.card_number or self.card_id}"
