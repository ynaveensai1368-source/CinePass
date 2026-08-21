/* ==========================================================================
   Movie Discovery System - Modular Theme & Interactive Client JS
   ========================================================================== */

(function () {
    'use strict';

    // Theme Management Engine
    const getStoredTheme = () => localStorage.getItem('theme');
    const setStoredTheme = theme => localStorage.setItem('theme', theme);

    const getPreferredTheme = () => {
        const storedTheme = getStoredTheme();
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    };

    const setTheme = theme => {
        document.documentElement.setAttribute('data-bs-theme', theme);
        updateThemeIcons(theme);
    };

    const updateThemeIcons = theme => {
        const desktopIcon = document.getElementById('themeIcon');
        const mobileIcon = document.getElementById('themeIconMobile');

        const applyIcon = elem => {
            if (!elem) return;
            if (theme === 'dark') {
                elem.className = 'fa-solid fa-sun text-warning';
                elem.setAttribute('title', 'Switch to Light Mode');
            } else {
                elem.className = 'fa-solid fa-moon text-info';
                elem.setAttribute('title', 'Switch to Dark Mode');
            }
        };

        applyIcon(desktopIcon);
        applyIcon(mobileIcon);
    };

    // Apply theme immediately on load
    const initialTheme = getPreferredTheme();
    setTheme(initialTheme);

    document.addEventListener('DOMContentLoaded', () => {
        setTheme(getPreferredTheme());

        // Bind click events to both desktop and mobile theme buttons
        const desktopBtn = document.getElementById('themeToggleBtn');
        const mobileBtn = document.getElementById('themeToggleBtnMobile');

        const toggleHandler = () => {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setStoredTheme(nextTheme);
            setTheme(nextTheme);
        };

        if (desktopBtn) desktopBtn.addEventListener('click', toggleHandler);
        if (mobileBtn) mobileBtn.addEventListener('click', toggleHandler);

        // Listen for OS Theme Preference changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (!getStoredTheme()) {
                setTheme(getPreferredTheme());
            }
        });

        // Auto dismiss alert messages after 5 seconds
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(alert => {
            setTimeout(() => {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                if (bsAlert) bsAlert.close();
            }, 5000);
        });

        // Auto-submit filter selects on change
        const autoFilterSelects = document.querySelectorAll('.auto-filter');
        autoFilterSelects.forEach(select => {
            select.addEventListener('change', () => {
                const form = select.closest('form');
                if (form) form.submit();
            });
        });

        // Global Broken Image Handler
        const images = document.querySelectorAll('img');
        images.forEach(img => {
            img.addEventListener('error', function () {
                if (!this.dataset.fallbackApplied) {
                    this.dataset.fallbackApplied = "true";
                    this.src = '/static/images/fallback_poster.png';
                }
            });
        });

        // Global Interactive Trailer Modal Handler
        const trailerModalEl = document.getElementById('globalTrailerModal');
        if (trailerModalEl) {
            const trailerIframe = document.getElementById('globalTrailerIframe');
            const trailerTitle = document.getElementById('globalTrailerMovieTitle');
            const trailerWatchBtn = document.getElementById('globalTrailerWatchBtn');
            const trailerFallback = document.getElementById('globalTrailerFallback');
            const trailerFallbackLink = document.getElementById('globalTrailerFallbackLink');

            const populateTrailer = (btn) => {
                if (!btn) return;
                let embedUrl = btn.getAttribute('data-trailer-url');
                const videoKey = btn.getAttribute('data-trailer-key');
                const title = btn.getAttribute('data-trailer-title') || 'Official Trailer';
                const watchUrl = btn.getAttribute('data-watch-url') || '#';

                let finalKey = (videoKey && videoKey.length === 11) ? videoKey : null;
                if (!finalKey && embedUrl) {
                    const m = embedUrl.match(/(?:embed\/|v=|\/)([\w-]{11})/);
                    if (m) finalKey = m[1];
                }

                if (finalKey) {
                    embedUrl = `https://www.youtube.com/embed/${finalKey}?autoplay=1`;
                }


                if (trailerTitle) trailerTitle.textContent = `${title} - Official Trailer`;
                if (trailerWatchBtn) trailerWatchBtn.href = watchUrl;
                if (trailerFallbackLink) trailerFallbackLink.href = watchUrl;

                if (trailerFallback) trailerFallback.classList.add('d-none');
                if (trailerIframe && embedUrl) {
                    trailerIframe.parentElement.classList.remove('d-none');
                    trailerIframe.src = embedUrl;
                }
            };

            // Bootstrap show.bs.modal event trigger
            trailerModalEl.addEventListener('show.bs.modal', (e) => {
                const btn = e.relatedTarget || document.activeElement;
                populateTrailer(btn);
            });

            // Manual click event fallback
            document.addEventListener('click', (e) => {
                const btn = e.target.closest('.play-trailer-btn');
                if (btn) {
                    populateTrailer(btn);
                    if (window.bootstrap && bootstrap.Modal) {
                        const modalInstance = bootstrap.Modal.getOrCreateInstance(trailerModalEl);
                        modalInstance.show();
                    }
                }
            });

            // Stop audio/video playback when modal is closed
            trailerModalEl.addEventListener('hide.bs.modal', () => {
                if (trailerIframe) {
                    trailerIframe.src = '';
                }
            });
        }



    });
})();

