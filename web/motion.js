/* =============================================================================
   motion.js — moteur d'animation de la direction artistique « Encre & Signal ».

   Aucune dépendance obligatoire. Lenis (défilement inertiel) est vendu à côté
   et utilisé S'IL est présent ; sinon le défilement natif prend le relais et
   tout le reste fonctionne à l'identique.

   Règle de sûreté : le contenu est VISIBLE par défaut. Les états masqués ne
   s'appliquent que si la classe `js` est posée sur <html> (ce fichier), et un
   filet de sécurité révèle tout au bout de 3 s si l'observateur ne se déclenche
   jamais. Un échec de script ne peut donc pas rendre la page vide.

   API :
     data-reveal="up|fade|clip|mask|scale"   apparition à l'entrée dans l'écran
     data-delay="120"                        décalage en ms
     data-stagger[="70"]                     décale automatiquement les enfants
     data-split="lines|words"                titre découpé, révélé mot à mot
     data-parallax="0.18"                    translation liée au défilement
     data-count="4200" data-suffix="+"       compteur animé
     data-scene                              expose --p (0→1) pendant la traversée
     data-magnetic                           bouton attiré par le curseur
     data-spot                               carte éclairée sous le curseur
     data-tilt                               légère inclinaison 3D au survol
     window.Motion.scan(racine)              (ré)active le contenu injecté en JS
   ========================================================================== */
