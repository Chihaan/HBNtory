const API_URL = "http://localhost:8002/ask";

const form = document.getElementById("query-form");
const input = document.getElementById("question");
const conversation = document.getElementById("conversation");
const emptyState = document.getElementById("empty-state");
const submitButton = document.getElementById("submit-button");
const themeToggle = document.getElementById("theme-toggle");

function setTheme(isDark) {
    document.body.classList.toggle("dark-theme", isDark);
    themeToggle.setAttribute("aria-pressed", String(isDark));
    themeToggle.setAttribute("aria-label", isDark ? "Activer le thème clair" : "Activer le thème sombre");
    localStorage.setItem("hbntory-theme", isDark ? "dark" : "light");
}

function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 126)}px`;
}

function addMessage(text, typing = false) {
    emptyState.hidden = true;
    conversation.hidden = false;

    const message = document.createElement("article");
    message.className = "message";
    message.innerHTML = `<div class="avatar"><img src="seahorse.png" alt=""></div><div class="message-content${typing ? " typing" : ""}"></div>`;

    const content = message.querySelector(".message-content");
    if (typing) content.innerHTML = "<i></i><i></i><i></i>";
    else content.textContent = text;

    conversation.append(message);
    conversation.scrollTop = conversation.scrollHeight;
    return message;
}

async function ask(question) {
    input.value = "";
    resizeInput();
    input.disabled = true;
    submitButton.disabled = true;
    const pending = addMessage("", true);

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        pending.remove();
        addMessage(data.answer || "Je n’ai pas reçu de réponse exploitable.");
    } catch (error) {
        pending.remove();
        addMessage("Impossible de contacter le service d’inventaire. Vérifiez qu’il est démarré, puis réessayez.");
        console.error("Erreur lors de l’appel à l’API :", error);
    } finally {
        input.disabled = false;
        submitButton.disabled = false;
        input.focus();
    }
}

setTheme(localStorage.getItem("hbntory-theme") === "dark");
themeToggle.addEventListener("click", () => setTheme(!document.body.classList.contains("dark-theme")));
form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (question) ask(question);
});
input.addEventListener("input", resizeInput);
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});
document.querySelectorAll(".suggestions button").forEach((button) => {
    button.addEventListener("click", () => ask(button.dataset.question));
});
