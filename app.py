from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st

# --- 1. 페이지 설정 (반드시 최상단 위치) ---
st.set_page_config(
    page_title="디지털 사이니지 통합 관리 시스템", page_icon="🖥️", layout="wide"
)

# --- 2. 데이터베이스 연결 및 초기 테이블 생성 (마이그레이션 포함) ---
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

  # 3) 설치이력관리 통합 테이블 ('설치현황' 문서의 시트별 데이터)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS installation_status (
            inst_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,      -- 하부메뉴 시트명
            building_name TEXT NOT NULL, -- 건물명
            region_1 TEXT,               -- 지역1
            region_2 TEXT,               -- 지역2
            install_count INTEGER,       -- 설치대수
            install_date TEXT,           -- 설치일
            program TEXT,                -- 프로그램
            version TEXT,                -- version
            ev_android TEXT,             -- E/V android
            board_count INTEGER,         -- 게시판 (ARI용)
            mirror_count INTEGER,        -- 미러 (ARI용)
            prog_history TEXT,           -- 버전 교체이력 (프로그램교체일정용)
            notes TEXT                   -- 비고
        )
    """)

  # 기본 초기 데이터 마이그레이션 (테이블이 비어있을 경우 샘플/기본 데이터 자동 적재)
  cursor.execute("SELECT COUNT(*) FROM installation_status")
  if cursor.fetchone()[0] == 0:
    sample_installations = [
        (
            "오피스보드설치현황",
            "강남 메가시티",
            "서울",
            "강남구",
            2,
            "2021. 2. 17",
            "ARV",
            "2.0.11",
            "7.0",
            0,
            0,
            "",
            "ev2대, 펌웨어업글, 밀착 / 철거",
        ),
        (
            "오피스보드설치현황",
            "양재정인빌딩",
            "서울",
            "강남구",
            1,
            "2025. 5. 15",
            "ARV",
            "2.0.11",
            "",
            0,
            0,
            "",
            "ev1대 25\" 강남대로42길 18",
        ),
        (
            "구축설치현황",
            "마곡에이스프라자",
            "서울",
            "강서구",
            1,
            "2021. 10. 29",
            "ARV",
            "2.0.11",
            "7.0",
            0,
            0,
            "",
            "신형25\" 1대 kt라우터 카상부함",
        ),
        (
            "조달설치",
            "충주교통대학교",
            "충청북도",
            "충주시",
            4,
            "2026. 1. 12",
            "",
            "",
            "",
            0,
            0,
            "",
            "25\" 3대, 55인치 1대",
        ),
        (
            "ARI설치현황",
            "디오빌역삼",
            "서울",
            "강남구",
            1,
            "2025. 2. 5",
            "ARI",
            "1.3.1",
            "",
            1,
            0,
            "",
            "1층 55\" 아리보드 설치",
        ),
        (
            "칩방식설치현황",
            "연세산돌병원",
            "서울",
            "",
            1,
            "2023. 11. 1",
            "",
            "",
            "",
            0,
            0,
            "",
            "21.5인치 1대 칩방식",
        ),
        (
            "타래커피설치현황",
            "연남점",
            "서울",
            "",
            2,
            "2022. 10. 28",
            "",
            "",
            "",
            0,
            0,
            "",
            "43\" 2대",
        ),
        (
            "전통시장설치현황",
            "광명전통시장",
            "",
            "",
            2,
            "",
            "",
            "",
            "",
            0,
            0,
            "",
            "왼쪽 과일생선집, 오른쪽 신발집",
        ),
        (
            "식자재설치현황",
            "우성식자재마트(계산점)",
            "",
            "",
            2,
            "2020. 4. 3",
            "",
            "",
            "",
            0,
            0,
            "",
            "55\" 2*2 멀티비전",
        ),
        (
            "프로그램교체일정",
            "강남 메가시티",
            "서울",
            "강남구",
            1,
            "",
            "ARV",
            "2.0.10",
            "",
            0,
            0,
            "2024.3.19",
            "",
        ),
    ]
    cursor.executemany(
        """
            INSERT INTO installation_status (
                category, building_name, region_1, region_2, install_count,
                install_date, program, version, ev_android, board_count, mirror_count, prog_history, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sample_installations,
    )

  conn.commit()
  conn.close()


init_db()


