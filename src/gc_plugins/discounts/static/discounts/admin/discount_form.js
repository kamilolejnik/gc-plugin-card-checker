"use strict";
// Discount form: show only the fields the chosen kind uses.
document.addEventListener("DOMContentLoaded", () => {
  const kind = document.getElementById("id_kind");
  if (!kind) {
    return;
  }
  const fieldsOfKind = {
    percentage: ["percentage", "zones"],
    minutes: ["minutes", "zones"],
    dynamic: ["zones"],
    access_change: ["accesses", "to_access"],
  };
  const kindFields = ["percentage", "minutes", "zones", "accesses", "to_access"];
  const update = () => {
    const shown = fieldsOfKind[kind.value] || kindFields;
    for (const name of kindFields) {
      const row = document.querySelector(`.form-row.field-${name}`);
      if (row) {
        row.style.display = shown.includes(name) ? "" : "none";
      }
    }
  };
  kind.addEventListener("change", update);
  update();
});
