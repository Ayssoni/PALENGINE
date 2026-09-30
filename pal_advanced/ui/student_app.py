"""Student practice screen. Talks to the FastAPI backend (run it first).
Run:  streamlit run ui/student_app.py --server.port 8501
"""
import time

import requests
import streamlit as st

API = "http://127.0.0.1:8000"
st.set_page_config(page_title="PAL Fractions", page_icon="🧮", layout="centered")


def api(method, path, **kw):
    r = requests.request(method, f"{API}{path}", timeout=10, **kw)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------ login
if "student_id" not in st.session_state:
    st.title("🧮 PAL Fractions")
    try:
        api("GET", "/health")
    except Exception:
        st.error(f"Can't reach the API at {API}. Start it first:\n\n`uvicorn pal.main:app --reload`")
        st.stop()
    students = api("GET", "/students")
    st.subheader("Continue as")
    for s in students:
        if st.button(f"{s['name']}  (id {s['student_id']})", key=f"s{s['student_id']}", width="stretch"):
            st.session_state.student_id = s["student_id"]
            st.session_state.student_name = s["name"]
            st.rerun()
    st.divider()
    st.subheader("Or start as a new student")
    name = st.text_input("Name")
    if st.button("Start", type="primary", disabled=not name.strip()):
        r = api("POST", "/students", json={"name": name.strip()})
        st.session_state.student_id = r["student_id"]
        st.session_state.student_name = r["name"]
        st.rerun()
    st.stop()

sid = st.session_state.student_id
for k in ("current", "result", "q_start"):
    st.session_state.setdefault(k, None)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header(st.session_state.student_name)
    mastery = api("GET", f"/students/{sid}/mastery")
    overall = round(sum(v["mastery_pct"] for v in mastery.values()) / len(mastery), 1)
    n_mastered = sum(1 for v in mastery.values() if v["mastery_pct"] >= 80)
    st.metric("Overall mastery", f"{overall}%")
    st.metric("Concepts mastered", f"{n_mastered} / {len(mastery)}")
    with st.expander("Mastery by concept"):
        for cid, v in mastery.items():
            st.progress(min(1.0, v["mastery_pct"] / 100), text=f"{v['label']} - {v['mastery_pct']}%")
    st.divider()
    page = st.radio("View", ["Practice", "My report"], label_visibility="collapsed")
    if st.button("Switch student"):
        for k in ("student_id", "student_name", "current", "result", "q_start"):
            st.session_state.pop(k, None)
        st.rerun()

# ------------------------------------------------------------------ practice page
def practice_page():
    st.title("🧮 Fractions practice")
    if st.session_state.current is None and st.session_state.result is None:
        nxt = api("GET", f"/students/{sid}/next")
        if nxt["done"]:
            st.success(nxt["message"])
            return
        st.session_state.current = nxt
        st.session_state.q_start = time.time()

    cur = st.session_state.current
    q = cur["question"]
    stars = "★" * q["difficulty"] + "☆" * (5 - q["difficulty"])
    tag = "🔁 Review" if cur["is_review"] else q["subtopic"]
    st.caption(f"{tag}  ·  Difficulty {stars}")
    st.subheader(q["question_text"])
    texts = {o["label"]: o["text"] for o in q["options"]}
    res = st.session_state.result

    if res is None:
        choice = st.radio("Choose one answer", list(texts), index=None,
                          format_func=lambda l: f"{l}.   {texts[l]}", key=f"choice_{q['question_id']}")
        if st.button("Submit answer", type="primary", disabled=choice is None):
            taken = round(time.time() - (st.session_state.q_start or time.time()), 1)
            st.session_state.result = api("POST", f"/students/{sid}/attempt", json={
                "question_id": q["question_id"], "option_label": choice,
                "is_review": cur["is_review"], "time_taken_sec": taken})
            st.rerun()
        with st.expander("Why this question?"):
            st.write(cur["reason"])
        return

    st.write(f"**Your answer:** {res['chosen_label']}.  {res['chosen_text']}")
    if res["is_correct"]:
        st.success("✅ Correct!")
        st.info(f"**Why it's right:** {res['explanation']}")
    else:
        st.error("❌ Not quite.")
        if res["feedback"]:
            st.warning(f"**What went wrong:** {res['feedback']}")
        if res["misconception"] and not res["is_guess_tag"]:
            st.caption(f"Mistake type: {res['misconception']}")
            st.caption(f"Revision tip: {res['remedy']}")
        with st.expander("Show the correct answer and working", expanded=True):
            st.write(f"**Correct answer:** {res['correct_label']}.  {res['correct_text']}")
            st.write(res["explanation"])
    if res["confirmed"]:
        st.warning(f"🔎 **Pattern spotted:** you've made this mistake more than once: *{res['misconception']}*. "
                   "Your next question on this topic checks whether it's fixed.")
    if res["concept_mastered_now"]:
        st.balloons()
        st.success(f"🎉 You've mastered **{res['concept_label']}**!")
    st.caption(f"{res['concept_label']} mastery: {res['mastery_before_pct']}% → {res['mastery_after_pct']}%")
    if st.button("Next question ▶", type="primary"):
        st.session_state.current = None
        st.session_state.result = None
        st.rerun()


def report_page():
    st.title("📊 My report")
    rep = api("GET", f"/students/{sid}/report")
    a, b, c = st.columns(3)
    a.metric("Overall mastery", f"{rep['overall_mastery_pct']}%")
    b.metric("Accuracy", f"{rep['accuracy_pct']}%", f"{rep['n_attempts']} answered")
    c.metric("Concepts mastered", f"{rep['concepts_mastered']} / {rep['concepts_total']}")

    st.subheader("Mastery by concept")
    import pandas as pd
    df = pd.DataFrame(rep["concepts"])[["label", "status", "mastery_pct", "attempts", "accuracy_pct"]]
    df.columns = ["Concept", "Status", "Mastery %", "Attempts", "Accuracy %"]
    st.dataframe(df, hide_index=True, width="stretch")

    st.subheader("Misconceptions detected")
    if rep["misconceptions"]:
        mdf = pd.DataFrame(rep["misconceptions"])[["description", "times", "remedy"]]
        mdf.columns = ["Misconception", "Times", "Fix"]
        st.dataframe(mdf, hide_index=True, width="stretch")
    else:
        st.write("None detected yet.")

    st.subheader("What to do next")
    for r in rep["recommendations"]:
        st.write("• " + r)


{"Practice": practice_page, "My report": report_page}[page]()
