# app.py — 🇯🇵 일본어 단어 학습 대시보드 (N5) + 통계 + TTS + 모바일 최적화
import streamlit as st
import pandas as pd
from pathlib import Path
import random
from io import BytesIO

st.set_page_config(page_title="🇯🇵 일본어 단어 학습 대시보드 (N5)", layout="wide")

# =========================
# 데이터 로더 (견고한 경로 탐색)
# =========================
@st.cache_data(show_spinner=False)
def load_data():
    candidates = [
        Path(__file__).resolve().parent / "n5_vocab.csv",
        Path.cwd() / "n5_vocab.csv",
        Path(__file__).resolve().parent / "data" / "n5_vocab.csv",
    ]
    checked = []
    for p in candidates:
        checked.append(str(p))
        if p.exists():
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

def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    need = ["word","kana","meaning_ko","pos","jlpt",
            "mnemonic_sound","mnemonic_image","mnemonic_story",
            "example_jp","example_ko"]
    for c in need:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str)
    return df

# =========================
# TTS (gTTS 사용, 캐시)
# =========================
@st.cache_data(show_spinner=False)
def tts_bytes(text: str, lang: str = "ja"):
    # gTTS는 인터넷 연결 필요 (Streamlit Cloud OK)
    from gtts import gTTS
    if not text or text.strip() == "":
        return None
    tts = gTTS(text=text, lang=lang)
    buf = BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()

# =========================
# 학습 진행 상태 저장소
# =========================
def init_state():
    if "progress" not in st.session_state:
        # key: (word,kana) -> {"status": "known"/"hold"}
        st.session_state.progress = {}
    if "card_idx" not in st.session_state:
        st.session_state.card_idx = 0

def set_status(row_key, status):
    st.session_state.progress[row_key] = {"status": status}

def get_status(row_key):
    d = st.session_state.progress.get(row_key, {})
    return d.get("status")

def export_progress_df(df):
    # base info + status merge
    base = df[["word","kana","meaning_ko","pos","jlpt"]].copy()
    statuses = []
    for _, r in base.iterrows():
        key = (r["word"], r["kana"])
        statuses.append(get_status(key))
    base["status"] = statuses
    return base

# =========================
# 데이터 로드
# =========================
df_raw = load_data()
df = ensure_columns(df_raw)
init_state()

# =========================
# 사이드바 (모바일 친화)
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
        prev_btn = st.button("◀ 이전", use_container_width=True)
    with colb2:
        rand_btn = st.button("🔀 랜덤", use_container_width=True)
    with colb3:
        next_btn = st.button("다음 ▶", use_container_width=True)

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
st.caption("연상 암기 + 예문 + 퀴즈 + 학습통계 + TTS")

# =========================
# 학습 카드
# =========================
st.subheader("📚 학습 카드")

if len(filtered) == 0:
    st.info("조건에 맞는 단어가 없습니다. 사이드바 필터를 조정해 주세요.")
else:
    if prev_btn:
        st.session_state.card_idx = (st.session_state.card_idx - 1) % len(filtered)
    if next_btn:
        st.session_state.card_idx = (st.session_state.card_idx + 1) % len(filtered)
    if rand_btn:
        st.session_state.card_idx = 0 if len(filtered) <= 1 else random.randrange(len(filtered))

    idx = min(st.session_state.card_idx, len(filtered) - 1)
    row = filtered.iloc[idx]
    row_key = (row["word"], row["kana"])
    status_now = get_status(row_key)

    # 카드 레이아웃 (모바일 고려: 한 열로도 보기 좋게)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"### **{row['word']}** ({row['kana']}) — {row['meaning_ko']}")
        st.write(f"**발음 연상:** {row['mnemonic_sound']}")
        st.write(f"**이미지:** {row['mnemonic_image']}")
        st.write(f"**스토리:** {row['mnemonic_story']}")
        st.write(f"**예문:** {row['example_jp']}")
        st.write(f"➡ {row['example_ko']}")

        # 상태 버튼 (큰 버튼, 모바일 손쉬운 터치)
        colk, colh, _ = st.columns([1,1,2])
        with colk:
            if st.button("✅ 암기", use_container_width=True):
                set_status(row_key, "known")
        with colh:
            if st.button("⏳ 보류", use_container_width=True):
                set_status(row_key, "hold")
        if status_now:
            st.caption(f"현재 상태: **{status_now}**")

    with c2:
        st.markdown("#### 🔊 발음(TTS)")
        if st.button("단어 재생", use_container_width=True):
            audio = tts_bytes(row["word"])
            if audio:
                st.audio(audio, format="audio/mp3")
        if st.button("예문 재생", use_container_width=True):
            audio = tts_bytes(row["example_jp"])
            if audio:
                st.audio(audio, format="audio/mp3")

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
# 학습 통계 (암기율)
# =========================
st.subheader("📈 학습 통계")

prog_df = export_progress_df(df)
# 집계
summary = prog_df.groupby(["jlpt","pos","status"], dropna=False).size().reset_index(name="count")
st.dataframe(summary, use_container_width=True)

# 레벨별 암기율
lvl = st.selectbox("레벨별 암기율 보기", sorted(df["jlpt"].unique().tolist()))
lvl_df = prog_df[prog_df["jlpt"] == lvl]
total = len(lvl_df)
known = (lvl_df["status"] == "known").sum()
rate = (known / total * 100) if total else 0.0
st.metric(f"{lvl} 암기율", f"{rate:.1f}% ( {known} / {total} )")

# 진도 저장/불러오기
colp1, colp2 = st.columns(2)
with colp1:
    st.download_button(
        "📥 학습 진도 CSV 다운로드",
        prog_df.to_csv(index=False).encode("utf-8-sig"),
        "progress_export.csv",
        "text/csv",
        use_container_width=True
    )
with colp2:
    uploaded = st.file_uploader("📤 저장했던 진도 불러오기 (CSV)", type=["csv"])
    if uploaded is not None:
        try:
            imp = pd.read_csv(uploaded, encoding="utf-8-sig")
            # 상태 로드
            for _, r in imp.iterrows():
                key = (str(r.get("word","")), str(r.get("kana","")))
                status = str(r.get("status","")).strip() or None
                if key != ("","") and status in {"known","hold"}:
                    set_status(key, status)
            st.success("학습 진도를 불러왔습니다!")
        except Exception as e:
            st.error(f"불러오기 실패: {e}")

st.divider()

# =========================
# 단어 목록 & 다운로드 (모바일 폭 자동맞춤)
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
    use_container_width=True
)
