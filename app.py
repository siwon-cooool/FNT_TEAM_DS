from datetime import datetime
import sqlite3
import urllib.parse
import pandas as pd
import streamlit as st

# --- 1. 페이지 설정 (반드시 최상단 위치) ---
st.set_page_config(
    page_title="디지털 사이니지 통합 관리 시스템", page_icon="🖥️", layout="wide"
)

# --- 2. 공유문서 연동 설정 ---
# 기준 공유문서: 설치현황
INSTALL_SHEET_ID = "12-GkUyvORMFkPenI5OdGQnUbVZKHGDsp4g6zgKqapEg"


@st.cache_data(ttl=60)
def load_google_sheet_by_name(sheet_name: str) -> pd.DataFrame:
  """공유문서(설치현황)에서 특정 시트 이름의 전체 데이터를 정확히 읽어오는 함수.

  상단 요약행(프로그램 현황 등)을 자동으로 건너뛰고 실제 헤더('No.' 또는
  '건물명')부터 파싱합니다.
  """
  encoded_name = urllib.parse.quote(sheet_name)
  url = f"https://docs.google.com/spreadsheets/d/{INSTALL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"

  try:
    raw_df = pd.read_csv(url, header=None, dtype=str)
  except Exception as e:
    st.error(f"시트 데이터를 불러오는 중 오류가 발생했습니다 ({sheet_name}): {e}")
    return pd.DataFrame()

  # 실제 테이블 헤더 행 찾기 ('No.' 또는 '건물명'이 포함된 행 탐색)
  header_idx = None
  for idx, row in raw_df.iterrows():
    row_vals = [str(v).strip() for v in row.values if pd.notna(v)]
    if "건물명" in row_vals or "No." in row_vals:
      header_idx = idx
      break

  if header_idx is None:
    return pd.DataFrame()

  # 헤더 설정 및 데이터 추출
  headers = [
      str(col).strip() if pd.notna(col) else f"Unnamed_{i}"
      for i, col in enumerate(raw_df.iloc[header_idx])
  ]
  df = raw_df.iloc[header_idx + 1 :].copy()
  df.columns = headers

  # 완전히 비어있는 열(Unnamed) 제거
  df = df.loc[:, ~df.columns.str.startswith("Unnamed_")]

  # '건물명'이 비어있거나 합계 행(숫자만 있는 하단 요약행 등) 제거
  if "건물명" in df.columns:
    df = df[df["건물명"].notna()]
    df = df[df["건물명"].str.strip() != ""]
    # 하단 총계 숫자만 적힌 행 필터링 (No.가 비어있고 건물명이 순수 숫자인 경우)
    if "No." in df.columns:
      df = df[~(df["No."].isna() & df["건물명"].str.strip().str.isdigit())]

  df = df.fillna("").reset_index(drop=True)
  return df


# --- 3. 로컬 데이터베이스 연결 및 초기 테이블 생성 ---
DB_NAME = "equipment_management.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # 1) 현장 AS 일지 테이블
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

  # 2) 자산관리 테이블 ('자재상태' 시트 구조)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS material_status (
            mat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbound_date TEXT NOT NULL,
            building_name TEXT NOT NULL,
            install_position TEXT,
            material_name TEXT,
            old_sn TEXT,   -- 제조사 S/N (TL) 또는 FNT
            new_sn TEXT,   -- 조달청 납품 S/N (FNT) 또는 TL
            symptom TEXT,
            notes TEXT
        )
    """)

  # 3) 설치이력관리 추가/수정 로컬 보완 테이블
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS installation_local_additions (
            add_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            building_name TEXT NOT NULL,
            region_1 TEXT,
            region_2 TEXT,
            install_count TEXT,
            install_date TEXT,
            program TEXT,
            version TEXT,
            ev_android TEXT,
            notes TEXT
        )
    """)

  conn.commit()
  conn.close()


init_db()


# --- 4. 비밀번호 인증 로직 (0000 고정) ---
def check_password():

  def password_entered():
    if st.session_state["password"] == "0000":
      st.session_state["password_correct"] = True
      del st.session_state["password"]
    else:
      st.session_state["password_correct"] = False

  if "password_correct" not in st.session_state:
    st.text_input(
        "🔒 개발 기간 접속 암호를 입력하세요 (초기 비밀번호: 0000)",
        type="password",
        on_change=password_entered,
        key="password",
    )
    return False
  elif not st.session_state["password_correct"]:
    st.text_input(
        "🔒 개발 기간 접속 암호를 입력하세요 (초기 비밀번호: 0000)",
        type="password",
        on_change=password_entered,
        key="password",
    )
    st.error("😕 비밀번호가 틀렸습니다. (0000 입력)")
    return False
  else:
    return True


