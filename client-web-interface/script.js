const form = document.getElementById("query-form");
const input = document.getElementById("question");
const response = document.getElementById("response");
const loading = document.getElementById("loading");
const submitButton = document.getElementById("submit-button");

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = input.value.trim();

    if (!question) {
        response.textContent = "Veuillez entrer une question.";
        return;
    }

    loading.classList.remove("hidden");
    submitButton.disabled = true;
    response.textContent = "";

    try {
        const apiResponse = await fetch("/api/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({question})
        });
        const data = await apiResponse.json().catch(() => ({}));

        if (!apiResponse.ok) {
            throw new Error(data.detail || "Réponse invalide du service.");
        }
        if (typeof data.answer !== "string" || !data.answer.trim()) {
            throw new Error("Le service n'a retourné aucune réponse.");
        }

        response.textContent = data.answer;
    } catch (error) {
        response.textContent = error.message ||
            "Impossible de contacter le service d'assistance.";
    } finally {
        loading.classList.add("hidden");
        submitButton.disabled = false;
    }
});

