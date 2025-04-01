document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("search-input");
  const autocompleteResults = document.getElementById("autocomplete-results");
  const resultContainer = document.getElementById("result-container");
  const coordinatesDisplay = document.getElementById("coordinates-display");
  const INTERSECTIONS_PATH = "./static/chicago-intersections.json";

  // State
  let intersections = [];
  let map = null;
  let marker = null;

  // Initialize map
  function initMap() {
    // Chicago center coordinates
    const chicagoCenter = [41.8781, -87.6298];
    map = L.map("map").setView(chicagoCenter, 11);

    // Use Esri's satellite imagery with streets overlay for a better map
    L.esri.basemapLayer("Streets").addTo(map);

    // Backup option if Esri fails
    map.on("baselayererror", function () {
      console.log("Falling back to OpenStreetMap");
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);
    });
  }

  // Fetch intersections data
  async function fetchIntersections() {
    try {
      const response = await fetch(INTERSECTIONS_PATH);
      intersections = await response.json();
      console.log(`Loaded ${intersections.length} intersections`);
    } catch (error) {
      console.error("Error loading intersections data:", error);
    }
  }

  // Filter intersections based on search input
  function filterIntersections(searchText) {
    if (!searchText.trim()) return [];

    // Normalize search text
    const tokens = searchText
      .toUpperCase()
      .split(/\s+/)
      .filter((token) => token !== "AND" && token !== "&");

    if (tokens.length === 0) return [];

    // Filter intersections that contain all tokens
    return intersections
      .filter((intersection) => {
        const name = intersection.intersection;
        return tokens.every((token) => name.includes(token));
      })
      .slice(0, 30);
  }

  // Show intersection on map
  function showIntersection(intersection) {
    coordinatesDisplay.style.display = "block";
    coordinatesDisplay.innerHTML = `<div class="coordinates">Latitude: <span class="value">${intersection.latitude.toFixed(5)}</span>
  <br>Longitude: <span class="value">${intersection.longitude.toFixed(5)}</span></div> `;

    // Center map on intersection
    map.setView([intersection.latitude, intersection.longitude], 17);

    // Update or add marker
    if (marker) {
      marker.setLatLng([intersection.latitude, intersection.longitude]);
    } else {
      marker = L.marker([intersection.latitude, intersection.longitude]).addTo(
        map,
      );
    }

    // Popup with intersection name
    marker.bindPopup(intersection.intersection).openPopup();
  }

  /**
  hacky input sanitizer, whatever
  */
  function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /**
   * highlight matching tokens and return the HTML markup
   */
  function highlightText(text, tokens) {
    if (!tokens || tokens.length === 0) {
      return text; // No tokens, just return original text
    }

    // Escape each token to avoid breaking the regex
    const escapedTokens = tokens.map((token) => escapeRegExp(token));

    // Create an alternation group like: (TOKEN1|TOKEN2|TOKEN3...)
    const pattern = escapedTokens.join("|");

    // Case-insensitive global regex that captures each token
    const regex = new RegExp(`(${pattern})`, "gi");

    // Replace each match with a <span class="highlight">
    return text.replace(regex, '<span class="highlight">$1</span>');
  }

  function updateAutocompleteResults(results) {
    autocompleteResults.innerHTML = "";

    if (results.length === 0) {
      autocompleteResults.style.display = "none";
      return;
    }

    // Get current search tokens from the input
    const searchTokens = searchInput.value
      .toUpperCase()
      .split(/\s+/)
      .filter(
        (token) => token !== "AND" && token !== "&" && token.trim() !== "",
      );

    results.forEach((result) => {
      const item = document.createElement("div");
      item.className = "autocomplete-item";

      // Use the original text from the JSON (assuming no HTML inside)
      const originalText = result.originalIntersection || result.intersection;
      const highlightedText = highlightText(originalText, searchTokens);

      item.innerHTML = highlightedText;

      item.addEventListener("click", () => {
        // Put the plain original text into the input
        searchInput.value = originalText;
        autocompleteResults.style.display = "none";
        showIntersection(result);
      });

      autocompleteResults.appendChild(item);
    });

    autocompleteResults.style.display = "block";
  }

  // Event listeners
  searchInput.addEventListener("input", () => {
    const results = filterIntersections(searchInput.value);
    updateAutocompleteResults(results);
  });

  searchInput.addEventListener("focus", () => {
    const results = filterIntersections(searchInput.value);
    updateAutocompleteResults(results);
  });

  // Close autocomplete when clicking outside
  document.addEventListener("click", (event) => {
    if (
      !searchInput.contains(event.target) &&
      !autocompleteResults.contains(event.target)
    ) {
      autocompleteResults.style.display = "none";
    }
  });

  // Initialize
  // Show the map container before initializing the map
  resultContainer.classList.remove("hidden");

  // Hide coordinates display until an intersection is selected
  coordinatesDisplay.style.display = "none";

  initMap();
  fetchIntersections();
});
