// Interactivité du simulateur : tous les calculs viennent de /api/calcul (calcul.py).
(function () {
  "use strict";

  const form = document.getElementById("simulateur");
  const brutInput = document.getElementById("brut");
  const slider = document.getElementById("brut-curseur");
  const persInput = document.getElementById("personnes");
  const errorBox = document.getElementById("erreur");
  const odometer = document.getElementById("net-chiffres");
  const netReader = document.getElementById("net-lecteur");
  const statement = document.querySelector(".statement");
  const bar = document.getElementById("split-bar");
  const tip = document.getElementById("split-tip");

  const PERS_MAX = Number(persInput.max);
  const SEGMENTS = { net: "Net", cnss_ipe: "CNSS + IPE", amo: "AMO", ir: "IR" };

  const state = { periode: "mensuel", raise: 10, data: null };
  let timer = null;
  let controller = null;

  // ---------- Formatage ----------
  function nombre(n) {
    const [ent, dec] = Math.abs(n).toFixed(2).split(".");
    const groupes = ent.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return (n < 0 ? "-" : "") + groupes + "," + dec;
  }
  const dh = (n) => nombre(n) + " DH";
  const facteur = () => (state.periode === "annuel" ? 12 : 1);

  function lireBrut() {
    const v = brutInput.value.replace(/[\s ]/g, "").replace(",", ".");
    return v === "" ? null : Number(v);
  }

  // ---------- Compteur à rouleaux ----------
  function setOdometer(texte) {
    const chars = Array.from(texte);
    const signature = chars.map((c) => (/\d/.test(c) ? "d" : c)).join("");

    if (odometer.dataset.sig !== signature) {
      odometer.dataset.sig = signature;
      odometer.textContent = "";
      chars.forEach((c) => {
        if (/\d/.test(c)) {
          const digit = document.createElement("span");
          digit.className = "odo-digit";
          const strip = document.createElement("span");
          strip.className = "odo-strip";
          for (let i = 0; i <= 9; i++) {
            const s = document.createElement("span");
            s.textContent = String(i);
            strip.appendChild(s);
          }
          digit.appendChild(strip);
          odometer.appendChild(digit);
        } else {
          const sep = document.createElement("span");
          sep.className = "odo-sep";
          sep.textContent = c;
          odometer.appendChild(sep);
        }
      });
      void odometer.offsetWidth; // départ à 0, puis défilement vers la valeur
    }

    const strips = odometer.querySelectorAll(".odo-strip");
    let i = 0;
    const total = strips.length;
    chars.forEach((c) => {
      if (!/\d/.test(c)) return;
      const strip = strips[i];
      strip.style.transitionDelay = (total - 1 - i) * 25 + "ms";
      strip.style.transform = "translateY(" + -Number(c) * 10 + "%)";
      i++;
    });
  }

  // ---------- Affichage ----------
  function render() {
    if (!state.data) return;
    const r = state.data.resultat;
    const f = facteur();
    const valeurs = Object.assign({}, r, { cnss_ipe: r.cnss + r.ipe });

    document.querySelectorAll("[data-money]").forEach((el) => {
      const v = valeurs[el.dataset.money];
      if (typeof v === "number") el.textContent = dh(v * f);
    });
    document.querySelector('[data-text="frais_pct"]').textContent =
      Math.round(r.taux_frais_pro * 100) + " %";
    document.querySelector('[data-text="personnes_retenues"]').textContent = r.personnes_retenues;
    document.querySelector('[data-text="taux_prelevement"]').textContent =
      String(r.taux_prelevement).replace(".", ",");

    // Montant net mis en avant
    setOdometer(nombre(r.net * f));
    netReader.textContent = dh(r.net * f);
    const annuel = state.periode === "annuel";
    document.querySelector("[data-autre-periode]").textContent = dh(annuel ? r.net : r.net * 12);
    document.querySelector("[data-autre-periode-label]").textContent = annuel ? "par mois" : "par an";
    document.querySelectorAll("[data-periode-label]").forEach((el) => {
      el.textContent = annuel ? "annuel" : "mensuel";
    });
    document.querySelector("[data-periode-label-court]").textContent = annuel ? "par an" : "par mois";

    // Barre de répartition
    Object.keys(SEGMENTS).forEach((cle) => {
      const seg = bar.querySelector('[data-seg="' + cle + '"]');
      const part = r.brut ? (valeurs[cle] / r.brut) * 100 : 0;
      seg.style.width = part + "%";
      seg.setAttribute(
        "aria-label",
        SEGMENTS[cle] + " : " + dh(valeurs[cle] * f) + ", " + nombre(part).replace(/,?0+$/, "") + " % du brut"
      );
    });

    const contribBrut = document.querySelector("[data-contrib-brut]");
    if (contribBrut) contribBrut.textContent = dh(r.brut);

    renderRaise();
  }

  function renderRaise() {
    const a = state.data.augmentations.find((x) => x.pourcentage === state.raise);
    if (!a) return;
    const f = facteur();
    document.querySelectorAll("[data-raise]").forEach((b) => {
      b.setAttribute("aria-pressed", String(Number(b.dataset.raise) === state.raise));
    });
    document.querySelector('[data-raise-field="gain_brut"]').textContent = dh(a.gain_brut * f);
    document.querySelector('[data-raise-field="gain_net"]').textContent = dh(a.gain_net * f);
    document.querySelector('[data-raise-field="net"]').textContent = dh(a.net * f);
    document.querySelector('[data-raise-field="part_conservee"]').textContent =
      String(a.part_conservee).replace(".", ",") + " DH";
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    statement.classList.add("is-stale");
  }

  function clearError() {
    errorBox.hidden = true;
    statement.classList.remove("is-stale");
  }

  // ---------- Appel à l'API ----------
  async function update() {
    const brut = lireBrut();
    if (brut === null) return; // champ vidé pendant la saisie : on garde le dernier résultat

    if (controller) controller.abort();
    controller = new AbortController();
    const params = new URLSearchParams({ brut: String(brut), personnes: persInput.value || "0" });

    try {
      const res = await fetch(form.dataset.api + "?" + params, { signal: controller.signal });
      const data = await res.json();
      if (!res.ok) {
        showError(data.erreur);
        return;
      }
      clearError();
      state.data = data;
      render();
    } catch (e) {
      if (e.name !== "AbortError") showError("Le serveur ne répond pas. Vérifiez qu'il est bien démarré.");
    }
  }

  function schedule(delai) {
    clearTimeout(timer);
    timer = setTimeout(update, delai);
  }

  // ---------- Curseur ----------
  function paintSlider() {
    const min = Number(slider.min);
    const max = Number(slider.max);
    const p = ((Number(slider.value) - min) / (max - min)) * 100;
    slider.style.setProperty("--p", p + "%");
  }

  slider.addEventListener("input", () => {
    brutInput.value = slider.value;
    paintSlider();
    schedule(40);
  });

  brutInput.addEventListener("input", () => {
    const v = lireBrut();
    if (v !== null && !Number.isNaN(v)) {
      slider.value = String(Math.min(Math.max(v, Number(slider.min)), Number(slider.max)));
      paintSlider();
    }
    schedule(180);
  });

  // ---------- Personnes à charge ----------
  function setPersonnes(n) {
    const v = Math.min(Math.max(Number.isFinite(n) ? n : 0, 0), PERS_MAX);
    persInput.value = String(v);
    form.querySelector('[data-step="-1"]').disabled = v <= 0;
    form.querySelector('[data-step="1"]').disabled = v >= PERS_MAX;
  }

  form.querySelectorAll("[data-step]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setPersonnes(parseInt(persInput.value || "0", 10) + Number(btn.dataset.step));
      schedule(0);
    });
  });

  persInput.addEventListener("input", () => {
    if (persInput.value === "") return;
    setPersonnes(parseInt(persInput.value, 10));
    schedule(120);
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    schedule(0);
  });

  // ---------- Mensuel / annuel ----------
  document.querySelectorAll("[data-periode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.periode = btn.dataset.periode;
      document.querySelectorAll("[data-periode]").forEach((b) => {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      render();
    });
  });

  // ---------- Augmentation ----------
  document.querySelectorAll("[data-raise]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.raise = Number(btn.dataset.raise);
      if (state.data) renderRaise();
    });
  });

  // ---------- Infobulle de la barre ----------
  function showTip(seg) {
    tip.textContent = seg.getAttribute("aria-label");
    tip.hidden = false;
    const barBox = bar.getBoundingClientRect();
    const segBox = seg.getBoundingClientRect();
    const centre = segBox.left - barBox.left + segBox.width / 2;
    const demi = tip.offsetWidth / 2;
    const x = Math.min(Math.max(centre, demi), barBox.width - demi);
    tip.style.left = x + "px";
  }

  bar.querySelectorAll(".seg").forEach((seg) => {
    seg.addEventListener("mouseenter", () => showTip(seg));
    seg.addEventListener("focus", () => showTip(seg));
    seg.addEventListener("mouseleave", () => { tip.hidden = true; });
    seg.addEventListener("blur", () => { tip.hidden = true; });
  });

  // ---------- Contribution aux statistiques (uniquement au clic) ----------
  const contribForm = document.getElementById("contribution");
  if (contribForm) {
    const contribMsg = contribForm.querySelector(".contrib-message");
    const contribBtn = contribForm.querySelector(".contrib-submit");

    const contribErreur = (texte) => {
      contribMsg.textContent = texte;
      contribMsg.classList.add("is-error");
      contribMsg.hidden = false;
    };

    contribForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const brut = lireBrut();
      if (brut === null || Number.isNaN(brut)) {
        contribErreur("Saisissez d'abord un salaire brut dans le simulateur.");
        return;
      }
      if (!contribForm.elements.consentement.checked) {
        contribErreur("Cochez la case de consentement pour ajouter votre salaire.");
        contribForm.elements.consentement.focus();
        return;
      }

      const corps = new FormData(contribForm);
      corps.set("brut", String(brut));
      corps.set("personnes", persInput.value || "0");
      contribBtn.disabled = true;

      try {
        const res = await fetch(contribForm.dataset.api, { method: "POST", body: corps });
        const data = await res.json();
        if (!res.ok) {
          contribErreur(data.erreur);
          contribBtn.disabled = res.status === 429;
          return;
        }
        const merci = document.createElement("p");
        merci.className = "contrib-done";
        merci.textContent = data.message + " ";
        const lien = document.createElement("a");
        lien.href = contribForm.dataset.stats;
        lien.textContent = "Voir les statistiques";
        merci.appendChild(lien);
        contribForm.replaceWith(merci);
      } catch (err) {
        contribErreur("Le serveur ne répond pas. Vérifiez qu'il est bien démarré.");
        contribBtn.disabled = false;
      }
    });
  }

  // ---------- Démarrage ----------
  const initialPressed = document.querySelector('[data-raise][aria-pressed="true"]');
  if (initialPressed) state.raise = Number(initialPressed.dataset.raise);
  setPersonnes(parseInt(persInput.value || "0", 10));
  paintSlider();
  update();
})();
