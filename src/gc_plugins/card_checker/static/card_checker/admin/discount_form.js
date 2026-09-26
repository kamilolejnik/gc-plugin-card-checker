"use strict";
// Discount form: show the fields the chosen kind uses; reload the zones and accesses of a newly picked parking.
document.addEventListener("DOMContentLoaded", () => {
  const parking = document.getElementById("id_parking");  // a select only on a new discount
  if (parking && parking.tagName === "SELECT") {
    parking.addEventListener("change", () => {
      const url = new URL(window.location.href);
      url.searchParams.set("parking", parking.value);
      window.location.assign(url);
    });
  }
  const kind = document.getElementById("id_kind");
  if (!kind) {
    return;
  }
  const fieldsOfKind = {
    percentage: ["percentage"],
    minutes: ["minutes"],
    dynamic: [],
    access_change: ["to_access"],
  };
  const kindFields = ["percentage", "minutes", "to_access"];
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
