# app.py — 🇯🇵 일본어 단어 학습 대시보드 (루트에 n5_vocab.csv)
import streamlit as st
import pandas as pd
from pathlib import Path
import random

st.set_page_config(page_title="🇯🇵 일본어 단어 학습 대시보드 (N5)", layout="wide")

# =========================
# 데이터 로더 (견고한 경로 탐색)
# =========================
@st.cache_data(show_spinner=False)
def load_data():
    candidates = [
        Path(__file__).resolve().parent / "n5_vocab.csv",          # app.py와 같은 폴더(루트)
        Path.cwd() / "n5_vocab.csv",                                # 현재 작업 디렉터리
        Path(__file__).resolve().parent / "data" / "n5_vocab.csv",  # 혹시 대비
    ]
    checked = []
    for p in candidates:
        checked.append(str(p))
        if p.exists():
            # utf-8-sig로 저장된 파일까지 안전하게 처리
            for enc in ("utf-8-sig", "utf-8", "cp949"):
                try:
                    return pd.read_csv(p, encoding=enc)
                except Exception:
                    continue
    st.error(
        "n5_vocab.csv 파일을 찾지 못했습니다.\n"
        "다음 경로들을 확인했습니다:\n- " + "\n- ".join(checked) +
        "\n\n리포 루트 구조가 아래와 같아야 합니다:\n"
        "README.md / app.py / n5_vocab.csv / requirements.txt"
    )
    st.stop()

# =========================
# 유틸
# =========================
def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """필요 컬럼이 누락되어도 앱이 꺼지지 않도록 기본값 채우기."""
    df = df.copy()
    need = ["word","kana","meaning_ko","pos","jlpt",
            "mnemonic_sound","mnemonic_image","mnemonic_story",
            "example_jp","example_ko"]
    for c in need:
        if c not in df.columns:
            df[c] = ""
    # 문자열화
    for c in ["word","kana","meaning_ko","pos","jlpt"]:
        df[c] = df[c].astype(str)
    return df

def pick_random_index(n: int) -> int:
    return 0 if n <= 1 else random.randrange(n)

# =========================
# 데이터 로드
# =========================
df_raw = load_data()
df = ensure_columns(df_raw)

# =========================
# 사이드바
# =========================
with st.sidebar:
    st.header("필터")
    jlpt_choices = sorted(df["jlpt"].dropna().unique().tolist()) or ["N5"]
    jlpt = st.selectbox("JLPT", jlpt_choices, index=0)
    pos_choices = sorted(df["pos"].dropna().unique().tolist())
    pos_sel = st.multiselect("품사", pos_choices)
    keyword = st.text_input("검색 (단어/뜻/가나)")

    st.markdown("---")
    st.caption("학습 카드 제어")
    colb1, colb2, colb3 = st.columns(3)
    with colb1:
        prev_btn = st.button("◀ 이전")
    with colb2:
        rand_btn = st.button("🔀 랜덤")
    with colb3:
        next_btn = st.button("다음 ▶")

# =========================
# 필터 적용
# =========================
filtered = df[df["jlpt"] == jlpt].copy()
if pos_sel:
    filtered = filtered[filtered["pos"].isin(pos_sel)]
if keyword:
    mask = (
        filtered["word"].str.contains(keyword, case=False, na=False) |
        filtered["meaning_ko"].str.contains(keyword, case=False, na=False) |
        filtered["kana"].str.contains(keyword, case=False, na=False)
    )
    filtered = filtered[mask]

# =========================
# 헤더
# =========================
st.title("🇯🇵 일본어 단어 학습 대시보드 (N5)")
st.caption("연상 암기 + 예문 + 퀴즈 모드 포함")

# =========================
# 학습 카드
# =========================
st.subheader("📚 학습 카드")

if len(filtered) == 0:
    st.info("조건에 맞는 단어가 없습니다. 사이드바 필터를 조정해 주세요.")
else:
    # 카드 인덱스 상태 관리
    if "card_idx" not in st.session_state:
        st.session_state.card_idx = 0

    if prev_btn:
        st.session_state.card_idx = (st.session_state.card_idx - 1) % len(filtered)
    if next_btn:
        st.session_state.card_idx = (st.session_state.card_idx + 1) % len(filtered)
    if rand_btn:
        st.session_state.card_idx = pick_random_index(len(filtered))

    idx = min(st.session_state.card_idx, len(filtered) - 1)
    row = filtered.iloc[idx]

    st.markdown(f"### **{row['word']}** ({row['kana']}) — {row['meaning_ko']}")
    st.write(f"**발음 연상:** {row['mnemonic_sound']}")
    st.write(f"**이미지:** {row['mnemonic_image']}")
    st.write(f"**스토리:** {row['mnemonic_story']}")
    st.write(f"**예문:** {row['example_jp']}")
    st.write(f"➡ {row['example_ko']}")

st.divider()

# =========================
# 퀴즈 모드
# =========================
st.subheader("📝 퀴즈 모드 (뜻 고르기)")

num_opts = 4
pool = df if len(df) >= num_opts else df.copy()
sample = pool.sample(num_opts, replace=len(pool) < num_opts) if len(pool) else df.head(1)
answer_row = sample.sample(1).iloc[0]

st.write(f"**문제:** `{answer_row['word']}` ({answer_row['kana']}) 의 한국어 뜻은?")
options = sample["meaning_ko"].tolist()
random.shuffle(options)
choice = st.radio("정답 선택", options, index=None, horizontal=True if len(options) <= 4 else False)

if st.button("정답 확인"):
    if choice == answer_row["meaning_ko"]:
        st.success("정답! 🎉")
    else:
        st.error(f"오답 😅  정답은 **{answer_row['meaning_ko']}**")
    st.caption(f"예문: {answer_row['example_jp']}\n➜ {answer_row['example_ko']}")

st.divider()

# =========================
# 단어 목록 & 다운로드
# =========================
st.subheader("📋 단어 목록")
table_cols = ["word","kana","meaning_ko","pos","mnemonic_sound","example_jp","example_ko"]
show_cols = [c for c in table_cols if c in filtered.columns]
st.dataframe(filtered[show_cols], use_container_width=True)

st.download_button(
    "현재 목록 CSV 다운로드",
    filtered.to_csv(index=False).encode("utf-8-sig"),
    "n5_filtered.csv",
    "text/csv",
)
