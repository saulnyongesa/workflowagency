document.documentElement.classList.add("js-enabled");

const BUTTON_ICON_MAP = [
    ["create account", "user-plus"],
    ["login", "log-in"],
    ["sign in", "log-in"],
    ["sign out", "log-out"],
    ["activate", "badge-check"],
    ["submit", "send"],
    ["request", "send"],
    ["withdraw", "send"],
    ["approve", "check"],
    ["reject", "x"],
    ["paid", "badge-check"],
    ["buy", "shopping-bag"],
    ["add to library", "library"],
    ["download", "download"],
    ["open", "external-link"],
    ["view", "eye"],
    ["filter", "sliders-horizontal"],
    ["disable jobs", "pause-circle"],
    ["enable jobs", "play-circle"],
    ["save", "save"],
    ["update", "save"],
    ["cancel", "x"],
    ["copy", "copy"],
    ["new ticket", "message-square-plus"],
    ["send reply", "send"],
    ["export", "download"],
];

function refreshIcons() {
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function iconForButton(text) {
    const normalized = text.trim().toLowerCase();
    const match = BUTTON_ICON_MAP.find(([label]) => normalized.includes(label));
    return match ? match[1] : null;
}

function decorateButtons() {
    document.querySelectorAll(".btn").forEach((button) => {
        if (button.querySelector("svg, [data-lucide], .spinner-border")) {
            button.classList.add("btn-with-icon");
            return;
        }
        const icon = iconForButton(button.textContent || "");
        if (!icon) {
            return;
        }
        button.insertAdjacentHTML("afterbegin", `<i data-lucide="${icon}" aria-hidden="true"></i>`);
        button.classList.add("btn-with-icon");
    });
}

function showMessageModal() {
    const modalElement = document.querySelector("[data-message-modal]");
    if (!modalElement || !window.bootstrap) {
        return;
    }
    const modal = new window.bootstrap.Modal(modalElement);
    modal.show();
}

function setupLoadingForms() {
    document.querySelectorAll("form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
            if (!submitter || submitter.disabled || form.dataset.noLoading === "true") {
                return;
            }
            const registrationForm = form.matches("[data-registration-form]");
            if (registrationForm && !form.dataset.passwordReady) {
                event.preventDefault();
                return;
            }
            const original = submitter.innerHTML;
            submitter.dataset.originalHtml = original;
            submitter.disabled = true;
            submitter.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>Processing...</span>';
        });
    });
}

function setupCopyButtons() {
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
                decorateButtons();
                refreshIcons();
            }, 1400);
        } catch {
            button.textContent = "Copy manually";
        }
    });
}

function setupMobileSidebar() {
    const openButton = document.querySelector("[data-sidebar-open]");
    const closeTargets = document.querySelectorAll("[data-sidebar-close]");
    const sidebar = document.querySelector(".app-sidebar");
    if (!openButton || !sidebar) {
        return;
    }

    const close = () => {
        document.body.classList.remove("sidebar-open");
        openButton.setAttribute("aria-expanded", "false");
    };
    const open = () => {
        document.body.classList.add("sidebar-open");
        openButton.setAttribute("aria-expanded", "true");
    };

    openButton.addEventListener("click", open);
    closeTargets.forEach((target) => target.addEventListener("click", close));
    sidebar.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            if (window.matchMedia("(max-width: 991.98px)").matches) {
                close();
            }
        });
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            close();
        }
    });
}

