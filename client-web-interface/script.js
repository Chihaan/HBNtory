const form = document.getElementById("query-form");
const input = document.getElementById("question");
const response = document.getElementById("response");
const loading = document.getElementById("loading");

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = input.value.trim();

    if (!question) {
        response.textContent = "Veuillez entrer une question.";
        return;
    }

    loading.classList.remove("hidden");
    response.textContent = "";

    try {
        const res = await fetch("http://localhost:8002/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: question
            })
        });

        if (!res.ok) {
            throw new Error(`Erreur HTTP ${res.status}`);
        }

        const data = await res.json();

        response.textContent = data.answer;

    } catch (error) {
        console.error(error);
        response.textContent =
            "Impossible de contacter le AI Query Service.";
    } finally {
        loading.classList.add("hidden");
    }
});
