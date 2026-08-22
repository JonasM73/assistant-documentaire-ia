/* =========================================================================
   formulaire.js — envoi des demandes de devis, sans serveur.

   ÉTAPE À FAIRE UNE FOIS, EN 2 MINUTES :
   ---------------------------------------------------------------------
   1. Aller sur https://web3forms.com — saisir jonas@jonasmionnet.com,
      recevoir une clé d'accès par courriel. Gratuit, aucun compte à créer.
   2. Coller cette clé ci-dessous à la place de METTRE_LA_CLE_ICI.
   3. Redéployer. C'est tout.

   TANT QUE LA CLÉ N'EST PAS RENSEIGNÉE, le formulaire ne se contente pas
   d'échouer en silence : il ouvre le logiciel de messagerie du visiteur
   avec un message déjà rédigé. La demande arrive quand même — c'est juste
   moins fluide pour lui.
   ========================================================================= */
(function () {
  "use strict";

  var CLE = "METTRE_LA_CLE_ICI";
  var DESTINATAIRE = "jonas@jonasmionnet.com";
  var ENDPOINT = "https://api.web3forms.com/submit";

  var form = document.getElementById("devis-form");
  if (!form) return;
  var etat = document.getElementById("f-etat");
  var bouton = form.querySelector('button[type=submit]');
  var libelle = bouton ? bouton.querySelector("span") : null;
  var libelleInitial = libelle ? libelle.textContent : "";

  function dire(texte, classe) {
    if (!etat) return;
    etat.textContent = texte;
    etat.className = "form__etat" + (classe ? " " + classe : "");
  }

  function valeur(nom) {
    var el = form.elements[nom];
    return el && el.value ? el.value.trim() : "";
  }

  function emailValide(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
  }

  function corpsLisible() {
    var l = [
      "Entreprise : " + valeur("entreprise"),
      "Contact    : " + valeur("nom"),
      "Courriel   : " + valeur("email"),
      "Site       : " + (valeur("site") || "—"),
      "Demande    : " + valeur("objet"),
      "",
      "Ce que leurs équipes cherchent le plus souvent :",
      valeur("message") || "—"
    ];
    return l.join("\n");
  }

  function replieVersMessagerie() {
    var sujet = "Demande de devis — " + (valeur("entreprise") || "assistant documentaire");
    var url = "mailto:" + DESTINATAIRE
      + "?subject=" + encodeURIComponent(sujet)
      + "&body=" + encodeURIComponent("Bonjour Jonas,\n\n" + corpsLisible() + "\n\nMerci.");
    window.location.href = url;
    dire("Votre logiciel de messagerie s'ouvre avec le message déjà rédigé. "
      + "Il ne reste qu'à l'envoyer. S'il ne s'ouvre pas, écrivez directement à "
      + DESTINATAIRE + ".", "ok");
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();

    /* piège à robots : rempli = on fait semblant d'accepter et on s'arrête */
    if (valeur("_gotcha")) { dire("Merci, votre demande est bien partie.", "ok"); return; }

    if (!valeur("nom") || !valeur("entreprise")) {
      dire("Il me manque votre nom et celui de votre entreprise.", "ko");
      (form.elements.nom.value ? form.elements.entreprise : form.elements.nom).focus();
      return;
    }
    if (!emailValide(valeur("email"))) {
      dire("Cette adresse électronique ne semble pas valide — je ne pourrais pas vous répondre.", "ko");
      form.elements.email.focus();
      return;
    }

    if (CLE === "METTRE_LA_CLE_ICI") { replieVersMessagerie(); return; }

    if (bouton) { bouton.disabled = true; }
    if (libelle) { libelle.textContent = "Envoi en cours…"; }
    dire("Envoi en cours…");

    var charge = {
      access_key: CLE,
      subject: "Demande de devis — " + valeur("entreprise"),
      from_name: "Site Assistant·docs",
      replyto: valeur("email"),
      Entreprise: valeur("entreprise"),
      Contact: valeur("nom"),
      Courriel: valeur("email"),
      Site: valeur("site") || "—",
      Demande: valeur("objet"),
      Message: valeur("message") || "—"
    };

    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(charge)
    })
      .then(function (r) { return r.json().catch(function () { return { success: r.ok }; }); })
      .then(function (d) {
        if (d && d.success) {
          form.reset();
          dire("C'est envoyé. Je vous réponds sous 48 h, souvent bien avant.", "ok");
        } else {
          dire("L'envoi a échoué. Je bascule sur votre messagerie…", "ko");
          setTimeout(replieVersMessagerie, 900);
        }
      })
      .catch(function () {
        dire("L'envoi a échoué. Je bascule sur votre messagerie…", "ko");
        setTimeout(replieVersMessagerie, 900);
      })
      .then(function () {
        if (bouton) { bouton.disabled = false; }
        if (libelle) { libelle.textContent = libelleInitial; }
      });
  });
})();
