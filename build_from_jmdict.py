# build_from_jmdict.py
# JMdict(EDRDG) 공개 데이터 → n5_vocab.csv 생성기
# 라이선스 고지: JMdict/EDICT dictionary files are the property of the Electronic Dictionary Research and Development Group,
# and are used in conformance with the Group's licence. (CC BY-SA)
import gzip
import io
import re
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

JMDICT_URL = "https://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"  # 영문 gloss 포함 버전
OUT_CSV   = "n5_vocab.csv"  # 앱에서 읽는 파일명과 동일하게

# POS 매핑(간단화): JMdict pos 태그(ex. "v1", "adj-i", "n") → 한국어 표기
POS_MAP = {
    "n": "명사",
    "adj-i": "형용사(i)",
    "adj-na": "형용동사(na)",
    "v1": "동사(1단)",
    "v5": "동사(5단)",
    "v5u": "동사(5단)",
    "v5k": "동사(5단)",
    "v5s": "동사(5단)",
    "v5t": "동사(5단)",
    "v5r": "동사(5단)",
    "vs": "사변동사(suru)",
    "vk": "동사(kuru)",
    "aux": "조동사",
    "prt": "조사",
}

# “기초/상용어” 판정: JMdict <pri> 태그로 제공되는 우선순위/빈도 표기
# - ichi1, news1, spec1, gai1, nf01~nf12 정도를 “매우 자주”로 간주
COMMON_PRI_RE = re.compile(r"^(ichi1|news1|spec1|gai1|nf0[1-9]|nf1[0-2])$")

def fetch_jmdict_xml() -> bytes:
    r = requests.get(JMDICT_URL, timeout=60)
    r.raise_for_status()
    return gzip.decompress(r.content)

def parse_entries(xml_bytes: bytes, limit: int | None = None):
    root = ET.fromstring(xml_bytes)
    # <entry> 단위
    for i, ent in enumerate(root.findall("entry")):
        # 표제어: <k_ele><keb> (없을 수도 있음 → 읽기만 있는 단어)
        kebs = [keb.text for k_ele in ent.findall("k_ele") for keb in k_ele.findall("keb")]
        # 읽기: <r_ele><reb>
        rebs = [reb.text for r_ele in ent.findall("r_ele") for reb in r_ele.findall("reb")]
        # priority: <k_ele><ke_pri>, <r_ele><re_pri>
        pris = [p.text for k_ele in ent.findall("k_ele") for p in k_ele.findall("ke_pri")]
        pris += [p.text for r_ele in ent.findall("r_ele") for p in r_ele.findall("re_pri")]

        # 의미/품사: sense마다 gloss/pos
        senses = []
        for s in ent.findall("sense"):
            poss = [p.text for p in s.findall("pos")]
            gloss_en = [g.text for g in s.findall("gloss") if (g.text and (g.attrib.get("lang") in (None, "eng")))]
            # 한국어 뜻 직접 제공 X → 우선 영문 gloss를 한국어로 적당히 보조(초기엔 빈칸으로 두고 UI상 학습/편집 권장)
            senses.append({"pos": poss, "gloss_en": gloss_en})

        yield {
            "kebs": kebs,
            "rebs": rebs,
            "pris": pris,
            "senses": senses,
        }
        if limit and i+1 >= limit:
            return

def is_common(pris: list[str]) -> bool:
    return any(COMMON_PRI_RE.match(p or "") for p in pris or [])

def first_pos_ko(pos_list: list[str]) -> str:
    if not pos_list:
        return ""
    # 여러 pos 중 첫 번째만 간단 매핑
    for p in pos_list:
        base = p.split("-")[0]
        label = POS_MAP.get(p, POS_MAP.get(base))
        if label:
            return label
    return pos_list[0]  # 매핑되지 않으면 원문

def build_csv(target_count=600):
    xml_bytes = fetch_jmdict_xml()
    rows = []
    for ent in parse_entries(xml_bytes):
        if not ent["rebs"] and not ent["kebs"]:
            continue

        # 기초/상용어 우선
        common = is_common(ent["pris"])

        # 대표 표기(표제어가 있으면 그중 하나, 없으면 읽기)
        word = (ent["kebs"][0] if ent["kebs"] else ent["rebs"][0]).strip()
        # 대표 읽기
        kana = (ent["rebs"][0] if ent["rebs"] else "").strip()

        # 대표 뜻/품사 (첫 sense 기준 간소화)
        if ent["senses"]:
            s0 = ent["senses"][0]
            pos_ko = first_pos_ko(s0["pos"])
            # gloss_en 여러 개면 ; 로 합치기
            meaning_en = "; ".join(s0["gloss_en"])[:300]
        else:
            pos_ko = ""
            meaning_en = ""

        # 초안: 한국어 뜻은 공백(또는 영문 → 한글 번역 파이프라인을 추후 붙일 수 있음)
        meaning_ko = ""

        rows.append({
            "word": word,
            "kana": kana,
            "meaning_ko": meaning_ko,
            "meaning_en": meaning_en,
            "pos": pos_ko or "",
            "jlpt": "N5*",   # 임시 표기(빈도/상용어 기반 코어셋) → 실제 JLPT 리스트 병합 시 갱신
            "is_common": common,
            # 연상/예문 필드(초기 빈칸, 앱에서 편집/보강 가능)
            "mnemonic_sound": "",
            "mnemonic_image": "",
            "mnemonic_story": "",
            "example_jp": "",
            "example_ko": "",
        })

    # 상용어 우선 정렬 → 상위 target_count 잘라내기
    df = pd.DataFrame(rows)
    df = df.sort_values(["is_common", "word"], ascending=[False, True]).head(target_count).reset_index(drop=True)

    # 파일 저장
    out = Path(OUT_CSV)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[OK] Saved {out} with {len(df)} rows at {datetime.now()}")
    return out

if __name__ == "__main__":
    build_csv(target_count=600)
