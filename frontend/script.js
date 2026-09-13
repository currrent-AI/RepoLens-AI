// ============================================================
// RepoLens AI — Frontend Script
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // --------------------------------------------------------
    // ELEMENTS
    // --------------------------------------------------------

    const navbar = document.querySelector(".navbar");
    const menuToggle = document.querySelector(".menu-toggle");
    const navLinks = document.querySelector(".nav-links");

    const getStartedButtons = document.querySelectorAll(
        ".get-started, .btn-primary, [data-action='get-started']"
    );

    const signInButtons = document.querySelectorAll(
        ".sign-in, [data-action='sign-in']"
    );

    const analyzerForm = document.querySelector(".analyzer-form");
    const repoInput = document.querySelector(
        "#repo-url, input[type='url'], input[placeholder*='github']"
    );

    // --------------------------------------------------------
    // PAGE NAVIGATION
    // --------------------------------------------------------

    function goToSignup() {
        // If signup section exists
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

        // Otherwise use signup page if available
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
        window.location.href = "dashboard.html";
    }

    // --------------------------------------------------------
    // GET STARTED
    // --------------------------------------------------------

    getStartedButtons.forEach(button => {
        button.addEventListener("click", (event) => {
            event.preventDefault();

            // Get Started should NOT directly open analyzer
            goToSignup();
        });
    });

    // --------------------------------------------------------
    // SIGN IN
    // --------------------------------------------------------

    signInButtons.forEach(button => {
        button.addEventListener("click", (event) => {
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

        navLinks.querySelectorAll("a").forEach(link => {
            link.addEventListener("click", () => {
                navLinks.classList.remove("active");
                menuToggle.classList.remove("active");
            });
        });
    }

    // --------------------------------------------------------
    // SMOOTH SCROLL
    // --------------------------------------------------------

    document.querySelectorAll("a[href^='#']").forEach(link => {

        link.addEventListener("click", (event) => {

            const targetId = link.getAttribute("href");

            if (!targetId || targetId === "#") {
                return;
            }

            const target = document.querySelector(targetId);

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

            const parsedUrl = new URL(url);

            return (
                parsedUrl.hostname === "github.com" ||
                parsedUrl.hostname === "www.github.com"
            );

        } catch (error) {
            return false;
        }
    }

    // --------------------------------------------------------
    // ANALYZER
    // --------------------------------------------------------

    if (analyzerForm) {

        analyzerForm.addEventListener("submit", async (event) => {

            event.preventDefault();

            const url = repoInput ? repoInput.value.trim() : "";

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
                submitButton ? submitButton.innerHTML : "";

            if (submitButton) {

                submitButton.disabled = true;

                submitButton.innerHTML = `
                    <span class="loading-spinner"></span>
                    Analyzing...
                `;
            }

            showNotification(
                "Repository analysis started...",
                "success"
            );

            // ------------------------------------------------
            // DEMO LOADING
            // ------------------------------------------------

            await new Promise(resolve =>
                setTimeout(resolve, 2200)
            );

            if (submitButton) {

                submitButton.disabled = false;
                submitButton.innerHTML = originalText;
            }

            showNotification(
                "Analysis completed successfully.",
                "success"
            );

            // ------------------------------------------------
            // FUTURE BACKEND CONNECTION
            // ------------------------------------------------
            //
            // Yahan baad mein actual Python backend API call
            // connect karenge.
            //
            // Example:
            //
            // const response = await fetch(
            //     "http://localhost:8000/analyze",
            //     {
            //         method: "POST",
            //         headers: {
            //             "Content-Type": "application/json"
            //         },
            //         body: JSON.stringify({
            //             repository_url: url
            //         })
            //     }
            // );
            //
            // const data = await response.json();
            //
            // ------------------------------------------------

        });

    }

    // --------------------------------------------------------
    // NOTIFICATION SYSTEM
    // --------------------------------------------------------

    function showNotification(message, type = "success") {

        const oldNotification =
            document.querySelector(".rl-notification");

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

        document.body.appendChild(notification);

        requestAnimationFrame(() => {
            notification.classList.add("show");
        });

        const closeButton =
            notification.querySelector(
                ".notification-close"
            );

        if (closeButton) {

            closeButton.addEventListener("click", () => {

                notification.classList.remove("show");

                setTimeout(() => {
                    notification.remove();
                }, 300);

            });

        }

        setTimeout(() => {

            if (notification.parentElement) {

                notification.classList.remove("show");

                setTimeout(() => {
                    notification.remove();
                }, 300);

            }

        }, 4000);
    }

    // --------------------------------------------------------
    // SCROLL REVEAL
    // --------------------------------------------------------

    const revealElements =
        document.querySelectorAll(
            ".feature-card, .workflow-step, .analyzer-card, .cta-card"
        );

    if ("IntersectionObserver" in window) {

        const observer =
            new IntersectionObserver(
                (entries) => {

                    entries.forEach(entry => {

                        if (entry.isIntersecting) {

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

        revealElements.forEach(element => {
            observer.observe(element);
        });
    }

    // --------------------------------------------------------
    // ARCHITECTURE NODE HOVER
    // --------------------------------------------------------

    const architectureNodes =
        document.querySelectorAll(
            ".architecture-node"
        );

    architectureNodes.forEach(node => {

        node.addEventListener("mouseenter", () => {
            node.classList.add("node-active");
        });

        node.addEventListener("mouseleave", () => {
            node.classList.remove("node-active");
        });

    });

    // --------------------------------------------------------
    // CODE WINDOW LINE ANIMATION
    // --------------------------------------------------------

    const codeLines =
        document.querySelectorAll(
            ".code-line"
        );

    codeLines.forEach((line, index) => {

        line.style.animationDelay =
            `${index * 0.08}s`;

    });

    // --------------------------------------------------------
    // PARALLAX EFFECT
    // --------------------------------------------------------

    const heroVisual =
        document.querySelector(
            ".hero-visual"
        );

    if (heroVisual) {

        window.addEventListener("mousemove", (event) => {

            const x =
                (window.innerWidth / 2 - event.clientX) / 80;

            const y =
                (window.innerHeight / 2 - event.clientY) / 80;

            heroVisual.style.transform =
                `translate(${x}px, ${y}px)`;
        });

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

    if (sections.length && navigationLinks.length) {

        window.addEventListener("scroll", () => {

            let currentSection = "";

            sections.forEach(section => {

                const sectionTop =
                    section.offsetTop - 180;

                if (
                    window.scrollY >= sectionTop
                ) {
                    currentSection =
                        section.getAttribute("id");
                }

            });

            navigationLinks.forEach(link => {

                link.classList.remove(
                    "active"
                );

                const href =
                    link.getAttribute("href");

                if (
                    href === `#${currentSection}`
                ) {
                    link.classList.add(
                        "active"
                    );
                }

            });

        });

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
                        `${event.clientX - rect.left - size / 2}px`;

                    ripple.style.top =
                        `${event.clientY - rect.top - size / 2}px`;

                    this.appendChild(ripple);

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

});