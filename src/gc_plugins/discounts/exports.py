"""CSV and Excel exports of the discount history, with the columns the users' spreadsheets expect."""

import csv
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook

COLUMNS = ["Card ID", "Card Number", "Plate", "Discount Name", "Parking", "Zones", "Accesses", "Applied At", "Applied By"]
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def rows(usages):
    for usage in usages.iterator(chunk_size=500):
        discount = usage.discount
        yield [
            usage.card_id,
            safe(usage.card_number),
            safe(usage.plates),
            safe(discount.name),
            safe(discount.parking.name),
            safe(", ".join(zone.name for zone in discount.zones.all())),
            safe(", ".join(access.name for access in discount.accesses.all())),
            timezone.localtime(usage.applied_at).strftime("%Y-%m-%d %H:%M:%S"),
            safe(usage.applied_by_label),
        ]


def safe(value):
    """Keep spreadsheet programs from running a cell as a formula."""
    return f"'{value}" if value and value[0] in "=+-@" else value


def filename(extension):
    return f"discount_usage_{timezone.localtime():%Y%m%d_%H%M%S}.{extension}"


def csv_response(usages):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename("csv")}"'
    response.write("﻿")  # lets Excel read the Polish letters
    writer = csv.writer(response)
    writer.writerow(COLUMNS)
    writer.writerows(rows(usages))
    return response


def xlsx_response(usages):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Discount Usage")
    sheet.append(COLUMNS)
    for row in rows(usages):
        sheet.append(row)
    content = BytesIO()
    workbook.save(content)
    response = HttpResponse(content.getvalue(), content_type=XLSX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename("xlsx")}"'
    return response
