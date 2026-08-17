from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from pykrx import stock


# ============================================================
# Streamlit 기본 설정
# ============================================================

st.set_page_config(
    page_title="500억봉 D+10 데이터 생성기",
    page_icon="📈",
    layout="centered"
)


# ============================================================
# 1. 날짜 검증
# ============================================================

def validate_event_date(event_date: str) -> datetime:

    event_date = event_date.strip()

    if len(event_date) != 8:
        raise ValueError(
            "500억봉 발생일은 20260107처럼 숫자 8자리로 입력해주세요."
        )

    if not event_date.isdigit():
        raise ValueError(
            "날짜에는 숫자만 입력해주세요. 예: 20260107"
        )

    try:
        event_dt = datetime.strptime(
            event_date,
            "%Y%m%d"
        )

    except ValueError:
        raise ValueError(
            "올바른 날짜가 아닙니다. 예: 20260107"
        )

    return event_dt


# ============================================================
# 2. stock_master.csv 읽기
# ============================================================

@st.cache_data
def load_stock_list():

    try:
        df = pd.read_csv(
            "stock_master.csv",
            dtype={
                "Code": str,
                "Name": str
            }
        )

    except FileNotFoundError:
        raise ValueError(
            "stock_master.csv 파일을 찾지 못했습니다.\n\n"
            "app.py와 같은 위치에 stock_master.csv가 있는지 확인해주세요."
        )

    except Exception as e:
        raise ValueError(
            "stock_master.csv를 읽는 중 오류가 발생했습니다.\n\n"
            f"{e}"
        )

    if df.empty:
        raise ValueError(
            "stock_master.csv가 비어 있습니다."
        )

    required_columns = {
        "Code",
        "Name"
    }

    if not required_columns.issubset(
        df.columns
    ):
        raise ValueError(
            "stock_master.csv에는 "
            "'Code'와 'Name' 컬럼이 필요합니다."
        )

    # 종목코드를 항상 6자리 문자열로 처리
    df["Code"] = (
        df["Code"]
        .astype(str)
        .str.strip()
        .str.zfill(6)
    )

    # 종목명 공백 제거
    df["Name"] = (
        df["Name"]
        .astype(str)
        .str.strip()
    )

    return df


# ============================================================
# 3. 종목명 → 종목코드 자동 검색
# ============================================================

def find_ticker(stock_name: str) -> str:

    stock_name = stock_name.strip()

    stock_df = load_stock_list()

    # --------------------------------------------------------
    # 1차: 종목명 정확히 일치
    # --------------------------------------------------------

    exact = stock_df[
        stock_df["Name"]
        == stock_name
    ]

    if len(exact) == 1:
        return exact.iloc[0]["Code"]

    # --------------------------------------------------------
    # 2차: 부분 일치
    # --------------------------------------------------------

    partial = stock_df[
        stock_df["Name"].str.contains(
            stock_name,
            case=False,
            na=False,
            regex=False
        )
    ]

    if len(partial) == 1:
        return partial.iloc[0]["Code"]

    # --------------------------------------------------------
    # 여러 종목이 검색된 경우
    # --------------------------------------------------------

    if len(partial) > 1:

        matches = []

        for _, row in (
            partial.head(10).iterrows()
        ):
            matches.append(
                f"{row['Name']} ({row['Code']})"
            )

        match_text = "\n".join(
            matches
        )

        raise ValueError(
            f"'{stock_name}'과 일치하는 종목이 여러 개 있습니다.\n\n"
            f"{match_text}\n\n"
            "종목명을 조금 더 정확하게 입력해주세요."
        )

    raise ValueError(
        f"'{stock_name}' 종목을 "
        "stock_master.csv에서 찾지 못했습니다."
    )


# ============================================================
# 4. 거래대금 별도 조회
# ============================================================

def get_trading_value(
    ticker: str,
    event_date: str
):

    # --------------------------------------------------------
    # 방법 1
    # OHLCV 결과에 거래대금 컬럼이 있으면 사용
    # --------------------------------------------------------

    try:

        one_day_df = stock.get_market_ohlcv(
            event_date,
            event_date,
            ticker
        )

        if (
            one_day_df is not None
            and not one_day_df.empty
            and "거래대금" in one_day_df.columns
        ):

            value = float(
                one_day_df.iloc[0]["거래대금"]
            )

            if value > 0:
                return (
                    value
                    / 100_000_000
                )

    except Exception:
        pass

    # --------------------------------------------------------
    # 방법 2
    # 투자자별 거래대금 조회
    # --------------------------------------------------------

    try:

        tv_df = (
            stock.get_market_trading_value_by_date(
                event_date,
                event_date,
                ticker
            )
        )

        if (
            tv_df is not None
            and not tv_df.empty
            and "전체" in tv_df.columns
        ):

            value = abs(
                float(
                    tv_df.iloc[0]["전체"]
                )
            )

            if value > 0:
                return (
                    value
                    / 100_000_000
                )

    except Exception:
        pass

    # --------------------------------------------------------
    # 방법 3
    # stock_master.csv의 Amount 사용
    #
    # CSV가 최신일 때만 의미가 있으므로
    # 과거 사례 거래대금에는 사용하지 않음.
    # --------------------------------------------------------

    return None


