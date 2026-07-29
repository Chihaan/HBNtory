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

        // ===== Réponse fictive =====

        await new Promise(resolve => setTimeout(resolve, 1000));

        response.textContent =
            "Réponse de démonstration :\n\n" +
            "Votre question était :\n\n" +
            question;

        // ===========================
        //
        // Plus tard, remplacer par :
        //
        // const res = await fetch("http://localhost:8000/query", {
        //     method: "POST",
        //     headers: {
        //         "Content-Type": "application/json"
        //     },
        //     body: JSON.stringify({
        //         question: question
        //     })
        // });
        //
        // const data = await res.json();
        // response.textContent = data.answer;
        //
        // ===========================

    } catch (error) {

        response.textContent =
            "Impossible de contacter le AI Query Service.";

    } finally {

        loading.classList.add("hidden");

    }

});
