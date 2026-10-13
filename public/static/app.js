// Interactivité du simulateur : tous les calculs viennent de l'API (calcul.py).
(function () {
  "use strict";

  const form = document.getElementById("simulateur");
  const brutInput = document.getElementById("brut");
  const slider = document.getElementById("brut-curseur");
  const personnesInput = document.getElementById("personnes");
  const errorBox = document.getElementById("erreur");
  const odometer = document.getElementById("net-chiffres");
  const netReader = document.getElementById("net-lecteur");
  const statement = document.querySelector(".statement");
  const bar = document.getElementById("split-bar");
  const tip = document.getElementById("split-tip");
  const montantLabel = document.getElementById("montant-label");
  const modeAide = document.getElementById("mode-aide");
  const negociationBox = document.getElementById("negociation");
  const positionBox = document.getElementById("position");

  const PERSONNES_MAX = Number(personnesInput.max);
  const SEGMENTS = { net: "Net", cnss_ipe: "CNSS + IPE", amo: "AMO", ir: "IR" };
  const MODES = {
    brut: { label: "Salaire brut mensuel", curseur: "Salaire brut mensuel (curseur)" },
    net: { label: "Salaire net mensuel souhaité", curseur: "Salaire net mensuel souhaité (curseur)" },
  };

  const state = { mode: "brut", periode: "mensuel", augmentation: 10, data: null };
  let timer = null;
  let controller = null;
  let positionController = null;

  // ---------- Formatage ----------
  function nombre(n) {
    const [ent, dec] = Math.abs(n).toFixed(2).split(".");
    const groupes = ent.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return (n < 0 ? "-" : "") + groupes + "," + dec;
  }
  const dh = (n) => nombre(n) + " DH";
  const entier = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const multiplicateurPeriode = () => (state.periode === "annuel" ? 12 : 1);

  // Brut en mode « Brut → Net », net souhaité en mode « Net → Brut ».
  function lireMontant() {
    // \s couvre aussi l'espace fine insécable des nombres saisis à la française.
    const texte = brutInput.value.replace(/\s/g, "").replace(",", ".");
    return texte === "" ? null : Number(texte);
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
      // Force le navigateur à afficher les rouleaux à 0 avant d'appliquer la
      // transition : sans cela, les nouveaux chiffres apparaîtraient sans défiler.
      void odometer.offsetWidth;
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
    const resultat = state.data.resultat;
    const mult = multiplicateurPeriode();
    const valeurs = Object.assign({}, resultat, { cnss_ipe: resultat.cnss + resultat.ipe });

    document.querySelectorAll("[data-money]").forEach((el) => {
      const montant = valeurs[el.dataset.money];
      if (typeof montant === "number") el.textContent = dh(montant * mult);
    });
    document.querySelector('[data-text="frais_pct"]').textContent =
      Math.round(resultat.taux_frais_pro * 100) + " %";
    document.querySelector('[data-text="personnes_retenues"]').textContent = resultat.personnes_retenues;
    document.querySelector('[data-text="taux_prelevement"]').textContent =
      String(resultat.taux_prelevement).replace(".", ",");

    setOdometer(nombre(resultat.net * mult));
    netReader.textContent = dh(resultat.net * mult);
    const annuel = state.periode === "annuel";
    document.querySelector("[data-autre-periode]").textContent =
      dh(annuel ? resultat.net : resultat.net * 12);
    document.querySelector("[data-autre-periode-label]").textContent = annuel ? "par mois" : "par an";
    document.querySelectorAll("[data-periode-label]").forEach((el) => {
      el.textContent = annuel ? "annuel" : "mensuel";
    });
    document.querySelector("[data-periode-label-court]").textContent = annuel ? "par an" : "par mois";

    Object.keys(SEGMENTS).forEach((cle) => {
      const seg = bar.querySelector('[data-seg="' + cle + '"]');
      const part = resultat.brut ? (valeurs[cle] / resultat.brut) * 100 : 0;
      seg.style.width = part + "%";
      seg.setAttribute(
        "aria-label",
        SEGMENTS[cle] + " : " + dh(valeurs[cle] * mult) + ", " +
          nombre(part).replace(/,?0+$/, "") + " % du brut"
      );
    });

    // Toujours mensuel : c'est le brut mensuel qui est enregistré.
    const contribBrut = document.querySelector("[data-contrib-brut]");
    if (contribBrut) contribBrut.textContent = dh(resultat.brut);
    // Sous-titre de la page : toujours le brut mensuel simulé.
    document.querySelector("[data-lede-brut]").textContent = dh(resultat.brut);

    const negociation = state.data.negociation;
    negociationBox.hidden = !negociation;
    negociationBox.textContent = negociation ? negociation.message : "";
    setAlerte("alerte-seuil", state.data.alerte);

    renderRaise();
  }

  function setAlerte(id, message) {
    const encart = document.getElementById(id);
    encart.querySelector(".seuil-message").textContent = message || "";
    encart.hidden = !message;
  }

  function renderRaise() {
    const scenario = state.data.augmentations.find((s) => s.pourcentage === state.augmentation);
    if (!scenario) return;
    const mult = multiplicateurPeriode();
    document.querySelectorAll("[data-raise]").forEach((bouton) => {
      bouton.setAttribute("aria-pressed", String(Number(bouton.dataset.raise) === state.augmentation));
    });
    document.querySelector('[data-raise-field="gain_brut"]').textContent = dh(scenario.gain_brut * mult);
    document.querySelector('[data-raise-field="gain_net"]').textContent = dh(scenario.gain_net * mult);
    document.querySelector('[data-raise-field="net"]').textContent = dh(scenario.net * mult);
    document.querySelector('[data-raise-field="part_conservee"]').textContent =
      String(scenario.part_conservee).replace(".", ",") + " DH";
    setAlerte("alerte-augmentation", scenario.alerte || state.data.alerte);
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
    const montant = lireMontant();
    if (montant === null) return; // champ vidé pendant la saisie : on garde le dernier résultat

    if (controller) controller.abort();
    controller = new AbortController();
    const modeNet = state.mode === "net";
    const params = new URLSearchParams({ personnes: personnesInput.value || "0" });
    params.set(modeNet ? "net" : "brut", String(montant));
    const api = modeNet ? form.dataset.apiNet : form.dataset.api;

    try {
      const res = await fetch(api + "?" + params, { signal: controller.signal });
      const data = await res.json();
      if (!res.ok) {
        showError(data.erreur);
        return;
      }
      clearError();
      state.data = data;
      render();
      updatePosition();
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
    const progression = ((Number(slider.value) - min) / (max - min)) * 100;
    slider.style.setProperty("--p", progression + "%");
  }

  slider.addEventListener("input", () => {
    brutInput.value = slider.value;
    paintSlider();
    schedule(40);
  });

  function syncSlider() {
    const montant = lireMontant();
    if (montant !== null && !Number.isNaN(montant)) {
      slider.value = String(Math.min(Math.max(montant, Number(slider.min)), Number(slider.max)));
      paintSlider();
    }
  }

  brutInput.addEventListener("input", () => {
    syncSlider();
    schedule(180);
  });

  // ---------- Brut → Net / Net → Brut ----------
  document.querySelectorAll("[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.mode;
      if (mode === state.mode) return;
      state.mode = mode;
      document.querySelectorAll("[data-mode]").forEach((bouton) => {
        bouton.setAttribute("aria-pressed", String(bouton === btn));
      });
      montantLabel.textContent = MODES[mode].label;
      slider.setAttribute("aria-label", MODES[mode].curseur);
      modeAide.hidden = mode !== "net";
      // On repart du résultat affiché : le net actuel devient l'objectif, ou inversement.
      if (state.data) {
        const r = state.data.resultat;
        brutInput.value = String(Math.round(mode === "net" ? r.net : r.brut));
        syncSlider();
      }
      schedule(0);
    });
  });

  // ---------- Personnes à charge ----------
  function setPersonnes(n) {
    const personnes = Math.min(Math.max(Number.isFinite(n) ? n : 0, 0), PERSONNES_MAX);
    personnesInput.value = String(personnes);
    form.querySelector('[data-step="-1"]').disabled = personnes <= 0;
    form.querySelector('[data-step="1"]').disabled = personnes >= PERSONNES_MAX;
  }

  form.querySelectorAll("[data-step]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setPersonnes(parseInt(personnesInput.value || "0", 10) + Number(btn.dataset.step));
      schedule(0);
    });
  });

  personnesInput.addEventListener("input", () => {
    if (personnesInput.value === "") return;
    setPersonnes(parseInt(personnesInput.value, 10));
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
      document.querySelectorAll("[data-periode]").forEach((bouton) => {
        bouton.setAttribute("aria-pressed", String(bouton === btn));
      });
      render();
    });
  });

  // ---------- Augmentation ----------
  document.querySelectorAll("[data-raise]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.augmentation = Number(btn.dataset.raise);
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

  // ---------- Où je me situe (rien n'est enregistré) ----------
  function ligne(...morceaux) {
    const li = document.createElement("li");
    morceaux.forEach((m) => li.append(m));
    return li;
  }

  function fort(texte) {
    const s = document.createElement("strong");
    s.textContent = texte;
    return s;
  }

  function ligneGroupe(groupe, intitule, autres) {
    const nom = groupe.nom === "Autre" ? autres : intitule + groupe.nom;
    if (groupe.pourcentage === null) {
      return ligne(nom + " : moins de 5 contributions, pas de comparaison possible.");
    }
    return ligne(nom + " : plus que ", fort(groupe.pourcentage + " %"),
      " des " + entier(groupe.nombre) + " contributeurs.");
  }

  async function updatePosition() {
    if (!positionBox || !state.data) return;
    const ville = document.getElementById("c-ville");
    const secteur = document.getElementById("c-secteur");
    const params = new URLSearchParams({ brut: String(state.data.resultat.brut) });
    if (ville && ville.value) params.set("ville", ville.value);
    if (secteur && secteur.value) params.set("secteur", secteur.value);

    if (positionController) positionController.abort();
    positionController = new AbortController();
    try {
      const res = await fetch(positionBox.dataset.api + "?" + params, { signal: positionController.signal });
      if (!res.ok) return;
      const data = await res.json();

      const lignes = [];
      if (data.ensemble.pourcentage === null) {
        lignes.push(ligne("Pas encore assez de contributions pour vous situer."));
      } else {
        lignes.push(ligne("Vous gagnez plus que ", fort(data.ensemble.pourcentage + " %"),
          " des " + entier(data.ensemble.nombre) + " contributeurs."));
      }
      if (data.ville) lignes.push(ligneGroupe(data.ville, "À ", "Autres villes"));
      if (data.secteur) lignes.push(ligneGroupe(data.secteur, "Secteur ", "Autres secteurs"));
      if (!data.ville && !data.secteur && ville && secteur) {
        const aide = ligne("Choisissez une ville ou un secteur plus bas pour vous comparer à votre groupe.");
        aide.className = "position-aide";
        lignes.push(aide);
      }
      document.getElementById("position-lignes").replaceChildren(...lignes);

      const demo = document.getElementById("position-demo");
      demo.hidden = !data.nb_demo;
      demo.textContent = data.nb_demo
        ? "Ces chiffres incluent " + entier(data.nb_demo) + " contributions fictives de démonstration : " +
          "ils illustrent la méthode, pas la réalité du marché."
        : "";
      positionBox.hidden = false;
    } catch (e) {
      // Bloc facultatif : en cas d'erreur, on garde simplement l'affichage précédent.
    }
  }

  ["c-ville", "c-secteur"].forEach((id) => {
    const select = document.getElementById(id);
    if (select) select.addEventListener("change", updatePosition);
  });

  // ---------- Contribution aux statistiques (uniquement au clic) ----------
  const contribForm = document.getElementById("contribution");
  if (contribForm) {
    const contribMsg = contribForm.querySelector(".contrib-message");
    const contribBtn = contribForm.querySelector(".contrib-submit");

    const showContribError = (texte) => {
      contribMsg.textContent = texte;
      contribMsg.classList.add("is-error");
      contribMsg.hidden = false;
    };

    contribForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      // En mode « Net → Brut », le brut est celui calculé par le simulateur.
      const brut = state.mode === "net" ? (state.data ? state.data.resultat.brut : null) : lireMontant();
      if (brut === null || Number.isNaN(brut)) {
        showContribError("Saisissez d'abord un salaire brut dans le simulateur.");
        return;
      }
      if (!contribForm.elements.consentement.checked) {
        showContribError("Cochez la case de consentement pour ajouter votre salaire.");
        contribForm.elements.consentement.focus();
        return;
      }

      const corps = new FormData(contribForm);
      corps.set("brut", String(brut));
      corps.set("personnes", personnesInput.value || "0");
      contribBtn.disabled = true;

      try {
        const res = await fetch(contribForm.dataset.api, { method: "POST", body: corps });
        const data = await res.json();
        if (!res.ok) {
          showContribError(data.erreur);
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
        showContribError("Le serveur ne répond pas. Vérifiez qu'il est bien démarré.");
        contribBtn.disabled = false;
      }
    });
  }

  // ---------- Démarrage ----------
  const initialPressed = document.querySelector('[data-raise][aria-pressed="true"]');
  if (initialPressed) state.augmentation = Number(initialPressed.dataset.raise);
  setPersonnes(parseInt(personnesInput.value || "0", 10));
  paintSlider();
  update();
})();
