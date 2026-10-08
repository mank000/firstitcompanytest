const form = document.querySelector("#receipt-form");

if (form) {
    const formError = document.querySelector("#form-error");
    const fields = ["fn", "fd", "fp", "purchase_date", "purchase_time", "amount"];

    function setError(name, message) {
        const input = form.elements[name];
        const error = document.querySelector(`[data-error-for="${name}"]`);
        if (!input || !error) return;
        error.textContent = message;
        input.classList.toggle("invalid", Boolean(message));
        input.setAttribute("aria-invalid", String(Boolean(message)));
        input.setAttribute("aria-describedby", error.id);
    }

    function clearErrors() {
        fields.forEach((name) => setError(name, ""));
        formError.textContent = "";
        formError.hidden = true;
    }

    function validDate(value) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
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

        if (!validDate(form.elements.purchase_date.value)) {
            setError("purchase_date", "Укажите корректную дату покупки.");
            valid = false;
        }

        if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(form.elements.purchase_time.value)) {
            setError("purchase_time", "Укажите корректное время покупки.");
            valid = false;
        }

        const amount = form.elements.amount.value.trim();
        const number = Number(amount);
        if (!amount || !Number.isFinite(number) || number < 1000) {
            setError("amount", "Сумма должна быть числом не меньше 1000 ₽.");
            valid = false;
        }
        return valid;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearErrors();
        if (!validate()) return;

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
                document.querySelector("#success-panel").hidden = false;
                return;
            }
            if (data.errors) {
                for (const [name, errors] of Object.entries(data.errors)) {
                    const message = errors.map((error) => error.message).join(" ");
                    if (name === "__all__") {
                        formError.textContent = message;
                        formError.hidden = false;
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
