const button = document.getElementById("send");


button.addEventListener(
    "click",
    async () => {

        const question =
        document.getElementById("question").value;


        const response =
        document.getElementById("response");


        response.innerHTML = "Loading...";


        try {

            const result = await fetch(
                "http://localhost:8000/ask",
                {
                    method:"POST",

                    headers:{
                        "Content-Type":"application/json"
                    },

                    body: JSON.stringify({
                        question: question
                    })
                }
            );


            const data = await result.json();


            response.innerHTML =
                data.answer;


        }
        catch(error){

            response.innerHTML =
            "AI service unavailable";

        }

    }
);
