from pykrx import stock
import pandas as pd


def make_stock_master():

    rows = []

    # 현재 전체 상장종목
    tickers = stock.get_market_ticker_list(
        market="ALL"
    )

    if not tickers:
        raise RuntimeError(
            "종목 목록을 가져오지 못했습니다."
        )

    for ticker in tickers:

        try:
            name = stock.get_market_ticker_name(
                ticker
            )

            if name:
                rows.append(
                    {
                        "ticker": str(ticker).zfill(6),
                        "stock_name": name.strip()
                    }
                )

        except Exception:
            continue

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "종목 데이터를 만들지 못했습니다."
        )

    df = (
        df
        .drop_duplicates(
            subset=["ticker"]
        )
        .sort_values(
            "ticker"
        )
        .reset_index(drop=True)
    )

    df.to_csv(
        "stock_master.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("==============================")
    print("stock_master.csv 생성 완료")
    print("==============================")
    print(f"종목 수: {len(df):,}개")
    print()

    print(
        df.head(20).to_string(
            index=False
        )
    )


if __name__ == "__main__":

    make_stock_master()