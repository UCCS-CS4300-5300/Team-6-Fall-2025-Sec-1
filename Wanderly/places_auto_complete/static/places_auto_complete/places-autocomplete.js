(function () {
  const __formsWithPacEnterHandler = new WeakSet();

  // Run after Maps is loaded; then import the new Places library on demand.
  async function boot() {
    // If Maps base isn't ready yet, poll briefly.
    if (!(window.google && google.maps && google.maps.importLibrary)) {
      await new Promise((res) => {
        const t = setInterval(() => {
          if (window.google && google.maps && google.maps.importLibrary) {
            clearInterval(t); res();
          }
        }, 50);
      });
    }

    // Loading in the google auto complete library
    const { PlaceAutocompleteElement } = await google.maps.importLibrary("places");

    // This is how we say what fields get autocomplete (data-places=1 or class = js-places)
    const inputs = document.querySelectorAll('[data-places="1"], .js-places');
    inputs.forEach((originalInput) => {
      // Build the Google element (its own input UI).
      const opts = {};
      // Map your old attributes to the new API:
      // includedPrimaryTypes ~ "establishment", "geocode" (see docs for full list)
      const types = originalInput.getAttribute("data-types");
      if (types && types !== "any") opts.includedPrimaryTypes = [types];

      // Restrict by country/countries: e.g., "us", or "us,ca"
      const country = originalInput.getAttribute("data-country");
      if (country) opts.includedRegionCodes = country.split(",").map(s => s.trim());

      const pac = new PlaceAutocompleteElement(opts);
      pac.style.setProperty('color-scheme', 'light');
      pac.style.width = "100%";
      pac.style.minHeight = "50px";
      // Copy placeholder for consistency
      pac.setAttribute("placeholder", originalInput.getAttribute("placeholder") || "");
      const initialValue = originalInput.value;
      
      // Insert the PAC and hide original input
      originalInput.insertAdjacentElement("beforebegin", pac);
      const syncOriginalFromPac = () => {
        originalInput.value = pac.value || "";
      };
      pac.addEventListener("input", syncOriginalFromPac);
      pac.addEventListener("change", syncOriginalFromPac);
      if (initialValue) {
        pac.value = initialValue;
        pac.setAttribute("value", initialValue);
        originalInput.value = initialValue;
        requestAnimationFrame(syncOriginalFromPac);
      }
      originalInput.style.display = "none";

      // Ensure pressing Enter submits the form even inside shadow DOM
      const form = pac.closest('form');
      if (form && !__formsWithPacEnterHandler.has(form)) {
        form.addEventListener('keydown', (e) => {
          if (e.key !== 'Enter') return;

          // Works with closed shadow DOM: use composed path to see if the event originated inside the PAC
          const path = e.composedPath ? e.composedPath() : [];
          const fromPac = path.some(
            (node) =>
              node && node.tagName &&
              String(node.tagName).toLowerCase().includes('place-autocomplete')
          );

          if (fromPac) {
            e.preventDefault();        // stop the component from swallowing it
            form.requestSubmit();      // behave like clicking the submit button
          }
        }, true); // capture!
        __formsWithPacEnterHandler.add(form);
      }



      // Copy all classes from the original input to maintain styling
      const classes = originalInput.className;
      if (classes) {
        pac.className = classes;
      }
      
      // Copy any ID from original (useful for styling)
      const originalId = originalInput.getAttribute("id");
      if (originalId) {
        pac.setAttribute("id", originalId + "-autocomplete");
      }

      // Insert the PAC just before the original input and hide the original
      originalInput.insertAdjacentElement("beforebegin", pac);
      originalInput.style.display = "none";

      // Targets to mirror values into
      function setTarget(attr, value) {
        const sel = originalInput.getAttribute(attr);
        if (!sel) return;
        const el = document.querySelector(sel) || document.querySelector('[name="' + sel + '"]');
        if (el) el.value = value ?? "";
      }

      // Listen for selection, fetch details, mirror into your form fields
      pac.addEventListener("gmp-select", async ({ placePrediction }) => {
        const place = placePrediction.toPlace();
        await place.fetchFields({ fields: ["id", "displayName", "formattedAddress", "location"] });
        // Mirror text into your *original* (hidden) input so forms/validation still see it
        originalInput.value = place.formattedAddress || place.displayName || "";

        // Hidden extras
        setTarget("data-place-id-target", place.id);
        const lat = place.location ? place.location.lat() : "";
        const lng = place.location ? place.location.lng() : "";
        setTarget("data-lat-target", lat);
        setTarget("data-lng-target", lng);
        const displayName =
          (place.displayName && (place.displayName.text || place.displayName)) ||
          place.name ||
          "";
        setTarget("data-name-target", displayName);

        // Optional: notify other scripts
        originalInput.dispatchEvent(new CustomEvent("places:changed", { detail: { place, lat, lng } }));
      });
    });
  }

  boot();
})();