(function () {
  "use strict";

  var root = document.documentElement;
  root.classList.add("js");

  var reduce = false;
  try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  var coarse = false;
  try { coarse = window.matchMedia("(hover: none)").matches; } catch (e) {}

  /* ---------------------------------------------------------------------- */
  /* Défilement inertiel (Lenis si présent)                                  */
  /* ---------------------------------------------------------------------- */
  var lenis = null;
  if (!reduce && window.Lenis) {
    try {
      lenis = new window.Lenis({
        duration: 1.05,
        easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
        smoothWheel: true,
        syncTouch: false
      });
    } catch (e) { lenis = null; }
  }

  /* Une seule boucle rAF pour tout le fichier : jamais deux boucles concurrentes. */
  var tasks = [];
  function every(fn) { tasks.push(fn); }
  function frame(time) {
    if (lenis) { try { lenis.raf(time); } catch (e) {} }
    for (var i = 0; i < tasks.length; i++) tasks[i]();
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  /* Défilement vers une cible, en pixels absolus. Passer l'élément à Lenis
     donnait une position fausse dès qu'une image en cours de chargement
     décalait la page : on mesure nous-mêmes, juste avant de partir. */
  function versElement(cible, marge) {
    var y = cible.getBoundingClientRect().top + (window.pageYOffset || 0) - (marge || 0);
    y = Math.max(0, y);
    if (lenis && !reduce) lenis.scrollTo(y, { duration: 1.15 });
    else window.scrollTo({ top: y, behavior: reduce ? "auto" : "smooth" });
  }

  /* Ancres internes. */
  document.addEventListener("click", function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest('a[href^="#"]') : null;
    if (!a) return;
    var id = a.getAttribute("href");
    if (!id || id === "#") return;
    var cible;
    try { cible = document.querySelector(id); } catch (e) { return; }
    if (!cible) return;
    ev.preventDefault();
    versElement(cible, 92);   // hauteur de l'en-tête + une respiration
    if (history.replaceState) history.replaceState(null, "", id);
  });

  /* ---------------------------------------------------------------------- */
  /* Découpe typographique — mot à mot, en préservant les balises internes    */
  /* ---------------------------------------------------------------------- */
  function split(el) {
    if (el._split) return;
    el._split = true;
    var index = 0;

    (function walk(noeud) {
      var enfants = Array.prototype.slice.call(noeud.childNodes);
      enfants.forEach(function (n) {
        if (n.nodeType === 3) {
          var mots = String(n.nodeValue).split(/(\s+)/);
          var frag = document.createDocumentFragment();
          mots.forEach(function (mot) {
            if (!mot) return;
            if (/^\s+$/.test(mot)) { frag.appendChild(document.createTextNode(mot)); return; }
            var ext = document.createElement("span");
            ext.className = "m-w";
            var int = document.createElement("span");
            int.className = "m-i";
            int.style.setProperty("--i", index++);
            int.textContent = mot;
            ext.appendChild(int);
            frag.appendChild(ext);
          });
          noeud.replaceChild(frag, n);
        } else if (n.nodeType === 1 && !n.classList.contains("m-w")) {
          walk(n);
        }
      });
    })(el);

    el.style.setProperty("--n", index);
  }

  /* ---------------------------------------------------------------------- */
  /* Compteurs                                                               */
  /* ---------------------------------------------------------------------- */
  function formate(n, dec) {
    var s = dec ? n.toFixed(dec).replace(".", ",") : String(Math.round(n));
    var p = s.split(",");
    p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return p.join(",");
  }

  function compte(el) {
    if (el._compte) return;
    el._compte = true;
    var fin = parseFloat(el.getAttribute("data-count"));
    if (!isFinite(fin)) return;
    var dec = parseInt(el.getAttribute("data-dec") || "0", 10);
    var pre = el.getAttribute("data-prefix") || "";
    var suf = el.getAttribute("data-suffix") || "";
    var duree = parseInt(el.getAttribute("data-duration") || "1600", 10);
    if (reduce) { el.textContent = pre + formate(fin, dec) + suf; return; }
    var t0 = null;
    function pas(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / duree);
      var e = 1 - Math.pow(1 - p, 4);
      el.textContent = pre + formate(fin * e, dec) + suf;
      if (p < 1) requestAnimationFrame(pas);
    }
    requestAnimationFrame(pas);
  }

  /* ---------------------------------------------------------------------- */
  /* Apparition à l'entrée dans l'écran                                      */
  /* ---------------------------------------------------------------------- */
  var io = null;
  if ("IntersectionObserver" in window) {
    io = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (!e.isIntersecting) return;
        montre(e.target);
        io.unobserve(e.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
  }

  function montre(el) {
    el.classList.add("is-in");
    /* Les enfants d'un bloc décalé sont révélés avec lui : ils ne sont pas
       observés individuellement, c'est le parent qui donne le signal. */
    if (el.hasAttribute("data-stagger")) {
      for (var k = 0; k < el.children.length; k++) el.children[k].classList.add("is-in");
    }
    if (el.hasAttribute("data-count")) compte(el);
    var cs = el.querySelectorAll ? el.querySelectorAll("[data-count]") : [];
    for (var i = 0; i < cs.length; i++) compte(cs[i]);
  }

  function prepare(el) {
    if (el._prep) return;
    el._prep = true;

    if (el.hasAttribute("data-split") && !reduce) split(el);

    var d = el.getAttribute("data-delay");
    if (d) el.style.setProperty("--d", parseInt(d, 10) + "ms");

    if (el.hasAttribute("data-stagger")) {
      var pas = parseInt(el.getAttribute("data-stagger") || "70", 10) || 70;
      var enfants = el.children;
      for (var i = 0; i < enfants.length; i++) {
        enfants[i].style.setProperty("--d", (i * pas) + "ms");
        if (!enfants[i].hasAttribute("data-reveal")) enfants[i].setAttribute("data-reveal", "up");
        enfants[i]._prep = true;
      }
    }

    if (reduce || !io) { montre(el); return; }
    io.observe(el);
  }

  /* ---------------------------------------------------------------------- */
  /* Parallaxe et scènes liées au défilement                                 */
  /* ---------------------------------------------------------------------- */
  var paras = [], scenes = [];
  var vh = window.innerHeight || 800;

  function mesure() { vh = window.innerHeight || 800; }
  window.addEventListener("resize", mesure);

  function boucleScroll() {
    var i, r, p;
    for (i = 0; i < paras.length; i++) {
      var el = paras[i];
      r = el.getBoundingClientRect();
      if (r.bottom < -200 || r.top > vh + 200) continue;
      /* -1 (sous l'écran) → +1 (au-dessus) */
      p = (vh / 2 - (r.top + r.height / 2)) / (vh / 2 + r.height / 2);
      el.style.setProperty("--y", (p * el._vitesse * vh * 0.5).toFixed(2) + "px");
    }
    for (i = 0; i < scenes.length; i++) {
      var s = scenes[i];
      r = s.getBoundingClientRect();
      var total = r.height + vh;
      p = (vh - r.top) / total;
      p = p < 0 ? 0 : p > 1 ? 1 : p;
      s.style.setProperty("--p", p.toFixed(4));
    }
  }

  /* ---------------------------------------------------------------------- */
  /* Micro-interactions                                                      */
  /* ---------------------------------------------------------------------- */
  function magnetique(el) {
    if (coarse || reduce) return;
    var force = parseFloat(el.getAttribute("data-magnetic")) || 0.3;
    var cx = 0, cy = 0, tx = 0, ty = 0, actif = false;
    el.addEventListener("pointerenter", function () { actif = true; });
    el.addEventListener("pointermove", function (e) {
      var r = el.getBoundingClientRect();
      tx = (e.clientX - (r.left + r.width / 2)) * force;
      ty = (e.clientY - (r.top + r.height / 2)) * force;
    });
    el.addEventListener("pointerleave", function () { tx = 0; ty = 0; });
    every(function () {
      if (!actif && Math.abs(cx) < 0.05 && Math.abs(cy) < 0.05) return;
      cx += (tx - cx) * 0.16; cy += (ty - cy) * 0.16;
      el.style.setProperty("--mx", cx.toFixed(2) + "px");
      el.style.setProperty("--my", cy.toFixed(2) + "px");
      if (Math.abs(cx) < 0.05 && Math.abs(cy) < 0.05) actif = false;
    });
  }

  function projecteur(el) {
    if (coarse) return;
    el.addEventListener("pointermove", function (e) {
      var r = el.getBoundingClientRect();
      el.style.setProperty("--sx", ((e.clientX - r.left) / r.width * 100).toFixed(1) + "%");
      el.style.setProperty("--sy", ((e.clientY - r.top) / r.height * 100).toFixed(1) + "%");
    });
  }

  function inclinaison(el) {
    if (coarse || reduce) return;
    var max = parseFloat(el.getAttribute("data-tilt")) || 6;
    el.addEventListener("pointermove", function (e) {
      var r = el.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5;
      var y = (e.clientY - r.top) / r.height - 0.5;
      el.style.setProperty("--rx", (-y * max).toFixed(2) + "deg");
      el.style.setProperty("--ry", (x * max).toFixed(2) + "deg");
    });
    el.addEventListener("pointerleave", function () {
      el.style.setProperty("--rx", "0deg");
      el.style.setProperty("--ry", "0deg");
    });
  }

  /* ---------------------------------------------------------------------- */
  /* Balayage                                                                */
  /* ---------------------------------------------------------------------- */
  function scan(racine) {
    racine = racine || document;
    var q = function (s) { return Array.prototype.slice.call(racine.querySelectorAll(s)); };

    q("[data-reveal], [data-stagger], [data-split]").forEach(prepare);

    q("[data-parallax]").forEach(function (el) {
      if (el._para) return;
      el._para = true;
      el._vitesse = parseFloat(el.getAttribute("data-parallax")) || 0.1;
      if (!reduce) paras.push(el);
    });

    q("[data-scene]").forEach(function (el) {
      if (el._scene) return;
      el._scene = true;
      scenes.push(el);
    });

    q("[data-magnetic]").forEach(function (el) {
      if (el._mag) return; el._mag = true; magnetique(el);
    });
    q("[data-spot]").forEach(function (el) {
      if (el._spot) return; el._spot = true; projecteur(el);
    });
    q("[data-tilt]").forEach(function (el) {
      if (el._tilt) return; el._tilt = true; inclinaison(el);
    });

    boucleScroll();
  }

  /* ---------------------------------------------------------------------- */
  /* En-tête : condensation, masquage au défilement, barre de progression     */
  /* ---------------------------------------------------------------------- */
  function entete() {
    var nav = document.querySelector("[data-nav]");
    var barre = document.querySelector("[data-progress]");
    if (!nav && !barre) return;
    var dernier = 0;
    every(function () {
      var y = window.pageYOffset || document.documentElement.scrollTop || 0;
      if (nav) {
        nav.classList.toggle("is-stuck", y > 24);
        var ouvert = nav.classList.contains("is-open");
        nav.classList.toggle("is-hidden", !ouvert && y > 420 && y > dernier + 4);
      }
      if (barre) {
        var h = document.documentElement.scrollHeight - vh;
        barre.style.setProperty("--sp", h > 0 ? (y / h).toFixed(4) : "0");
      }
      dernier = y;
    });
  }

  /* ---------------------------------------------------------------------- */
  /* Démarrage                                                               */
  /* ---------------------------------------------------------------------- */
  function demarre() {
    mesure();
    scan(document);
    entete();
    every(boucleScroll);
    requestAnimationFrame(function () {
      root.classList.add("is-ready");
      /* Le rideau d'ouverture ne dure jamais plus que son animation. */
      setTimeout(function () { root.classList.add("is-loaded"); }, reduce ? 0 : 520);
    });
    /* Filet : si un observateur ne se déclenche pas (onglet en arrière-plan,
       navigateur exotique), tout devient visible au bout de 3 secondes. */
    setTimeout(function () {
      Array.prototype.forEach.call(
        document.querySelectorAll("[data-reveal]:not(.is-in)"),
        function (el) { if (el.getBoundingClientRect().top < vh * 1.4) montre(el); }
      );
    }, 3000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", demarre);
  } else {
    demarre();
  }

  window.Motion = {
    scan: scan,
    versElement: versElement,
    lenis: function () { return lenis; },
    reduce: reduce,
    stop: function () { if (lenis) lenis.stop(); else root.classList.add("m-lock"); },
    start: function () { if (lenis) lenis.start(); else root.classList.remove("m-lock"); }
  };
})();
