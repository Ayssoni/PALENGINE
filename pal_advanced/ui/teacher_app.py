"""Teacher dashboard. Run:  streamlit run ui/teacher_app.py --server.port 8502"""
import pandas as pd
import requests
import streamlit as st

API = "http://127.0.0.1:8000"
st.set_page_config(page_title="PAL Teacher Dashboard", page_icon="🧑‍🏫", layout="wide")


def api(method, path, **kw):
    r = requests.request(method, f"{API}{path}", timeout=10, **kw)
    r.raise_for_status()
    return r.json()


st.title("🧑‍🏫 Class dashboard - Fractions")
try:
    api("GET", "/health")
except Exception:
    st.error(f"Can't reach the API at {API}. Start it first:\n\n`uvicorn pal.main:app --reload`")
    st.stop()

if st.button("🔄 Refresh"):
    st.rerun()

dash = api("GET", "/teacher/dashboard")
a, b, c = st.columns(3)
a.metric("Students", dash["n_students"])
b.metric("Total attempts", dash["n_attempts"])
c.metric("At-risk students", len(dash["at_risk_students"]))

if dash["at_risk_students"]:
    st.warning("**At-risk:** " + ", ".join(s["name"] for s in dash["at_risk_students"]))

st.subheader("Students (weakest first)")
sdf = pd.DataFrame(dash["students"])
if not sdf.empty:
    sdf = sdf[["name", "attempts", "accuracy_pct", "overall_mastery_pct", "at_risk"]]
    sdf.columns = ["Name", "Attempts", "Accuracy %", "Overall mastery %", "At risk"]
    st.dataframe(sdf, hide_index=True, width="stretch")
else:
    st.write("No students yet.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Weakest concepts (class average)")
    wdf = pd.DataFrame(dash["weakest_concepts"])
    if not wdf.empty:
        wdf = wdf[["label", "class_avg_mastery_pct", "students_attempted"]]
        wdf.columns = ["Concept", "Class avg mastery %", "Students who tried it"]
        st.dataframe(wdf, hide_index=True, width="stretch")
        st.bar_chart(wdf.set_index("Concept")["Class avg mastery %"])
    else:
        st.write("No data yet.")

with col2:
    st.subheader("Most common misconceptions")
    mdf = pd.DataFrame(dash["top_misconceptions"])
    if not mdf.empty:
        mdf = mdf[["description", "times", "remedy"]]
        mdf.columns = ["Misconception", "Times (class-wide)", "Suggested fix"]
        st.dataframe(mdf, hide_index=True, width="stretch")
    else:
        st.write("No data yet.")

st.divider()
st.subheader("Concept mastery, all concepts (class average)")
cdf = pd.DataFrame(dash["concept_averages"])
if not cdf.empty:
    cdf = cdf[["label", "class_avg_mastery_pct", "students_attempted"]]
    cdf.columns = ["Concept", "Class avg mastery %", "Students who tried it"]
    st.dataframe(cdf, hide_index=True, width="stretch")

st.divider()
st.subheader("Look up one student")
students = api("GET", "/students")
names = {s["name"]: s["student_id"] for s in students}
if names:
    pick = st.selectbox("Student", list(names))
    rep = api("GET", f"/students/{names[pick]}/report")
    x, y, z = st.columns(3)
    x.metric("Overall mastery", f"{rep['overall_mastery_pct']}%")
    y.metric("Accuracy", f"{rep['accuracy_pct']}%")
    z.metric("Concepts mastered", f"{rep['concepts_mastered']} / {rep['concepts_total']}")
    cdf2 = pd.DataFrame(rep["concepts"])[["label", "status", "mastery_pct", "attempts"]]
    cdf2.columns = ["Concept", "Status", "Mastery %", "Attempts"]
    st.dataframe(cdf2, hide_index=True, width="stretch")
    if rep["misconceptions"]:
        st.write("**Misconceptions:**")
        for m in rep["misconceptions"]:
            st.write(f"- {m['description']} ({m['times']}x) - {m['remedy']}")
