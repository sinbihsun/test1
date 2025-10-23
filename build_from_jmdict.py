import requests
import gzip
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path

JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"  # JMdict 다운로드 URL
OUT_CSV = "n5_vocab.csv"  # 저장할 CSV 파일 이름

def fetch_jmdict_xml():
    r = requests.get(JMDICT_URL)
    r.raise_for_status()
    return gzip.decompress(r.content)

def parse_entries(xml_bytes):
    root = ET.fromstring(xml_bytes)
    for entry in root.findall("entry"):
        # 표제어 및 읽기
        word = entry.find(".//k_ele/keb").text if entry.find(".//k_ele/keb") is not None else ""
        kana = entry.find(".//r_ele/reb").text if entry.find(".//r_ele/reb") is not None else ""
        yield word, kana

def build_csv(target_count=300):  # 기본값 300개의 단어로 변경
    # JMdict 데이터를 CSV로 변환
    xml_bytes = fetch_jmdict_xml()
    rows = []
    for word, kana in parse_entries(xml_bytes):
        rows.append({"word": word, "kana": kana, "meaning_ko": "", "pos": "", "jlpt": "N5"})
        
        # 단어 개수가 target_count에 도달하면 종료
        if len(rows) >= target_count:
            break

    # n5_vocab.csv 파일로 저장
    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[INFO] Saved {OUT_CSV} with {len(df)} rows")
    return OUT_CSV

if __name__ == "__main__":
    build_csv(target_count=300)  # 기본 300개 단어로 설정
