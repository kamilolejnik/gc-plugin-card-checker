# gc-plugin-discounts

Rabatownik for [gc-platform](../green_cloud_services): project users apply parking discounts to cards
(percentage of the fee, free minutes, minutes chosen on the spot, or a change of the card's access),
and managers browse and export the history of applied discounts.

## Development

From the platform directory, with its virtual environment active:

```bash
uv pip install -e ../gc-plugin-discounts --config-setting editable_mode=compat
echo "GC_APPS=discounts" >> .env
python manage.py migrate
```
