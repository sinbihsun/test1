
import streamlit as st
import pandas as pd
from pathlib import Path
import random

st.set_page_config(page_title="🇯🇵 일본어 단어 학습 대시보드", layout="wide")

@st.cache_data
def load_data():
    base = Path(__file__).resolve().parent.parent / "data" / "n5_vocab.csv"
    return pd.read_csv(base)

df = load_data()

st.title("🇯🇵 일본어 단어 학습 대시보드 (N5)")
st.caption("연상 암기 + 예문 + 퀴즈 모드 포함")

with st.sidebar:
    st.header("필터")
    jlpt = st.selectbox("JLPT", sorted(df["jlpt"].unique()))
    pos = st.multiselect("품사", sorted(df["pos"].unique()))
    keyword = st.text_input("검색 (단어/뜻/가나)")

filtered = df.copy()
filtered = filtered[filtered["jlpt"]==jlpt]
if pos:
    filtered = filtered[filtered["pos"].isin(pos)]
if keyword:
    mask = (
        filtered["word"].astype(str).str.contains(keyword, case=False, na=False) |
        filtered["meaning_ko"].astype(str).str.contains(keyword, case=False, na=False) |
        filtered["kana"].astype(str).str.contains(keyword, case=False, na=False)
    )
    filtered = filtered[mask]

st.subheader("📚 학습 카드")
if len(filtered) == 0:
    st.info("조건에 맞는 단어가 없습니다. 필터를 조정하세요.")
else:
    idx = st.session_state.get("card_idx", 0)
    if st.button("🔀 랜덤 카드"):
        idx = random.randrange(len(filtered))
        st.session_state["card_idx"] = idx
    row = filtered.iloc[idx]
    st.markdown(f"### **{row['word']}** ({row['kana']}) — {row['meaning_ko']}")
    st.write(f"**발음 연상:** {row['mnemonic_sound']}")
    st.write(f"**이미지:** {row['mnemonic_image']}")
    st.write(f"**스토리:** {row['mnemonic_story']}")
    st.write(f"**예문:** {row['example_jp']}  \n➡ {row['example_ko']}")

st.divider()

st.subheader("📝 퀴즈 모드 (뜻 고르기)")
num_opts = 4
sample = df.sample(num_opts) if len(df) >= num_opts else df.copy()
answer_row = sample.sample(1).iloc[0]

st.write(f"**문제:** `{answer_row['word']}` ({answer_row['kana']}) 의 한국어 뜻은?")
options = sample["meaning_ko"].tolist()
random.shuffle(options)
choice = st.radio("정답 선택", options, index=None)

if st.button("정답 확인"):
    if choice == answer_row["meaning_ko"]:
        st.success("정답! 🎉")
    else:
        st.error(f"오답 😅  정답은 **{answer_row['meaning_ko']}**")
        st.caption(f"예문: {answer_row['example_jp']}  \n➜ {answer_row['example_ko']}")

st.divider()

st.subheader("📋 단어 목록")
st.dataframe(filtered[["word","kana","meaning_ko","pos","mnemonic_sound","example_jp","example_ko"]], use_container_width=True)

st.download_button(
    "현재 목록 CSV 다운로드",
    filtered.to_csv(index=False).encode("utf-8-sig"),
    "n5_filtered.csv",
    "text/csv"
)