# ============================================================
# 5. 가격 데이터 분석
# ============================================================

def analyze_price(
    stock_name: str,
    event_date: str
) -> dict:

    event_dt = validate_event_date(
        event_date
    )

    # 종목코드 자동검색
    ticker = find_ticker(
        stock_name
    )

    # D+10 거래일까지 충분히 확보
    end_dt = (
        event_dt
        + timedelta(days=35)
    )

    end_date = (
        end_dt.strftime(
            "%Y%m%d"
        )
    )

    # ========================================================
    # 가격 조회
    #
    # adjusted=False 사용하지 않음
    # ========================================================

    try:

        df = stock.get_market_ohlcv(
            event_date,
            end_date,
            ticker
        )

    except Exception as e:

        raise ValueError(
            "pykrx 가격 조회 중 오류가 발생했습니다.\n\n"
            f"{e}"
        )

    if (
        df is None
        or df.empty
    ):

        raise ValueError(
            f"{stock_name}({ticker})의 "
            "주가 데이터를 가져오지 못했습니다."
        )

    df = df.sort_index()

    # ========================================================
    # 입력 날짜가 실제 거래일인지 확인
    # ========================================================

    event_date_text = (
        event_dt.strftime(
            "%Y-%m-%d"
        )
    )

    matching_dates = [
        idx
        for idx in df.index
        if idx.strftime(
            "%Y-%m-%d"
        )
        == event_date_text
    ]

    if not matching_dates:

        raise ValueError(
            f"{event_date_text}는 "
            "해당 종목의 거래일 데이터가 없습니다.\n"
            "주말·공휴일 또는 날짜 입력을 확인해주세요."
        )

    d0_index = (
        matching_dates[0]
    )

    df = df.loc[
        d0_index:
    ]

    # D0 + D+1~D+10 = 총 11개 거래일
    if len(df) < 11:

        raise ValueError(
            "D+10까지 충분한 거래일 데이터가 없습니다."
        )

    df = df.iloc[
        :11
    ].copy()

    # ========================================================
    # D0 데이터
    # ========================================================

    d0 = df.iloc[0]

    d0_open = float(
        d0["시가"]
    )

    d0_high = float(
        d0["고가"]
    )

    d0_low = float(
        d0["저가"]
    )

    d0_close = float(
        d0["종가"]
    )

    # --------------------------------------------------------
    # 당일 등락률
    # --------------------------------------------------------

    if "등락률" in df.columns:

        event_return = float(
            d0["등락률"]
        )

    else:

        event_return = None

    # --------------------------------------------------------
    # 당일 거래대금
    # --------------------------------------------------------

    trading_value_eok = (
        get_trading_value(
            ticker,
            event_date
        )
    )

    # ========================================================
    # 수익률 계산 함수
    # ========================================================

    def pct_return(price):

        return (
            float(price)
            / d0_close
            - 1
        ) * 100

    # ========================================================
    # D+3 / D+5 / D+10
    # ========================================================

    d3_return = pct_return(
        df.iloc[3]["종가"]
    )

    d5_return = pct_return(
        df.iloc[5]["종가"]
    )

    d10_return = pct_return(
        df.iloc[10]["종가"]
    )

    # D+1 ~ D+10
    future = df.iloc[
        1:11
    ]

    # ========================================================
    # MFE / MAE
    # ========================================================

    max_high = float(
        future["고가"].max()
    )

    min_low = float(
        future["저가"].min()
    )

    mfe_10d = pct_return(
        max_high
    )

    mae_10d = pct_return(
        min_low
    )

    # ========================================================
    # 기준봉 고가 재돌파
    # ========================================================

    breakout_rows = future[
        future["고가"]
        > d0_high
    ]

    if not breakout_rows.empty:

        rebreak_high_10d = "O"

        first_break_date = (
            breakout_rows.index[0]
        )

        days_to_rebreak = (
            df.index.get_loc(
                first_break_date
            )
        )

        first_break_date_text = (
            first_break_date.strftime(
                "%Y-%m-%d"
            )
        )

    else:

        rebreak_high_10d = "X"

        days_to_rebreak = (
            "확인불가"
        )

        first_break_date_text = (
            "없음"
        )

    # ========================================================
    # 기준봉 저가 이탈
    # ========================================================

    if (
        future["저가"]
        < d0_low
    ).any():

        break_event_low = "O"

    else:

        break_event_low = "X"

    # ========================================================
    # 최종 반환
    # ========================================================

    return {

        "stock_name":
            stock_name,

        "ticker":
            ticker,

        "event_date":
            event_dt.strftime(
                "%Y-%m-%d"
            ),

        "event_return":
            event_return,

        "trading_value_eok":
            trading_value_eok,

        "d0_open":
            int(d0_open),

        "d0_high":
            int(d0_high),

        "d0_low":
            int(d0_low),

        "d0_close":
            int(d0_close),

        "d3_return":
            round(
                d3_return,
                2
            ),

        "d5_return":
            round(
                d5_return,
                2
            ),

        "d10_return":
            round(
                d10_return,
                2
            ),

        "mfe_10d":
            round(
                mfe_10d,
                2
            ),

        "mae_10d":
            round(
                mae_10d,
                2
            ),

        "rebreak_high_10d":
            rebreak_high_10d,

        "days_to_rebreak":
            days_to_rebreak,

        "first_break_date":
            first_break_date_text,

        "break_event_low":
            break_event_low,
    }


