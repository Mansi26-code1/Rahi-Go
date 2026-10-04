// =========================================================
// RAAHIGO - FRONTEND JAVASCRIPT
// =========================================================


// =========================================================
// GET TRAVEL INPUT
// =========================================================

function getTravelInput() {
    return document.getElementById("travelInput");
}


// =========================================================
// SET EXAMPLE PROMPT
// =========================================================

function setPrompt(text) {

    const input = getTravelInput();

    if (!input) {
        console.error("travelInput not found.");
        return;
    }

    input.value = text;
    input.focus();
}


// =========================================================
// PLAN TRIP
// =========================================================

async function planTrip() {

    console.log("Plan My Trip button clicked.");

    const input = getTravelInput();

    if (!input) {
        alert("Travel input box not found.");
        return;
    }

    const message = input.value.trim();

    if (!message) {
        alert("Please enter your travel request.");
        input.focus();
        return;
    }


    // -----------------------------------------------------
    // Get UI elements
    // -----------------------------------------------------

    const planButton =
        document.getElementById("planButton");

    const buttonText =
        document.getElementById("buttonText");

    const loadingSection =
        document.getElementById("loadingSection");

    const resultsSection =
        document.getElementById("results");

    const finalAnswer =
        document.getElementById("finalAnswer");


    // -----------------------------------------------------
    // Disable button
    // -----------------------------------------------------

    if (planButton) {
        planButton.disabled = true;
        planButton.style.opacity = "0.7";
        planButton.style.cursor = "wait";
    }

    if (buttonText) {
        buttonText.textContent = "Planning...";
    }


    // -----------------------------------------------------
    // Show loading
    // -----------------------------------------------------

    if (loadingSection) {
        loadingSection.classList.remove("hidden");
        loadingSection.style.display = "block";
    }

    if (resultsSection) {
        resultsSection.classList.add("hidden");
        resultsSection.style.display = "none";
    }


    try {

        console.log("Sending request to /api/travel");
        console.log("User message:", message);


        // -------------------------------------------------
        // CALL FASTAPI
        // -------------------------------------------------

        const response = await fetch("/api/travel", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })
        });


        console.log("HTTP status:", response.status);


        const data = await response.json();

        console.log("Backend response:", data);


        // -------------------------------------------------
        // CHECK BACKEND ERROR
        // -------------------------------------------------

        if (!response.ok || data.success === false) {

            throw new Error(
                data.error ||
                data.detail ||
                "Unable to generate your travel plan."
            );
        }


        // -------------------------------------------------
        // HIDE LOADING
        // -------------------------------------------------

        if (loadingSection) {
            loadingSection.classList.add("hidden");
            loadingSection.style.display = "none";
        }


        // -------------------------------------------------
        // SHOW RESULTS
        // -------------------------------------------------

        if (resultsSection) {
            resultsSection.classList.remove("hidden");
            resultsSection.style.display = "block";
        }


        // -------------------------------------------------
        // FINAL AI ANSWER
        // -------------------------------------------------

        if (finalAnswer) {

            finalAnswer.innerHTML =
                formatAnswer(data.answer);
        }


        // -------------------------------------------------
        // FLIGHT STATUS
        // -------------------------------------------------

        const flightStatus =
            document.getElementById("flightStatus");

        if (flightStatus) {

            if (data.flight_results) {
                flightStatus.textContent = "Available";
            } else {
                flightStatus.textContent = "Not available";
            }
        }


        // -------------------------------------------------
        // HOTEL STATUS
        // -------------------------------------------------

        const hotelStatus =
            document.getElementById("hotelStatus");

        if (hotelStatus) {

            if (data.hotel_results) {
                hotelStatus.textContent = "Searched";
            } else {
                hotelStatus.textContent = "Not available";
            }
        }


        // -------------------------------------------------
        // FLIGHT RAW RESULTS
        // -------------------------------------------------

        const flightResults =
            document.getElementById("flightResults");

        if (flightResults) {

            flightResults.textContent =
                data.flight_results ||
                "No flight information available.";
        }


        // -------------------------------------------------
        // HOTEL RAW RESULTS
        // -------------------------------------------------

        const hotelResults =
            document.getElementById("hotelResults");

        if (hotelResults) {

            hotelResults.textContent =
                data.hotel_results ||
                "No hotel information available.";
        }


        // -------------------------------------------------
        // ITINERARY
        // -------------------------------------------------

        const itineraryResults =
            document.getElementById("itineraryResults");

        if (itineraryResults) {

            itineraryResults.textContent =
                data.itinerary ||
                "No itinerary available.";
        }


        // -------------------------------------------------
        // LLM CALL COUNT
        // -------------------------------------------------

        const llmCalls =
            document.getElementById("llmCalls");

        if (llmCalls) {

            llmCalls.textContent =
                data.llm_calls ?? "0";
        }


        // -------------------------------------------------
        // SCROLL TO RESULTS
        // -------------------------------------------------

        if (resultsSection) {

            setTimeout(() => {

                resultsSection.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

            }, 200);
        }


    } catch (error) {

        console.error("Travel Planner Error:", error);


        if (loadingSection) {
            loadingSection.classList.add("hidden");
            loadingSection.style.display = "none";
        }


        alert(
            "Unable to generate your travel plan.\n\n" +
            error.message
        );


    } finally {

        // -------------------------------------------------
        // ENABLE BUTTON AGAIN
        // -------------------------------------------------

        if (planButton) {
            planButton.disabled = false;
            planButton.style.opacity = "1";
            planButton.style.cursor = "pointer";
        }

        if (buttonText) {
            buttonText.textContent = "Plan My Trip";
        }
    }
}


