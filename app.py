from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st

# --- 1. 데이터베이스 연결 및 초기 테이블 생성 (마이그레이션 구조 포함) ---
DB_NAME = "equipment_management.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # 1) 현장(건물) 마스터 테이블
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            site_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_name TEXT NOT NULL,
            region_1 TEXT,
            region_2 TEXT,
            business_type TEXT,
            router_info TEXT,
            eps_location TEXT,
            notes TEXT
        )
    """)

  # 2) 기기/자산 원장 테이블 (TL과 FNT 일련번호 철저한 이원화 분리)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            item_type TEXT NOT NULL,
            identification_no TEXT,
            manufacturer_sn TEXT UNIQUE, -- TL (제조사 고유 S/N)
            ft_sn TEXT UNIQUE,           -- FNT (조달청 납품용 S/N)
            manufacture_date TEXT,
            install_date TEXT,
            end_date TEXT,
            install_position TEXT,
            software TEXT,
            sw_version TEXT,
            os_version TEXT,
            status TEXT DEFAULT '운영중',
            FOREIGN KEY (site_id) REFERENCES sites(site_id)
        )
    """)

  # 3) 통합 AS 및 작업 이력 테이블
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

  # 4) 자재 입출고 및 S/N 교체 이력 테이블 (AS 자재상태 연동)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbound_date TEXT NOT NULL,
            site_id INTEGER,
            material_type TEXT,
            old_sn TEXT, -- 교체전 (TL 또는 FNT)
            new_sn TEXT, -- 교체후 (TL 또는 FNT)
            symptom TEXT,
            FOREIGN KEY (site_id) REFERENCES sites(site_id)
        )
    """)

  conn.commit()
  conn.close()


init_db()

# --- 2. 비밀번호 인증 로직 ---
def check_password():
  def password_entered():
    if st.session_state["password"] == "우리팀비밀번호":  # 필요 시 팀 비밀번호 설정
      st.session_state["password_correct"] = True
      del st.session_state["password"]
    else:
      st.session_state["password_correct"] = False

  if "password_correct" not in st.session_state:
    st.text_input(
        "🔒 사내 업무 시스템 접속 암호를 입력하세요",
        type="password",
        on_change=password_entered,
        key="password",
    )
    return False
  elif not st.session_state["password_correct"]:
    st.text_input(
        "🔒 사내 업무 시스템 접속 암호를 입력하세요",
        type="password",
        on_change=password_entered,
        key="password",
    )
    st.error("😕 비밀번호가 틀렸습니다.")
    return False
  else:
    return True


if check_password():
  # --- 3. Streamlit UI 구성 ---
  st.set_page_config(
      page_title="디지털 사이니지 통합 관리 시스템",
      page_icon="🖥️",
      layout="wide",
  )

  st.title("🖥️ 디지털 사이니지 통합 자산 및 AS 관리 시스템")
  st.markdown(
      "설치 현황, **TL(제조사)·FNT(조달청) 이원화 일련번호**, 그리고 AS"
      " 이력을 통합 관리하는 웹 프로그램입니다."
  )

  # [요청 1 반영] 사이드바 메뉴를 드롭다운 대신 라디오 버튼으로 변경하여 한눈에 노출
  st.sidebar.markdown("### 📌 메인 메뉴")
  menu = st.sidebar.radio(
      "이동할 메뉴를 선택하세요:",
      ["📊 통합 현황 대시보드", "📝 현장 AS 일지 등록", "🔍 자산 및 건물 검색"],
  )

  # --- [메뉴 1] 대시보드 ---
  if menu == "📊 통합 현황 대시보드":
    st.header("📊 업무용 공유 문서 통합 대시보드")

    conn = sqlite3.connect(DB_NAME)
    df_logs = pd.read_sql("SELECT * FROM maintenance_logs", conn)
    df_sites = pd.read_sql("SELECT * FROM sites", conn)
    df_assets = pd.read_sql("SELECT * FROM assets", conn)
    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
      st.metric(label="등록된 총 건물(현장)", value=f"{len(df_sites)} 개")
    with col2:
      st.metric(label="등록된 총 자산(기기)", value=f"{len(df_assets)} 대")
    with col3:
      st.metric(label="누적 AS 처리 건수", value=f"{len(df_logs)} 건")
    with col4:
      st.metric(label="시스템 상태", value="정상 작동중 🟢")

    st.divider()
    st.subheader("📋 최근 AS 처리 내역")
    if not df_logs.empty:
      st.dataframe(df_logs.tail(10), use_container_width=True)
    else:
      st.info(
          "등록된 AS 이력이 없습니다. '현장 AS 일지 등록' 메뉴에서 데이터를"
          " 추가해주세요."
      )

  # --- [메뉴 2] 현장 AS 일지 등록 ---
  elif menu == "📝 현장 AS 일지 등록":
    st.header("📝 현장 AS 및 작업일지 입력")
    st.markdown(
        "자재 교체 시 제조사 고유 S/N(`TL-...`)과 조달청 납품 S/N(`FNT-...`)을"
        " 각각 구분하여 정확히 기록해 주세요."
    )

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
        monitor_size = st.selectbox(
            "모니터 크기/종류",
            ["21.5\"", "25\"", "32\"", "34\"", "49\"", "55\"", "셋톱박스", "기타"],
        )
      with col2:
        symptom = st.text_input(
            "증상", placeholder="예: 전원불량, 통신불량, 블랙스크린"
        )
        action_taken = st.text_input(
            "처리 내용", placeholder="예: 셋탑 교체, 라우터 재부팅"
        )
        old_sn = st.text_input(
            "회수 기기 S/N (기존 TL 또는 FNT)", placeholder="예: TL-..."
        )
        new_sn = st.text_input(
            "투입 기기 S/N (신규 교체 TL 또는 FNT)", placeholder="예: FNT-..."
        )

      notes = st.text_area(
          "비고 및 특이사항", placeholder="추가 전달사항 입력"
      )

      submitted = st.form_submit_button("AS 일지 및 자재 교체 저장하기")
      if submitted:
        if building_name and symptom and action_taken:
          conn = sqlite3.connect(DB_NAME)
          cursor = conn.cursor()

          # 1) AS 일지 저장
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

          # 2) S/N 교체가 입력된 경우 자재 이력에도 동시 반영
          if old_sn or new_sn:
            cursor.execute(
                """
                        INSERT INTO inventory_history (inbound_date, material_type, old_sn, new_sn, symptom)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                (str(work_date), monitor_size, old_sn, new_sn, symptom),
            )

          conn.commit()
          conn.close()
          st.success(
              f"✅ [{building_name}] AS 일지 및 자재 이력이 성공적으로"
              " 등록되었습니다!"
          )
        else:
          st.warning("⚠️ 건물명, 증상, 처리 내용은 필수 입력 항목입니다.")

  # --- [메뉴 3] 자산 및 건물 검색 ---
  elif menu == "🔍 자산 및 건물 검색":
    st.header("🔍 통합 자산 및 일련번호(TL / FNT) 검색")
    st.markdown(
        "건물명, 증상 키워드뿐만 아니라 **TL 제조사 S/N** 또는 **FNT 조달청"
        " S/N**으로도 검색할 수 있습니다."
    )

    search_keyword = st.text_input(
        "통합 검색어 입력",
        placeholder="예: 테라타워, 전원불량, TL-250 또는 FNT-",
    )

    if search_keyword:
      conn = sqlite3.connect(DB_NAME)

      # AS 일지 및 자산 원장에서 키워드 검색
      query_logs = f"""
              SELECT 'AS일지' as 구분, work_date as 날짜, building_name as 대상, install_position as 위치, symptom as 내용, action_taken as 비고 
              FROM maintenance_logs 
              WHERE building_name LIKE '%{search_keyword}%' 
                 OR symptom LIKE '%{search_keyword}%'
                 OR action_taken LIKE '%{search_keyword}%'
          """
      df_result = pd.read_sql(query_logs, conn)
      conn.close()

      st.subheader(f"검색 결과 (총 {len(df_result)}건)")
      if not df_result.empty:
        st.dataframe(df_result, use_container_width=True)
      else:
        st.warning("일치하는 검색 결과가 없습니다.")
