"use strict";
// Rabatownik: choose a discount, find the card (preview), apply the discount.
(function ($) {
  const form = document.getElementById("discount-form");
  if (!form) {
    return;
  }
  const texts = JSON.parse(document.getElementById("discount-texts").textContent);
  const cardNumber = form.elements.card_number;
  const plate = form.elements.plate;
  const minutes = form.elements.minutes;
  const findButton = form.querySelector("[type=submit]");
  const applyButton = document.getElementById("apply-button");

  function formatMinutes(value) {
    const total = parseInt(value, 10);
    if (isNaN(total)) {
      return "-";
    }
    const hours = Math.floor(total / 60);
    const rest = String(total % 60).padStart(2, "0");
    return hours ? `${hours} h ${rest} min` : `${rest} min`;
  }

  function showError(message) {
    document.getElementById("error-message").textContent = message || texts.failed;
    $(".modal").modal("hide");
    $("#error-modal").modal("show");
  }

  function fillCard(prefix, card) {
    for (const [name, value] of Object.entries(card)) {
      const element = document.querySelector(`[data-field="${prefix}-${name}"]`);
      if (element) {
        element.textContent = value || "-";
      }
    }
    const exit = document.querySelector(`[data-field="${prefix}-exit_time"]`);
    exit.classList.remove("text-success", "text-danger");
    if (card.exit_ok !== null) {
      exit.classList.add(card.exit_ok ? "text-success" : "text-danger");
    }
  }

  // Sends the form; resolves with the JSON answer or rejects with a message for the user.
  async function send(url, button) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = texts.processing;
    try {
      const response = await fetch(url, {
        method: "POST",
        body: new FormData(form),
        headers: {"X-CSRFToken": form.elements.csrfmiddlewaretoken.value},
      });
      if (response.redirected) {
        throw new Error(texts.session);
      }
      if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
        throw new Error(texts.failed);
      }
      const answer = await response.json();
      if (!response.ok) {
        throw new Error(answer.message);
      }
      return answer;
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  }

  document.querySelectorAll("[data-discount]").forEach((button) => {
    button.addEventListener("click", () => {
      form.elements.discount.value = button.dataset.discount;
      document.getElementById("discount-modal-title").textContent = `${texts.chosen} ${button.dataset.name}`;
      document.getElementById("minutes-group").classList.toggle("d-none", button.dataset.kind !== "dynamic");
      for (const field of [cardNumber, plate]) {
        field.value = "";
        field.disabled = false;
      }
      $("#discount-modal").modal("show");
    });
  });

  // One identifier at a time: typing in one field disables the other.
  cardNumber.addEventListener("input", () => {
    cardNumber.value = cardNumber.value.replace(/\D/g, "");
    plate.disabled = cardNumber.value !== "";
  });
  plate.addEventListener("input", () => {
    plate.value = plate.value.replace(/\s/g, "").toUpperCase();
    cardNumber.disabled = plate.value !== "";
  });
  minutes.addEventListener("input", () => {
    document.getElementById("minutes-value").textContent = formatMinutes(minutes.value);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!cardNumber.value && !plate.value) {
      showError(texts.missing);
      return;
    }
    try {
      const card = await send(form.dataset.checkUrl, findButton);
      fillCard("preview", card);
      $("#discount-modal").modal("hide");
      $("#preview-modal").modal("show");
    } catch (error) {
      showError(error.message);
    }
  });

  applyButton.addEventListener("click", async () => {
    try {
      const result = await send(form.dataset.applyUrl, applyButton);
      document.getElementById("success-discount").textContent = result.discount;
      document.getElementById("success-added").textContent = formatMinutes(result.added_minutes);
      document.getElementById("success-added-row").hidden = !result.added_minutes;
      fillCard("success", result);
      $("#preview-modal").modal("hide");
      $("#success-modal").modal("show");
    } catch (error) {
      showError(error.message);
    }
  });
})(jQuery);
