"""
app.py — Interface de démonstration (Streamlit).

Lancement :
    streamlit run app.py

Prérequis : avoir lancé `python ingest.py` au moins une fois.
"""

import os
import streamlit as st
from rag_core import (answer_question, TOP_K,
                      resolve_llm_provider, resolve_embedding_provider)

# --- Personnalisation client : change ces deux lignes pour chaque démo -------
CLIENT_NAME = os.environ.get("CLIENT_NAME", "Boréale Équipement")
ASSISTANT_NAME = os.environ.get("ASSISTANT_NAME", "Assistant documentaire")
# ---------------------------------------------------------------------------

st.set_page_config(page_title=f"{ASSISTANT_NAME} — {CLIENT_NAME}",
                   page_icon="📄", layout="centered")

st.markdown(f"""
<div style="padding:8px 0 4px 0;">
  <h1 style="margin-bottom:0;">{ASSISTANT_NAME}</h1>
  <p style="color:#6b7280;margin-top:2px;">
    Répond aux questions à partir des documents de <b>{CLIENT_NAME}</b> — chaque réponse cite sa source.
  </p>
</div>
""", unsafe_allow_html=True)

EXAMPLES = [
    "Combien de semaines de vacances après 5 ans d'ancienneté ?",
    "Quelle est la garantie du compresseur d'une thermopompe BOR-TP24 ?",
    "Comment retourner un produit après 45 jours ?",
    "Quel est le prix net d'un chauffe-eau instantané au gaz ?",
    "Quel montant de geste commercial un représentant peut-il accorder sans directeur ?",
]

if "history" not in st.session_state:
    st.session_state.history = []
if "pending" not in st.session_state:
    st.session_state.pending = None

with st.sidebar:
    st.subheader("Exemples de questions")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True):
            st.session_state.pending = ex
    st.divider()
    st.caption(f"Récupération : {TOP_K} extraits les plus pertinents par question.")
    st.caption(f"Embeddings : {resolve_embedding_provider()} · LLM : {resolve_llm_provider()}")


def run_query(question: str):
    history = []
    for turn in st.session_state.history:
        history.append({"role": "user", "content": turn["q"]})
        history.append({"role": "assistant", "content": turn["a"]})
    with st.spinner("Recherche dans les documents..."):
        try:
            result = answer_question(question, history=history)
        except Exception as e:
            st.session_state.history.append(
                {"q": question, "a": f"Erreur : {e}", "sources": [], "chunks": []})
            return
    st.session_state.history.append({
        "q": question, "a": result.answer,
        "sources": result.sources, "chunks": result.chunks,
    })


typed = st.chat_input("Posez une question sur les documents…")
if typed:
    st.session_state.pending = typed

if st.session_state.pending:
    q = st.session_state.pending
    st.session_state.pending = None
    run_query(q)

def _md_safe(text: str) -> str:
    """Empêche Streamlit d'interpréter les montants en $ comme des formules LaTeX."""
    return text.replace("$", "\\$")


for turn in reversed(st.session_state.history):
    with st.chat_message("user"):
        st.write(_md_safe(turn["q"]))
    with st.chat_message("assistant"):
        st.write(_md_safe(turn["a"]))
        if turn["chunks"]:
            with st.expander("Voir les extraits utilisés"):
                for c in turn["chunks"]:
                    st.markdown(f"**{c['source']}** (extrait {c['chunk']})")
                    st.text(c["text"])