# --- 3. 비밀번호 인증 로직 (요구사항 1: 0000 고정) ---
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

  # --- 4. 사이드바 메인 메뉴 (4개 메뉴 한눈에 배치) ---
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
    df_inst = pd.read_sql("SELECT * FROM installation_status", conn)
    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
      st.metric(
          label="총 설치 현장 수", value=f"{len(df_inst)} 개소"
      )
    with col2:
      st.metric(
          label="자재 교체/입고 건수", value=f"{len(df_mat)} 건"
      )
    with col3:
      st.metric(label="누적 AS 처리 건수", value=f"{len(df_logs)} 건")
    with col4:
      st.metric(label="시스템 상태", value="실시간 연동중 🟢")

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

          # 2) S/N 입력 시 자재상태 테이블에도 실시간 동시 반영
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
      with tf := st.form("material_form"):
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
  # [메뉴 4] 설치이력관리 (요구사항 2: 내비게이션 제목 '설치이력관리' 통일, 비고 삭제)
  # ==============================================================================
  elif menu == "🏢 설치이력관리":
    st.header("🏢 설치이력관리 (설치현황 통합 대장)")

    # 요청사항 2: 하부메뉴에서 '비고' 시트 삭제 및 9개 시트만 유지
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
    # 요청사항 2: 하부 메뉴 내비게이션 제목을 동일하게 '설치이력관리'로 출력
    st.sidebar.markdown("### 📂 설치이력관리")
    selected_sheet = st.sidebar.radio(
        "하부 시트를 선택하세요:", SHEET_MENUS
    )

    st.subheader(f"📑 [설치이력관리 - {selected_sheet}] 현황")

    conn = sqlite3.connect(DB_NAME)
    df_sheet = pd.read_sql(
        "SELECT * FROM installation_status WHERE category = ? ORDER BY inst_id ASC",
        conn,
        params=(selected_sheet,),
    )
    conn.close()

    search_inst = st.text_input(
        f"🔍 [{selected_sheet}] 내 검색", placeholder="건물명 또는 지역 검색..."
    )
    if search_inst and not df_sheet.empty:
      mask = df_sheet["building_name"].str.contains(
          search_inst, case=False, na=False
      ) | df_sheet["region_1"].str.contains(search_inst, case=False, na=False)
      df_sheet = df_sheet[mask]

    tab_list, tab_add = st.tabs(
        [f"📋 {selected_sheet} 목록 ({len(df_sheet)}건)", "➕ 신규 등록"]
    )

    with tab_list:
      if not df_sheet.empty:
        if selected_sheet in ["오피스보드설치현황", "구축설치현황", "조달설치"]:
          d_cols = [
              "inst_id",
              "building_name",
              "region_1",
              "region_2",
              "install_count",
              "install_date",
              "program",
              "version",
              "ev_android",
              "notes",
          ]
          r_map = {
              "inst_id": "No.",
              "building_name": "건물명",
              "region_1": "지역1",
              "region_2": "지역2",
              "install_count": "설치대수",
              "install_date": "설치일",
              "program": "프로그램",
              "version": "version",
              "ev_android": "E/V android",
              "notes": "비고",
          }
        elif selected_sheet == "ARI설치현황":
          d_cols = [
              "inst_id",
              "building_name",
              "region_1",
              "region_2",
              "install_count",
              "install_date",
              "board_count",
              "mirror_count",
              "version",
              "notes",
          ]
          r_map = {
              "inst_id": "No.",
              "building_name": "건물명",
              "region_1": "지역1",
              "region_2": "지역2",
              "install_count": "설치대수",
              "install_date": "설치일자",
              "board_count": "게시판",
              "mirror_count": "미러",
              "version": "version",
              "notes": "비고",
          }
        elif selected_sheet == "프로그램교체일정":
          d_cols = [
              "inst_id",
              "building_name",
              "region_1",
              "region_2",
              "program",
              "version",
              "prog_history",
              "notes",
          ]
          r_map = {
              "inst_id": "No.",
              "building_name": "건물명",
              "region_1": "지역1",
              "region_2": "지역2",
              "program": "프로그램",
              "version": "현재버전",
              "prog_history": "버전별 교체일자 이력",
              "notes": "비고",
          }
        else:
          d_cols = [
              "inst_id",
              "building_name",
              "region_1",
              "region_2",
              "install_count",
              "install_date",
              "version",
              "notes",
          ]
          r_map = {
              "inst_id": "No.",
              "building_name": "건물명/항목",
              "region_1": "지역1",
              "region_2": "지역2",
              "install_count": "설치대수",
              "install_date": "설치일자",
              "version": "version",
              "notes": "비고/상세내용",
          }

        st.data_editor(
            df_sheet[d_cols].rename(columns=r_map),
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"ed_{selected_sheet}",
        )
      else:
        st.info("등록된 데이터가 없습니다.")

    with tab_add:
      st.subheader(f"➕ [{selected_sheet}] 데이터 추가")
      with st.form(f"f_{selected_sheet}"):
        c1, c2, c3 = st.columns(3)
        with c1:
          i_b = st.text_input("건물명", placeholder="건물명 입력")
          i_r1 = st.text_input("지역1", placeholder="시/도")
          i_r2 = st.text_input("지역2", placeholder="구/군")
        with c2:
          i_c = st.number_input("설치대수", min_value=0, value=1)
          i_d = st.text_input("설치일자", placeholder="예: 2026. 11. 18")
          i_p = st.text_input("프로그램", placeholder="ARV 등")
        with c3:
          i_v = st.text_input("version", placeholder="버전")
          i_a = st.text_input("E/V android", placeholder="버전 또는 수량")
          i_h = st.text_input("교체이력", placeholder="교체일정용")

        i_n = st.text_area("비고 및 상세내용", placeholder="상세 내용 입력")

        if st.form_submit_button("저장하기"):
          if i_b:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                """
                            INSERT INTO installation_status (
                                category, building_name, region_1, region_2, install_count,
                                install_date, program, version, ev_android, prog_history, notes
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    i_h,
                    i_n,
                ),
            )
            conn.commit()
            conn.close()
            st.success("✅ 실시간 저장되었습니다!")
          else:
            st.warning("⚠️ 건물명은 필수입니다.")
