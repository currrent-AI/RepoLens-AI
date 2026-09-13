// ============================================================
// RepoLens AI — Frontend Script
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // --------------------------------------------------------
    // API CONFIG
    // --------------------------------------------------------

    // Local development:
    // http://127.0.0.1:8000
    //
    // Production:
    // RepoLens AI FastAPI deployed on Vercel

    const API_BASE =
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"
            ? "http://127.0.0.1:8000"
            : "https://repo-lens-ai-kappa.vercel.app";


    // --------------------------------------------------------
    // ELEMENTS
    // --------------------------------------------------------

    const navbar = document.querySelector(".navbar");

    const menuToggle =
        document.querySelector(".menu-toggle");

    const navLinks =
        document.querySelector(".nav-links");

    const getStartedButtons =
        document.querySelectorAll(
            ".get-started, .btn-primary, [data-action='get-started']"
        );

    const signInButtons =
        document.querySelectorAll(
            ".sign-in, [data-action='sign-in']"
        );

    const analyzerForm =
        document.querySelector(".analyzer-form");

    const repoInput =
        document.querySelector(
            "#repo-url, input[type='url'], input[placeholder*='github']"
        );


    // --------------------------------------------------------
    // PAGE NAVIGATION
    // --------------------------------------------------------

    function goToSignup() {

        const signupSection =
            document.querySelector("#signup") ||
            document.querySelector(".signup-section");

        if (signupSection) {

            signupSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

            return;
        }

        window.location.href = "signup.html";
    }


    function goToLogin() {

        const loginSection =
            document.querySelector("#login") ||
            document.querySelector(".login-section");

        if (loginSection) {

            loginSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

            return;
        }

        window.location.href = "login.html";
    }


    function goToDashboard() {

        window.location.href =
            "dashboard.html";
    }


    // --------------------------------------------------------
    // GET STARTED
    // --------------------------------------------------------

    getStartedButtons.forEach(button => {

        button.addEventListener("click", event => {

            event.preventDefault();

            goToSignup();

        });

    });


    // --------------------------------------------------------
    // SIGN IN
    // --------------------------------------------------------

    signInButtons.forEach(button => {

        button.addEventListener("click", event => {

            event.preventDefault();

            goToLogin();

        });

    });


    // --------------------------------------------------------
    // NAVBAR
    // --------------------------------------------------------

    if (navbar) {

        window.addEventListener("scroll", () => {

            if (window.scrollY > 20) {

                navbar.classList.add("scrolled");

            } else {

                navbar.classList.remove("scrolled");

            }

        });

    }


    // --------------------------------------------------------
    // MOBILE MENU
    // --------------------------------------------------------

    if (menuToggle && navLinks) {

        menuToggle.addEventListener("click", () => {

            navLinks.classList.toggle("active");

            menuToggle.classList.toggle("active");

        });


        navLinks.querySelectorAll("a")
            .forEach(link => {

                link.addEventListener("click", () => {

                    navLinks.classList.remove("active");

                    menuToggle.classList.remove("active");

                });

            });

    }


    // --------------------------------------------------------
    // SMOOTH SCROLL
    // --------------------------------------------------------

    document
        .querySelectorAll("a[href^='#']")
        .forEach(link => {

            link.addEventListener("click", event => {

                const targetId =
                    link.getAttribute("href");

                if (!targetId || targetId === "#") {

                    return;

                }

                const target =
                    document.querySelector(targetId);

                if (target) {

                    event.preventDefault();

                    target.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });

                }

            });

        });


    // --------------------------------------------------------
    // GITHUB URL VALIDATION
    // --------------------------------------------------------

    function isValidGithubUrl(url) {

        if (!url) {

            return false;

        }

        try {

            const parsedUrl =
                new URL(url);

            return (
                parsedUrl.hostname === "github.com" ||
                parsedUrl.hostname === "www.github.com"
            );

        } catch (error) {

            return false;

        }

    }


    // --------------------------------------------------------
    // REPOSITORY NAME
    // --------------------------------------------------------

    function getRepositoryName(url) {

        try {

            const parsed =
                new URL(url);

            const parts =
                parsed.pathname
                    .split("/")
                    .filter(Boolean);

            if (parts.length >= 2) {

                return parts[1]
                    .replace(".git", "");

            }

            return "Repository";

        } catch (error) {

            return "Repository";

        }

    }


    // --------------------------------------------------------
    // SAVE ANALYSIS
    // --------------------------------------------------------

    function saveAnalysis(data, url) {

        try {

            const history =
                JSON.parse(
                    localStorage.getItem(
                        "repolens_analyses"
                    ) || "[]"
                );

            const item = {

                id:
                    Date.now().toString(),

                url:
                    url,

                name:
                    getRepositoryName(url),

                date:
                    new Date().toLocaleString(),

                data:
                    data

            };


            history.unshift(item);


            localStorage.setItem(
                "repolens_analyses",
                JSON.stringify(
                    history.slice(0, 10)
                )
            );


            localStorage.setItem(
                "repolens_last_analysis",
                JSON.stringify(data)
            );


        } catch (error) {

            console.error(
                "Failed to save analysis:",
                error
            );

        }

    }


    // --------------------------------------------------------
    // ANALYZER
    // --------------------------------------------------------

    if (analyzerForm) {

        analyzerForm.addEventListener(
            "submit",
            async event => {

                event.preventDefault();


                const url =
                    repoInput
                        ? repoInput.value.trim()
                        : "";


                // Validate URL

                if (!isValidGithubUrl(url)) {

                    showNotification(
                        "Please enter a valid GitHub repository URL.",
                        "error"
                    );

                    return;

                }


                const submitButton =
                    analyzerForm.querySelector(
                        "button[type='submit'], .btn-primary"
                    );


                const originalText =
                    submitButton
                        ? submitButton.innerHTML
                        : "";


                // ------------------------------------------------
                // BUTTON LOADING STATE
                // ------------------------------------------------

                if (submitButton) {

                    submitButton.disabled =
                        true;

                    submitButton.innerHTML = `
                        <span class="loading-spinner"></span>
                        Analyzing Repository...
                    `;

                }


                showNotification(
                    "Repository analysis started...",
                    "success"
                );


                try {

                    // ------------------------------------------------
                    // REAL BACKEND API CALL
                    // ------------------------------------------------

                    console.log(
                        "RepoLens API:",
                        `${API_BASE}/analyze`
                    );

                    console.log(
                        "Repository:",
                        url
                    );


                    const response =
                        await fetch(
                            `${API_BASE}/analyze`,
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                body:
                                    JSON.stringify({
                                        github_url: url
                                    })
                            }
                        );


                    // ------------------------------------------------
                    // READ RESPONSE
                    // ------------------------------------------------

                    let data;

                    try {

                        data =
                            await response.json();

                    } catch (jsonError) {

                        throw new Error(
                            "Server returned an invalid response."
                        );

                    }


                    // ------------------------------------------------
                    // HTTP ERROR
                    // ------------------------------------------------

                    if (!response.ok) {

                        const message =
                            data?.detail ||
                            data?.message ||
                            "Repository analysis failed.";

                        throw new Error(message);

                    }


                    // ------------------------------------------------
                    // BACKEND SUCCESS CHECK
                    // ------------------------------------------------

                    if (
                        data &&
                        data.success === false
                    ) {

                        throw new Error(
                            data.message ||
                            "Repository analysis failed."
                        );

                    }


                    // ------------------------------------------------
                    // SAVE RESULT
                    // ------------------------------------------------

                    saveAnalysis(
                        data,
                        url
                    );


                    // ------------------------------------------------
                    // SUCCESS
                    // ------------------------------------------------

                    showNotification(
                        "Analysis completed successfully.",
                        "success"
                    );


                    console.log(
                        "RepoLens analysis result:",
                        data
                    );


                    // Small delay so user can see success

                    setTimeout(() => {

                        window.location.href =
                            "architecture.html";

                    }, 700);


                } catch (error) {

                    console.error(
                        "RepoLens analysis error:",
                        error
                    );


                    let errorMessage =
                        "Unable to analyze repository.";


                    if (error?.message) {

                        errorMessage =
                            error.message;

                    }


                    showNotification(
                        errorMessage,
                        "error"
                    );


                } finally {

                    // ------------------------------------------------
                    // RESTORE BUTTON
                    // ------------------------------------------------

                    if (submitButton) {

                        submitButton.disabled =
                            false;

                        submitButton.innerHTML =
                            originalText;

                    }

                }

            }
        );

    }


    // --------------------------------------------------------
    // NOTIFICATION SYSTEM
    // --------------------------------------------------------

    function showNotification(
        message,
        type = "success"
    ) {

        const oldNotification =
            document.querySelector(
                ".rl-notification"
            );


        if (oldNotification) {

            oldNotification.remove();

        }


        const notification =
            document.createElement("div");


        notification.className =
            `rl-notification ${type}`;


        notification.innerHTML = `
            <div class="notification-icon">
                ${type === "error" ? "!" : "✓"}
            </div>

            <div class="notification-message">
                ${message}
            </div>

            <button class="notification-close">
                ×
            </button>
        `;


        document.body.appendChild(
            notification
        );


        requestAnimationFrame(() => {

            notification.classList.add(
                "show"
            );

        });


        const closeButton =
            notification.querySelector(
                ".notification-close"
            );


        if (closeButton) {

            closeButton.addEventListener(
                "click",
                () => {

                    notification.classList.remove(
                        "show"
                    );


                    setTimeout(() => {

                        notification.remove();

                    }, 300);

                }
            );

        }


        setTimeout(() => {

            if (
                notification.parentElement
            ) {

                notification.classList.remove(
                    "show"
                );


                setTimeout(() => {

                    notification.remove();

                }, 300);

            }

        }, 5000);

    }


    // --------------------------------------------------------
    // SCROLL REVEAL
    // --------------------------------------------------------

    const revealElements =
        document.querySelectorAll(
            ".feature-card, .workflow-step, .analyzer-card, .cta-card"
        );


    if (
        "IntersectionObserver"
        in window
    ) {

        const observer =
            new IntersectionObserver(
                entries => {

                    entries.forEach(entry => {

                        if (
                            entry.isIntersecting
                        ) {

                            entry.target.classList.add(
                                "revealed"
                            );


                            observer.unobserve(
                                entry.target
                            );

                        }

                    });

                },
                {
                    threshold: 0.12
                }
            );


        revealElements.forEach(
            element => {

                observer.observe(
                    element
                );

            }
        );

    }


    // --------------------------------------------------------
    // ARCHITECTURE NODE HOVER
    // --------------------------------------------------------

    const architectureNodes =
        document.querySelectorAll(
            ".architecture-node"
        );


    architectureNodes.forEach(node => {

        node.addEventListener(
            "mouseenter",
            () => {

                node.classList.add(
                    "node-active"
                );

            }
        );


        node.addEventListener(
            "mouseleave",
            () => {

                node.classList.remove(
                    "node-active"
                );

            }
        );

    });


    // --------------------------------------------------------
    // CODE WINDOW LINE ANIMATION
    // --------------------------------------------------------

    const codeLines =
        document.querySelectorAll(
            ".code-line"
        );


    codeLines.forEach(
        (line, index) => {

            line.style.animationDelay =
                `${index * 0.08}s`;

        }
    );


    // --------------------------------------------------------
    // PARALLAX EFFECT
    // --------------------------------------------------------

    const heroVisual =
        document.querySelector(
            ".hero-visual"
        );


    if (heroVisual) {

        window.addEventListener(
            "mousemove",
            event => {

                const x =
                    (
                        window.innerWidth / 2 -
                        event.clientX
                    ) / 80;


                const y =
                    (
                        window.innerHeight / 2 -
                        event.clientY
                    ) / 80;


                heroVisual.style.transform =
                    `translate(${x}px, ${y}px)`;

            }
        );

    }


    // --------------------------------------------------------
    // ACTIVE NAVIGATION
    // --------------------------------------------------------

    const sections =
        document.querySelectorAll(
            "section[id]"
        );


    const navigationLinks =
        document.querySelectorAll(
            ".nav-links a"
        );


    if (
        sections.length &&
        navigationLinks.length
    ) {

        window.addEventListener(
            "scroll",
            () => {

                let currentSection =
                    "";


                sections.forEach(
                    section => {

                        const sectionTop =
                            section.offsetTop -
                            180;


                        if (
                            window.scrollY >=
                            sectionTop
                        ) {

                            currentSection =
                                section.getAttribute(
                                    "id"
                                );

                        }

                    }
                );


                navigationLinks.forEach(
                    link => {

                        link.classList.remove(
                            "active"
                        );


                        const href =
                            link.getAttribute(
                                "href"
                            );


                        if (
                            href ===
                            `#${currentSection}`
                        ) {

                            link.classList.add(
                                "active"
                            );

                        }

                    }
                );

            }
        );

    }


    // --------------------------------------------------------
    // BUTTON RIPPLE EFFECT
    // --------------------------------------------------------

    document
        .querySelectorAll(
            ".btn-primary, .btn-secondary, button"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                function (event) {

                    const ripple =
                        document.createElement(
                            "span"
                        );


                    ripple.classList.add(
                        "ripple"
                    );


                    const rect =
                        this.getBoundingClientRect();


                    const size =
                        Math.max(
                            rect.width,
                            rect.height
                        );


                    ripple.style.width =
                        `${size}px`;


                    ripple.style.height =
                        `${size}px`;


                    ripple.style.left =
                        `${event.clientX -
                            rect.left -
                            size / 2}px`;


                    ripple.style.top =
                        `${event.clientY -
                            rect.top -
                            size / 2}px`;


                    this.appendChild(
                        ripple
                    );


                    setTimeout(() => {

                        ripple.remove();

                    }, 600);

                }
            );

        });


    // --------------------------------------------------------
    // CONSOLE BRANDING
    // --------------------------------------------------------

    console.log(
        "%c RepoLens AI ",
        "font-size:20px;font-weight:bold;color:#3b82f6;"
    );


    console.log(
        "%c See Your Codebase. Understand Its Architecture.",
        "font-size:13px;color:#94a3b8;"
    );


    console.log(
        "%c API:",
        "font-weight:bold;color:#22c55e;",
        API_BASE
    );


});