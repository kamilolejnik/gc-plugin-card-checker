# gc-plugin-card-checker

The card checker (Rabatownik) for [gc-platform](https://github.com/kamilolejnik/gc-platform): users of a project apply parking discounts to
cards, and managers browse and export the history of applied discounts. The kiosk is a separate plugin.

## What it does

- **Discounts** belong to a parking and come in four kinds:
  - *percentage* pays that share of the card's current parking fee;
  - *minutes* adds free minutes to the card;
  - *dynamic* adds the minutes the user picks, 10 to 1440 in steps of 10;
  - *access change* gives the card another access, if it has one of the required accesses.
  A discount applies only to cards in its zones (required for all kinds but the access change) and,
  if accesses are chosen, with one of them. Each discount may be limited per month.
- **Rabatownik** (panel): the user picks a discount of the current parking, enters the card number or
  the plate, sees the card (entry, paid-until time, zone, access) and applies the discount. Payments
  are registered at the user's station with their payment kind (the platform's parking assignment).
- **Discount history** (panel): the applied discounts of the user's parkings, with search, filters,
  sorting and CSV / Excel exports.
- A card gets each discount once. Uses are reserved before the parking system is called, so a double
  click cannot pay twice; a use the parking did not confirm stays *pending* in the admin.

## Configuration (admin, by Green staff)

1. **Discounts**: the parking, kind, zones and accesses (only those of the discount's parking are
   offered; picking the parking of a new discount reloads the form) and an optional monthly limit.
2. **Discount users**: for each project user, the discounts they may apply and their monthly limit.
   Green staff need no entry: they may apply every discount of their parkings.
3. **Groups** with the plugin's permissions:
   - *Can apply discounts* (`card_checker.apply_discount`): the Rabatownik page;
   - *Can view discount usage* (`card_checker.view_discountusage`): the discount history.
4. Each user also needs an assignment to the parking with a station and payment kind that exist in
   that parking's system.

## Development

From the platform directory, with its virtual environment active:

```bash
uv pip install -e ../gc-plugin-card-checker --config-setting editable_mode=compat
python manage.py migrate      # an installed plugin is enabled; GC_APPS can only narrow the list
```

Translations live in `src/gc_plugins/card_checker/locale`. Everything outside the admin is translated:
templates, messages, the script's texts (passed from the view), exports and the receipt line (in the
deployment's language). Code and message ids are English; the Polish texts repeat the Card Checker's
wording. The admin is always English.

```bash
cd src/gc_plugins/card_checker
python ../../../../green_cloud_services/manage.py makemessages -l pl --no-location --no-wrap
python ../../../../green_cloud_services/manage.py compilemessages
```

Try parking system calls only against the Green demo parking system, never a customer's.
