/**
 * Postman Pytest Migrator Client Actions
 * Premium Interactions, animations, drag-drop, tab controls, dynamic loaders, and audits.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Initialize system tooltips or setup global listeners
    console.log("Postman Pytest Migrator client engine ready.");
    
    // Determine which page is currently loaded structure
    const indexWrapper = document.getElementById("index-page-wrapper");
    const uploadWrapper = document.getElementById("upload-page-wrapper");
    const dashboardWrapper = document.getElementById("dashboard-page-wrapper");
    const resultsWrapper = document.getElementById("results-page-wrapper");

    if (indexWrapper) {
        initIndexPage();
    } else if (uploadWrapper) {
        initUploadPage();
    } else if (dashboardWrapper) {
        initDashboardPage();
    } else if (resultsWrapper) {
        initResultsPage();
    }
});

/**
 * INDEX LANDING PAGE INITIALIZER
 */
function initIndexPage() {
    console.log("Landing platform active.");
    // Micro interaction animations for feature cards
    const cards = document.querySelectorAll(".feature-card");
    cards.forEach((card, index) => {
        card.style.opacity = "0";
        card.style.transform = "translateY(20px)";
        setTimeout(() => {
            card.style.transition = "all 0.6s cubic-bezier(0.16, 1, 0.3, 1)";
            card.style.opacity = "1";
            card.style.transform = "translateY(0)";
        }, 150 + index * 100);
    });
}

/**
 * UPLOAD PAGE INTERACTIVE DRAG-DROP
 */
function initUploadPage() {
    const dropzone = document.getElementById("upload-dropzone");
    const fileInput = document.getElementById("file-input");
    const fileDetails = document.getElementById("file-details");
    const fileNameSpan = document.getElementById("file-name-display");
    const fileSizeSpan = document.getElementById("file-size-display");
    const uploadForm = document.getElementById("upload-form");
    const progressContainer = document.getElementById("progress-container");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const submitBtn = document.getElementById("btn-submit");

    if (!dropzone || !fileInput) return;

    // Direct click to trigger select dialog
    dropzone.addEventListener("click", () => fileInput.click());

    // Highlight area when dragging over
    ["dragenter", "dragover"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add("drag-hover");
        }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove("drag-hover");
        }, false);
    });

    // Capture dropped files
    dropzone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateFileDisplay(files[0]);
        }
    });

    // Change input file trigger
    fileInput.addEventListener("change", (e) => {
        if (fileInput.files.length > 0) {
            updateFileDisplay(fileInput.files[0]);
        }
    });

    function updateFileDisplay(file) {
        if (!file) return;
        fileNameSpan.textContent = file.name;
        // Format size to KB
        const kbSize = (file.size / 1024).toFixed(1);
        fileSizeSpan.textContent = `${kbSize} KB`;
        
        fileDetails.classList.remove("hidden");
        fileDetails.classList.add("animate-fade-in");
        
        // Change submit button to visual emphasis state
        submitBtn.removeAttribute("disabled");
        submitBtn.classList.remove("bg-slate-800", "text-slate-500", "cursor-not-allowed");
        submitBtn.classList.add("bg-indigo-600", "hover:bg-indigo-500", "text-white", "hover:shadow-indigo-500/20");
    }

    // Submit animation loader handler
    uploadForm.addEventListener("submit", (e) => {
        e.preventDefault();
        
        const files = fileInput.files;
        if (files.length === 0) {
            showToast("Please select some valid collection JSON to begin", "error");
            return;
        }

        // Display progress bar and loader sequences
        dropzone.classList.add("pointer-events-none", "opacity-50");
        submitBtn.setAttribute("disabled", "true");
        submitBtn.textContent = "Processing Collection Pipeline...";
        progressContainer.classList.remove("hidden");
        progressContainer.classList.add("animate-fade-in");

        // Simple Simulated upload chunk progress
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.floor(Math.random() * 15) + 5;
            if (progress >= 100) {
                progress = 100;
                clearInterval(interval);
                progressText.textContent = "Validating schemas and structure constraints...";
                
                // Let's execute the actual submit pipeline structure asynchronously to the server
                setTimeout(() => {
                    uploadForm.submit();
                }, 800);
            }
            progressBar.style.width = `${progress}%`;
            if (progress < 90) {
                progressText.textContent = `Analyzing nodes and extracting endpoints (${progress}%)...`;
            }
        }, 120);
    });
}

