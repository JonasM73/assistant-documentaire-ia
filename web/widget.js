/* widget.js — Assistant documentaire, widget de chat embarquable.
 *
 * v3 — refonte visuelle. Le langage graphique (jetons de couleur, ombres,
 * typographie, animations) est IDENTIQUE à celui de gestion.html : mêmes
 * valeurs, mêmes noms de rôles. Les jetons sont préfixés `--da-` pour ne
 * jamais entrer en collision avec la feuille de style du site hôte.
 *
 * Principes de la refonte :
 *   - les surfaces se détachent par la LUMIÈRE (ombres en couches, liseré
 *     interne clair) et non par des contours gris ;
 *   - fonds travaillés : dégradés longs, halos radiaux, grain très léger ;
 *   - hiérarchie typographique franche (display serré / labels espacés) ;
 *   - micro-interactions douces, toutes désactivables (prefers-reduced-motion).
 *
 * API publique inchangée :
 *   DocAssistant.mount({ mode, apiBase, assistantName, clientName, examples, target })
 *   DocAssistant.unmountAll()
 */
(function () {
  "use strict";

  /* Grain fin, en SVG inline : aucune requête réseau, quelques centaines d'octets. */
  const GRAIN = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E\")";

  const CSS = `
  .da-root{
    /* ---- encre ---- */
    --da-ink:#0B1512; --da-ink-2:#14231D; --da-ink-3:#1E332B;
    --da-txt:#101E19; --da-txt-2:#4A5A53; --da-txt-3:#77877F;
    /* ---- surfaces ---- */
    --da-paper:#F6F7F4; --da-paper-2:#EFF2ED; --da-surface:#FFFFFF;
    /* ---- accent ---- */
    --da-a-700:#0A5443; --da-a-600:#0C6A54; --da-a-500:#0E7C62;
    --da-a-400:#13997A; --da-a-300:#3DB99B; --da-a-050:#E6F3EF;
    --da-marker:#C6F24E;
    --da-grad:linear-gradient(135deg,#0C6A54 0%,#13997A 100%);
    --da-grad-head:linear-gradient(150deg,#0B1512 0%,#14332A 52%,#0C6A54 145%);
    /* ---- ombres : c'est ce qui remplace les bordures ---- */
    --da-ring:inset 0 0 0 1px rgba(11,21,18,.055);
    --da-lift:inset 0 1px 0 rgba(255,255,255,.9);
    --da-sh-1:0 1px 2px rgba(11,21,18,.04), 0 2px 6px -2px rgba(11,21,18,.06);
    --da-sh-2:0 2px 4px rgba(11,21,18,.03), 0 10px 24px -12px rgba(11,21,18,.14);
    --da-sh-3:0 8px 18px -10px rgba(11,21,18,.18), 0 34px 70px -28px rgba(11,21,18,.34);
    --da-glow:0 6px 16px -8px rgba(12,106,84,.55);
    /* ---- typo ---- */
    --da-disp:'Bricolage Grotesque',ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
    --da-ui:'Inter',ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
    --da-mono:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
    /* ---- courbes ---- */
    --da-ease:cubic-bezier(.22,.75,.24,1);
  }
  .da-root, .da-root *{box-sizing:border-box;}
  .da-root{font-family:var(--da-ui);color:var(--da-txt);-webkit-font-smoothing:antialiased;}
  .da-root button{font:inherit;}

  /* ==================== lanceur ==================== */
  .da-launcher{
    position:fixed;right:26px;bottom:26px;z-index:2147483000;
    display:flex;align-items:center;gap:11px;
    background:var(--da-grad);color:#fff;border:none;cursor:pointer;
    border-radius:999px;padding:15px 24px 15px 19px;
    font-family:var(--da-disp);font-weight:700;font-size:15px;letter-spacing:-.008em;
    box-shadow:var(--da-glow), 0 18px 40px -16px rgba(11,21,18,.5),
               inset 0 1px 0 rgba(255,255,255,.22);
    transition:transform .22s var(--da-ease), box-shadow .22s var(--da-ease);
  }
  .da-launcher::before{
    content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
    background:radial-gradient(120% 160% at 20% -40%, rgba(255,255,255,.30), transparent 60%);
  }
  .da-launcher:hover{transform:translateY(-3px);
    box-shadow:0 10px 22px -8px rgba(12,106,84,.6), 0 28px 60px -20px rgba(11,21,18,.55),
               inset 0 1px 0 rgba(255,255,255,.28);}
  .da-launcher:active{transform:translateY(-1px);}
  .da-launcher:focus-visible{outline:none;box-shadow:var(--da-glow),0 0 0 4px rgba(19,153,122,.35);}
  .da-launcher svg{width:20px;height:20px;flex:none;position:relative;}
  .da-launcher span{position:relative;}
  .da-launcher .da-dot{position:absolute;top:10px;right:15px;width:8px;height:8px;
    background:var(--da-marker);border-radius:50%;
    animation:da-pulse 2.4s ease-out infinite;}
  @keyframes da-pulse{0%{box-shadow:0 0 0 0 rgba(198,242,78,.6);}
    70%{box-shadow:0 0 0 10px rgba(198,242,78,0);}100%{box-shadow:0 0 0 0 rgba(198,242,78,0);}}

  /* ==================== panneau ==================== */
  .da-panel{
    display:flex;flex-direction:column;background:var(--da-surface);
    overflow:hidden;isolation:isolate;
  }
  .da-panel.da-floating{
    position:fixed;right:26px;bottom:26px;z-index:2147483001;
    width:412px;height:min(640px, calc(100vh - 52px));
    border-radius:26px;box-shadow:var(--da-sh-3), var(--da-ring);
    transform-origin:bottom right;
    animation:da-pop .34s var(--da-ease);
  }
  .da-panel.da-inline{
    position:relative;width:100%;height:580px;border-radius:22px;
    box-shadow:var(--da-sh-3), var(--da-ring);
  }
  .da-panel.da-fullscreen{
    position:fixed;inset:0;z-index:2147483001;width:100%;height:100%;
    border-radius:0;box-shadow:none;
  }
  @keyframes da-pop{from{opacity:0;transform:scale(.94) translateY(16px);}to{opacity:1;transform:none;}}

  /* ==================== en-tête ==================== */
  .da-head{
    position:relative;display:flex;align-items:center;gap:13px;
    padding:19px 19px 17px;background:var(--da-grad-head);color:#fff;flex:none;
  }
  .da-head::before{content:"";position:absolute;inset:0;pointer-events:none;
    background:
      radial-gradient(340px 150px at 96% -40%, rgba(198,242,78,.20), transparent 68%),
      radial-gradient(300px 200px at 8% 130%, rgba(19,153,122,.34), transparent 70%);}
  .da-head::after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.16),transparent);}
  .da-head > *{position:relative;}
  .da-avatar{
    width:42px;height:42px;border-radius:14px;flex:none;position:relative;
    background:var(--da-grad);display:flex;align-items:center;justify-content:center;
    box-shadow:0 8px 18px -8px rgba(12,106,84,.9), inset 0 1px 0 rgba(255,255,255,.3);
  }
  .da-avatar svg{width:21px;height:21px;}
  .da-avatar .da-status{position:absolute;right:-3px;bottom:-3px;width:12px;height:12px;
    background:#4BDCA6;border-radius:50%;box-shadow:0 0 0 2.5px #142B24, 0 0 10px rgba(75,220,166,.8);}
  .da-head h3{margin:0;font-family:var(--da-disp);font-size:16px;font-weight:700;
    line-height:1.1;letter-spacing:-.018em;}
  .da-head p{margin:4px 0 0;font-size:11.5px;color:#9DB4AB;line-height:1.3;letter-spacing:.004em;}
  .da-head p b{color:#C8DAD3;font-weight:600;}
  .da-head .da-close{margin-left:auto;background:rgba(255,255,255,.08);
    border:none;color:#AEC2BA;cursor:pointer;font-size:19px;line-height:1;width:32px;height:32px;
    border-radius:11px;display:flex;align-items:center;justify-content:center;flex:none;
    transition:background .18s var(--da-ease), color .18s var(--da-ease), transform .18s var(--da-ease);}
  .da-head .da-close:hover{color:#fff;background:rgba(255,255,255,.18);transform:rotate(90deg);}
  .da-head .da-close:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(198,242,78,.45);}

  /* ==================== corps ==================== */
  .da-body{
    flex:1;overflow-y:auto;overflow-x:hidden;padding:20px 17px 8px;position:relative;
    background:
      radial-gradient(520px 260px at 100% 0%, rgba(19,153,122,.09), transparent 66%),
      radial-gradient(420px 300px at -10% 82%, rgba(198,242,78,.13), transparent 68%),
      linear-gradient(180deg,var(--da-paper) 0%,#FAFBF8 62%,var(--da-paper) 100%);
    scrollbar-width:thin;scrollbar-color:rgba(11,21,18,.16) transparent;
  }
  .da-body::before{content:"";position:absolute;inset:0;pointer-events:none;z-index:0;
    background-image:${GRAIN};opacity:.028;}
  .da-body > *{position:relative;z-index:1;}
  .da-body::-webkit-scrollbar{width:6px;}
  .da-body::-webkit-scrollbar-thumb{background:rgba(11,21,18,.14);border-radius:99px;}
  .da-body::-webkit-scrollbar-thumb:hover{background:rgba(11,21,18,.24);}

  /* ---- accueil ---- */
  .da-hello{display:flex;gap:10px;align-items:flex-start;margin:0 0 15px;
    animation:da-in .4s var(--da-ease) both;}
  .da-hello .da-mini{width:30px;height:30px;border-radius:11px;background:var(--da-grad);flex:none;
    display:flex;align-items:center;justify-content:center;
    box-shadow:0 5px 12px -5px rgba(12,106,84,.7), inset 0 1px 0 rgba(255,255,255,.25);}
  .da-hello .da-mini svg{width:15px;height:15px;}
  .da-hello .da-bulle{background:var(--da-surface);border-radius:6px 18px 18px 18px;
    padding:13px 15px;font-size:13.5px;line-height:1.55;color:var(--da-txt);max-width:90%;
    box-shadow:var(--da-sh-1), var(--da-ring), var(--da-lift);}
  .da-hello .da-bulle b{font-weight:650;color:var(--da-ink);}

  .da-suggest{font-family:var(--da-disp);font-size:10px;font-weight:700;
    letter-spacing:.13em;text-transform:uppercase;color:var(--da-txt-3);
    margin:0 0 9px 41px;animation:da-in .4s var(--da-ease) .05s both;}
  .da-examples{display:flex;flex-direction:column;gap:8px;margin:0 0 14px 41px;}
  .da-chip-q{display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left;
    background:var(--da-surface);border:none;border-radius:14px;padding:12px 14px;
    font-family:var(--da-ui);font-size:13px;color:var(--da-txt);cursor:pointer;line-height:1.4;
    box-shadow:var(--da-sh-1), var(--da-ring), var(--da-lift);
    transition:transform .2s var(--da-ease), box-shadow .2s var(--da-ease), color .2s var(--da-ease);
    animation:da-in .42s var(--da-ease) both;}
  .da-chip-q:nth-child(1){animation-delay:.06s;} .da-chip-q:nth-child(2){animation-delay:.12s;}
  .da-chip-q:nth-child(3){animation-delay:.18s;} .da-chip-q:nth-child(4){animation-delay:.24s;}
  .da-chip-q::after{content:"";width:15px;height:15px;flex:none;opacity:0;transform:translateX(-5px);
    background:currentColor;transition:opacity .2s var(--da-ease), transform .2s var(--da-ease);
    -webkit-mask:var(--da-arrow) center/contain no-repeat;mask:var(--da-arrow) center/contain no-repeat;}
  .da-chip-q{--da-arrow:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12h13'/%3E%3Cpath d='m12 5 7 7-7 7'/%3E%3C/svg%3E");}
  .da-chip-q:hover{transform:translateY(-2px);color:var(--da-a-600);
    box-shadow:var(--da-sh-2), inset 0 0 0 1px rgba(12,106,84,.16), var(--da-lift);}
  .da-chip-q:hover::after{opacity:1;transform:none;}
  .da-chip-q:focus-visible{outline:none;box-shadow:var(--da-sh-2),0 0 0 3px rgba(19,153,122,.28);}

  /* ==================== messages ==================== */
  .da-msg{margin:0 0 14px;display:flex;gap:9px;align-items:flex-end;
    animation:da-in .34s var(--da-ease) both;}
  @keyframes da-in{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  .da-msg.user{justify-content:flex-end;}
  .da-msg.bot .da-mini{width:28px;height:28px;border-radius:10px;background:var(--da-grad);flex:none;
    display:flex;align-items:center;justify-content:center;margin-bottom:2px;
    box-shadow:0 4px 10px -4px rgba(12,106,84,.65), inset 0 1px 0 rgba(255,255,255,.22);}
  .da-msg.bot .da-mini svg{width:14px;height:14px;}
  .da-bubble{max-width:87%;padding:12px 15px;border-radius:18px;font-size:14px;line-height:1.6;
    letter-spacing:-.002em;}
  .da-msg.user .da-bubble{background:var(--da-grad);color:#fff;border-bottom-right-radius:6px;
    box-shadow:var(--da-glow), inset 0 1px 0 rgba(255,255,255,.18);}
  .da-msg.bot .da-bubble{background:var(--da-surface);border-bottom-left-radius:6px;
    box-shadow:var(--da-sh-2), var(--da-ring), var(--da-lift);}
  .da-bubble p{margin:0 0 9px;} .da-bubble p:last-child{margin-bottom:0;}
  .da-bubble strong{font-weight:650;color:var(--da-ink);}
  .da-msg.user .da-bubble strong{color:#fff;}
  .da-bubble ul,.da-bubble ol{margin:8px 0;padding-left:19px;}
  .da-bubble li{margin:4px 0;}
  .da-bubble li::marker{color:var(--da-a-400);}
  .da-bubble a{color:var(--da-a-600);text-underline-offset:2px;}
  .da-bubble code{background:var(--da-paper-2);box-shadow:var(--da-ring);
    padding:1.5px 6px;border-radius:6px;font-family:var(--da-mono);font-size:12.5px;}
  .da-bubble.da-alert{background:#FFF9F0;box-shadow:var(--da-sh-1), inset 0 0 0 1px rgba(180,83,9,.18);
    color:#7C4A0B;}
  .da-bubble.da-alert b{color:#8A4B04;}

  /* ---- sources & extraits ---- */
  .da-sources{margin-top:11px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;}
  .da-src-chip{display:inline-flex;align-items:center;gap:6px;max-width:100%;
    font-family:var(--da-mono);font-size:10.5px;color:var(--da-a-700);letter-spacing:-.01em;
    background:var(--da-a-050);box-shadow:inset 0 0 0 1px rgba(12,106,84,.14);
    border-radius:999px;padding:4.5px 11px 4.5px 8px;font-weight:500;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .da-src-chip svg{width:11px;height:11px;flex:none;opacity:.75;}
  .da-extracts{margin-top:10px;padding-top:9px;position:relative;}
  .da-extracts::before{content:"";position:absolute;top:0;left:0;right:0;height:1px;
    background:linear-gradient(90deg,rgba(11,21,18,.10),rgba(11,21,18,.02) 70%,transparent);}
  .da-extracts summary{cursor:pointer;font-size:12px;color:var(--da-txt-2);font-weight:500;
    list-style:none;display:flex;align-items:center;gap:7px;transition:color .18s var(--da-ease);}
  .da-extracts summary::-webkit-details-marker{display:none;}
  .da-extracts summary::before{content:"";width:12px;height:12px;flex:none;background:var(--da-a-500);
    -webkit-mask:var(--da-caret) center/contain no-repeat;mask:var(--da-caret) center/contain no-repeat;
    transition:transform .22s var(--da-ease);}
  .da-extracts{--da-caret:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 6 6 6-6 6'/%3E%3C/svg%3E");}
  .da-extracts[open] summary::before{transform:rotate(90deg);}
  .da-extracts summary:hover{color:var(--da-ink);}
  .da-extracts pre{white-space:pre-wrap;word-break:break-word;font-size:11.5px;
    background:var(--da-paper);box-shadow:var(--da-ring);border-radius:12px;padding:12px;
    margin:9px 0 0;max-height:180px;overflow:auto;font-family:var(--da-mono);
    color:var(--da-txt-2);line-height:1.6;animation:da-in .26s var(--da-ease);}

  /* ---- indicateur de frappe ---- */
  .da-typing{display:inline-flex;gap:5px;padding:5px 2px;align-items:center;}
  .da-typing span{width:7px;height:7px;border-radius:50%;background:var(--da-a-400);
    opacity:.3;animation:da-blink 1.2s infinite;}
  .da-typing span:nth-child(2){animation-delay:.18s;} .da-typing span:nth-child(3){animation-delay:.36s;}
  @keyframes da-blink{0%,100%{opacity:.22;transform:translateY(0) scale(.9);}
    50%{opacity:1;transform:translateY(-3px) scale(1);}}

  /* ==================== pied ==================== */
  .da-foot{padding:13px 15px 10px;background:var(--da-surface);position:relative;flex:none;
    display:flex;gap:10px;align-items:flex-end;}
  .da-foot::before{content:"";position:absolute;top:0;left:15px;right:15px;height:1px;
    background:linear-gradient(90deg,transparent,rgba(11,21,18,.09),transparent);}
  .da-foot .da-field{flex:1;display:flex;align-items:flex-end;background:var(--da-paper);
    border-radius:16px;padding:4px 5px 4px 15px;box-shadow:var(--da-ring);
    transition:box-shadow .2s var(--da-ease), background .2s var(--da-ease);}
  .da-foot .da-field:focus-within{background:#fff;
    box-shadow:inset 0 0 0 1.5px var(--da-a-400), 0 0 0 4px rgba(19,153,122,.13);}
  .da-foot textarea{flex:1;resize:none;border:none;background:transparent;outline:none;
    padding:9px 0;font-family:var(--da-ui);font-size:14px;max-height:120px;
    line-height:1.45;color:var(--da-txt);}
  .da-foot textarea::placeholder{color:var(--da-txt-3);}
  .da-send{flex:none;width:38px;height:38px;border-radius:12px;border:none;cursor:pointer;
    background:var(--da-grad);color:#fff;display:flex;align-items:center;justify-content:center;
    margin:2px;box-shadow:var(--da-glow), inset 0 1px 0 rgba(255,255,255,.2);
    transition:transform .18s var(--da-ease), box-shadow .18s var(--da-ease), opacity .18s var(--da-ease);}
  .da-send:hover:not(:disabled){transform:translateY(-1.5px);
    box-shadow:0 10px 20px -8px rgba(12,106,84,.65), inset 0 1px 0 rgba(255,255,255,.24);}
  .da-send:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none;}
  .da-send:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(19,153,122,.35);}
  .da-send svg{width:17px;height:17px;}
  .da-poweredby{font-size:10px;color:var(--da-txt-3);text-align:center;padding:0 0 11px;
    background:var(--da-surface);letter-spacing:.06em;text-transform:uppercase;font-weight:600;flex:none;}
  .da-poweredby b{color:var(--da-txt-2);font-weight:700;}

  /* ==================== responsive ==================== */
  @media (max-width:520px){
    .da-panel.da-floating{width:calc(100vw - 20px);right:10px;bottom:10px;
      height:calc(100dvh - 84px);border-radius:22px;}
    .da-launcher{right:14px;bottom:14px;padding:13px 20px 13px 16px;font-size:14px;}
    .da-bubble{max-width:92%;}
    .da-examples,.da-suggest{margin-left:0;}
  }
  @media (max-width:380px){
    .da-launcher span:not(.da-dot){display:none;}
    .da-launcher{padding:14px;}
  }
  @media (prefers-reduced-motion:reduce){
    .da-root *,.da-root *::before,.da-root *::after{
      animation-duration:.001ms !important;animation-iteration-count:1 !important;
      transition-duration:.001ms !important;}
    .da-launcher:hover,.da-send:hover,.da-chip-q:hover{transform:none;}
  }`;

  const ICON_CHAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  const ICON_SPARK = '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v2M12 19v2M3 12h2M19 12h2"/><path d="M12 7l1.7 3.3L17 12l-3.3 1.7L12 17l-1.7-3.3L7 12l3.3-1.7z" fill="#fff" stroke="none"/></svg>';
  const ICON_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/></svg>';
  const ICON_FILE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>';

  const DEFAULT_EXAMPLES = [
    "Combien de semaines de vacances après 5 ans d'ancienneté ?",
    "La garantie du compresseur d'une thermopompe BOR-TP24 est de combien ?",
    "Quel est le prix net d'un chauffe-eau instantané au gaz ?",
    "Comment retourner un produit acheté il y a 45 jours ?"
  ];

  /* Messages d'erreur : toujours une phrase en français qui dit quoi faire. */
  const ERREURS = {
    reseau: "Impossible de joindre l'assistant. Vérifiez votre connexion, puis réessayez.",
    session: "Votre session a expiré. Rechargez la page pour ressaisir le mot de passe.",
    debit: "Trop de questions d'un coup. Patientez une minute avant de réessayer.",
    indispo: "L'assistant est momentanément indisponible. Réessayez dans quelques instants.",
    interne: "L'assistant n'a pas pu traiter votre question. Réessayez dans quelques instants.",
    vide: "L'assistant n'a rien renvoyé. Reformulez votre question."
  };

  let styleInjected = false;
  let mounted = [];

  // Le mot de passe est validé par l'écran d'accueil (index.html) et stocké ici.
  function getApiPassword() {
    try { return localStorage.getItem("da_api_password") || ""; }
    catch (e) { return ""; }          // navigation privée : stockage inaccessible
  }

  function forgetApiPassword() {
    try { localStorage.removeItem("da_api_password"); } catch (e) { /* ignoré */ }
  }

  function injectStyle() {
    if (styleInjected || document.getElementById("da-widget-style")) { styleInjected = true; return; }
    const s = document.createElement("style");
    s.id = "da-widget-style";
    s.textContent = CSS;
    document.head.appendChild(s);
    styleInjected = true;
  }

  function esc(t) {
    return String(t == null ? "" : t)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderMarkdown(text) {
    const inline = (s) => esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+?)`/g, "<code>$1</code>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    const blocks = String(text || "").split(/\n{2,}/);
    let html = "";
    for (const block of blocks) {
      const lines = block.split("\n");
      const isUl = lines.every(l => /^\s*[*-]\s+/.test(l));
      const isOl = lines.every(l => /^\s*\d+[.)]\s+/.test(l));
      if (isUl && lines.length) {
        html += "<ul>" + lines.map(l => "<li>" + inline(l.replace(/^\s*[*-]\s+/, "")) + "</li>").join("") + "</ul>";
      } else if (isOl && lines.length) {
        html += "<ol>" + lines.map(l => "<li>" + inline(l.replace(/^\s*\d+[.)]\s+/, "")) + "</li>").join("") + "</ol>";
      } else {
        html += "<p>" + lines.map(inline).join("<br>") + "</p>";
      }
    }
    return html;
  }

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  /* Corps JSON d'une réponse, quoi qu'il arrive (page HTML d'erreur, corps vide,
     proxy qui renvoie du texte) : le widget ne doit jamais planter sur un parse. */
  async function lireJson(reponse) {
    try { return await reponse.json(); }
    catch (e) { return null; }
  }

  function buildPanel(cfg, modeClass, withClose) {
    const panel = el("div", "da-panel " + modeClass);
    panel._history = [];

    // ---- en-tête ----
    const head = el("div", "da-head");
    const avatar = el("div", "da-avatar", ICON_SPARK + '<span class="da-status"></span>');
    head.appendChild(avatar);
    const titles = el("div");
    titles.appendChild(el("h3", null, esc(cfg.assistantName)));
    titles.appendChild(el("p", null,
      "En ligne · répond à partir des documents de <b>" + esc(cfg.clientName) + "</b>"));
    head.appendChild(titles);
    if (withClose) {
      const close = el("button", "da-close", "×");
      close.setAttribute("type", "button");
      close.setAttribute("aria-label", "Fermer l'assistant");
      close.onclick = () => cfg._onClose && cfg._onClose();
      head.appendChild(close);
    }
    panel.appendChild(head);

    // ---- corps ----
    const body = el("div", "da-body");
    body.setAttribute("role", "log");
    body.setAttribute("aria-live", "polite");
    const hello = el("div", "da-hello");
    hello.appendChild(el("div", "da-mini", ICON_SPARK));
    hello.appendChild(el("div", "da-bulle",
      "Bonjour ! Posez votre question sur les documents de <b>" + esc(cfg.clientName) +
      "</b>. Chaque réponse cite sa source."));
    body.appendChild(hello);
    const suggest = el("div", "da-suggest", "Pour démarrer");
    body.appendChild(suggest);
    const examples = el("div", "da-examples");
    (cfg.examples || []).forEach(q => {
      const b = el("button", "da-chip-q");
      b.setAttribute("type", "button");
      b.appendChild(el("span", null, esc(q)));
      b.onclick = () => { send(q); };
      examples.appendChild(b);
    });
    body.appendChild(examples);
    panel.appendChild(body);

    // ---- pied ----
    const foot = el("div", "da-foot");
    const field = el("div", "da-field");
    const ta = el("textarea");
    ta.rows = 1;
    ta.placeholder = "Écrivez votre question…";
    ta.setAttribute("aria-label", "Votre question");
    ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; });
    ta.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(ta.value); }
    });
    field.appendChild(ta);
    const send_btn = el("button", "da-send", ICON_SEND);
    send_btn.setAttribute("type", "button");
    send_btn.setAttribute("aria-label", "Envoyer");
    send_btn.onclick = () => send(ta.value);
    field.appendChild(send_btn);
    foot.appendChild(field);
    panel.appendChild(foot);

    panel.appendChild(el("div", "da-poweredby",
      "Réponses sourcées · <b>documents de l'entreprise</b>"));

    function addMsg(role, node) {
      if (examples.parentNode) { hello.remove(); suggest.remove(); examples.remove(); }
      const wrap = el("div", "da-msg " + role);
      if (role === "bot") wrap.appendChild(el("div", "da-mini", ICON_SPARK));
      const bubble = el("div", "da-bubble");
      bubble.appendChild(node);
      wrap.appendChild(bubble);
      body.appendChild(wrap);
      body.scrollTop = body.scrollHeight;
      return { wrap, bubble };
    }

    /* Remplace la bulle en cours par un message d'erreur lisible. */
    function afficherErreur(cible, message) {
      cible.bubble.innerHTML = "";
      cible.bubble.classList.add("da-alert");
      cible.bubble.appendChild(el("div", null, "<b>Oups.</b> " + esc(message)));
    }

    async function send(text) {
      text = (text || "").trim();
      if (!text || panel._busy) return;
      panel._busy = true;
      send_btn.disabled = true;
      ta.value = ""; ta.style.height = "auto";

      addMsg("user", el("span", null, esc(text)));
      const typing = el("div", "da-typing", "<span></span><span></span><span></span>");
      const t = addMsg("bot", typing);

      const historyToSend = panel._history.slice(-8);
      try {
        const r = await fetch(cfg.apiBase + "/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Password": getApiPassword()
          },
          body: JSON.stringify({ question: text, history: historyToSend })
        });

        if (r.status === 401) {
          forgetApiPassword();
          afficherErreur(t, ERREURS.session);
          return;
        }
        if (r.status === 429) { afficherErreur(t, ERREURS.debit); return; }

        const data = await lireJson(r);

        if (!r.ok) {
          // Le serveur rédige déjà ses messages en français ; on retombe sur un
          // texte générique s'il n'a rien pu renvoyer (proxy, coupure…).
          const msg = (data && (data.error || (typeof data.detail === "string" && data.detail)))
            || (r.status === 503 ? ERREURS.indispo : ERREURS.interne);
          afficherErreur(t, msg);
          return;
        }
        if (!data) { afficherErreur(t, ERREURS.interne); return; }
        if (data.error) { afficherErreur(t, data.error); return; }
        if (!data.answer) { afficherErreur(t, ERREURS.vide); return; }

        t.bubble.innerHTML = "";
        t.bubble.appendChild(el("div", null, renderMarkdown(data.answer)));
        panel._history.push({ role: "user", content: text });
        panel._history.push({ role: "assistant", content: data.answer });

        if (Array.isArray(data.sources) && data.sources.length) {
          const srow = el("div", "da-sources");
          data.sources.forEach(s => {
            const chip = el("span", "da-src-chip", ICON_FILE + esc(s));
            chip.title = String(s);
            srow.appendChild(chip);
          });
          t.bubble.appendChild(srow);
        }
        if (Array.isArray(data.chunks) && data.chunks.length) {
          const det = el("details", "da-extracts");
          det.appendChild(el("summary", null, "Voir les " + data.chunks.length + " extraits utilisés"));
          const pre = el("pre");
          pre.textContent = data.chunks
            .map(c => "[" + (c && c.source || "?") + "]\n" + (c && c.text || "")).join("\n\n———\n\n");
          det.appendChild(pre);
          t.bubble.appendChild(det);
        }
      } catch (e) {
        afficherErreur(t, ERREURS.reseau);
      } finally {
        body.scrollTop = body.scrollHeight;
        panel._busy = false;
        send_btn.disabled = false;
        ta.focus();
      }
    }

    panel._send = send;
    return panel;
  }

  function mount(options) {
    injectStyle();
    const cfg = Object.assign({
      mode: "floating",
      apiBase: "",
      assistantName: "Assistant documentaire",
      clientName: "Boréale Équipement",
      examples: DEFAULT_EXAMPLES,
      target: null
    }, options || {});

    const root = el("div", "da-root");
    let controller = { destroy: () => root.remove() };

    if (cfg.mode === "inline") {
      const panel = buildPanel(cfg, "da-inline", false);
      root.appendChild(panel);
      (cfg.target || document.body).appendChild(root);
    } else if (cfg.mode === "fullscreen") {
      cfg._onClose = () => controller.destroy();
      const panel = buildPanel(cfg, "da-fullscreen", true);
      root.appendChild(panel);
      document.body.appendChild(root);
    } else {
      const launcher = el("button", "da-launcher",
        ICON_CHAT + "<span>Une question ?</span><span class='da-dot'></span>");
      launcher.setAttribute("type", "button");
      launcher.setAttribute("aria-label", "Ouvrir l'assistant documentaire");
      let panel = null;
      launcher.onclick = () => {
        if (panel) return;
        cfg._onClose = () => { panel.remove(); panel = null; launcher.style.display = ""; };
        panel = buildPanel(cfg, "da-floating", true);
        root.appendChild(panel);
        launcher.style.display = "none";
        const ta = panel.querySelector("textarea"); if (ta) ta.focus();
      };
      root.appendChild(launcher);
      document.body.appendChild(root);
    }

    mounted.push(controller);
    return controller;
  }

  function unmountAll() {
    mounted.forEach(c => c.destroy());
    mounted = [];
  }

  window.DocAssistant = { mount, unmountAll };
})();
