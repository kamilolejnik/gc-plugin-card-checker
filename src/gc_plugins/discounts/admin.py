from django import forms
from django.contrib import admin

from core.scoping.admin import ScopedAdmin

from .models import Discount, DiscountUsage, DiscountUser

# The admin is always in English, so its own texts are not translated.


class DiscountForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parking_id = self.instance.parking_id
        for name in ("zones", "accesses", "to_access"):
            field = self.fields[name]
            if parking_id:  # the parking is fixed once the discount exists
                field.queryset = field.queryset.filter(parking=parking_id)
            field.queryset = field.queryset.select_related("parking")
            field.label_from_instance = lambda item: f"{item.parking} – {item.name} ({item.external_id})"

    def clean(self):
        cleaned_data = super().clean()
        parking = cleaned_data.get("parking") or getattr(self.instance, "parking", None)
        kind = cleaned_data.get("kind")
        if parking is None:
            return cleaned_data
        for name in ("zones", "accesses"):
            if cleaned_data.get(name) and cleaned_data[name].exclude(parking=parking).exists():
                self.add_error(name, f"Choose only {name} of the parking {parking}.")
        if cleaned_data.get("to_access") and cleaned_data["to_access"].parking_id != parking.pk:
            self.add_error("to_access", f"Choose an access of the parking {parking}.")
        if kind == Discount.Kind.ACCESS_CHANGE and not cleaned_data.get("accesses"):
            self.add_error("accesses", "Choose the accesses a card must have to get the access change.")
        if kind and kind != Discount.Kind.ACCESS_CHANGE and not cleaned_data.get("zones"):
            self.add_error("zones", "Choose the zones where cards may get this discount.")
        return cleaned_data


@admin.register(Discount)
class DiscountAdmin(ScopedAdmin):
    form = DiscountForm
    list_display = ["name", "parking", "kind", "monthly_limit", "is_active"]
    list_filter = ["parking", "kind", "is_active"]
    list_select_related = ["parking"]
    search_fields = ["name"]
    fieldsets = [
        (None, {"fields": ["parking", "name", "description", "kind", "monthly_limit", "is_active"]}),
        ("What the discount does", {"fields": ["percentage", "minutes", "zones", "accesses", "to_access"]}),
    ]
    filter_horizontal = ["zones", "accesses"]

    class Media:
        js = ["discounts/admin/discount_form.js"]

    def get_readonly_fields(self, request, obj=None):
        # Moving a discount to another parking would detach its history from the parking.
        return ["parking"] if obj else []

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if request.parking:
            initial.setdefault("parking", request.parking.pk)
        return initial


class DiscountUserForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        discounts = self.fields["discounts"]
        discounts.queryset = discounts.queryset.select_related("parking")
        discounts.label_from_instance = lambda discount: f"{discount.name} ({discount.parking})"

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get("user") or getattr(self.instance, "user", None)
        discounts = cleaned_data.get("discounts")
        if user and user.project_id and discounts and discounts.exclude(parking__project=user.project_id).exists():
            self.add_error("discounts", "Choose only discounts of the user's project.")
        return cleaned_data


@admin.register(DiscountUser)
class DiscountUserAdmin(ScopedAdmin):
    form = DiscountUserForm
    list_display = ["user", "monthly_limit", "discount_names"]
    list_filter = ["user__project"]
    list_select_related = ["user"]
    search_fields = ["user__username", "user__first_name", "user__last_name"]
    filter_horizontal = ["discounts"]

    @admin.display(description="discounts")
    def discount_names(self, discount_user):
        return ", ".join(discount.name for discount in discount_user.discounts.all())

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("discounts")

    def get_readonly_fields(self, request, obj=None):
        return ["user"] if obj else []


@admin.register(DiscountUsage)
class DiscountUsageAdmin(ScopedAdmin):
    """History, read-only. Deleting an entry lets the card get the discount again (e.g. a stuck pending one)."""

    list_display = ["applied_at", "discount", "parking", "card_number", "plates", "applied_by_label", "status"]
    list_filter = ["status", "discount__parking", "discount"]
    list_select_related = ["discount__parking"]
    search_fields = ["card_number", "plates", "applied_by_label"]
    date_hierarchy = "applied_at"

    @admin.display(description="parking", ordering="discount__parking__name")
    def parking(self, usage):
        return usage.discount.parking

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
