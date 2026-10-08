const receiptTable = document.querySelector(".receipt-table[data-status-url]");

if (receiptTable) {
    async function refreshStatuses() {
        if (document.hidden) return;
        try {
            const response = await fetch(receiptTable.dataset.statusUrl, {
                headers: { Accept: "application/json" },
                cache: "no-store",
            });
            if (!response.ok) return;
            const receipts = await response.json();
            for (const receipt of receipts) {
                const row = receiptTable.querySelector(`[data-receipt-id="${receipt.id}"]`);
                if (!row) continue;
                const status = row.querySelector(".status");
                status.className = `status status-${receipt.status}`;
                status.textContent = receipt.status_display;
                row.querySelector(".receipt-info-text").textContent =
                    receipt.rejection_reason || (receipt.status === "pending" ? "Чек на проверке" : "Чек принят");
            }
        } catch {
            // Следующая проверка повторит запрос.
        }
    }

    window.setInterval(refreshStatuses, 30000);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) refreshStatuses();
    });
}