/**
 * DASHBOARD PAGE LOG AND STATISTICS CONTROLS
 */
function initDashboardPage() {
    console.log("Dashboard analytics dashboard console loaded.");
    // Connect interactive filter criteria
    const statusFilter = document.getElementById("status-filter");
    if (statusFilter) {
        statusFilter.addEventListener("change", (e) => {
            const filterVal = e.target.value.toLowerCase();
            const rows = document.querySelectorAll(".collection-row");
            
            rows.forEach(row => {
                const statusBadge = row.querySelector(".status-badge");
                if (!statusBadge) return;
                const statusText = statusBadge.textContent.trim().toLowerCase();
                
                if (filterVal === "all" || statusText === filterVal) {
                    row.style.display = "table-row";
                } else {
                    row.style.display = "none";
                }
            });
        });
    }
}

/**
 * RESULTS PAGE CODE VIEWER & COPY SYSTEMS
 */
function initResultsPage() {
    console.log("Results code terminal loaded.");

    // Simple Interactive Tab selection transitions
    const tabs = document.querySelectorAll(".tab-btn");
    const contents = document.querySelectorAll(".tab-pane");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const targetId = tab.getAttribute("data-tab");
            
            tabs.forEach(t => {
                t.classList.remove("border-indigo-500", "text-indigo-400");
                t.classList.add("border-transparent", "text-slate-400");
            });
            tab.classList.add("border-indigo-500", "text-indigo-400");
            tab.classList.remove("border-transparent", "text-slate-400");

            contents.forEach(content => {
                if (content.id === targetId) {
                    content.classList.remove("hidden");
                    content.classList.add("animate-fade-in");
                } else {
                    content.classList.add("hidden");
                }
            });
        });
    });

    // Code Copy handler
    const copyBtns = document.querySelectorAll(".btn-copy-code");
    copyBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const codeSelector = btn.getAttribute("data-copy-target");
            const codeContent = document.querySelector(codeSelector);
            if (!codeContent) return;

            navigator.clipboard.writeText(codeContent.textContent).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = `
                    <svg class="h-4.5 w-4.5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Copied!</span>
                `;
                btn.classList.add("bg-teal-950/40", "border-teal-800/60");
                showToast("Copied script structure to clipboard!", "success");

                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.classList.remove("bg-teal-950/40", "border-teal-800/60");
                }, 2000);
            }).catch(err => {
                console.error("Unable to copy layout contents: ", err);
                showToast("Failed copying code to clipboard.", "error");
            });
        });
    });
}

/**
 * NOTIFICATION SYSTEM: Dynamic toast popup popups
 */
function showToast(message, type = "success") {
    // Check if toast wrapper container exists
    let wrapper = document.getElementById("toast-wrapper-container");
    if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.id = "toast-wrapper-container";
        wrapper.className = "fixed bottom-5 right-5 z-50 flex flex-col gap-3 max-w-sm pointer-events-none";
        document.body.appendChild(wrapper);
    }

    const toast = document.createElement("div");
    toast.className = `p-4 rounded-xl border flex items-start gap-3 shadow-2xl transition-all duration-300 transform translate-y-4 opacity-0 pointer-events-auto ${
        type === "success" 
            ? "bg-slate-900/95 border-emerald-800/60 text-emerald-300" 
            : "bg-slate-900/95 border-rose-850/60 text-rose-300"
    }`;

    // Fill Icons
    const icon = type === "success" 
        ? `<svg class="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
           </svg>`
        : `<svg class="h-5 w-5 text-rose-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
           </svg>`;

    toast.innerHTML = `
        ${icon}
        <div class="flex-grow">
            <p class="text-sm font-medium text-slate-100">${message}</p>
        </div>
    `;

    wrapper.appendChild(toast);

    // Fade and slide layout
    setTimeout(() => {
        toast.classList.remove("translate-y-4", "opacity-0");
    }, 10);

    // Automatically remove after 4 seconds
    setTimeout(() => {
        toast.classList.add("translate-y-4", "opacity-0");
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4000);
}
