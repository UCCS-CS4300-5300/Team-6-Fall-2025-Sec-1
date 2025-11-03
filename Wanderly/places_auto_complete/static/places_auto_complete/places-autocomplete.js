(function () {
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
  
      const { PlaceAutocompleteElement } = await google.maps.importLibrary("places");
  
      // Any marker will do; keep both for flexibility.
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
        // Optional: copy placeholder / classes for styling consistency
        pac.setAttribute("placeholder", originalInput.getAttribute("placeholder") || "");
  
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
  
          // Optional: notify other scripts
          originalInput.dispatchEvent(new CustomEvent("places:changed", { detail: { place, lat, lng } }));
        });
      });
    }
  
    boot();
  })();
  