function setupNavigationState() {
    const navAreas = document.querySelectorAll(".sidebar-nav, .mobile-tabbar");
    if (!navAreas.length) {
        return;
    }

    const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
    navAreas.forEach((nav) => {
        let bestMatch = null;
        nav.querySelectorAll("a[href]").forEach((link) => {
            const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/+$/, "") || "/";
            const isMatch = currentPath === linkPath || (linkPath !== "/" && currentPath.startsWith(`${linkPath}/`));
            link.classList.remove("active");
            link.removeAttribute("aria-current");
            if (isMatch && (!bestMatch || linkPath.length > bestMatch.path.length)) {
                bestMatch = { link, path: linkPath };
            }
        });
        if (bestMatch) {
            bestMatch.link.classList.add("active");
            bestMatch.link.setAttribute("aria-current", "page");
        }
    });

    const sidebarNav = document.querySelector(".sidebar-nav");
    if (!sidebarNav) {
        return;
    }
    const storageKey = "workflowSidebarScrollTop";
    const savedScroll = window.sessionStorage.getItem(storageKey);
    if (savedScroll !== null) {
        sidebarNav.scrollTop = Number(savedScroll);
    }
    sidebarNav.addEventListener("scroll", () => {
        window.sessionStorage.setItem(storageKey, String(sidebarNav.scrollTop));
    });
    sidebarNav.querySelectorAll("a[href]").forEach((link) => {
        link.addEventListener("click", () => {
            window.sessionStorage.setItem(storageKey, String(sidebarNav.scrollTop));
        });
    });
}

function setupFilterPanels() {
    document.querySelectorAll("[data-filter-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const panel = button.closest(".filter-panel");
            if (!panel) {
                return;
            }
            panel.classList.toggle("is-open");
        });
    });
}

function setupPasswordChecklist() {
    const form = document.querySelector("[data-registration-form]");
    if (!form) {
        return;
    }
    const password = form.querySelector("#id_password1");
    const confirm = form.querySelector("#id_password2");
    const referral = form.querySelector("#id_referral_code");
    const submit = form.querySelector("[data-registration-submit]");
    const meterBar = form.querySelector("[data-password-meter-bar]");
    const matchMessage = form.querySelector("[data-password-match]");
    const referralStatus = form.querySelector("[data-referral-status]");
    const ruleElements = {
        length: form.querySelector('[data-password-rule="length"]'),
        upper: form.querySelector('[data-password-rule="upper"]'),
        lower: form.querySelector('[data-password-rule="lower"]'),
        digit: form.querySelector('[data-password-rule="digit"]'),
        symbol: form.querySelector('[data-password-rule="symbol"]'),
    };

    const update = () => {
        const value = password.value || "";
        const confirmValue = confirm.value || "";
        const rules = {
            length: value.length >= 8,
            upper: /[A-Z]/.test(value),
            lower: /[a-z]/.test(value),
            digit: /\d/.test(value),
            symbol: /[^A-Za-z0-9]/.test(value),
        };
        const passed = Object.values(rules).filter(Boolean).length;
        Object.entries(rules).forEach(([key, passedRule]) => {
            ruleElements[key]?.classList.toggle("is-valid", passedRule);
        });
        if (meterBar) {
            meterBar.style.width = `${(passed / Object.keys(rules).length) * 100}%`;
            meterBar.dataset.strength = String(passed);
        }
        const passwordsMatch = value.length > 0 && value === confirmValue;
        if (matchMessage) {
            matchMessage.textContent = passwordsMatch ? "Passwords match." : "Passwords must match.";
            matchMessage.classList.toggle("text-success", passwordsMatch);
            matchMessage.classList.toggle("text-danger", confirmValue.length > 0 && !passwordsMatch);
        }
        const hasReferral = (referral.value || "").trim().length > 0;
        if (referralStatus) {
            referralStatus.textContent = hasReferral
                ? "Referral code entered. It will be verified when you submit."
                : "A valid referral code is required before registration.";
            referralStatus.classList.toggle("text-success", hasReferral);
            referralStatus.classList.toggle("text-danger", !hasReferral);
        }
        const ready = passed === Object.keys(rules).length && passwordsMatch && hasReferral;
        form.dataset.passwordReady = ready ? "true" : "";
        if (submit) {
            submit.disabled = !ready;
        }
    };

    [password, confirm, referral].forEach((input) => input?.addEventListener("input", update));
    update();
}

document.addEventListener("DOMContentLoaded", () => {
    setupNavigationState();
    decorateButtons();
    refreshIcons();
    showMessageModal();
    setupLoadingForms();
    setupCopyButtons();
    setupMobileSidebar();
    setupFilterPanels();
    setupPasswordChecklist();
});