if check_password():
  st.title("🖥️ 디지털 사이니지 통합 자산 및 AS 관리 시스템")
  st.markdown(
      "설치 현황, **TL(제조사)·FNT(조달청) 이원화 일련번호**, 그리고 AS"
      " 이력을 통합 관리하는 웹 프로그램입니다."
  )

  # --- 5. 사이드바 메인 메뉴 ---
  st.sidebar.markdown("### 📌 메인 메뉴")
  menu = st.sidebar.radio(
      "이동할 메뉴를 선택하세요:",
      [
          "📊 통합 현황 대시보드",
          "📝 현장 AS 일지 등록",
          "📦 자산관리",
          "🏢 설치이력관리",
      ],
  )

  # ==============================================================================
  # [메뉴 1] 통합 현황 대시보드
  # ==============================================================================
  if menu == "📊 통합 현황 대시보드":
    st.header("📊 업무용 공유 문서 통합 대시보드")

    conn = sqlite3.connect(DB_NAME)
    df_logs = pd.read_sql("SELECT * FROM maintenance_logs", conn)
    df_mat = pd.read_sql("SELECT * FROM material_status", conn)
    conn.close()

    # 주요 시트 실시간 카운트 집계
    df_office = load_google_sheet_by_name("오피스보드설치현황")
    df_build = load_google_sheet_by_name("구축설치현황")
    df_procure = load_google_sheet_by_name("조달설치")
    df_ari = load_google_sheet_by_name("ARI설치현황")

    total_sites = (
        len(df_office) + len(df_build) + len(df_procure) + len(df_ari)
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
      st.metric(
          label="주요 설치 현장 (오피스/구축/조달/ARI)",
          value=f"{total_sites} 개소",
      )
    with col2:
      st.metric(
          label="자재 교체/입고 건수", value=f"{len(df_mat)} 건"
      )
    with col3:
      st.metric(label="누적 AS 처리 건수", value=f"{len(df_logs)} 건")
    with col4:
      st.metric(label="공유문서 연동 상태", value="실시간 동기화 🟢")

    st.divider()

    tab_a, tab_b = st.tabs(["📋 최근 AS 일지", "📦 최근 자재상태 변동"])
    with tab_a:
      if not df_logs.empty:
        st.dataframe(
            df_logs.sort_values(by="log_id", ascending=False).head(15),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.info("등록된 AS 이력이 없습니다.")

    with tab_b:
      if not df_mat.empty:
        st.dataframe(
            df_mat.sort_values(by="mat_id", ascending=False).head(15),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.info("등록된 자재 이력이 없습니다.")

  # ==============================================================================
  # [메뉴 2] 현장 AS 일지 등록
  # ==============================================================================
  elif menu == "📝 현장 AS 일지 등록":
    st.header("📝 현장 AS 및 작업일지 입력")
    st.markdown(
        "현장 AS 처리 내역을 기록합니다. **자재 교체가 동반된 경우** 일련번호를"
        " 입력하시면 `자산관리(자재상태)`에도 실시간 동시 반영됩니다."
    )

    with st.form("as_form"):
      col1, col2 = st.columns(2)
      with col1:
        work_date = st.date_input("작업일", datetime.today())
        building_name = st.text_input(
            "건물명", placeholder="예: 문정역테라타워"
        )
        install_position = st.text_input(
            "설치 위치", placeholder="예: ev13, L층, B1"
        )
        monitor_size = st.selectbox(
            "모니터( \" )",
            [
                "21.5\"",
                "25\"",
                "32\"",
                "34\"",
                "43\"",
                "49\"",
                "55\"",
                "65\"",
                "75\"",
                "셋탑/기타",
            ],
        )
      with col2:
        symptom = st.text_input(
            "증상", placeholder="예: 통신불량, 전원불량, 블랙스크린"
        )
        action_taken = st.text_input(
            "처리내용", placeholder="예: 모니터 교체, 라우터 전원 재연결"
        )
        old_sn = st.text_input(
            "교체전 일련번호 (회수 S/N - TL 또는 FNT)",
            placeholder="예: TL-202112160050",
        )
        new_sn = st.text_input(
            "교체후 일련번호 (투입 S/N - TL 또는 FNT)",
            placeholder="예: FNT-202512260001",
        )

      notes = st.text_area("비고", placeholder="추가 전달사항 입력")

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

          if old_sn or new_sn:
            cursor.execute(
                """
                            INSERT INTO material_status (inbound_date, building_name, install_position, material_name, old_sn, new_sn, symptom, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                (
                    str(work_date),
                    building_name,
                    install_position,
                    monitor_size.replace('"', ""),
                    old_sn,
                    new_sn,
                    symptom,
                    notes,
                ),
            )

          conn.commit()
          conn.close()
          st.success(
              f"✅ [{building_name}] AS 일지가 실시간 저장되었습니다!"
          )
        else:
          st.warning("⚠️ 건물명, 증상, 처리내용은 필수 입력 항목입니다.")

  # ==============================================================================
  # [메뉴 3] 자산관리
  # ==============================================================================
  elif menu == "📦 자산관리":
    st.header("📦 자산관리 (자재상태 및 일련번호 교체 원장)")
    st.markdown(
        "제조사 S/N(`TL-...`)과 조달청 납품 S/N(`FNT-...`)의 입출고 및 교체"
        " 이력을 실시간 관리합니다."
    )

    tab1, tab2 = st.tabs(["📋 자재상태 전체 조회 및 편집", "➕ 자재 입출고/교체 신규 등록"])

    with tab1:
      search_mat = st.text_input(
          "🔍 자재 및 일련번호 검색",
          placeholder="건물명, 자재명, S/N, 증상 키워드 입력...",
      )

      conn = sqlite3.connect(DB_NAME)
      if search_mat:
        query = """
                    SELECT 
                        mat_id AS "No.",
                        inbound_date AS "AS입고일",
                        building_name AS "건물명",
                        install_position AS "설치 위치",
                        material_name AS "자재명",
                        old_sn AS "교체전 일련번호",
                        new_sn AS "교체후 일련번호",
                        symptom AS "증상",
                        notes AS "비고"
                    FROM material_status
                    WHERE building_name LIKE ? OR material_name LIKE ? OR old_sn LIKE ? OR new_sn LIKE ? OR symptom LIKE ?
                    ORDER BY inbound_date DESC, mat_id DESC
                """
        lp = f"%{search_mat}%"
        df_mat = pd.read_sql(query, conn, params=(lp, lp, lp, lp, lp))
      else:
        query = """
                    SELECT 
                        mat_id AS "No.",
                        inbound_date AS "AS입고일",
                        building_name AS "건물명",
                        install_position AS "설치 위치",
                        material_name AS "자재명",
                        old_sn AS "교체전 일련번호",
                        new_sn AS "교체후 일련번호",
                        symptom AS "증상",
                        notes AS "비고"
                    FROM material_status
                    ORDER BY inbound_date DESC, mat_id DESC
                """
        df_mat = pd.read_sql(query, conn)
      conn.close()

      st.write(f"총 **{len(df_mat)}** 건 조회됨 (표를 직접 수정하면 실시간 반영됩니다)")
      st.data_editor(
          df_mat,
          use_container_width=True,
          hide_index=True,
          num_rows="dynamic",
          key="mat_editor",
      )

    with tab2:
      st.subheader("➕ 자재상태 신규 등록")
      with st.form("material_form"):
        c1, c2 = st.columns(2)
        with c1:
          inbound_date = st.date_input("AS입고일", datetime.today())
          m_building = st.text_input("건물명", placeholder="예: 서울숲에이원")
          m_position = st.text_input("설치 위치", placeholder="예: B5층")
          m_name = st.text_input("자재명", placeholder="예: 34, 25, 셋탑")
        with c2:
          m_old_sn = st.text_input("교체전 일련번호", placeholder="예: TL-...")
          m_new_sn = st.text_input("교체후 일련번호", placeholder="예: FNT-...")
          m_symptom = st.text_input("증상", placeholder="예: 블랙스크린")
          m_notes = st.text_input("비고", placeholder="특이사항")

        if st.form_submit_button("자재상태 저장하기"):
          if m_building:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                """
                            INSERT INTO material_status (inbound_date, building_name, install_position, material_name, old_sn, new_sn, symptom, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                (
                    str(inbound_date),
                    m_building,
                    m_position,
                    m_name,
                    m_old_sn,
                    m_new_sn,
                    m_symptom,
                    m_notes,
                ),
            )
            conn.commit()
            conn.close()
            st.success("✅ 실시간 저장되었습니다!")
          else:
            st.warning("⚠️ 건물명은 필수입니다.")

  # ==============================================================================
  # [메뉴 4] 설치이력관리 (공유문서 '설치현황' 각 시트 전체 데이터 직접 연동)
  # ==============================================================================
  elif menu == "🏢 설치이력관리":
    st.header("🏢 설치이력관리 (설치현황 공유문서 실시간 연동)")

    SHEET_MENUS = [
        "오피스보드설치현황",
        "구축설치현황",
        "조달설치",
        "ARI설치현황",
        "칩방식설치현황",
        "타래커피설치현황",
        "전통시장설치현황",
        "식자재설치현황",
        "프로그램교체일정",
    ]

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 설치이력관리")
    selected_sheet = st.sidebar.radio(
        "하부 시트를 선택하세요:", SHEET_MENUS
    )

    col_title, col_btn = st.columns([4, 1])
    with col_title:
      st.subheader(f"📑 [설치이력관리 - {selected_sheet}] 전체 데이터")
    with col_btn:
      if st.button("🔄 공유문서 새로고침"):
        st.cache_data.clear()
        st.rerun()

    # 공유문서에서 해당 시트 전체 데이터 읽어오기
    df_sheet = load_google_sheet_by_name(selected_sheet)

    # 로컬 DB에 추가된 신규 행이 있다면 병합 표시
    conn = sqlite3.connect(DB_NAME)
    df_local = pd.read_sql(
        "SELECT * FROM installation_local_additions WHERE category = ?",
        conn,
        params=(selected_sheet,),
    )
    conn.close()

    if not df_local.empty and not df_sheet.empty:
      local_mapped = pd.DataFrame()
      local_mapped["No."] = [
          f"신규-{i+1}" for i in range(len(df_local))
      ]
      if "건물명" in df_sheet.columns:
        local_mapped["건물명"] = df_local["building_name"]
      if "지역1" in df_sheet.columns:
        local_mapped["지역1"] = df_local["region_1"]
      if "지역2" in df_sheet.columns:
        local_mapped["지역2"] = df_local["region_2"]
      if "설치대수" in df_sheet.columns:
        local_mapped["설치대수"] = df_local["install_count"]
      if "설치일" in df_sheet.columns:
        local_mapped["설치일"] = df_local["install_date"]
      elif "설치일자" in df_sheet.columns:
        local_mapped["설치일자"] = df_local["install_date"]
      if "프로그램" in df_sheet.columns:
        local_mapped["프로그램"] = df_local["program"]
      if "version" in df_sheet.columns:
        local_mapped["version"] = df_local["version"]
      if "E/V android" in df_sheet.columns:
        local_mapped["E/V android"] = df_local["ev_android"]
      if "비고" in df_sheet.columns:
        local_mapped["비고"] = df_local["notes"]

      df_sheet = pd.concat([df_sheet, local_mapped], ignore_index=True).fillna(
          ""
      )

    # 통합 검색 필터 (모든 컬럼 대상)
    search_inst = st.text_input(
        f"🔍 [{selected_sheet}] 내 통합 검색 (건물명, 지역, 버전, 비고 등)",
        placeholder="검색어를 입력하세요...",
    )
    if search_inst and not df_sheet.empty:
      mask = df_sheet.apply(
          lambda row: row.astype(str)
          .str.contains(search_inst, case=False, na=False)
          .any(),
          axis=1,
      )
      df_sheet = df_sheet[mask]

    tab_list, tab_add = st.tabs(
        [f"📋 {selected_sheet} 목록 ({len(df_sheet)}건)", "➕ 신규 현장 추가"]
    )

    with tab_list:
      if not df_sheet.empty:
        st.caption(
            "※ 공유문서의 실제 시트 열 구조와 전체 행 데이터를 그대로"
            " 불러왔습니다."
        )
        st.data_editor(
            df_sheet,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"ed_{selected_sheet}",
        )
      else:
        st.warning(
            f"[{selected_sheet}] 시트에서 데이터를 불러오지 못했습니다."
            " 공유문서 링크 권한('링크가 있는 모든 사용자 보기')을"
            " 확인해주세요."
        )

    with tab_add:
      st.subheader(f"➕ [{selected_sheet}] 신규 현장 데이터 추가")
      with st.form(f"f_{selected_sheet}"):
        c1, c2, c3 = st.columns(3)
        with c1:
          i_b = st.text_input("건물명", placeholder="건물명 입력")
          i_r1 = st.text_input("지역1", placeholder="시/도 (예: 서울)")
          i_r2 = st.text_input("지역2", placeholder="구/군 (예: 강남구)")
        with c2:
          i_c = st.text_input("설치대수", value="1")
          i_d = st.text_input("설치일 / 설치일자", placeholder="예: 2026. 11. 18")
          i_p = st.text_input("프로그램", placeholder="예: ARV, I-Vision")
        with c3:
          i_v = st.text_input("version", placeholder="예: 2.0.11")
          i_a = st.text_input("E/V android", placeholder="예: 5.0, 7.0")

        i_n = st.text_area("비고", placeholder="상세 내용 입력")

        if st.form_submit_button("저장하기"):
          if i_b:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                """
                            INSERT INTO installation_local_additions (
                                category, building_name, region_1, region_2, install_count,
                                install_date, program, version, ev_android, notes
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                (
                    selected_sheet,
                    i_b,
                    i_r1,
                    i_r2,
                    i_c,
                    i_d,
                    i_p,
                    i_v,
                    i_a,
                    i_n,
                ),
            )
            conn.commit()
            conn.close()
            st.success("✅ 추가되었습니다! 목록 탭에서 바로 확인됩니다.")
          else:
            st.warning("⚠️ 건물명은 필수 입력 항목입니다.")
