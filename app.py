import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# --- 1. 데이터베이스 연결 및 초기 테이블 생성 ---
DB_NAME = "equipment_management.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # 현장 테이블
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            site_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_name TEXT NOT NULL,
            region_1 TEXT,
            region_2 TEXT,
            business_type TEXT,
            notes TEXT
        )
    """)

  # AS 일지 테이블
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_date TEXT NOT NULL,
            building_name TEXT NOT NULL,
            install_position TEXT,
            monitor_size TEXT,
            symptom TEXT NOT NULL,
            action_taken TEXT NOT NULL,
            notes TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()

# --- 2. Streamlit UI 구성 ---
st.set_page_config(
    page_title="디지털 사이니지 통합 관리 시스템", page_icon="🖥️", layout="wide"
)

st.title("🖥️ 디지털 사이니지 통합 자산 및 AS 관리 시스템")
st.markdown(
    "설치 현황, 자산 시리얼 번호, 그리고 AS 일지를 통합 관리하는 웹"
    " 프로그램입니다."
)

# 사이드바 메뉴
menu = st.sidebar.selectbox(
    "메뉴 선택", ["📊 통합 현황 대시보드", "📝 현장 AS 일지 등록", "🔍 자산 및 건물 검색"]
)

# --- [메뉴 1] 대시보드 ---
if menu == "📊 통합 현황 대시보드":
  st.header("📊 업무용 공유 문서 통합 대시보드")

  conn = sqlite3.connect(DB_NAME)
  df_logs = pd.read_sql("SELECT * FROM maintenance_logs", conn)
  df_sites = pd.read_sql("SELECT * FROM sites", conn)
  conn.close()

  col1, col2, col3 = st.columns(3)
  with col1:
    st.metric(
        label="등록된 총 건물(현장) 수", value=f"{len(df_sites)} 개"
    )
  with col2:
    st.metric(label="누적 AS 접수/처리 건수", value=f"{len(df_logs)} 건")
  with col3:
    st.metric(label="시스템 상태", value="정상 작동중 🟢")

  st.divider()
  st.subheader("최근 AS 처리 내역")
  if not df_logs.empty:
    st.dataframe(df_logs.tail(10), use_container_width=True)
  else:
    info_col, _ = st.columns([1, 1])
    with info_col:
      st.info(
          "등록된 AS 이력이 없습니다. '현장 AS 일지 등록' 메뉴에서 데이터를"
          " 추가해주세요."
      )

# --- [메뉴 2] 현장 AS 일지 등록 ---
elif menu == "📝 현장 AS 일지 등록":
  st.header("📝 현장 AS 및 작업일지 입력")

  with st.form("as_form"):
    col1, col2 = st.columns(2)
    with col1:
      work_date = st.date_input("작업일", datetime.today())
      building_name = st.text_input(
          "건물명 (예: 문정역 테라타워)", placeholder="건물명을 입력하세요"
      )
      install_position = st.text_input(
          "설치 위치 (예: ev13, L층 로비)", placeholder="위치 입력"
      )
    with col2:
      monitor_size = st.selectbox(
          "모니터 크기", ["21.5\"", "25\"", "32\"", "34\"", "49\"", "55\"", "기타"]
      )
      symptom = st.text_input(
          "증상", placeholder="예: 전원불량, 통신불량, 블랙스크린"
      )
      action_taken = st.text_input(
          "처리 내용", placeholder="예: 셋탑 교체, 라우터 재부팅"
      )

    notes = st.text_area("비고 및 특이사항", placeholder="추가 전달사항 입력")

    submitted = st.form_submit_button("AS 일지 저장하기")
    if submitted:
      if building_name and symptom and action_taken:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
                    INSERT INTO maintenance_logs (work_date, building_name, install_position, monitor_size, symptom, action_taken, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
            (
                str(work_date),
                building_name,
                install_position,
                monitor_size,
                symptom,
                action_taken,
                notes,
            ),
        )
        conn.commit()
        conn.close()
        st.success(
            f"✅ [{building_name}] AS 일지가 성공적으로 등록되었습니다!"
        )
      else:
        st.warning("⚠️ 건물명, 증상, 처리 내용은 필수 입력 항목입니다.")

# --- [메뉴 3] 자산 및 건물 검색 ---
elif menu == "🔍 자산 및 건물 검색":
  st.header("🔍 통합 자산 및 AS 이력 검색")

  search_keyword = st.text_input(
      "검색어 입력 (건물명 또는 증상 키워드)", placeholder="예: 테라타워 또는 전원불량"
  )

  if search_keyword:
    conn = sqlite3.connect(DB_NAME)
    query = f"""
            SELECT * FROM maintenance_logs 
            WHERE building_name LIKE '%{search_keyword}%' 
               OR symptom LIKE '%{search_keyword}%'
               OR action_taken LIKE '%{search_keyword}%'
        """
    df_result = pd.read_sql(query, conn)
    conn.close()

    st.subheader(f"검색 결과 ({len(df_result)}건)")
    if not df_result.empty:
      st.dataframe(df_result, use_container_width=True)
    else:
      st.warning("일치하는 검색 결과가 없습니다.")
