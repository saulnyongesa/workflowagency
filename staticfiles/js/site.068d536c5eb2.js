document.documentElement.classList.add("js-enabled");

document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy-value]");
    if (!button) {
        return;
    }

    const value = button.getAttribute("data-copy-value");
    try {
        await navigator.clipboard.writeText(value);
        const original = button.textContent;
        button.textContent = "Copied";
        window.setTimeout(() => {
            button.textContent = original;
        }, 1400);
    } catch {
        button.textContent = "Copy manually";
    }
});
