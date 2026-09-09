/* widget.js — Assistant documentaire, widget de chat embarquable.
 *
 * v4 — direction artistique « Encre & Signal », déclinaison CLAIRE. Le langage
 * graphique est celui de web/da.css : papier chaud, signal émeraude, typographie
 * très serrée, surfaces posées par la lumière plutôt que cernées par des
 * bordures. Seul l'en-tête reste en émeraude profonde : c'est lui qui donne
 * l'identité, le reste respire.
 * Les jetons restent préfixés `--da-` : le widget ne peut jamais entrer en
 * collision avec la feuille de style du site hôte, ni en hériter.
 *
 * Principes :
 *   - le panneau est une SURFACE POSÉE : ombres en couches, liseré interne,
 *     halos de couleur, grain — aucun contour gris ;
 *   - la conversation se lit comme du texte, pas comme une pile de boîtes :
 *     seule la question de l'utilisateur est dans une pastille pleine ;
 *   - chaque élément entre en scène (panneau, message, extrait, source) et
 *     sort de scène ; tout est neutralisé par prefers-reduced-motion.
 *
 * API publique inchangée :
 *   DocAssistant.mount({ mode, apiBase, assistantName, clientName, examples, target })
 *   DocAssistant.unmountAll()
 */
(function () {
  "use strict";

  /* Grain fin, en SVG inline : aucune requête réseau, quelques centaines d'octets. */
  const GRAIN = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.78' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='180' height='180' filter='url(%23n)'/%3E%3C/svg%3E\")";

  const CSS = `
  .da-root{
    /* ---- papier ---- */
    --da-paper-0:#FFFFFF; --da-paper:#FCFBF7; --da-paper-2:#F7F5EF;
    --da-paper-3:#F1EEE6; --da-paper-4:#E8E4DA;
    /* ---- texte ---- */
    --da-txt:#0B1512; --da-txt-2:#3A4941; --da-txt-3:#5F6F67; --da-txt-4:#8B968F;
    /* ---- filets ---- */
    --da-rule:rgba(11,21,18,.14); --da-rule-2:rgba(11,21,18,.065);
    /* ---- signal ---- */
    --da-a-700:#075E44; --da-a-600:#0B7A58; --da-a-500:#10B981;
    --da-a-400:#0B7A58; --da-a-300:#0A6B4E; --da-a-050:#E9F6F1;
    --da-marker:#C6F24E; --da-coral:#C24E1E;
    --da-grad:linear-gradient(135deg,#0B7A58 0%,#10B981 100%);
    --da-grad-head:linear-gradient(150deg,#062E22 0%,#0B7A58 62%,#10B981 165%);
    /* ---- ombres : c'est ce qui remplace les bordures ---- */
    --da-ring:inset 0 0 0 1px rgba(11,21,18,.09);
    --da-sh-2:0 2px 6px rgba(11,21,18,.05), 0 18px 34px -20px rgba(11,21,18,.3);
    --da-sh-3:0 8px 20px -14px rgba(11,21,18,.22), 0 44px 84px -44px rgba(11,21,18,.5);
    --da-glow:0 10px 28px -12px rgba(16,185,129,.55);
    /* ---- typo ---- */
    --da-disp:'Bricolage Grotesque',ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
    --da-ui:'Inter',ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
    --da-mono:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
    --da-micro:700 9.5px/1.4 var(--da-mono);
    /* ---- courbes ---- */
    --da-e:cubic-bezier(.16,1,.3,1);
  }
  .da-root, .da-root *{box-sizing:border-box;}
  .da-root{font-family:var(--da-ui);color:var(--da-txt);-webkit-font-smoothing:antialiased;}
  .da-root button{font:inherit;}

  /* ==================== lanceur ==================== */
  .da-launcher{
    position:fixed;right:26px;bottom:26px;z-index:2147483000;
    display:flex;align-items:center;gap:12px;
    background:var(--da-grad);color:#FFFFFF;border:none;cursor:pointer;
    border-radius:999px;padding:15px 26px 15px 20px;overflow:visible;
    font-family:var(--da-disp);font-weight:700;font-size:15px;letter-spacing:-.02em;
    box-shadow:var(--da-glow), 0 22px 46px -22px rgba(11,21,18,.5),
               inset 0 1px 0 rgba(255,255,255,.28);
    animation:da-launch .6s var(--da-e) both;
    transition:transform .3s var(--da-e), box-shadow .3s var(--da-e);
  }
  @keyframes da-launch{from{opacity:0;transform:translateY(20px) scale(.9);}to{opacity:1;transform:none;}}
  .da-launcher::before{
    content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
    background:radial-gradient(120% 160% at 22% -40%, rgba(255,255,255,.4), transparent 62%);
  }
  /* halo qui respire, derrière la pastille */
  .da-launcher::after{
    content:"";position:absolute;inset:-3px;border-radius:inherit;z-index:-1;
    background:var(--da-grad);filter:blur(14px);opacity:.5;
    animation:da-halo 3.4s ease-in-out infinite;
  }
  @keyframes da-halo{0%,100%{opacity:.34;transform:scale(1);}50%{opacity:.62;transform:scale(1.06);}}
  .da-launcher:hover{transform:translateY(-4px) scale(1.03);
    box-shadow:0 16px 34px -14px rgba(16,185,129,.7), 0 34px 70px -26px rgba(11,21,18,.55),
               inset 0 1px 0 rgba(255,255,255,.34);}
  .da-launcher:active{transform:translateY(-1px) scale(1);}
  .da-launcher:focus-visible{outline:none;
    box-shadow:var(--da-glow),0 0 0 4px rgba(16,185,129,.35);}
  .da-launcher svg{width:20px;height:20px;flex:none;position:relative;}
  .da-launcher span{position:relative;}
  .da-launcher .da-dot{position:absolute;top:9px;right:13px;width:9px;height:9px;
    background:var(--da-marker);border-radius:50%;
    box-shadow:0 0 0 2px rgba(7,94,68,.5);
    animation:da-pulse 2.4s ease-out infinite;}
  @keyframes da-pulse{0%{box-shadow:0 0 0 0 rgba(198,242,78,.75),0 0 0 2px rgba(7,94,68,.5);}
    70%{box-shadow:0 0 0 12px rgba(198,242,78,0),0 0 0 2px rgba(7,94,68,.5);}
    100%{box-shadow:0 0 0 0 rgba(198,242,78,0),0 0 0 2px rgba(7,94,68,.5);}}

  /* ==================== panneau ==================== */
  .da-panel{
    display:flex;flex-direction:column;background:var(--da-paper);
    overflow:hidden;isolation:isolate;
  }
  .da-panel.da-floating{
    position:fixed;right:26px;bottom:26px;z-index:2147483001;
    width:420px;height:min(660px, calc(100vh - 52px));
    border-radius:28px;box-shadow:var(--da-sh-3), var(--da-ring);
    transform-origin:bottom right;
    animation:da-pop .5s var(--da-e);
  }
  .da-panel.da-inline{
    position:relative;width:100%;height:600px;border-radius:24px;
    box-shadow:var(--da-sh-3), var(--da-ring);
    animation:da-rise .7s var(--da-e);
  }
  .da-panel.da-fullscreen{
    position:fixed;inset:0;z-index:2147483001;width:100%;height:100%;
    border-radius:0;box-shadow:none;animation:da-fade .45s var(--da-e);
  }
  .da-panel.da-out{animation:da-close .28s cubic-bezier(.5,0,.75,0) forwards;pointer-events:none;}
  @keyframes da-pop{from{opacity:0;transform:scale(.93) translateY(22px);}to{opacity:1;transform:none;}}
  @keyframes da-rise{from{opacity:0;transform:translateY(26px);}to{opacity:1;transform:none;}}
  @keyframes da-fade{from{opacity:0;}to{opacity:1;}}
  @keyframes da-close{to{opacity:0;transform:scale(.95) translateY(14px);}}

  /* ==================== en-tête ==================== */
  .da-head{
    position:relative;display:flex;align-items:center;gap:14px;
    padding:20px 20px 18px;background:var(--da-grad-head);color:#FFFFFF;flex:none;
  }
  .da-head::before{content:"";position:absolute;inset:0;pointer-events:none;
    background:
      radial-gradient(360px 160px at 96% -46%, rgba(198,242,78,.28), transparent 68%),
      radial-gradient(320px 220px at 6% 136%, rgba(6,46,34,.5), transparent 70%);}
  .da-head::after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.26),transparent);}
  .da-head > *{position:relative;}
  .da-avatar{
    width:44px;height:44px;border-radius:15px;flex:none;position:relative;
    background:rgba(255,255,255,.16);display:flex;align-items:center;justify-content:center;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,.26), inset 0 1px 0 rgba(255,255,255,.4);
  }
  .da-avatar svg{width:21px;height:21px;}
  .da-avatar .da-status{position:absolute;right:-3px;bottom:-3px;width:12px;height:12px;
    background:#C6F24E;border-radius:50%;box-shadow:0 0 0 2.5px #0B7A58, 0 0 12px rgba(198,242,78,.8);}
  .da-head h3{margin:0;font-family:var(--da-disp);font-size:16.5px;font-weight:800;
    line-height:1.1;letter-spacing:-.035em;color:#FFFFFF;}
  .da-head p{margin:5px 0 0;font-size:11px;color:rgba(255,255,255,.72);line-height:1.35;
    font-family:var(--da-mono);letter-spacing:.05em;}
  .da-head p b{color:#DDF5A8;font-weight:600;}
  .da-head .da-close{margin-left:auto;background:rgba(255,255,255,.14);
    border:none;color:rgba(255,255,255,.85);cursor:pointer;font-size:19px;line-height:1;
    width:34px;height:34px;border-radius:12px;display:flex;align-items:center;
    justify-content:center;flex:none;
    transition:background .25s var(--da-e), color .25s var(--da-e), transform .35s var(--da-e);}
  .da-head .da-close:hover{color:#fff;background:rgba(255,255,255,.26);transform:rotate(90deg);}
  .da-head .da-close:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(198,242,78,.6);}

  /* ==================== corps ==================== */
  .da-body{
    flex:1;overflow-y:auto;overflow-x:hidden;padding:24px 20px 12px;position:relative;
    background:
      radial-gradient(480px 320px at 106% -8%, rgba(16,185,129,.13), transparent 64%),
      radial-gradient(400px 300px at -14% 34%, rgba(185,228,60,.14), transparent 64%),
      radial-gradient(440px 360px at 62% 110%, rgba(255,142,92,.09), transparent 66%),
      linear-gradient(180deg,#FDFCF9 0%,var(--da-paper) 58%,var(--da-paper-2) 100%);
    scrollbar-width:thin;scrollbar-color:rgba(11,21,18,.2) transparent;
  }
  .da-body::before{content:"";position:absolute;inset:0;pointer-events:none;z-index:0;
    background-image:${GRAIN};opacity:.045;mix-blend-mode:multiply;}
  .da-body > *{position:relative;z-index:1;}
  .da-body::-webkit-scrollbar{width:7px;}
  .da-body::-webkit-scrollbar-thumb{background:rgba(11,21,18,.16);border-radius:99px;}
  .da-body::-webkit-scrollbar-thumb:hover{background:rgba(11,21,18,.3);}

  /* ---- accueil : du texte posé sur le papier, aucune bulle ---- */
  .da-hello{display:flex;gap:12px;align-items:flex-start;margin:0 0 26px;
    animation:da-in .5s var(--da-e) both;}
  .da-hello .da-mini{width:28px;height:28px;border-radius:10px;background:var(--da-grad);flex:none;
    display:flex;align-items:center;justify-content:center;margin-top:2px;
    box-shadow:0 8px 16px -8px rgba(16,185,129,.9);}
  .da-hello .da-mini svg{width:13px;height:13px;}
  .da-hello .da-bulle{font-family:var(--da-disp);font-weight:700;font-size:19px;line-height:1.28;
    letter-spacing:-.038em;color:var(--da-txt);max-width:96%;}
  .da-hello .da-bulle b{font-weight:700;color:var(--da-a-400);}

  .da-suggest{font:var(--da-micro);letter-spacing:.2em;text-transform:uppercase;
    color:var(--da-txt-4);margin:0 0 6px;display:flex;align-items:center;gap:11px;
    animation:da-in .5s var(--da-e) .06s both;}
  .da-suggest::before{content:"";width:20px;height:1px;background:var(--da-a-500);flex:none;}
  /* Suggestions : des lignes séparées par un filet, jamais des cartes. */
  .da-examples{display:flex;flex-direction:column;margin:0 0 14px;}
  .da-chip-q{display:flex;align-items:center;justify-content:space-between;gap:14px;text-align:left;
    background:none;border:none;padding:14px 2px;position:relative;
    font-family:var(--da-ui);font-size:13.5px;color:var(--da-txt-2);cursor:pointer;line-height:1.45;
    letter-spacing:-.014em;transition:color .25s var(--da-e), padding-left .25s var(--da-e);
    animation:da-in .5s var(--da-e) both;}
  .da-chip-q::before{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;
    background:linear-gradient(90deg,var(--da-rule-2),transparent 84%);}
  .da-chip-q:last-child::before{display:none;}
  .da-chip-q:nth-child(1){animation-delay:.08s;} .da-chip-q:nth-child(2){animation-delay:.14s;}
  .da-chip-q:nth-child(3){animation-delay:.2s;} .da-chip-q:nth-child(4){animation-delay:.26s;}
  .da-chip-q::after{content:"";width:15px;height:15px;flex:none;opacity:.3;transform:translateX(-5px);
    background:currentColor;transition:opacity .25s var(--da-e), transform .25s var(--da-e);
    -webkit-mask:var(--da-arrow) center/contain no-repeat;mask:var(--da-arrow) center/contain no-repeat;}
  .da-chip-q{--da-arrow:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12h13'/%3E%3Cpath d='m12 5 7 7-7 7'/%3E%3C/svg%3E");}
  .da-chip-q:hover{color:var(--da-a-300);padding-left:9px;}
  .da-chip-q:hover::after{opacity:1;transform:none;}
  .da-chip-q:focus-visible{outline:2px solid var(--da-a-500);outline-offset:3px;border-radius:3px;}

  /* ==================== messages ==================== */
  /* Aligné en HAUT : sans bulle, une réponse longue laisserait sinon l'avatar
     flotter tout en bas, à côté de rien. */
  .da-msg{margin:0 0 22px;display:flex;gap:12px;align-items:flex-start;
    animation:da-in .42s var(--da-e) both;}
  @keyframes da-in{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
  .da-msg.user{justify-content:flex-end;align-items:flex-end;}
  .da-msg.bot .da-mini{width:28px;height:28px;border-radius:10px;background:var(--da-grad);flex:none;
    display:flex;align-items:center;justify-content:center;margin-top:1px;
    box-shadow:0 8px 16px -8px rgba(16,185,129,.9);}
  .da-msg.bot .da-mini svg{width:13px;height:13px;}
  /* Chaque tour de parole est une SURFACE : la question en pastille pleine, la
     réponse sur une carte blanche. C'est ce qui fait qu'on suit une
     conversation d'un coup d'œil, sans chercher où commence quoi. */
  .da-bubble{max-width:88%;font-size:14.5px;line-height:1.68;letter-spacing:-.01em;}
  .da-msg.user .da-bubble{background:var(--da-grad);color:#FFFFFF;padding:12px 17px;
    border-radius:18px;border-bottom-right-radius:6px;max-width:84%;font-weight:500;
    box-shadow:var(--da-glow), inset 0 1px 0 rgba(255,255,255,.24);}
  .da-msg.bot .da-bubble{padding:15px 18px 16px;color:var(--da-txt-2);
    background:var(--da-paper-0);border-radius:18px;border-bottom-left-radius:6px;
    box-shadow:inset 0 0 0 1px var(--da-rule-2),
               0 1px 2px rgba(11,21,18,.04), 0 12px 24px -18px rgba(11,21,18,.3);}
  .da-bubble p{margin:0 0 10px;} .da-bubble p:last-child{margin-bottom:0;}
  .da-bubble .da-h{font-family:var(--da-disp);font-weight:800;font-size:15.5px;
    letter-spacing:-.035em;line-height:1.25;color:var(--da-txt);margin:18px 0 9px;}
  .da-bubble > div > .da-h:first-child{margin-top:0;}
  .da-bubble .da-hr{border:0;height:1px;margin:16px 0;
    background:linear-gradient(90deg,var(--da-rule),transparent 70%);}
  .da-bubble strong{font-weight:650;color:var(--da-txt);}
  .da-msg.user .da-bubble strong{color:#FFFFFF;}
  .da-bubble ul,.da-bubble ol{margin:9px 0;padding-left:19px;}
  .da-bubble li{margin:5px 0;}
  .da-bubble li::marker{color:var(--da-a-500);}
  .da-bubble a{color:var(--da-a-600);text-underline-offset:2px;}
  .da-bubble code{background:rgba(11,21,18,.055);padding:2px 7px;border-radius:6px;
    font-family:var(--da-mono);font-size:12.5px;color:var(--da-a-700);}
  /* Alerte : une nappe de couleur qui s'éteint, pas un cadre. */
  .da-msg.bot .da-bubble.da-alert{color:#7C4A0B;padding:14px 16px;border-radius:16px;
    background:linear-gradient(160deg,#FDEBE0,#FBF4EF);
    box-shadow:inset 0 0 0 1px rgba(194,78,30,.2);}
  .da-bubble.da-alert b{color:var(--da-coral);font-weight:700;}

  /* ---- sources & extraits ---- */
  /* Les sources sont des PASTILLES : un document cité doit se voir comme une
     étiquette qu'on pourrait attraper, pas comme une ligne de texte gris. */
  .da-sources{margin-top:15px;padding-top:13px;display:flex;flex-wrap:wrap;
    gap:6px;align-items:center;position:relative;}
  .da-sources::before{content:"";position:absolute;top:0;left:0;right:0;height:1px;
    background:linear-gradient(90deg,var(--da-rule-2),transparent 84%);}
  .da-src-chip{display:inline-flex;align-items:center;gap:6px;max-width:100%;
    padding:5px 11px 5px 9px;border-radius:999px;
    background:var(--da-a-050);color:var(--da-a-700);
    box-shadow:inset 0 0 0 1px rgba(11,122,88,.14);
    font-family:var(--da-mono);font-size:10px;letter-spacing:.03em;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
    transition:background .25s var(--da-e), box-shadow .25s var(--da-e);}
  .da-src-chip:hover{background:#DCF0E8;box-shadow:inset 0 0 0 1px rgba(11,122,88,.3);}
  .da-src-chip svg{width:11px;height:11px;flex:none;opacity:.65;}

  .da-extracts{margin-top:11px;position:relative;}
  .da-extracts summary{cursor:pointer;list-style:none;display:inline-flex;align-items:center;
    gap:8px;padding:7px 13px 7px 11px;border-radius:999px;
    background:rgba(11,21,18,.045);color:var(--da-txt-3);
    font-size:11.5px;font-weight:500;letter-spacing:-.005em;
    transition:background .2s var(--da-e), color .2s var(--da-e);}
  .da-extracts summary::-webkit-details-marker{display:none;}
  .da-extracts summary::before{content:"";width:11px;height:11px;flex:none;background:currentColor;
    -webkit-mask:var(--da-caret) center/contain no-repeat;mask:var(--da-caret) center/contain no-repeat;
    transition:transform .25s var(--da-e);}
  .da-extracts{--da-caret:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 6 6 6-6 6'/%3E%3C/svg%3E");}
  .da-extracts[open] summary::before{transform:rotate(90deg);}
  .da-extracts summary:hover{background:rgba(11,21,18,.075);color:var(--da-txt);}
  /* Un extrait = un bloc, avec le nom de son document en tête. Le gros pavé
     unique séparé par des tirets était illisible. */
  .da-extraits{margin-top:10px;display:flex;flex-direction:column;gap:8px;
    animation:da-in .3s var(--da-e);}
  .da-extrait{background:var(--da-paper-2);border-radius:12px;padding:11px 13px;
    box-shadow:inset 0 0 0 1px var(--da-rule-2);}
  .da-extrait b{display:block;font-family:var(--da-mono);font-size:9.5px;font-weight:700;
    letter-spacing:.16em;text-transform:uppercase;color:var(--da-a-600);margin-bottom:7px;}
  .da-extrait p{margin:0;font-size:11.5px;line-height:1.7;color:var(--da-txt-3);
    white-space:pre-wrap;word-break:break-word;max-height:160px;overflow:auto;}

  /* ---- indicateur de frappe ---- */
  .da-typing{display:inline-flex;gap:6px;padding:6px 2px;align-items:center;}
  .da-typing span{width:7px;height:7px;border-radius:50%;background:var(--da-a-500);
    opacity:.3;animation:da-blink 1.2s infinite;}
  .da-typing span:nth-child(2){animation-delay:.18s;} .da-typing span:nth-child(3){animation-delay:.36s;}
  @keyframes da-blink{0%,100%{opacity:.22;transform:translateY(0) scale(.85);}
    50%{opacity:1;transform:translateY(-4px) scale(1);}}

  /* ==================== pied ==================== */
  /* Champ souligné, pas encadré : la même règle que les filtres de gestion.html. */
  .da-foot{padding:15px 20px 11px;background:var(--da-paper-2);position:relative;flex:none;
    display:flex;gap:13px;align-items:flex-end;}
  .da-foot::before{content:"";position:absolute;top:0;left:0;right:0;height:1px;
    background:linear-gradient(90deg,transparent,var(--da-rule) 18%,var(--da-rule) 82%,transparent);}
  .da-foot .da-field{flex:1;display:flex;align-items:flex-end;gap:8px;
    border-bottom:1px solid var(--da-rule);padding:0 0 3px;
    transition:border-color .25s var(--da-e);}
  .da-foot .da-field:focus-within{border-bottom-color:var(--da-a-500);border-bottom-width:1.5px;}
  .da-foot textarea{flex:1;resize:none;border:none;background:transparent;outline:none;
    padding:10px 0;font-family:var(--da-ui);font-size:14.5px;max-height:120px;
    line-height:1.5;color:var(--da-txt);letter-spacing:-.014em;}
  .da-foot textarea::placeholder{color:var(--da-txt-4);}
  .da-send{flex:none;width:38px;height:38px;border-radius:50%;border:none;cursor:pointer;
    background:var(--da-grad);color:#FFFFFF;display:flex;align-items:center;justify-content:center;
    margin:0 0 3px;box-shadow:var(--da-glow);
    transition:transform .25s var(--da-e), box-shadow .25s var(--da-e), opacity .25s var(--da-e);}
  .da-send:hover:not(:disabled){transform:translateY(-2px) scale(1.06);
    box-shadow:0 14px 26px -10px rgba(16,185,129,.7);}
  .da-send:disabled{opacity:.3;cursor:not-allowed;transform:none;box-shadow:none;}
  .da-send:focus-visible{outline:2px solid var(--da-a-500);outline-offset:3px;}
  .da-send svg{width:15px;height:15px;}
  .da-poweredby{font:var(--da-micro);color:var(--da-txt-4);text-align:center;
    padding:0 0 13px;background:var(--da-paper-2);letter-spacing:.2em;text-transform:uppercase;
    flex:none;}
  .da-poweredby b{color:var(--da-txt-3);font-weight:700;}

  /* ==================== responsive ==================== */
  @media (max-width:520px){
    .da-panel.da-floating{width:calc(100vw - 20px);right:10px;bottom:10px;
      height:calc(100dvh - 84px);border-radius:24px;}
    .da-launcher{right:14px;bottom:14px;padding:14px 22px 14px 17px;font-size:14px;}
    .da-bubble{max-width:92%;}
    .da-examples,.da-suggest{margin-left:0;}
    .da-hello .da-bulle{font-size:17px;}
  }
  @media (max-width:380px){
    .da-launcher span:not(.da-dot){display:none;}
    .da-launcher{padding:15px;}
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

  /* Exemples neutres : ils s'affichent tant que l'intégration ne fournit pas
     d'`examples` propres au client. Aucune référence à un secteur, aucun prix. */
  const DEFAULT_EXAMPLES = [
    "Quelle est la procédure à suivre dans ce cas ?",
    "Que dit le document sur les délais ?",
    "Quelles pièces dois-je fournir ?",
    "Où trouver la version à jour de ce document ?"
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
        /* Titres `##` et séparateurs `---` : sans ça, le balisage du modèle
           s'affichait tel quel au milieu de la réponse. */
        const parts = [];
        let tampon = [];
        const vider = () => {
          if (tampon.length) { parts.push("<p>" + tampon.map(inline).join("<br>") + "</p>"); tampon = []; }
        };
        lines.forEach(l => {
          const titre = /^\s*#{1,6}\s+(.+?)\s*$/.exec(l);
          if (titre) { vider(); parts.push('<h4 class="da-h">' + inline(titre[1]) + "</h4>"); return; }
          if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(l)) { vider(); parts.push('<hr class="da-hr">'); return; }
          tampon.push(l);
        });
        vider();
        html += parts.join("");
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
      /* Échap ferme le panneau : réflexe attendu d'une surface superposée. */
      panel._onKey = (ev) => { if (ev.key === "Escape" && cfg._onClose) cfg._onClose(); };
      document.addEventListener("keydown", panel._onKey);
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
          const n = data.chunks.length;
          det.appendChild(el("summary", null,
            n > 1 ? "Voir les " + n + " extraits utilisés" : "Voir l'extrait utilisé"));
          const liste = el("div", "da-extraits");
          data.chunks.forEach(c => {
            const bloc = el("div", "da-extrait");
            bloc.appendChild(el("b", null, esc((c && c.source) || "Document")));
            const p = el("p");
            p.textContent = (c && c.text) || "";   // texte brut : jamais interprété
            bloc.appendChild(p);
            liste.appendChild(bloc);
          });
          det.appendChild(liste);
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

  /* Retire un panneau en le laissant SORTIR de scène. */
  function fermerPanneau(panel, apres) {
    if (!panel) return;
    if (panel._onKey) document.removeEventListener("keydown", panel._onKey);
    panel.classList.add("da-out");
    setTimeout(function () { panel.remove(); if (apres) apres(); }, 280);
  }

  function mount(options) {
    injectStyle();
    const cfg = Object.assign({
      mode: "floating",
      apiBase: "",
      assistantName: "Assistant documentaire",
      clientName: "l'entreprise",
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
      const panel = buildPanel(cfg, "da-fullscreen", true);
      cfg._onClose = () => fermerPanneau(panel, () => controller.destroy());
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
        panel = buildPanel(cfg, "da-floating", true);
        const ouvert = panel;
        cfg._onClose = () => {
          if (panel !== ouvert) return;      // déjà fermé : rien à faire
          panel = null;
          fermerPanneau(ouvert);
          launcher.style.display = "";
        };
        root.appendChild(ouvert);
        launcher.style.display = "none";
        const ta = ouvert.querySelector("textarea"); if (ta) ta.focus();
      };
      root.appendChild(launcher);
      document.body.appendChild(root);
    }

    mounted.push(controller);
    return controller;
  }

  function unmountAll() {
    /* Les écouteurs clavier des panneaux ouverts partent avec eux. */
    document.querySelectorAll(".da-root .da-panel").forEach(p => {
      if (p._onKey) document.removeEventListener("keydown", p._onKey);
    });
    mounted.forEach(c => c.destroy());
    mounted = [];
  }

  window.DocAssistant = { mount, unmountAll };
})();