# ============================================================
# 6. 출력 포맷
# ============================================================

def format_event_return(value):

    if value is None:
        return "확인불가"

    return f"{value:.2f}%"


def format_trading_value(value):

    if value is None:
        return "확인불가"

    return f"{value:,.0f}억원"


# ============================================================
# 7. GPT 입력용 최종 텍스트
# ============================================================

def make_output_text(
    result: dict,
    news_url: str
) -> str:

    event_return_text = (
        format_event_return(
            result["event_return"]
        )
    )

    trading_value_text = (
        format_trading_value(
            result["trading_value_eok"]
        )
    )

    return f"""
종목: {result['stock_name']}
종목코드: {result['ticker']}
500억봉 발생일: {result['event_date']}
당일 상승률: {event_return_text}
당일 거래대금: {trading_value_text}

[당시 상승 뉴스]
{news_url}

[10거래일 주가 결과]

D0 시가: {result['d0_open']:,}원
D0 고가: {result['d0_high']:,}원
D0 저가: {result['d0_low']:,}원
D0 종가: {result['d0_close']:,}원

D+3 수익률: {result['d3_return']:.2f}%
D+5 수익률: {result['d5_return']:.2f}%
D+10 수익률: {result['d10_return']:.2f}%

MFE 10D: {result['mfe_10d']:.2f}%
MAE 10D: {result['mae_10d']:.2f}%

10거래일 내 기준봉 고가 재돌파: {result['rebreak_high_10d']}
재돌파 소요일: {result['days_to_rebreak']}
최초 재돌파일: {result['first_break_date']}
10거래일 내 기준봉 저가 이탈: {result['break_event_low']}
""".strip()


# ============================================================
# 8. Streamlit 입력 UI
# ============================================================

with st.form(
    "stock_form"
):

    stock_name = st.text_input(
        "종목명",
        placeholder="예: 현대오토에버"
    )

    event_date = st.text_input(
        "500억봉 발생일",
        placeholder="예: 20260107",
        max_chars=8
    )

    news_url = st.text_input(
        "당시 상승 뉴스 링크",
        placeholder="https://..."
    )

    submitted = (
        st.form_submit_button(
            "📊 데이터 생성",
            use_container_width=True
        )
    )


# ============================================================
# 9. 실행
# ============================================================

if submitted:

    stock_name = (
        stock_name.strip()
    )

    event_date = (
        event_date.strip()
    )

    news_url = (
        news_url.strip()
    )

    # --------------------------------------------------------
    # 입력값 검증
    # --------------------------------------------------------

    if not stock_name:

        st.warning(
            "종목명을 입력해주세요."
        )

    elif not event_date:

        st.warning(
            "500억봉 발생일을 입력해주세요."
        )

    elif not news_url:

        st.warning(
            "뉴스 링크를 입력해주세요."
        )

    else:

        try:

            with st.spinner(
                "종목코드와 주가 데이터를 조회하고 있습니다..."
            ):

                result = (
                    analyze_price(
                        stock_name,
                        event_date
                    )
                )

            output_text = (
                make_output_text(
                    result,
                    news_url
                )
            )

            # =================================================
            # 성공 메시지
            # =================================================

            st.success(
                f"데이터 생성 완료 · "
                f"{result['stock_name']} "
                f"({result['ticker']})"
            )

            # -------------------------------------------------
            # 거래대금만 조회 실패한 경우
            # -------------------------------------------------

            if (
                result[
                    "trading_value_eok"
                ]
                is None
            ):

                st.warning(
                    "주가 데이터는 정상 조회됐지만 "
                    "당일 거래대금은 자동 조회하지 못했습니다. "
                    "GPT 입력문에는 '확인불가'로 표시했습니다."
                )

            # =================================================
            # GPT 입력용 결과만 표시
            # =================================================

            st.text_area(
                "GPTs 입력용 결과",
                value=output_text,
                height=520
            )

        except Exception as e:

            st.error(
                f"오류가 발생했습니다.\n\n{e}"
            )
