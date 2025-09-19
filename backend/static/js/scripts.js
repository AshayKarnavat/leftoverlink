// --- 1. Google Maps Initialization (GLOBAL SCOPE) ---
// This function is now smart enough to handle maps on different pages.
let searchMapMarker; // Make the search map marker globally accessible within this script

function initMap() {
    const postMapDiv = document.getElementById('map');
    const searchMapDiv = document.getElementById('search-map');

    // --- Logic for the "Post Food" and "Edit Post" pages ---
    if (postMapDiv) {
        let startCoords;
        let startZoom;

        // Check if we are on the 'edit' page by looking for the global 'initialCoords' variable
        if (typeof initialCoords !== 'undefined') {
            startCoords = { lat: initialCoords.lat, lng: initialCoords.lon };
            startZoom = 15; // Zoom in closer for an existing point
        } else {
            startCoords = { lat: 20.5937, lng: 78.9629 }; // Default to India
            startZoom = 5;
        }

        const map = new google.maps.Map(postMapDiv, { center: startCoords, zoom: startZoom });
        const marker = new google.maps.Marker({ position: startCoords, map: map, draggable: true });
        const geocoder = new google.maps.Geocoder();

        function updateFormFields(latLng) {
            document.getElementById('lat').value = latLng.lat().toFixed(6);
            document.getElementById('lon').value = latLng.lng().toFixed(6);
            geocoder.geocode({ location: latLng }, (results, status) => {
                if (status === "OK" && results[0]) {
                    let city = "Unknown Location";
                    for (const component of results[0].address_components) {
                        if (component.types.includes("locality") || component.types.includes("administrative_area_level_2")) {
                            city = component.long_name;
                            break;
                        }
                    }
                    document.getElementById('city').value = city;
                }
            });
        }

        if (typeof initialCoords === 'undefined' && navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const userCoords = { lat: position.coords.latitude, lng: position.coords.longitude };
                    map.setCenter(userCoords);
                    map.setZoom(13);
                    marker.setPosition(userCoords);
                    updateFormFields(marker.getPosition());
                },
                () => { updateFormFields(marker.getPosition()); }
            );
        } else {
            updateFormFields(marker.getPosition());
        }

        marker.addListener('dragend', () => { updateFormFields(marker.getPosition()); });
    }

    // --- Logic for the "Search" page ---
    if (searchMapDiv) {
        const startCoords = { lat: 20.5937, lng: 78.9629 };
        const map = new google.maps.Map(searchMapDiv, { center: startCoords, zoom: 5 });
        // Assign the marker to the global variable so the search button can find it
        searchMapMarker = new google.maps.Marker({ position: startCoords, map: map, draggable: true });

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition((position) => {
                const userCoords = { lat: position.coords.latitude, lng: position.coords.longitude };
                map.setCenter(userCoords);
                map.setZoom(12);
                searchMapMarker.setPosition(userCoords);
            });
        }
    }
}


// --- 2. Other Scripts (Run after page loads) ---
document.addEventListener('DOMContentLoaded', () => {

        // --- Hamburger Menu Toggle ---
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const navLinks = document.getElementById('nav-links');

    if (hamburgerBtn && navLinks) {
        hamburgerBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
    }

        // --- NEW: Google Maps Dynamic Loader ---
    const mapDiv = document.getElementById('map') || document.getElementById('search-map');
    if (mapDiv && !window.google) { // Check if a map div exists AND google API is not already loaded
        const apiKey = mapDiv.dataset.apiKey;
        if (apiKey) {
            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&callback=initMap`;
            script.async = true;
            document.head.appendChild(script);
        }
    }

    // Alert Handler
    const messagesData = document.body.dataset.messages;
    if (messagesData && messagesData !== '[]') {
        try {
            const messages = JSON.parse(messagesData);
            messages.forEach(([category, msg]) => { alert(msg); });
        } catch (e) {
            console.error("Could not parse messages:", e);
        }
    }

    // Password Toggles
    const toggleRegister = document.getElementById("toggleRegisterPassword");
    if (toggleRegister) {
        toggleRegister.addEventListener("click", () => {
            const pwd = document.getElementById("password");
            const cpwd = document.getElementById("confirm_password");
            pwd.type = pwd.type === "password" ? "text" : "password";
            cpwd.type = cpwd.type === "password" ? "text" : "password";
        });
    }

    const toggleLogin = document.getElementById("toggleLoginPassword");
    if (toggleLogin) {
        toggleLogin.addEventListener("click", () => {
            const pwd = document.getElementById("login_password");
            pwd.type = pwd.type === "password" ? "text" : "password";
        });
    }
    
    // Slider and Input Box Synchronization
    const radiusSlider = document.getElementById('radius-slider');
    const radiusInput = document.getElementById('radius');
    if (radiusSlider && radiusInput) {
        radiusSlider.addEventListener('input', () => { radiusInput.value = radiusSlider.value; });
        radiusInput.addEventListener('input', () => { radiusSlider.value = radiusInput.value; });
    }
    
    // UPDATED Nearby Search Logic
    const findNearbyBtn = document.getElementById('find-nearby-btn');
    if (findNearbyBtn) {
        findNearbyBtn.addEventListener('click', () => {
            // Check if the search map's marker has been created
            if (!searchMapMarker) {
                alert("Map is not ready yet. Please wait a moment.");
                return;
            }

            const radius = document.getElementById('radius').value;
            const postContainer = document.querySelector('#nearby-posts-container');
            
            // Get coordinates from the map marker, NOT from a new geolocation call
            const position = searchMapMarker.getPosition();
            const lat = position.lat();
            const lon = position.lng();

            postContainer.innerHTML = `<p>Searching for food within ${radius} km...</p>`;

            fetch(`/api/nearby_posts?lat=${lat}&lon=${lon}&radius_km=${radius}`)
                .then(response => response.json())
                .then(posts => {
                    postContainer.innerHTML = '';
                    if (posts.length > 0) {
                        posts.forEach(post => {
                            const postCardHTML = `
                            <a href="/post/${post.id}" class="post-card-link">
                                <div class="post-card">
                                    <img src="/static/uploads/${post.image_filename}" alt="${post.food_name}">
                                    <h3>${post.food_name}</h3>
                                    <p class="post-description">${post.description}</p>
                                    <p><strong>Quantity:</strong> ${post.quantity}</p>
                                    <p><strong>Location:</strong> ${post.city}</p>
                                    <p class="posted-by">Posted by: ${post.author_username}</p>
                                </div>
                            </a>`;
                            postContainer.innerHTML += postCardHTML;
                        });
                    } else {
                        postContainer.innerHTML = '<p>No food found within that radius. Try a larger distance!</p>';
                    }
                });
        });
    }
});