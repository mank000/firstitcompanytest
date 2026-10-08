const form = document.querySelector("#receipt-form");

if (form) {
    const formError = document.querySelector("#form-error");
    const fields = ["fn", "fd", "fp", "purchase_datetime", "amount", "photo"];

    function setError(name, message) {
        const input = form.elements[name];
        const error = document.querySelector(`[data-error-for="${name}"]`);
        if (!input || !error) return;
        const hasError = Boolean(message);
        error.textContent = message;
        input.classList.toggle("invalid", hasError);
        input.closest(".field").classList.toggle("has-error", hasError);
        input.setAttribute("aria-invalid", String(hasError));
        if (hasError) input.setAttribute("aria-describedby", error.id);
        else input.removeAttribute("aria-describedby");
    }

    function clearErrors() {
        fields.forEach((name) => setError(name, ""));
        formError.textContent = "";
        formError.hidden = true;
    }

    function validDateTime(value) {
        const match = /^(\d{4})-(\d{2})-(\d{2})T([01]\d|2[0-3]):([0-5]\d)$/.exec(value);
        if (!match) return false;
        const [, year, month, day] = match.map(Number);
        const date = new Date(Date.UTC(year, month - 1, day));
        return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 &&
            date.getUTCDate() === day;
    }

    function validate() {
        let valid = true;
        for (const name of ["fn", "fd", "fp"]) {
            const value = form.elements[name].value.trim();
            if (!value || !/^[0-9]+$/.test(value)) {
                setError(name, value ? "Допустимы только цифры." : "Заполните это поле.");
                valid = false;
            }
        }

        if (!validDateTime(form.elements.purchase_datetime.value)) {
            setError("purchase_datetime", "Укажите корректные дату и время покупки.");
            valid = false;
        }

        const amount = form.elements.amount.value.trim();
        const number = Number(amount);
        if (!amount || !Number.isFinite(number) || number < 1000) {
            setError("amount", "Сумма должна быть числом не меньше 1000 ₽.");
            valid = false;
        }
        const photo = form.elements.photo.files[0];
        if (photo && !["image/jpeg", "image/png"].includes(photo.type)) {
            setError("photo", "Загрузите фото в формате JPG или PNG.");
            valid = false;
        } else if (photo && photo.size > 5 * 1024 * 1024) {
            setError("photo", "Размер фото не должен превышать 5 МБ.");
            valid = false;
        }
        return valid;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearErrors();
        if (!validate()) return;

        const [purchaseDate, purchaseTime] = form.elements.purchase_datetime.value.split("T");
        form.elements.purchase_date.value = purchaseDate;
        form.elements.purchase_time.value = purchaseTime;

        const button = form.querySelector('button[type="submit"]');
        button.disabled = true;
        try {
            const response = await fetch(form.action || window.location.href, {
                method: "POST",
                body: new FormData(form),
                headers: { "X-CSRFToken": form.elements.csrfmiddlewaretoken.value },
            });
            const data = await response.json();
            if (response.ok) {
                form.reset();
                document.querySelector("#form-content").hidden = true;
                document.querySelector("#form-card").classList.add("is-success");
                document.querySelector("#success-panel").hidden = false;
                return;
            }
            if (data.errors) {
                for (const [name, errors] of Object.entries(data.errors)) {
                    const message = errors.map((error) => error.message).join(" ");
                    if (name === "__all__") {
                        formError.textContent = message;
                        formError.hidden = false;
                    } else if (name === "purchase_date" || name === "purchase_time") {
                        setError("purchase_datetime", message);
                    } else {
                        setError(name, message);
                    }
                }
            } else {
                throw new Error("Не удалось отправить чек.");
            }
        } catch (error) {
            formError.textContent = "Не удалось отправить чек. Попробуйте ещё раз.";
            formError.hidden = false;
        } finally {
            button.disabled = false;
        }
    });
}
