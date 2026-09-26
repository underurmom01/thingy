    screened,
    sector_focus,
    finalist_limit,
    diversify_finalists=True,
):
    if screened is None or screened.empty:
        return pd.DataFrame()

    # "Best Stocks" mode must preserve the actual score ranking even in
    # all-market mode. Sector balancing is only used by the diversified mode.
    if (
        sector_focus != "All US-listed stocks (all sectors)"
        or not diversify_finalists
    ):
        return (
            screened
            .sort_values("Quick Score", ascending=False)
            .head(finalist_limit)
            .reset_index(drop=True)
        )

    real_sectors = [
        sector
        for sector in (
            screened["Sector"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if (
            sector.strip()
            and sector.strip().lower()
            != "unknown"
        )
    ]

    if not real_sectors:
        return (
            screened
            .head(finalist_limit)
            .reset_index(drop=True)
        )

    selected_indices = []

    per_sector = max(
        6,
        int(
            np.ceil(
                finalist_limit
                / max(
                    len(real_sectors) * 2,
                    1,
                )
            )
        ),
    )

    for sector in real_sectors:
        sector_rows = screened[
            screened["Sector"]
            .astype(str)
            == sector
        ].head(per_sector)

        selected_indices.extend(
            sector_rows.index.tolist()
        )

    selected_indices = list(
        dict.fromkeys(
            selected_indices
        )
    )

    diversified = screened.loc[
        selected_indices
    ].copy()

    if len(diversified) < finalist_limit:
        remaining = screened.drop(
            index=selected_indices,
            errors="ignore",
        )

        need = (
            finalist_limit
            - len(diversified)
        )

        diversified = pd.concat(
            [
                diversified,
                remaining.head(need),
            ],
            ignore_index=True,
        )

    return (
        diversified
        .sort_values(
            "Quick Score",
            ascending=False,
        )
        .head(finalist_limit)
        .reset_index(drop=True)
    )


def _extract_close_series(batch, ticker):
    if batch is None or batch.empty:
        return None
    if isinstance(batch.columns, pd.MultiIndex):
        for key in ((ticker, "Close"), ("Close", ticker)):
            if key in batch.columns:
                close = batch[key]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                return close.dropna()
    frame = _clean_price_frame(batch, ticker=ticker)
    return frame["Close"].dropna() if frame is not None else None


def fast_screen_sector(
    sector_focus,
    finalist_limit=150,
    scan_limit=600,
    _progress=None,
    diversify_finalists=True,
):
    """
    Stage 1 still scans the broad selected U.S. universe, but the complete
    quick-score table is now also saved locally. Rebuilding a portfolio
    shortly afterward can therefore skip the full-market price scan.

    Do not wrap this function in st.cache_data: its progress callback writes
    to a placeholder created by the caller, which cannot be safely replayed
    from Streamlit's cached UI messages. The disk cache below retains the
    30-minute screening cache without caching page-specific UI callbacks.
    """
    cache_key = "{}__{}".format(sector_focus, scan_limit)
    disk_cached = _read_screen_cache(cache_key)

    if (
        disk_cached is not None
        and not disk_cached.empty
    ):
        return _select_fast_finalists(
            disk_cached,
            sector_focus,
            finalist_limit,
            diversify_finalists=diversify_finalists,
        )

    yf = get_yfinance()

    full_universe = (
        get_us_stock_universe()
    )
