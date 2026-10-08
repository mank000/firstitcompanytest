function parseReceiptQr(text) {
    const query = text.includes("?") ? text.slice(text.indexOf("?") + 1) : text;
    const params = new URLSearchParams(query);
    const values = {};

    for (const key of ["t", "s", "fn", "i", "fp"]) {
        const matches = params.getAll(key);
        if (matches.length !== 1) throw new Error("Неверные данные QR-кода.");
        values[key] = matches[0];
    }

    const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(?:[0-5]\d)?$/.exec(values.t);
    if (!match) throw new Error("Неверная дата в QR-коде.");

    const [, year, month, day, hour, minute] = match.map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 ||
        date.getUTCDate() !== day || hour > 23 || minute > 59) {
        throw new Error("Неверная дата в QR-коде.");
    }

    if (!/^\d+(?:\.\d{1,2})?$/.test(values.s) ||
        ![values.fn, values.i, values.fp].every((value) => /^\d+$/.test(value))) {
        throw new Error("Неверные реквизиты в QR-коде.");
    }

    return {
        fn: values.fn,
        fd: values.i,
        fp: values.fp,
        purchase_date: `${match[1]}-${match[2]}-${match[3]}`,
        purchase_time: `${match[4]}:${match[5]}`,
        amount: values.s,
    };
}

const scanButton = document.querySelector("#scan-qr");

if (scanButton) {
    const scanForm = document.querySelector("#receipt-form");
    const qrInput = document.querySelector("#qr-text");
    const qrError = document.querySelector("#qr-text-error");
    const panel = document.querySelector("#scan-panel");
    const video = document.querySelector("#scan-video");
    const message = document.querySelector("#scan-message");
    let stream = null;
    let detector = null;
    let requestId = 0;

    function showMessage(text) {
        message.textContent = text;
        message.hidden = !text;
    }

    function setQrError(text) {
        qrError.textContent = text;
        qrInput.classList.toggle("invalid", Boolean(text));
        qrInput.closest(".field").classList.toggle("has-error", Boolean(text));
        qrInput.setAttribute("aria-invalid", String(Boolean(text)));
        if (text) qrInput.setAttribute("aria-describedby", qrError.id);
        else qrInput.removeAttribute("aria-describedby");
    }

    function stopScanner() {
        requestId += 1;
        if (stream) stream.getTracks().forEach((track) => track.stop());
        stream = null;
        video.srcObject = null;
        panel.hidden = true;
        scanButton.disabled = false;
    }

    function fillForm(values) {
        setQrError("");
        const fields = {
            ...values,
            purchase_datetime: `${values.purchase_date}T${values.purchase_time}`,
        };
        for (const [name, value] of Object.entries(fields)) {
            const input = scanForm.elements[name];
            input.value = value;
            input.classList.remove("invalid");
            input.closest(".field")?.classList.remove("has-error");
            input.setAttribute("aria-invalid", "false");
            input.removeAttribute("aria-describedby");
            const error = document.querySelector(`[data-error-for="${name}"]`);
            if (error) error.textContent = "";
        }
        const formError = document.querySelector("#form-error");
        formError.textContent = "";
        formError.hidden = true;
    }

    async function readFrame(scanId) {
        if (!stream || scanId !== requestId) return;
        try {
            const codes = await detector.detect(video);
            if (!stream || scanId !== requestId) return;
            if (codes.length) {
                stopScanner();
                try {
                    fillForm(parseReceiptQr(codes[0].rawValue));
                    showMessage("Данные чека заполнены. Проверьте их и отправьте форму.");
                } catch (error) {
                    showMessage(`${error.message} Введите данные вручную или попробуйте ещё раз.`);
                }
                return;
            }
        } catch (error) {
            if (scanId !== requestId) return;
            stopScanner();
            showMessage("Не удалось прочитать QR-код. Введите данные вручную.");
            return;
        }
        requestAnimationFrame(() => readFrame(scanId));
    }

    document.querySelector("#fill-qr").addEventListener("click", () => {
        showMessage("");
        try {
            fillForm(parseReceiptQr(qrInput.value.trim()));
            showMessage("Данные чека заполнены. Проверьте их и отправьте форму.");
        } catch (error) {
            setQrError(error.message);
        }
    });
    qrInput.addEventListener("input", () => setQrError(""));

    scanButton.addEventListener("click", async () => {
        showMessage("");
        if (!navigator.mediaDevices?.getUserMedia || !("BarcodeDetector" in window)) {
            showMessage(
                "Сканирование недоступно. Откройте сайт по HTTPS в поддерживаемом браузере или введите данные вручную."
            );
            return;
        }

        scanButton.disabled = true;
        const currentRequest = ++requestId;
        try {
            const formats = await BarcodeDetector.getSupportedFormats();
            if (!formats.includes("qr_code")) {
                stopScanner();
                showMessage("Этот браузер не распознаёт QR-коды. Введите данные вручную.");
                return;
            }
            detector = new BarcodeDetector({ formats: ["qr_code"] });
            const camera = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "environment" } },
                audio: false,
            });
            if (currentRequest !== requestId) {
                camera.getTracks().forEach((track) => track.stop());
                return;
            }
            stream = camera;
            video.srcObject = stream;
            panel.hidden = false;
            showMessage("Наведите камеру на QR-код чека.");
            await video.play();
            if (stream) requestAnimationFrame(() => readFrame(currentRequest));
        } catch (error) {
            if (currentRequest === requestId) {
                stopScanner();
                showMessage("Не удалось открыть сканер. Разрешите доступ к камере или введите данные вручную.");
            }
        }
    });

    document.querySelector("#stop-scan").addEventListener("click", () => {
        stopScanner();
        showMessage("");
    });
    scanForm.addEventListener("submit", stopScanner);
    window.addEventListener("pagehide", stopScanner);
    document.addEventListener("visibilitychange", () => {
        if (document.hidden && (stream || scanButton.disabled)) {
            stopScanner();
            showMessage("");
        }
    });
}