// =========================================================
// FORMAT AI RESPONSE
// =========================================================

function formatAnswer(answer) {

    if (!answer) {
        return "No travel plan was generated.";
    }


    let formatted = String(answer);


    // Escape basic HTML characters
    formatted = formatted
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");


    // Bold markdown
    formatted = formatted.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );


    // Convert line breaks
    formatted = formatted.replace(
        /\n/g,
        "<br>"
    );


    return formatted;
}


// =========================================================
// NEW TRIP
// =========================================================

function newTrip() {

    const input = getTravelInput();

    const resultsSection =
        document.getElementById("results");

    const loadingSection =
        document.getElementById("loadingSection");


    if (input) {
        input.value = "";
        input.focus();
    }


    if (resultsSection) {
        resultsSection.classList.add("hidden");
        resultsSection.style.display = "none";
    }


    if (loadingSection) {
        loadingSection.classList.add("hidden");
        loadingSection.style.display = "none";
    }


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// =========================================================
// COPY ANSWER
// =========================================================

async function copyAnswer() {

    const answer =
        document.getElementById("finalAnswer");

    if (!answer) {
        return;
    }


    try {

        await navigator.clipboard.writeText(
            answer.innerText
        );

        alert("Travel plan copied!");

    } catch (error) {

        console.error(
            "Copy failed:",
            error
        );

        alert("Unable to copy the travel plan.");
    }
}


// =========================================================
// CTRL + ENTER
// =========================================================

document.addEventListener(
    "keydown",
    function(event) {

        if (
            event.ctrlKey &&
            event.key === "Enter"
        ) {

            event.preventDefault();

            planTrip();
        }
    }
);


// =========================================================
// PAGE LOADED
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function() {

        console.log(
            "RaaHiGo frontend loaded successfully."
        );

        const button =
            document.getElementById("planButton");

        const input =
            document.getElementById("travelInput");


        if (button) {
            console.log(
                "Plan button found."
            );
        } else {
            console.error(
                "Plan button NOT found."
            );
        }


        if (input) {
            console.log(
                "Travel input found."
            );
        } else {
            console.error(
                "Travel input NOT found."
            );
        }
    }
);
