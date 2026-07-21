/* widget.js — Assistant documentaire, widget de chat embarquable.
 *
 * Utilisation minimale sur n'importe quelle page :
 *   <script src="/widget.js"></script>
 *   <script>DocAssistant.mount({ mode: "floating" });</script>
 *
 * Modes : "floating" (bulle bas-droite), "inline" (dans un élément cible),
 *         "fullscreen" (plein écran).
 */
(function () {
  "use strict";

  const CSS = `
  :root{
    --da-emerald:#0E6E57; --da-emerald-dark:#0A5443; --da-ink:#15211D;
    --da-ink-soft:#586460; --da-paper:#F3F4F1; --da-card:#FFFFFF;
    --da-marker:#C6F24E; --da-line:#DBDED7;
    --da-font:'Bricolage Grotesque',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  }
  .da-root, .da-root *{box-sizing:border-box;}
  .da-root{font-family:var(--da-font);color:var(--da-ink);}

  /* Launcher (bulle flottante) */
  .da-launcher{
    position:fixed;right:24px;bottom:24px;z-index:2147483000;
    display:flex;align-items:center;gap:10px;
    background:var(--da-emerald);color:#fff;border:none;cursor:pointer;
    border-radius:999px;padding:14px 20px 14px 16px;
    font-family:var(--da-font);font-weight:700;font-size:15px;
    box-shadow:0 12px 30px -10px rgba(14,110,87,.6);
    transition:transform .15s ease, background .15s ease;
  }
  .da-launcher:hover{transform:translateY(-2px);background:var(--da-emerald-dark);}
  .da-launcher svg{width:22px;height:22px;flex:none;}
  .da-launcher .da-dot{position:absolute;top:10px;right:12px;width:9px;height:9px;
    background:var(--da-marker);border-radius:50%;box-shadow:0 0 0 3px var(--da-emerald);}

  /* Panneau */
  .da-panel{
    display:flex;flex-direction:column;background:var(--da-card);
    border:1px solid var(--da-line);overflow:hidden;
  }
  .da-panel.da-floating{
    position:fixed;right:24px;bottom:24px;z-index:2147483001;
    width:392px;height:600px;max-height:calc(100vh - 48px);
    border-radius:18px;box-shadow:0 24px 60px -20px rgba(21,33,29,.55);
    transform-origin:bottom right;
    animation:da-pop .22s cubic-bezier(.2,.8,.2,1);
  }
  .da-panel.da-inline{
    position:relative;width:100%;height:560px;border-radius:16px;
    box-shadow:0 14px 40px -28px rgba(21,33,29,.5);
  }
  .da-panel.da-fullscreen{
    position:fixed;inset:0;z-index:2147483001;width:100%;height:100%;
    border-radius:0;border:none;
  }
  @keyframes da-pop{from{opacity:0;transform:scale(.94) translateY(8px);}to{opacity:1;transform:none;}}

  /* En-tête */
  .da-head{
    display:flex;align-items:center;gap:12px;padding:16px 18px;
    background:var(--da-ink);color:#fff;
  }
  .da-head .da-avatar{width:34px;height:34px;border-radius:9px;background:var(--da-emerald);
    display:flex;align-items:center;justify-content:center;flex:none;}
  .da-head .da-avatar svg{width:18px;height:18px;}
  .da-head h3{margin:0;font-size:15px;font-weight:700;line-height:1.1;}
  .da-head p{margin:2px 0 0;font-size:12px;color:#9fb0aa;font-family:system-ui,sans-serif;}
  .da-head .da-close{margin-left:auto;background:transparent;border:none;color:#9fb0aa;
    cursor:pointer;font-size:22px;line-height:1;padding:4px 6px;border-radius:8px;}
  .da-head .da-close:hover{color:#fff;background:rgba(255,255,255,.08);}

  /* Zone messages */
  .da-body{flex:1;overflow-y:auto;padding:18px;background:var(--da-paper);
    font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;}
  .da-intro{color:var(--da-ink-soft);font-size:14px;line-height:1.5;margin:0 0 14px;}
  .da-examples{display:flex;flex-direction:column;gap:8px;margin-bottom:6px;}
  .da-chip-q{text-align:left;background:var(--da-card);border:1px solid var(--da-line);
    border-radius:12px;padding:11px 13px;font-size:13.5px;color:var(--da-ink);cursor:pointer;
    font-family:inherit;transition:border-color .12s ease, background .12s ease;line-height:1.35;}
  .da-chip-q:hover{border-color:var(--da-emerald);background:#fff;}

  .da-msg{margin:0 0 14px;display:flex;}
  .da-msg.user{justify-content:flex-end;}
  .da-bubble{max-width:88%;padding:11px 14px;border-radius:14px;font-size:14px;line-height:1.5;}
  .da-msg.user .da-bubble{background:var(--da-emerald);color:#fff;border-bottom-right-radius:4px;}
  .da-msg.bot .da-bubble{background:var(--da-card);border:1px solid var(--da-line);
    border-bottom-left-radius:4px;}
  .da-bubble p{margin:0 0 8px;} .da-bubble p:last-child{margin-bottom:0;}
  .da-bubble strong{font-weight:700;}
  .da-bubble ul,.da-bubble ol{margin:6px 0;padding-left:20px;}
  .da-bubble li{margin:3px 0;}
  .da-bubble a{color:var(--da-emerald);}
  .da-bubble code{background:var(--da-paper);border:1px solid var(--da-line);
    padding:1px 5px;border-radius:5px;font-size:12.5px;}

  .da-sources{margin-top:9px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;}
  .da-src-chip{display:inline-flex;align-items:center;gap:6px;
    font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;color:var(--da-ink);
    background:var(--da-paper);border:1px solid var(--da-line);border-radius:999px;padding:4px 9px;}
  .da-src-chip::before{content:"";width:7px;height:7px;border-radius:2px;background:var(--da-emerald);}
  .da-extracts{margin-top:8px;}
  .da-extracts summary{cursor:pointer;font-size:12px;color:var(--da-ink-soft);
    font-family:system-ui,sans-serif;}
  .da-extracts pre{white-space:pre-wrap;font-size:11.5px;background:var(--da-paper);
    border:1px solid var(--da-line);border-radius:8px;padding:10px;margin:8px 0 0;
    max-height:160px;overflow:auto;font-family:'IBM Plex Mono',ui-monospace,monospace;}

  .da-typing{display:inline-flex;gap:4px;padding:12px 14px;}
  .da-typing span{width:7px;height:7px;border-radius:50%;background:var(--da-ink-soft);
    opacity:.4;animation:da-blink 1s infinite;}
  .da-typing span:nth-child(2){animation-delay:.2s;} .da-typing span:nth-child(3){animation-delay:.4s;}
  @keyframes da-blink{0%,100%{opacity:.25;transform:translateY(0);}50%{opacity:.9;transform:translateY(-2px);}}

  /* Saisie */
  .da-foot{padding:12px;border-top:1px solid var(--da-line);background:var(--da-card);
    display:flex;gap:9px;align-items:flex-end;}
  .da-foot textarea{flex:1;resize:none;border:1px solid var(--da-line);border-radius:11px;
    padding:10px 12px;font-family:system-ui,sans-serif;font-size:14px;max-height:120px;
    line-height:1.4;outline:none;color:var(--da-ink);}
  .da-foot textarea:focus{border-color:var(--da-emerald);}
  .da-send{flex:none;width:42px;height:42px;border-radius:11px;border:none;cursor:pointer;
    background:var(--da-emerald);color:#fff;display:flex;align-items:center;justify-content:center;}
  .da-send:hover{background:var(--da-emerald-dark);}
  .da-send:disabled{opacity:.5;cursor:not-allowed;}
  .da-send svg{width:19px;height:19px;}
  .da-poweredby{font-size:10.5px;color:var(--da-ink-soft);text-align:center;padding:6px;
    font-family:system-ui,sans-serif;background:var(--da-card);}

  @media (max-width:480px){
    .da-panel.da-floating{width:calc(100vw - 24px);right:12px;bottom:12px;height:calc(100vh - 90px);}
    .da-launcher{right:14px;bottom:14px;}
  }
  @media (prefers-reduced-motion:reduce){
    .da-panel.da-floating{animation:none;} .da-launcher:hover{transform:none;}
    .da-typing span{animation:none;}
  }`;

  const ICON_CHAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  const ICON_DOC = '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/></svg>';
  const ICON_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/></svg>';

  const DEFAULT_EXAMPLES = [
    "Combien de semaines de vacances après 5 ans d'ancienneté ?",
    "La garantie du compresseur d'une thermopompe BOR-TP24 est de combien ?",
    "Quel est le prix net d'un chauffe-eau instantané au gaz ?",
    "Comment retourner un produit acheté il y a 45 jours ?"
  ];

  let styleInjected = false;
  let mounted = [];

  function injectStyle() {
    if (styleInjected) return;
    const s = document.createElement("style");
    s.id = "da-widget-style";
    s.textContent = CSS;
    document.head.appendChild(s);
    styleInjected = true;
  }

  function esc(t) {
    return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Rendu markdown minimal : gras, code, liens, listes, paragraphes.
  function renderMarkdown(text) {
    const inline = (s) => esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+?)`/g, "<code>$1</code>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    const blocks = text.split(/\n{2,}/);
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

  function buildPanel(cfg, modeClass, withClose) {
    const panel = el("div", "da-panel " + modeClass);
    panel._history = [];

    const head = el("div", "da-head");
    head.appendChild(el("div", "da-avatar", ICON_DOC));
    const titles = el("div");
    titles.appendChild(el("h3", null, esc(cfg.assistantName)));
    titles.appendChild(el("p", null, "Répond à partir des documents de " + esc(cfg.clientName)));
    head.appendChild(titles);
    if (withClose) {
      const close = el("button", "da-close", "×");
      close.setAttribute("aria-label", "Fermer");
      close.onclick = () => cfg._onClose && cfg._onClose();
      head.appendChild(close);
    }
    panel.appendChild(head);

    const body = el("div", "da-body");
    const intro = el("p", "da-intro",
      "Posez une question sur les documents. Chaque réponse cite sa source.");
    body.appendChild(intro);
    const examples = el("div", "da-examples");
    cfg.examples.forEach(q => {
      const b = el("button", "da-chip-q", esc(q));
      b.onclick = () => { send(q); };
      examples.appendChild(b);
    });
    body.appendChild(examples);
    panel.appendChild(body);

    const foot = el("div", "da-foot");
    const ta = el("textarea");
    ta.rows = 1;
    ta.placeholder = "Écrivez votre question…";
    ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; });
    ta.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(ta.value); }
    });
    const send_btn = el("button", "da-send", ICON_SEND);
    send_btn.onclick = () => send(ta.value);
    foot.appendChild(ta);
    foot.appendChild(send_btn);
    panel.appendChild(foot);

    panel.appendChild(el("div", "da-poweredby", "Assistant sur vos documents · démo"));

    function addMsg(role, node) {
      if (examples.parentNode) { intro.remove(); examples.remove(); }
      const wrap = el("div", "da-msg " + role);
      const bubble = el("div", "da-bubble");
      bubble.appendChild(node);
      wrap.appendChild(bubble);
      body.appendChild(wrap);
      body.scrollTop = body.scrollHeight;
      return { wrap, bubble };
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
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: text, history: historyToSend })
        });
        const data = await r.json();
        t.bubble.innerHTML = "";
        if (data.error) {
          t.bubble.appendChild(el("p", null, "⚠️ " + esc(data.error)));
        } else {
          t.bubble.appendChild(el("div", null, renderMarkdown(data.answer)));
          panel._history.push({ role: "user", content: text });
          panel._history.push({ role: "assistant", content: data.answer });
          if (data.sources && data.sources.length) {
            const srow = el("div", "da-sources");
            data.sources.forEach(s => srow.appendChild(el("span", "da-src-chip", esc(s))));
            t.bubble.appendChild(srow);
          }
          if (data.chunks && data.chunks.length) {
            const det = el("details", "da-extracts");
            det.appendChild(el("summary", null, "Voir les extraits utilisés"));
            const pre = el("pre");
            pre.textContent = data.chunks
              .map(c => "[" + c.source + "]\n" + c.text).join("\n\n———\n\n");
            det.appendChild(pre);
            t.bubble.appendChild(det);
          }
        }
      } catch (e) {
        t.bubble.innerHTML = "";
        t.bubble.appendChild(el("p", null, "⚠️ Impossible de joindre le serveur. Est-il démarré ?"));
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
    } else { // floating
      const launcher = el("button", "da-launcher", ICON_CHAT + "<span>Une question ?</span><span class='da-dot'></span>");
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