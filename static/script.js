// ============================================================
// RAHI-GO FRONTEND JAVASCRIPT
// ============================================================

// Current LangGraph conversation/thread
let currentThreadId = null;


// ============================================================
// GET USER INPUT
// ============================================================

function getTravelInput() {

    const input = document.getElementById("travelInput");

    if (!input) {
        console.error("travelInput element not found.");
        return "";
    }

    return input.value.trim();
}


// ============================================================
// SET EXAMPLE PROMPT
// ============================================================

function setPrompt(prompt) {

    const input = document.getElementById("travelInput");

    if (!input) {
        return;
    }

    input.value = prompt;
    input.focus();
}


// ============================================================
// MARKDOWN FORMATTER
// ============================================================

function formatAnswer(answer) {

    if (!answer) {
        return "<p>No travel plan was generated.</p>";
    }

    // marked.js available
    if (typeof marked !== "undefined") {

        marked.setOptions({
            breaks: true,
            gfm: true
        });

        return marked.parse(String(answer));
    }

    // Fallback if marked.js fails to load
    return String(answer)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>");
}


// ============================================================
// FORMAT MCP RESULTS
// ============================================================

function formatMCPResult(result) {

    if (
        result === null ||
        result === undefined ||
        result === ""
    ) {
        return "<p>No information available.</p>";
    }


    // --------------------------------------------------------
    // MCP may return an object / array instead of a string.
    // Convert it into readable JSON first.
    // --------------------------------------------------------

    if (typeof result === "object") {

        try {

            const jsonText =
                JSON.stringify(
                    result,
                    null,
                    2
                );

            return formatAnswer(
                "```json\n" +
                jsonText +
                "\n```"
            );

        } catch (error) {

            console.error(
                "Unable to format MCP result:",
                error
            );

            return "<p>Information received but could not be displayed.</p>";
        }
    }


    // --------------------------------------------------------
    // Normal string / Markdown result
    // --------------------------------------------------------

    return formatAnswer(result);
}


// ============================================================
// PLAN TRIP
// ============================================================

async function planTrip() {

    const message = getTravelInput();

    if (!message) {

        alert(
            "Please describe your travel plans first."
        );

        return;
    }


    const planButton =
        document.getElementById("planButton");

    const buttonText =
        document.getElementById("buttonText");

    const loadingSection =
        document.getElementById("loadingSection");

    const results =
        document.getElementById("results");


    // Disable button
    if (planButton) {
        planButton.disabled = true;
    }

    if (buttonText) {
        buttonText.textContent = "Planning...";
    }


    // Show loading
    if (loadingSection) {
        loadingSection.style.display = "block";
    }

    if (results) {
        results.style.display = "none";
    }


    try {

        console.log(
            "Sending travel request:",
            message
        );


        const response = await fetch(
            "/api/travel",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    message: message
                })
            }
        );


        const data = await response.json();


        console.log(
            "Travel API response:",
            data
        );


        if (!response.ok || data.success === false) {

            throw new Error(
                data.error ||
                "Unable to generate travel plan."
            );
        }


        // ====================================================
        // SAVE THREAD ID
        // ====================================================

        currentThreadId = data.thread_id;

        console.log(
            "Current thread:",
            currentThreadId
        );


        // ====================================================
        // SHOW RESULTS
        // ====================================================

        if (results) {
            results.style.display = "block";
        }


        // ====================================================
        // FINAL ANSWER
        // ====================================================

        const finalAnswer =
            document.getElementById("finalAnswer");

        if (finalAnswer) {

            finalAnswer.innerHTML =
                formatAnswer(data.answer);
        }


        // ====================================================
        // FLIGHT RESULTS
        // ====================================================

        const flightResults =
            document.getElementById("flightResults");

        if (flightResults) {

            flightResults.innerHTML =
                formatMCPResult(
                    data.flight_results ||
                    "No flight information available."
                );
        }


        // ====================================================
        // HOTEL RESULTS
        // ====================================================

        const hotelResults =
            document.getElementById("hotelResults");

        if (hotelResults) {

            hotelResults.innerHTML =
                formatMCPResult(
                    data.hotel_results ||
                    "No hotel information available."
                );
        }


        // ====================================================
        // ITINERARY
        // ====================================================

        const itineraryResults =
            document.getElementById("itineraryResults");

        if (itineraryResults) {

            itineraryResults.innerHTML =
                formatMCPResult(
                    data.itinerary ||
                    "No itinerary available."
                );
        }


        // ====================================================
        // LLM CALLS
        // ====================================================

        const llmCalls =
            document.getElementById("llmCalls");

        if (llmCalls) {

            llmCalls.textContent =
                data.llm_calls ?? 0;
        }


        // ====================================================
        // APPROVAL / HUMAN-IN-THE-LOOP
        // ====================================================

        const approvalPanel =
            document.getElementById("approvalPanel");

        const approvalMessage =
            document.getElementById("approvalMessage");


        if (data.requires_approval) {

            console.log(
                "Human approval required."
            );


            if (approvalPanel) {

                approvalPanel.classList.remove(
                    "hidden"
                );

                approvalPanel.style.display =
                    "block";
            }


            if (approvalMessage) {

                approvalMessage.textContent =
                    data.approval_request ||
                    "Please review your itinerary and approve it or request changes.";
            }

        } else {

            if (approvalPanel) {

                approvalPanel.classList.add(
                    "hidden"
                );

                approvalPanel.style.display =
                    "none";
            }
        }


        // ====================================================
        // SCROLL TO RESULTS
        // ====================================================

        if (results) {

            setTimeout(() => {

                results.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

            }, 100);
        }


    } catch (error) {

        console.error(
            "Travel planning error:",
            error
        );


        alert(
            "Unable to generate your travel plan.\n\n" +
            error.message
        );

    } finally {

        // Hide loading
        if (loadingSection) {
            loadingSection.style.display = "none";
        }


        // Enable button
        if (planButton) {
            planButton.disabled = false;
        }

        if (buttonText) {
            buttonText.textContent =
                "Plan My Trip";
        }
    }
}


