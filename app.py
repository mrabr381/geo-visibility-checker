"""GEO Visibility Checker — Streamlit web app.

Deploy: Streamlit Community Cloud → repo, branch main, file app.py.
No key needed for sample mode; optional GEMINI_API_KEY in Secrets for live runs.
"""

import io
import os
import sqlite3

import streamlit as st

from geo_check import audit as audit_mod
from geo_check import engine, prompts as prompts_mod
from geo_check import report as report_mod
from geo_check import store

st.set_page_config(page_title="GEO Visibility Checker",
                   page_icon="🔍",
                   layout="wide")
st.title("🔍 GEO Visibility Checker")
st.write(
    "Track whether AI answer engines mention your brand — free, with your "
    "own Gemini free-tier key. **This app measures Gemini answers only.** "
    "There is no official free API for ChatGPT or Perplexity, so this tool "
    "does not scrape them and does not claim to measure them."
)

DB_PATH = "geo_visibility.db"


def get_conn():
    return store.connect(DB_PATH)


tab_run, tab_history, tab_audit = st.tabs(
    ["▶ Run prompts", "📈 History", "🧾 Citation audit"])

with tab_run:
    st.subheader("Run a prompt check")
    brand = st.text_input("Brand / site", value="toolenix.com",
                          help="e.g. toolenix.com — mentions are matched "
                               "case-insensitively, including the bare name.")
    uploaded = st.file_uploader("prompts.yaml (optional)",
                                type=["yaml", "yml", "txt"])
    pasted = st.text_area("Or paste prompts (one per line)",
                          value="What are the best free online tools for converting PDF files?\n"
                                "What is the best free word counter tool online?",
                          height=120)
    api_key = st.text_input("Gemini API key (optional — leave blank for sample mode)",
                            type="password",
                            help="Get a free key at Google AI Studio. "
                                 "It is never stored by this app.")
    mode = st.radio("Mode", ["Sample (no key — bundled sample answers)",
                             "Live (Gemini free tier)"],
                    horizontal=True)
    if st.button("Run check", type="primary"):
        if uploaded is not None:
            tmp = "/tmp/_uploaded_prompts.yaml"
            with open(tmp, "wb") as fh:
                fh.write(uploaded.read())
            try:
                data = prompts_mod.load_prompts(tmp)
            except prompts_mod.PromptError as exc:
                st.error(str(exc))
                st.stop()
            prompt_list = data["prompts"]
            brand = data["brand"] or brand
        else:
            prompt_list = [ln.strip() for ln in pasted.splitlines() if ln.strip()]
            if not prompt_list:
                st.error("Add at least one prompt.")
                st.stop()
            if len(prompt_list) > 50:
                st.error("Maximum 50 prompts per run.")
                st.stop()
        variants = prompts_mod.brand_variants(brand)
        results, live_mode = [], "sample"
        progress = st.progress(0, text="Running prompts…")
        if mode.startswith("Sample"):
            from geo_check.cli import load_sample_answers
            answers = load_sample_answers()
            for i, prompt in enumerate(prompt_list):
                answer = answers.get(prompt, answers.get("__default__", ""))
                results.append(engine.analyse_answer(prompt, answer, variants))
                progress.progress((i + 1) / len(prompt_list))
            st.warning("Sample mode — answers come from the bundled sample "
                       "dataset, NOT live measurements.")
        else:
            key = api_key or os.environ.get("GEMINI_API_KEY", "")
            if not key:
                st.error("Live mode needs a Gemini API key.")
                st.stop()
            live_mode = "live"
            for i, prompt in enumerate(prompt_list):
                progress.progress(i / len(prompt_list),
                                  text=f"[{i + 1}/{len(prompt_list)}] {prompt}")
                try:
                    answer = engine.ask(prompt, key)
                except engine.EngineError as exc:
                    st.error(str(exc))
                    st.stop()
                results.append(engine.analyse_answer(prompt, answer, variants))
            progress.progress(1.0)
        conn = get_conn()
        run_id = store.save_run(conn, brand, "gemini", engine.DEFAULT_MODEL,
                                live_mode, results)
        history = store.run_history(conn, brand)
        conn.close()
        mentioned = sum(1 for r in results if r["mentioned"])
        rate = round(100.0 * mentioned / len(results), 1) if results else 0.0
        st.success(f"Run #{run_id}: **{brand} mentioned in {mentioned}/"
                   f"{len(results)} prompts ({rate}%)** [{live_mode}]")
        st.dataframe(
            [{"Prompt": r["prompt"], "Mentioned": "✅ Yes" if r["mentioned"] else "❌ No",
              "Position": f"{r['position_pct']}%" if r["position_pct"] is not None else "—",
              "Rank": f"#{r['list_rank']}" if r["list_rank"] else "—",
              "Sentiment": r["sentiment"] or "—",
              "Snippet": r["snippet"] or "—"} for r in results],
            use_container_width=True)
        buf = io.StringIO()
        import csv as _csv
        w = _csv.DictWriter(buf, fieldnames=report_mod.CSV_FIELDS)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in report_mod.CSV_FIELDS})
        st.download_button("⬇ Download results.csv", buf.getvalue(),
                           file_name="results.csv", mime="text/csv")

with tab_history:
    st.subheader("Run history")
    brand_h = st.text_input("Brand", value="toolenix.com", key="brand_h")
    conn = get_conn()
    runs = store.list_runs(conn, brand_h)
    conn.close()
    if not runs:
        st.info("No runs yet for this brand — run a check first (sample mode works).")
    else:
        st.dataframe(
            [{"Run": r["id"], "When (UTC)": r["started_at"], "Mode": r["mode"],
              "Prompts": r["prompt_count"], "Mentioned": r["mention_count"],
              "Rate": f"{r['mention_rate']}%"} for r in runs],
            use_container_width=True)

with tab_audit:
    st.subheader("Citation-readiness audit")
    st.write("Checks whether AI engines can easily find, trust and cite a page: "
             "llms.txt, robots.txt, FAQ/schema, headings, dates, content length.")
    url = st.text_input("Page URL", value="https://toolenix.com")
    if st.button("Audit page"):
        with st.spinner("Fetching page…"):
            result = audit_mod.audit_url(url)
        st.success(f"**{result['score']}/{result['max_score']} — {result['grade']}**")
        st.dataframe(
            [{"Check": c["label"], "Weight": c["weight"],
              "Result": "✅ Pass" if c["passed"] else "❌ Fail",
              "Detail": c["detail"]} for c in result["checks"]],
            use_container_width=True)
