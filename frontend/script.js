"use strict";

/*
    CONSTRUCTION BOQ ENGINE
    Project 3 Frontend

    Supports:
    - DWG file picker
    - Drag & Drop
    - DWG validation
    - Backend analysis
    - Construction element display
    - Material estimation
    - BOQ
    - PDF
    - Parser diagnostics
*/


document.addEventListener("DOMContentLoaded", () => {

    console.log("Construction BOQ Engine frontend loaded.");


    // ---------------------------------------------------------
    // ELEMENT HELPER
    // ---------------------------------------------------------

    const $ = (id) => document.getElementById(id);


    // ---------------------------------------------------------
    // GET DOM ELEMENTS
    // ---------------------------------------------------------

    const chooseButton = $("choose");
    const fileInput = $("file");
    const dropArea = $("drop");
    const analyzeButton = $("analyze");

    const fileName = $("name");
    const message = $("msg");

    const results = $("results");

    const healthElement = $("health");


    // ---------------------------------------------------------
    // CHECK REQUIRED ELEMENTS
    // ---------------------------------------------------------

    if (!chooseButton) {
        console.error("Upload button #choose was not found.");
        return;
    }

    if (!fileInput) {
        console.error("File input #file was not found.");
        return;
    }

    if (!dropArea) {
        console.error("Drop area #drop was not found.");
        return;
    }

    if (!analyzeButton) {
        console.error("Analyze button #analyze was not found.");
        return;
    }


    // ---------------------------------------------------------
    // STATE
    // ---------------------------------------------------------

    let selectedFile = null;


    // ---------------------------------------------------------
    // MESSAGE FUNCTION
    // ---------------------------------------------------------

    function msg(text, cls = "") {

        if (!message) {
            return;
        }

        message.textContent = text;
        message.className = cls;

    }


    // ---------------------------------------------------------
    // NUMBER FORMAT
    // ---------------------------------------------------------

    function num(value, decimals = 3) {

        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "0";
        }

        return number.toLocaleString("en-IN", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });

    }


    // ---------------------------------------------------------
    // MONEY FORMAT
    // ---------------------------------------------------------

    function money(value) {

        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "₹0.00";
        }

        return "₹" + number.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

    }


    // ---------------------------------------------------------
    // HTML ESCAPE
    // ---------------------------------------------------------

    function esc(value) {

        return String(value ?? "")
            .replace(/[&<>"']/g, (character) => {

                const entities = {
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#039;"
                };

                return entities[character];

            });

    }


    // ---------------------------------------------------------
    // FILE VALIDATION
    // ---------------------------------------------------------

    function isDWG(file) {

        if (!file) {
            return false;
        }

        const filename = String(file.name || "").toLowerCase();

        return filename.endsWith(".dwg");

    }


    // ---------------------------------------------------------
    // HANDLE FILE
    // ---------------------------------------------------------

    function handleFile(file) {

        if (!file) {

            selectedFile = null;

            fileName.textContent = "No drawing selected";

            analyzeButton.disabled = true;

            return;

        }


        console.log("Selected file:", file.name);


        // Validate DWG
        if (!isDWG(file)) {

            selectedFile = null;

            fileName.textContent =
                "Invalid file. Please select a .DWG file.";

            analyzeButton.disabled = true;

            msg(
                "Only DWG files are accepted.",
                "error"
            );

            return;

        }


        // File accepted
        selectedFile = file;


        fileName.textContent =
            `${file.name} (${formatFileSize(file.size)})`;


        analyzeButton.disabled = false;


        msg(
            "DWG selected successfully. Click Analyze Drawing.",
            "success"
        );


        // Remove drag styling
        dropArea.classList.remove("dragover");

    }


    // ---------------------------------------------------------
    // FILE SIZE
    // ---------------------------------------------------------

    function formatFileSize(bytes) {

        if (!bytes || bytes <= 0) {
            return "0 KB";
        }

        const kb = bytes / 1024;

        if (kb < 1024) {

            return `${kb.toFixed(1)} KB`;

        }

        const mb = kb / 1024;

        return `${mb.toFixed(2)} MB`;

    }


    // ---------------------------------------------------------
    // CHOOSE FILE BUTTON
    // ---------------------------------------------------------

    chooseButton.addEventListener("click", (event) => {

        event.preventDefault();
        event.stopPropagation();

        console.log("Choose DWG button clicked.");

        /*
            Reset the value so selecting the same DWG twice
            still fires the change event.
        */
        fileInput.value = "";

        try {

            fileInput.click();

        } catch (error) {

            console.error(
                "Unable to open file picker:",
                error
            );

            msg(
                "Unable to open file picker. Please try again.",
                "error"
            );

        }

    });


    // ---------------------------------------------------------
    // FILE INPUT CHANGE
    // ---------------------------------------------------------

    fileInput.addEventListener("change", (event) => {

        console.log("File input changed.");

        const files = event.target.files;

        if (!files || files.length === 0) {

            console.log("No file selected.");

            return;

        }

        handleFile(files[0]);

    });


    // ---------------------------------------------------------
    // DRAG OVER
    // ---------------------------------------------------------

    dropArea.addEventListener("dragover", (event) => {

        event.preventDefault();

        event.stopPropagation();

        dropArea.classList.add("dragover");

    });


    // ---------------------------------------------------------
    // DRAG ENTER
    // ---------------------------------------------------------

    dropArea.addEventListener("dragenter", (event) => {

        event.preventDefault();

        event.stopPropagation();

        dropArea.classList.add("dragover");

    });


    // ---------------------------------------------------------
    // DRAG LEAVE
    // ---------------------------------------------------------

    dropArea.addEventListener("dragleave", (event) => {

        event.preventDefault();

        event.stopPropagation();

        dropArea.classList.remove("dragover");

    });


    // ---------------------------------------------------------
    // DROP
    // ---------------------------------------------------------

    dropArea.addEventListener("drop", (event) => {

        event.preventDefault();

        event.stopPropagation();

        dropArea.classList.remove("dragover");


        const files = event.dataTransfer.files;


        if (!files || files.length === 0) {

            msg(
                "No file was dropped.",
                "error"
            );

            return;

        }


        handleFile(files[0]);

    });


    // ---------------------------------------------------------
    // HEALTH CHECK
    // ---------------------------------------------------------

    async function health() {

        try {

            const response =
                await fetch("/api/health", {
                    method: "GET",
                    cache: "no-store"
                });


            if (!response.ok) {

                throw new Error(
                    `Health check failed: HTTP ${response.status}`
                );

            }


            const data =
                await response.json();


            console.log(
                "Engine health:",
                data
            );


            if (
                data.dwg_reader === "ready"
            ) {

                healthElement.textContent =
                    "● Engine Ready";

                healthElement.className =
                    "healthy";

            } else {

                healthElement.textContent =
                    "● LibreDWG Missing";

                healthElement.className =
                    "unhealthy";

            }

        } catch (error) {

            console.error(
                "Health check error:",
                error
            );


            healthElement.textContent =
                "● Backend Offline";

            healthElement.className =
                "unhealthy";

        }

    }


    // ---------------------------------------------------------
    // ANALYZE BUTTON
    // ---------------------------------------------------------

    analyzeButton.addEventListener(
        "click",
        analyzeDrawing
    );


    // ---------------------------------------------------------
    // ANALYZE DRAWING
    // ---------------------------------------------------------

    async function analyzeDrawing() {

        if (!selectedFile) {

            msg(
                "Please select a DWG file first.",
                "error"
            );

            return;

        }


        if (!isDWG(selectedFile)) {

            msg(
                "Only DWG files are supported.",
                "error"
            );

            return;

        }


        console.log(
            "Starting DWG analysis:",
            selectedFile.name
        );


        // Create multipart form
        const formData =
            new FormData();

        formData.append(
            "file",
            selectedFile,
            selectedFile.name
        );


        // Update UI
        analyzeButton.disabled = true;

        analyzeButton.textContent =
            "Analyzing DWG…";

        msg(
            "Uploading DWG and analyzing geometry, quantities and materials…",
            "loading"
        );


        try {

            const response =
                await fetch(
                    "/api/analyze",
                    {
                        method: "POST",
                        body: formData
                    }
                );


            console.log(
                "Analyze HTTP status:",
                response.status
            );


            // Try to parse JSON
            let data;

            try {

                data =
                    await response.json();

            } catch {

                throw new Error(
                    `Server returned HTTP ${response.status} without valid JSON.`
                );

            }


            // Backend error
            if (!response.ok) {

                const detail =
                    data?.detail ||
                    data?.message ||
                    "DWG analysis failed.";

                throw new Error(detail);

            }


            console.log(
                "Analysis result:",
                data
            );


            // Render result
            render(data);


            results.classList.remove("hidden");


            msg(
                "Analysis completed successfully.",
                "success"
            );


            // Scroll to result
            results.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

        } catch (error) {

            console.error(
                "DWG analysis error:",
                error
            );


            msg(
                error.message ||
                "Unable to analyze DWG.",
                "error"
            );

        } finally {

            analyzeButton.disabled =
                !selectedFile;

            analyzeButton.textContent =
                "Analyze Drawing";

        }

    }


    // ---------------------------------------------------------
    // RENDER COMPLETE RESULT
    // ---------------------------------------------------------

    function render(data) {

        const analysis =
            data?.analysis || {};


        // -----------------------------------------------------
        // METRICS
        // -----------------------------------------------------

        $("entities").textContent =
            num(
                analysis.entities,
                0
            );


        $("layers").textContent =
            num(
                analysis.layers,
                0
            );


        $("units").textContent =
            analysis.units ||
            "Verify scale";


        $("count").textContent =
            num(
                analysis.element_types,
                0
            );


        // -----------------------------------------------------
        // DIAGNOSTICS
        // -----------------------------------------------------

        renderDiagnostics(
            analysis
        );


        // -----------------------------------------------------
        // ELEMENTS
        // -----------------------------------------------------

        renderElements(
            analysis.elements || []
        );


        // -----------------------------------------------------
        // MATERIALS
        // -----------------------------------------------------

        renderMaterials(
            data?.materials?.items || []
        );


        // -----------------------------------------------------
        // BOQ
        // -----------------------------------------------------

        renderBOQ(
            data?.boq || {}
        );


        // -----------------------------------------------------
        // PDF
        // -----------------------------------------------------

        const pdfButton =
            $("pdf");


        if (data?.pdf_url) {

            pdfButton.href =
                data.pdf_url;

            pdfButton.style.display =
                "inline-flex";

        } else {

            pdfButton.href =
                "#";

        }

    }


    // ---------------------------------------------------------
    // DIAGNOSTICS
    // ---------------------------------------------------------

    function renderDiagnostics(analysis) {

        const diagnostics =
            analysis.diagnostics || [];

        const notes =
            analysis.notes || [];


        let html = "";


        if (diagnostics.length > 0) {

            html += `
                <div class="diaggrid">
                    ${diagnostics.map(item => {

                        const success =
                            Boolean(item.success);

                        return `
                            <div class="diag ${
                                success ? "ok" : "bad"
                            }">

                                <strong>
                                    ${esc(item.parser || "Parser")}
                                </strong>

                                <span>
                                    ${
                                        success
                                            ? "SUCCESS"
                                            : "FAILED"
                                    }
                                </span>

                                <small>
                                    Return code:
                                    ${esc(item.return_code ?? "—")}

                                    ${
                                        item.stderr
                                            ? " · " +
                                              esc(
                                                  String(
                                                      item.stderr
                                                  ).slice(0, 250)
                                              )
                                            : ""
                                    }
                                </small>

                            </div>
                        `;

                    }).join("")}
                </div>
            `;

        } else {

            html += `
                <div class="note">
                    No parser diagnostic information returned.
                </div>
            `;

        }


        if (notes.length > 0) {

            html += notes.map(note => `
                <div class="note">
                    ${esc(note)}
                </div>
            `).join("");

        }


        $("diagnostics").innerHTML =
            html;

    }


    // ---------------------------------------------------------
    // ELEMENTS
    // ---------------------------------------------------------

    function renderElements(elements) {

        const container =
            $("elements");


        if (!elements.length) {

            container.innerHTML = `
                <div class="empty">
                    No construction elements detected.
                </div>
            `;

            return;

        }


        container.innerHTML =
            elements.map(element => {

                return `
                    <div class="element">

                        <div>
                            <strong>
                                ${esc(element.name)}
                            </strong>

                            <span>
                                ${num(element.count, 0)}
                                detected
                            </span>
                        </div>

                        <div class="elementstats">

                            <span>
                                L
                                ${num(element.length_m)}
                                m
                            </span>

                            <span>
                                A
                                ${num(element.area_m2)}
                                m²
                            </span>

                            <span>
                                V
                                ${num(element.volume_m3)}
                                m³
                            </span>

                        </div>

                    </div>
                `;

            }).join("");

    }


    // ---------------------------------------------------------
    // MATERIALS
    // ---------------------------------------------------------

    function renderMaterials(materials) {

        const container =
            $("materials");


        if (!materials.length) {

            container.innerHTML = `
                <div class="empty">
                    No material quantities calculated.
                </div>
            `;

            return;

        }


        container.innerHTML =
            materials.map(material => {

                return `
                    <div class="material">

                        <div>

                            <strong>
                                ${esc(material.material)}
                            </strong>

                            <small>
                                ${esc(material.basis || "")}
                            </small>

                        </div>


                        <div class="materialqty">

                            <strong>
                                ${num(material.quantity)}
                            </strong>

                            <span>
                                ${esc(material.unit)}
                            </span>

                        </div>


                        <em>
                            ${esc(material.source || "")}
                        </em>

                    </div>
                `;

            }).join("");

    }


    // ---------------------------------------------------------
    // BOQ
    // ---------------------------------------------------------

    function renderBOQ(boq) {

        const rows =
            boq.items || [];


        const tableBody =
            $("boq");


        if (!rows.length) {

            tableBody.innerHTML = `
                <tr>
                    <td
                        colspan="7"
                        class="empty"
                    >
                        No BOQ items calculated.
                    </td>
                </tr>
            `;

            return;

        }


        let html =
            rows.map(row => {

                return `
                    <tr>

                        <td>
                            ${esc(row.sr_no)}
                        </td>

                        <td>

                            <strong>
                                ${esc(row.description)}
                            </strong>

                            <small>
                                ${esc(row.basis || "")}
                            </small>

                        </td>

                        <td>
                            ${num(row.quantity)}
                        </td>

                        <td>
                            ${esc(row.unit)}
                        </td>

                        <td>
                            ${money(row.rate)}
                        </td>

                        <td>
                            ${money(row.amount)}
                        </td>

                        <td>
                            <span class="status">
                                ${esc(row.status || "")}
                            </span>
                        </td>

                    </tr>
                `;

            }).join("");


        // Grand total
        html += `
            <tr class="total">

                <td colspan="5">
                    GRAND TOTAL
                </td>

                <td>
                    ${money(boq.grand_total)}
                </td>

                <td>
                    INR
                </td>

            </tr>
        `;


        tableBody.innerHTML =
            html;

    }


    // ---------------------------------------------------------
    // INITIAL HEALTH CHECK
    // ---------------------------------------------------------

    health();


    // ---------------------------------------------------------
    // DEBUG
    // ---------------------------------------------------------

    console.log(
        "Upload controls initialized successfully."
    );

});