// ============================================================
// HUMAN APPROVAL
// ============================================================

async function handleApproval(
    approved,
    feedback = ""
) {

    if (!currentThreadId) {

        alert(
            "Travel session not found. Please start a new trip."
        );

        return;
    }


    const approvalPanel =
        document.getElementById("approvalPanel");

    const approveButton =
        document.getElementById("approveButton");

    const reviseButton =
        document.getElementById("reviseButton");


    // Disable buttons while processing

    if (approveButton) {
        approveButton.disabled = true;
    }

    if (reviseButton) {
        reviseButton.disabled = true;
    }


    if (approvalPanel) {

        approvalPanel.style.opacity = "0.6";
        approvalPanel.style.pointerEvents = "none";
    }


    try {

        console.log(
            "Sending human approval:",
            {
                thread_id: currentThreadId,
                approved: approved,
                feedback: feedback
            }
        );


        const response = await fetch(
            "/api/travel/approval",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    thread_id:
                        currentThreadId,

                    approved:
                        approved,

                    feedback:
                        feedback
                })
            }
        );


        const data =
            await response.json();


        console.log(
            "Approval API response:",
            data
        );


        if (
            !response.ok ||
            data.success === false
        ) {

            throw new Error(
                data.error ||
                "Unable to process your approval."
            );
        }


        // ====================================================
        // UPDATE FINAL ANSWER
        // ====================================================

        if (data.answer) {

            const finalAnswer =
                document.getElementById(
                    "finalAnswer"
                );

            if (finalAnswer) {

                finalAnswer.innerHTML =
                    formatAnswer(
                        data.answer
                    );
            }
        }


        // ====================================================
        // UPDATE ITINERARY
        // ====================================================

        if (data.itinerary) {

            const itineraryResults =
                document.getElementById(
                    "itineraryResults"
                );

            if (itineraryResults) {

                itineraryResults.innerHTML =
                    formatMCPResult(
                        data.itinerary
                    );
            }
        }


        // ====================================================
        // UPDATE FLIGHT RESULTS
        // ====================================================

        if (data.flight_results) {

            const flightResults =
                document.getElementById(
                    "flightResults"
                );

            if (flightResults) {

                flightResults.innerHTML =
                    formatMCPResult(
                        data.flight_results
                    );
            }
        }


        // ====================================================
        // UPDATE HOTEL RESULTS
        // ====================================================

        if (data.hotel_results) {

            const hotelResults =
                document.getElementById(
                    "hotelResults"
                );

            if (hotelResults) {

                hotelResults.innerHTML =
                    formatMCPResult(
                        data.hotel_results
                    );
            }
        }


        // ====================================================
        // UPDATE LLM COUNT
        // ====================================================

        const llmCalls =
            document.getElementById(
                "llmCalls"
            );

        if (llmCalls) {

            llmCalls.textContent =
                data.llm_calls ?? 0;
        }


        // ====================================================
        // CHECK IF APPROVAL IS STILL REQUIRED
        // ====================================================

        if (data.requires_approval) {

            if (approvalPanel) {

                approvalPanel.style.display =
                    "block";

                approvalPanel.classList.remove(
                    "hidden"
                );
            }

        } else {

            if (approvalPanel) {

                approvalPanel.classList.add(
                    "hidden"
                );

                approvalPanel.style.display =
                    "none";
            }
        }


        // ====================================================
        // SUCCESS MESSAGE
        // ====================================================

        if (approved) {

            alert(
                "Trip approved! Your final travel plan is ready."
            );

        } else {

            alert(
                "Your feedback has been submitted and the itinerary was revised."
            );
        }


        // Clear feedback
        const feedbackInput =
            document.getElementById(
                "feedbackInput"
            );

        if (feedbackInput) {
            feedbackInput.value = "";
        }


    } catch (error) {

        console.error(
            "Approval error:",
            error
        );


        alert(
            "Unable to process your request.\n\n" +
            error.message
        );

    } finally {

        if (approveButton) {
            approveButton.disabled = false;
        }

        if (reviseButton) {
            reviseButton.disabled = false;
        }

        if (approvalPanel) {

            approvalPanel.style.opacity =
                "1";

            approvalPanel.style.pointerEvents =
                "auto";
        }
    }
}


