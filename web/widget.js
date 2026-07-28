/* widget.js — Assistant documentaire, widget de chat embarquable. v2 (design modernisé) */
(function () {
  "use strict";

  const CSS = `
  :root{
    --da-emerald:#0E6E57; --da-emerald-2:#129671; --da-emerald-dark:#0A5443;
    --da-ink:#111C18; --da-ink-2:#1B2B25; --da-ink-soft:#5C6B65;
    --da-paper:#F5F6F3; --da-card:#FFFFFF; --da-marker:#C6F24E;
    --da-line:#E2E6DF; --da-line-2:#D3D9D1;
    --da-grad:linear-gradient(135deg,#0E6E57 0%,#129671 100%);
    --da-font:'Bricolage Grotesque',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    --da-body:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  }
  .da-root, .da-root *{box-sizing:border-box;}
  .da-root{font-family:var(--da-font);color:var(--da-ink);}

  /* ---------- launcher ---------- */
  .da-launcher{
    position:fixed;right:24px;bottom:24px;z-index:2147483000;
    display:flex;align-items:center;gap:10px;
    background:var(--da-grad);color:#fff;border:none;cursor:pointer;
    border-radius:999px;padding:15px 22px 15px 18px;
    font-family:var(--da-font);font-weight:700;font-size:15px;letter-spacing:.01em;
    box-shadow:0 8px 20px -6px rgba(14,110,87,.45), 0 20px 44px -16px rgba(14,110,87,.5);
    transition:transform .18s cubic-bezier(.2,.8,.2,1), box-shadow .18s ease;
  }
  .da-launcher:hover{transform:translateY(-2px) scale(1.02);
    box-shadow:0 12px 26px -6px rgba(14,110,87,.5), 0 26px 54px -18px rgba(14,110,87,.55);}
  .da-launcher svg{width:21px;height:21px;flex:none;}
  .da-launcher .da-dot{position:absolute;top:9px;right:13px;width:9px;height:9px;
    background:var(--da-marker);border-radius:50%;box-shadow:0 0 0 3px rgba(255,255,255,.25);
    animation:da-pulse 2.2s ease-out infinite;}
  @keyframes da-pulse{0%{box-shadow:0 0 0 0 rgba(198,242,78,.55);}
    70%{box-shadow:0 0 0 9px rgba(198,242,78,0);}100%{box-shadow:0 0 0 0 rgba(198,242,78,0);}}

  /* ---------- panel ---------- */
  .da-panel{
    display:flex;flex-direction:column;background:var(--da-card);
    border:1px solid var(--da-line);overflow:hidden;
  }
  .da-panel.da-floating{
    position:fixed;right:24px;bottom:24px;z-index:2147483001;
    width:400px;height:620px;max-height:calc(100vh - 48px);
    border-radius:22px;box-shadow:0 10px 30px -12px rgba(17,28,24,.25), 0 40px 90px -30px rgba(17,28,24,.5);
    transform-origin:bottom right;
    animation:da-pop .3s cubic-bezier(.2,.9,.25,1.05);
  }
  .da-panel.da-inline{
    position:relative;width:100%;height:560px;border-radius:18px;
    box-shadow:0 18px 44px -30px rgba(17,28,24,.45);
  }
  .da-panel.da-fullscreen{
    position:fixed;inset:0;z-index:2147483001;width:100%;height:100%;
    border-radius:0;border:none;
  }
  @keyframes da-pop{from{opacity:0;transform:scale(.92) translateY(14px);}to{opacity:1;transform:none;}}

  /* ---------- header ---------- */
  .da-head{
    position:relative;display:flex;align-items:center;gap:13px;padding:18px 18px 16px;
    background:linear-gradient(135deg,#111C18 0%,#14332A 55%,#0E6E57 130%);color:#fff;
  }
  .da-head::after{content:"";position:absolute;inset:0;pointer-events:none;
    background:radial-gradient(320px 120px at 92% -30%, rgba(198,242,78,.16), transparent 70%);}
  .da-avatar{
    position:relative;width:42px;height:42px;border-radius:14px;flex:none;
    background:var(--da-grad);display:flex;align-items:center;justify-content:center;
    box-shadow:0 6px 16px -6px rgba(14,110,87,.7), inset 0 1px 0 rgba(255,255,255,.25);
  }
  .da-avatar svg{width:21px;height:21px;}
  .da-avatar .da-status{position:absolute;right:-3px;bottom:-3px;width:12px;height:12px;
    background:#3DDC97;border-radius:50%;border:2.5px solid #14332A;}
  .da-head h3{margin:0;font-size:15.5px;font-weight:700;line-height:1.15;letter-spacing:.01em;}
  .da-head p{margin:3px 0 0;font-size:12px;color:#9FB5AC;font-family:var(--da-body);line-height:1.3;}
  .da-head .da-close{position:relative;margin-left:auto;background:rgba(255,255,255,.07);
    border:none;color:#B9C8C1;cursor:pointer;font-size:20px;line-height:1;width:32px;height:32px;
    border-radius:10px;display:flex;align-items:center;justify-content:center;flex:none;
    transition:background .15s ease,color .15s ease;}
  .da-head .da-close:hover{color:#fff;background:rgba(255,255,255,.16);}

  /* ---------- body ---------- */
  .da-body{flex:1;overflow-y:auto;padding:18px 16px;background:var(--da-paper);
    font-family:var(--da-body);scrollbar-width:thin;scrollbar-color:var(--da-line-2) transparent;}
  .da-body::-webkit-scrollbar{width:5px;}
  .da-body::-webkit-scrollbar-thumb{background:var(--da-line-2);border-radius:99px;}
  .da-hello{display:flex;gap:10px;align-items:flex-start;margin:0 0 16px;}
  .da-hello .da-mini{width:30px;height:30px;border-radius:10px;background:var(--da-grad);flex:none;
    display:flex;align-items:center;justify-content:center;box-shadow:0 4px 10px -4px rgba(14,110,87,.6);}
  .da-hello .da-mini svg{width:15px;height:15px;}
  .da-hello .da-bulle{background:var(--da-card);border:1px solid var(--da-line);border-radius:4px 16px 16px 16px;
    padding:12px 14px;font-size:13.5px;line-height:1.5;color:var(--da-ink);max-width:88%;}
  .da-examples{display:flex;flex-direction:column;gap:8px;margin:0 0 6px 40px;}
  .da-chip-q{display:flex;align-items:center;justify-content:space-between;gap:10px;text-align:left;
    background:var(--da-card);border:1px solid var(--da-line);
    border-radius:13px;padding:11px 13px;font-size:13px;color:var(--da-ink);cursor:pointer;
    font-family:var(--da-body);line-height:1.35;
    transition:border-color .15s ease, box-shadow .15s ease, transform .15s ease;}
  .da-chip-q::after{content:"→";font-family:var(--da-font);color:var(--da-emerald);font-weight:700;
    opacity:0;transform:translateX(-4px);transition:opacity .15s ease,transform .15s ease;flex:none;}
  .da-chip-q:hover{border-color:var(--da-emerald);box-shadow:0 4px 14px -8px rgba(14,110,87,.4);transform:translateY(-1px);}
  .da-chip-q:hover::after{opacity:1;transform:none;}

  /* ---------- messages ---------- */
  .da-msg{margin:0 0 14px;display:flex;gap:9px;align-items:flex-end;
    animation:da-in .28s cubic-bezier(.2,.8,.2,1);}
  @keyframes da-in{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
  .da-msg.user{justify-content:flex-end;}
  .da-msg.bot .da-mini{width:28px;height:28px;border-radius:9px;background:var(--da-grad);flex:none;
    display:flex;align-items:center;justify-content:center;margin-bottom:2px;}
  .da-msg.bot .da-mini svg{width:14px;height:14px;}
  .da-bubble{max-width:86%;padding:11px 14px;border-radius:16px;font-size:14px;line-height:1.55;}
  .da-msg.user .da-bubble{background:var(--da-grad);color:#fff;border-bottom-right-radius:5px;
    box-shadow:0 6px 16px -8px rgba(14,110,87,.55);}
  .da-msg.bot .da-bubble{background:var(--da-card);border:1px solid var(--da-line);
    border-bottom-left-radius:5px;box-shadow:0 2px 10px -6px rgba(17,28,24,.12);}
  .da-bubble p{margin:0 0 8px;} .da-bubble p:last-child{margin-bottom:0;}
  .da-bubble strong{font-weight:650;}
  .da-bubble ul,.da-bubble ol{margin:6px 0;padding-left:20px;}
  .da-bubble li{margin:3px 0;}
  .da-bubble a{color:var(--da-emerald);}
  .da-bubble code{background:var(--da-paper);border:1px solid var(--da-line);
    padding:1px 5px;border-radius:5px;font-size:12.5px;}

  /* ---------- sources & extraits ---------- */
  .da-sources{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;}
  .da-src-chip{display:inline-flex;align-items:center;gap:6px;
    font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:10.5px;color:var(--da-emerald-dark);
    background:rgba(14,110,87,.07);border:1px solid rgba(14,110,87,.22);
    border-radius:999px;padding:4px 10px 4px 7px;font-weight:500;}
  .da-src-chip svg{width:11px;height:11px;flex:none;}
  .da-extracts{margin-top:9px;border-top:1px dashed var(--da-line);padding-top:8px;}
  .da-extracts summary{cursor:pointer;font-size:12px;color:var(--da-ink-soft);
    font-family:var(--da-body);list-style:none;display:flex;align-items:center;gap:6px;
    transition:color .15s ease;}
  .da-extracts summary::-webkit-details-marker{display:none;}
  .da-extracts summary::before{content:"›";font-family:var(--da-font);font-weight:700;
    color:var(--da-emerald);transition:transform .18s ease;display:inline-block;}
  .da-extracts[open] summary::before{transform:rotate(90deg);}
  .da-extracts summary:hover{color:var(--da-ink);}
  .da-extracts pre{white-space:pre-wrap;font-size:11.5px;background:var(--da-paper);
    border:1px solid var(--da-line);border-radius:10px;padding:10px;margin:8px 0 0;
    max-height:170px;overflow:auto;font-family:'IBM Plex Mono',ui-monospace,monospace;
    color:var(--da-ink-2);}

  /* ---------- typing ---------- */
  .da-typing{display:inline-flex;gap:5px;padding:4px 2px;align-items:center;}
  .da-typing span{width:7px;height:7px;border-radius:50%;background:var(--da-emerald);
    opacity:.35;animation:da-blink 1.1s infinite;}
  .da-typing span:nth-child(2){animation-delay:.18s;} .da-typing span:nth-child(3){animation-delay:.36s;}
  @keyframes da-blink{0%,100%{opacity:.25;transform:translateY(0);}50%{opacity:.95;transform:translateY(-3px);}}

  /* ---------- footer ---------- */
  .da-foot{padding:12px 14px;border-top:1px solid var(--da-line);background:var(--da-card);
    display:flex;gap:9px;align-items:flex-end;}
  .da-foot .da-field{flex:1;display:flex;align-items:flex-end;background:var(--da-paper);
    border:1.5px solid var(--da-line);border-radius:14px;padding:4px 6px 4px 14px;
    transition:border-color .15s ease, box-shadow .15s ease;}
  .da-foot .da-field:focus-within{border-color:var(--da-emerald);background:#fff;
    box-shadow:0 0 0 3px rgba(14,110,87,.1);}
  .da-foot textarea{flex:1;resize:none;border:none;background:transparent;outline:none;
    padding:8px 0;font-family:var(--da-body);font-size:14px;max-height:120px;
    line-height:1.4;color:var(--da-ink);}
  .da-send{flex:none;width:38px;height:38px;border-radius:11px;border:none;cursor:pointer;
    background:var(--da-grad);color:#fff;display:flex;align-items:center;justify-content:center;
    margin:2px;box-shadow:0 5px 12px -5px rgba(14,110,87,.6);
    transition:transform .15s ease, box-shadow .15s ease, opacity .15s ease;}
  .da-send:hover{transform:translateY(-1px);box-shadow:0 8px 16px -6px rgba(14,110,87,.65);}
  .da-send:disabled{opacity:.45;cursor:not-allowed;transform:none;box-shadow:none;}
  .da-send svg{width:17px;height:17px;}
  .da-poweredby{font-size:10.5px;color:#9AA69F;text-align:center;padding:7px;
    font-family:var(--da-body);background:var(--da-card);letter-spacing:.02em;}

  @media (max-width:480px){
    .da-panel.da-floating{width:calc(100vw - 24px);right:12px;bottom:12px;height:calc(100vh - 90px);}
    .da-launcher{right:14px;bottom:14px;}
  }
  @media (prefers-reduced-motion:reduce){
    .da-panel.da-floating,.da-msg{animation:none;}
    .da-launcher:hover,.da-send:hover{transform:none;}
    .da-typing span{animation:none;}
    .da-launcher .da-dot{animation:none;}
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

  let styleInjected = false;
  let mounted = [];

  // Le mot de passe est validé par l'écran d'accueil (index.html) et stocké ici.
  function getApiPassword() {
    return localStorage.getItem("da_api_password") || "";
  }

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

    // ---- header ----
    const head = el("div", "da-head");
    const avatar = el("div", "da-avatar", ICON_SPARK + '<span class="da-status"></span>');
    head.appendChild(avatar);
    const titles = el("div");
    titles.appendChild(el("h3", null, esc(cfg.assistantName)));
    titles.appendChild(el("p", null, "En ligne · répond à partir des documents de " + esc(cfg.clientName)));
    head.appendChild(titles);
    if (withClose) {
      const close = el("button", "da-close", "×");
      close.setAttribute("aria-label", "Fermer");
      close.onclick = () => cfg._onClose && cfg._onClose();
      head.appendChild(close);
    }
    panel.appendChild(head);

    // ---- body ----
    const body = el("div", "da-body");
    const hello = el("div", "da-hello");
    hello.appendChild(el("div", "da-mini", ICON_SPARK));
    hello.appendChild(el("div", "da-bulle",
      "Bonjour ! Posez une question sur les documents — chaque réponse cite sa source. Quelques exemples :"));
    body.appendChild(hello);
    const examples = el("div", "da-examples");
    cfg.examples.forEach(q => {
      const b = el("button", "da-chip-q");
      b.appendChild(el("span", null, esc(q)));
      b.onclick = () => { send(q); };
      examples.appendChild(b);
    });
    body.appendChild(examples);
    panel.appendChild(body);

    // ---- footer ----
    const foot = el("div", "da-foot");
    const field = el("div", "da-field");
    const ta = el("textarea");
    ta.rows = 1;
    ta.placeholder = "Écrivez votre question…";
    ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; });
    ta.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(ta.value); }
    });
    field.appendChild(ta);
    const send_btn = el("button", "da-send", ICON_SEND);
    send_btn.setAttribute("aria-label", "Envoyer");
    send_btn.onclick = () => send(ta.value);
    field.appendChild(send_btn);
    foot.appendChild(field);
    panel.appendChild(foot);

    panel.appendChild(el("div", "da-poweredby", "Assistant sur vos documents · réponses sourcées"));

    function addMsg(role, node) {
      if (examples.parentNode) { hello.remove(); examples.remove(); }
      const wrap = el("div", "da-msg " + role);
      if (role === "bot") wrap.appendChild(el("div", "da-mini", ICON_SPARK));
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
          headers: {
            "Content-Type": "application/json",
            "X-API-Password": getApiPassword()
          },
          body: JSON.stringify({ question: text, history: historyToSend })
        });
        if (r.status === 401) {
          localStorage.removeItem("da_api_password");
          t.bubble.innerHTML = "";
          t.bubble.appendChild(el("p", null, "⚠️ Session expirée. Rechargez la page pour ressaisir le mot de passe."));
          return;
        }
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
            data.sources.forEach(s => srow.appendChild(el("span", "da-src-chip", ICON_FILE + esc(s))));
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
    } else {
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