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

        // Global Broken Image Handler (works for static and dynamically loaded images)
        const handleImageError = (img) => {
            if (!img.dataset.fallbackApplied) {
                img.dataset.fallbackApplied = "true";
                img.src = '/static/images/fallback_poster.png';
            }
        };

        document.querySelectorAll('img').forEach(img => {
            img.addEventListener('error', () => handleImageError(img));
        });

        // Live Movie Search Suggestions & Autocomplete Engine
        const initSearchSuggestions = () => {
            const searchInput = document.getElementById('movieSearchInput');
            const dropdown = document.getElementById('searchSuggestionsDropdown');
            const list = document.getElementById('suggestionsList');
            const viewAllLink = document.getElementById('viewAllSearchLink');

            if (!searchInput || !dropdown || !list) return;

            let debounceTimer = null;
            let currentFocusIndex = -1;

            const renderSuggestions = (items, query) => {
                list.innerHTML = '';
                currentFocusIndex = -1;

                if (viewAllLink) {
                    viewAllLink.href = query ? `/discover/?q=${encodeURIComponent(query)}` : '/discover/';
                }

                if (!items || items.length === 0) {
                    list.innerHTML = `
                        <div class="p-3 text-center text-secondary">
                            <i class="fa-solid fa-film mb-2 fs-4 text-secondary opacity-50"></i>
                            <div class="small">No matching movies found</div>
                            <div class="text-white-50 small mt-1">Try another title, genre, or keyword</div>
                        </div>
                    `;
                    dropdown.classList.remove('d-none');
                    return;
                }

                items.forEach((movie, idx) => {
                    const itemLink = document.createElement('a');
                    itemLink.className = 'suggestion-item';
                    itemLink.href = movie.url;
                    itemLink.setAttribute('data-index', idx);

                    const genresHtml = (movie.genres || []).map(g => `<span class="badge bg-secondary bg-opacity-25 text-white-50 small me-1">${g}</span>`).join('');
                    const ratingHtml = movie.rating > 0
                        ? `<span class="suggestion-rating"><i class="fa-solid fa-star me-1"></i>${movie.rating}</span>`
                        : '';
                    const bookingBadge = movie.has_active_shows
                        ? `<span class="badge bg-danger-subtle text-danger border border-danger-subtle ms-auto small"><i class="fa-solid fa-ticket me-1"></i>Book</span>`
                        : `<span class="badge bg-secondary-subtle text-secondary ms-auto small">Details</span>`;

                    itemLink.innerHTML = `
                        <img src="${movie.poster_url}" alt="${movie.title}" class="suggestion-poster" onerror="this.onerror=null; this.src='/static/images/fallback_poster.png';">
                        <div class="flex-grow-1 min-w-0">
                            <div class="suggestion-title text-truncate">${movie.title}</div>
                            <div class="suggestion-meta">
                                ${ratingHtml}
                                ${movie.release_year ? `<span>${movie.release_year}</span>` : ''}
                                ${movie.language ? `<span>${movie.language}</span>` : ''}
                                <span>${genresHtml}</span>
                            </div>
                        </div>
                        ${bookingBadge}
                    `;
                    list.appendChild(itemLink);
                });

                dropdown.classList.remove('d-none');
            };

            const fetchSuggestions = async (query) => {
                try {
                    const res = await fetch(`/api/movies/suggestions/?q=${encodeURIComponent(query)}&limit=6`);
                    if (!res.ok) return;
                    const data = await res.json();
                    if (data && data.suggestions) {
                        renderSuggestions(data.suggestions, query);
                    }
                } catch (err) {
                    console.warn('Movie suggestions fetch warning:', err);
                }
            };

            searchInput.addEventListener('input', (e) => {
                const q = e.target.value.trim();
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    fetchSuggestions(q);
                }, 200);
            });

            searchInput.addEventListener('focus', () => {
                const q = searchInput.value.trim();
                fetchSuggestions(q);
            });

            // Keyboard navigation for suggestions
            searchInput.addEventListener('keydown', (e) => {
                const items = list.querySelectorAll('.suggestion-item');
                if (!items.length || dropdown.classList.contains('d-none')) return;

                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    currentFocusIndex = (currentFocusIndex + 1) % items.length;
                    updateActiveItem(items);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    currentFocusIndex = (currentFocusIndex - 1 + items.length) % items.length;
                    updateActiveItem(items);
                } else if (e.key === 'Enter') {
                    if (currentFocusIndex >= 0 && items[currentFocusIndex]) {
                        e.preventDefault();
                        window.location.href = items[currentFocusIndex].href;
                    }
                } else if (e.key === 'Escape') {
                    dropdown.classList.add('d-none');
                }
            });

            const updateActiveItem = (items) => {
                items.forEach((item, idx) => {
                    if (idx === currentFocusIndex) {
                        item.classList.add('active');
                        item.scrollIntoView({ block: 'nearest' });
                    } else {
                        item.classList.remove('active');
                    }
                });
            };

            // Close dropdown on outside click
            document.addEventListener('click', (e) => {
                if (!dropdown.contains(e.target) && !searchInput.contains(e.target)) {
                    dropdown.classList.add('d-none');
                }
            });
        };

        initSearchSuggestions();

        // Global Interactive Trailer Modal Handler
        const trailerModalEl = document.getElementById('globalTrailerModal');
        if (trailerModalEl) {
            const trailerIframe = document.getElementById('globalTrailerIframe');
            const trailerTitle = document.getElementById('globalTrailerMovieTitle');
            const trailerWatchBtn = document.getElementById('globalTrailerWatchBtn');
            const trailerFallback = document.getElementById('globalTrailerFallback');
            const trailerFallbackLink = document.getElementById('globalTrailerFallbackLink');
            const iframeContainer = trailerIframe ? trailerIframe.parentElement : null;

            const resetTrailerModal = () => {
                if (trailerIframe) {
                    trailerIframe.src = '';
                }
                if (iframeContainer) {
                    iframeContainer.classList.add('d-none');
                }
                if (trailerFallback) {
                    trailerFallback.classList.add('d-none');
                }
                if (trailerWatchBtn) {
                    trailerWatchBtn.classList.add('d-none');
                    trailerWatchBtn.href = '#';
                }
            };

            const populateTrailer = (btn) => {
                if (!btn) return;
                
                // Immediately reset to prevent playing previous movie's video
                resetTrailerModal();

                const videoKey = (btn.getAttribute('data-trailer-key') || '').trim();
                const embedUrlAttr = (btn.getAttribute('data-trailer-url') || '').trim();
                const title = (btn.getAttribute('data-trailer-title') || 'Official Trailer').trim();
                const watchUrlAttr = (btn.getAttribute('data-watch-url') || '').trim();

                let finalKey = null;
                const keyRegex = /^[A-Za-z0-9_-]{11}$/;

                if (videoKey && keyRegex.test(videoKey)) {
                    finalKey = videoKey;
                } else if (embedUrlAttr) {
                    const match = embedUrlAttr.match(/(?:embed\/|v=|\/|youtu\.be\/)([A-Za-z0-9_-]{11})/);
                    if (match && keyRegex.test(match[1])) {
                        finalKey = match[1];
                    }
                }

                if (finalKey) {
                    const safeEmbedUrl = `https://www.youtube.com/embed/${finalKey}?autoplay=1`;
                    const safeWatchUrl = `https://www.youtube.com/watch?v=${finalKey}`;

                    if (trailerTitle) trailerTitle.textContent = `${title} - Official Trailer`;
                    if (trailerWatchBtn) {
                        trailerWatchBtn.href = safeWatchUrl;
                        trailerWatchBtn.classList.remove('d-none');
                    }
                    if (trailerFallbackLink) trailerFallbackLink.href = safeWatchUrl;

                    if (iframeContainer && trailerIframe) {
                        iframeContainer.classList.remove('d-none');
                        trailerIframe.src = safeEmbedUrl;
                    }
                } else {
                    // No valid trailer key available for this movie
                    if (trailerTitle) trailerTitle.textContent = `${title} - Trailer Unavailable`;
                    if (trailerFallback) {
                        trailerFallback.classList.remove('d-none');
                        const msgEl = trailerFallback.querySelector('p');
                        if (msgEl) msgEl.textContent = 'Official trailer is currently unavailable for this title.';
                        if (trailerFallbackLink) {
                            if (watchUrlAttr && watchUrlAttr !== '#') {
                                trailerFallbackLink.href = watchUrlAttr;
                                trailerFallbackLink.classList.remove('d-none');
                            } else {
                                trailerFallbackLink.classList.add('d-none');
                            }
                        }
                    }
                }
            };

            // Event listener on document to intercept trailer button clicks
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

            // Bootstrap show.bs.modal listener for relatedTarget
            trailerModalEl.addEventListener('show.bs.modal', (e) => {
                if (e.relatedTarget && e.relatedTarget.classList && e.relatedTarget.classList.contains('play-trailer-btn')) {
                    populateTrailer(e.relatedTarget);
                }
            });

            // Stop audio/video playback and reset state when modal is closed
            trailerModalEl.addEventListener('hide.bs.modal', () => {
                resetTrailerModal();
            });
        }

        // ======================================================================
        // Interactive City / Location Selector & Geolocation Auto-Detection
        // ======================================================================
        const initLocationSelector = () => {
            const locationModalEl = document.getElementById('locationModal');
            const detectBtn = document.getElementById('detectLocationBtn');
            const detectIcon = document.getElementById('detectLocationIcon');
            const detectText = document.getElementById('detectLocationText');
            const alertBanner = document.getElementById('locationAlertBanner');
            const alertText = document.getElementById('locationAlertText');
            const searchInput = document.getElementById('citySearchInput');
            const noMatchState = document.getElementById('noCityMatchState');

            const showAlert = (msg, type = 'info') => {
                if (!alertBanner || !alertText) return;
                alertBanner.className = `alert alert-${type} py-2 px-3 mb-3 small d-flex align-items-center gap-2`;
                alertText.textContent = msg;
                alertBanner.classList.remove('d-none');
            };

            const hideAlert = () => {
                if (alertBanner) alertBanner.classList.add('d-none');
            };

            // 1. City Selection Action (1-click from grid/list)
            document.addEventListener('click', async (e) => {
                const btn = e.target.closest('.city-select-btn');
                if (!btn) return;

                const cityId = btn.getAttribute('data-city-id');
                const cityName = btn.getAttribute('data-city-name');
                if (!cityId) return;

                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin me-1"></i> ${cityName}`;

                try {
                    const res = await fetch(`/api/location/set/?city_id=${encodeURIComponent(cityId)}`, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    const data = await res.json();
                    if (data.status === 'success') {
                        // Update active city labels
                        document.querySelectorAll('.active-city-label').forEach(el => el.textContent = data.city.name);
                        
                        // Close modal if open
                        if (locationModalEl && window.bootstrap && bootstrap.Modal) {
                            const modal = bootstrap.Modal.getInstance(locationModalEl);
                            if (modal) modal.hide();
                        }
                        // Refresh page or current explore view to apply new location
                        const currentUrl = new URL(window.location.href);
                        if (currentUrl.searchParams.has('city')) {
                            currentUrl.searchParams.set('city', data.city.id);
                            window.location.href = currentUrl.toString();
                        } else {
                            window.location.reload();
                        }
                    } else {
                        showAlert(data.message || 'Unable to update location.', 'warning');
                        btn.disabled = false;
                        btn.textContent = cityName;
                    }
                } catch (err) {
                    console.error('Error setting location:', err);
                    window.location.reload();
                }
            });

            // 2. "Detect My Location" via Browser Geolocation API
            if (detectBtn) {
                detectBtn.addEventListener('click', () => {
                    if (!navigator.geolocation) {
                        showAlert('Geolocation is not supported by your browser. Please pick your city manually.', 'warning');
                        return;
                    }

                    detectBtn.disabled = true;
                    if (detectIcon) detectIcon.className = 'fa-solid fa-spinner fa-spin text-danger';
                    if (detectText) detectText.textContent = 'Detecting GPS...';
                    showAlert('Locating your nearest cinema hub...', 'info');

                    navigator.geolocation.getCurrentPosition(
                        async (position) => {
                            const lat = position.coords.latitude;
                            const lng = position.coords.longitude;

                            try {
                                const res = await fetch(`/api/location/detect/?lat=${lat}&lng=${lng}`, {
                                    method: 'POST',
                                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                                });
                                const data = await res.json();
                                if (data.status === 'success') {
                                    showAlert(`Found nearest city: ${data.city.name} (${data.city.distance_km || 0} km away). Applying...`, 'success');
                                    setTimeout(() => {
                                        if (locationModalEl && window.bootstrap && bootstrap.Modal) {
                                            const modal = bootstrap.Modal.getInstance(locationModalEl);
                                            if (modal) modal.hide();
                                        }
                                        window.location.reload();
                                    }, 600);
                                } else {
                                    showAlert(data.message || 'Could not find closest city. Please choose from the list.', 'warning');
                                    resetDetectBtn();
                                }
                            } catch (err) {
                                showAlert('Failed to resolve location. Please select your city manually.', 'danger');
                                resetDetectBtn();
                            }
                        },
                        (error) => {
                            let msg = 'Location access denied. Please select your city manually from the list.';
                            if (error.code === error.POSITION_UNAVAILABLE) {
                                msg = 'Location information is currently unavailable. Please pick your city below.';
                            } else if (error.code === error.TIMEOUT) {
                                msg = 'Location request timed out. Please select your city manually.';
                            }
                            showAlert(msg, 'warning');
                            resetDetectBtn();
                        },
                        { timeout: 10000, maximumAge: 60000 }
                    );
                });

                const resetDetectBtn = () => {
                    detectBtn.disabled = false;
                    if (detectIcon) detectIcon.className = 'fa-solid fa-crosshairs text-danger';
                    if (detectText) detectText.textContent = 'Detect My Location';
                };
            }

            // 3. Real-time City Search Filter
            if (searchInput) {
                searchInput.addEventListener('input', () => {
                    const query = searchInput.value.toLowerCase().trim();
                    const cityItems = document.querySelectorAll('.city-item');
                    let visibleCount = 0;

                    cityItems.forEach(item => {
                        const cityName = item.getAttribute('data-city-name') || '';
                        if (!query || cityName.includes(query)) {
                            item.classList.remove('d-none');
                            visibleCount++;
                        } else {
                            item.classList.add('d-none');
                        }
                    });

                    if (noMatchState) {
                        if (visibleCount === 0) {
                            noMatchState.classList.remove('d-none');
                        } else {
                            noMatchState.classList.add('d-none');
                        }
                    }
                });
            }
        };

        initLocationSelector();

        // ======================================================================
        // Explore Page Coupled Filters (City -> Theaters -> Languages)
        // ======================================================================
        const initExploreFiltersCoupling = () => {
            const citySelect = document.getElementById('filterCitySelect');
            const theaterSelect = document.getElementById('filterTheaterSelect');

            if (!citySelect || !theaterSelect) return;

            citySelect.addEventListener('change', async () => {
                const selectedCityId = citySelect.value;
                if (!selectedCityId) {
                    return;
                }

                try {
                    const res = await fetch(`/api/theaters-by-city/?city_id=${encodeURIComponent(selectedCityId)}`);
                    const data = await res.json();
                    if (data.status === 'success' && data.theaters) {
                        // Reset and rebuild theater options
                        theaterSelect.innerHTML = '<option value="">All Theaters</option>';
                        data.theaters.forEach(t => {
                            const opt = document.createElement('option');
                            opt.value = t.id;
                            opt.textContent = `${t.name}`;
                            theaterSelect.appendChild(opt);
                        });
                    }
                } catch (err) {
                    console.error('Error fetching theaters for city:', err);
                }
            });
        };

        initExploreFiltersCoupling();

    });
})();