// ============================================================
// APPROVE TRIP
// ============================================================

function approveTrip() {

    handleApproval(
        true,
        ""
    );
}


// ============================================================
// REQUEST REVISION
// ============================================================

function requestRevision() {

    const feedbackInput =
        document.getElementById(
            "feedbackInput"
        );


    const feedback =
        feedbackInput
            ? feedbackInput.value.trim()
            : "";


    if (!feedback) {

        alert(
            "Please tell Rahi-Go what you want to change."
        );

        if (feedbackInput) {
            feedbackInput.focus();
        }

        return;
    }


    handleApproval(
        false,
        feedback
    );
}


// ============================================================
// NEW TRIP
// ============================================================

function newTrip() {

    currentThreadId = null;


    const input =
        document.getElementById(
            "travelInput"
        );

    const results =
        document.getElementById(
            "results"
        );

    const approvalPanel =
        document.getElementById(
            "approvalPanel"
        );


    if (input) {
        input.value = "";
    }


    if (results) {
        results.style.display = "none";
    }


    if (approvalPanel) {

        approvalPanel.classList.add(
            "hidden"
        );

        approvalPanel.style.display =
            "none";
    }


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// ============================================================
// COPY FINAL ANSWER
// ============================================================

async function copyAnswer() {

    const finalAnswer =
        document.getElementById(
            "finalAnswer"
        );


    if (!finalAnswer) {
        return;
    }


    const text =
        finalAnswer.innerText;


    try {

        await navigator.clipboard.writeText(
            text
        );

        alert(
            "Travel plan copied to clipboard."
        );

    } catch (error) {

        console.error(
            "Copy failed:",
            error
        );

        alert(
            "Unable to copy the travel plan."
        );
    }
}


// ============================================================
// CTRL + ENTER
// ============================================================

document.addEventListener(
    "keydown",
    function(event) {

        const input =
            document.getElementById(
                "travelInput"
            );


        if (
            event.ctrlKey &&
            event.key === "Enter" &&
            document.activeElement === input
        ) {

            event.preventDefault();

            planTrip();
        }
    }
);


// ============================================================
// PAGE LOAD
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    function() {

        console.log(
            "Rahi-Go frontend loaded successfully."
        );

        console.log(
            "HITL approval system ready."
        );
    }
);