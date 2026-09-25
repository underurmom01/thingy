    total = float(table["Value"].sum())
    table["Weight"] = table["Value"] / total
    rated = table["Research score"].notna()
    coverage = float(table.loc[rated, "Weight"].sum())
    score = float((table.loc[rated, "Research score"] * table.loc[rated, "Weight"]).sum() / coverage) if coverage else None
    table = table.sort_values("Weight", ascending=False).reset_index(drop=True)
    return {"table": table, "total": total, "score": score, "coverage": coverage}


st.divider()
st.markdown('<div id="rate-my-portfolio"></div>', unsafe_allow_html=True)
st.subheader("Rate my portfolio")
st.caption("Enter your USD-priced stocks and share counts. Fractional shares work; duplicate tickers are combined.")
with st.form("rate_portfolio_form"):
    rating_entries = st.data_editor(
        pd.DataFrame({"Ticker": ["", ""], "Shares": [0.0, 0.0]}),
        num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={"Ticker": st.column_config.TextColumn("Stock ticker", help="For example: AAPL or MSFT"),
                       "Shares": st.column_config.NumberColumn("Shares owned", min_value=0.0, format="%.6f")},
        key="rating_holdings_editor",
    )
    rate_clicked = st.form_submit_button("Rate my portfolio", type="primary", use_container_width=True)

if rate_clicked:
    try:
        entered_holdings = normalize_portfolio_entries(rating_entries)
    except ValueError as exc:
        st.error(str(exc))
    else:
        rows, failures = [], []
        with st.spinner("Checking your holdings…"):
            with ThreadPoolExecutor(max_workers=min(4, len(entered_holdings))) as executor:
                jobs = {executor.submit(rate_portfolio_position, ticker, shares): ticker
                        for ticker, shares in entered_holdings.items()}
                for job in as_completed(jobs):
                    try:
                        rows.append(job.result())
                    except Exception as exc:
                        failures.append(jobs[job] + ": " + (str(exc) if isinstance(exc, ValueError) else "Market data unavailable; try again."))
        result = summarize_portfolio_rating(rows) if rows else None
        st.session_state["portfolio_rating_result"] = {"result": result, "failures": sorted(failures),
                                                       "time": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC")}

if "portfolio_rating_result" in st.session_state:
    saved_rating = st.session_state["portfolio_rating_result"]
    st.caption("Last submitted portfolio · {} · Submit again after editing holdings.".format(saved_rating["time"]))
    for failure in saved_rating["failures"]:
        st.warning(failure)
    result = saved_rating["result"]
    if result is None:
        st.error("No holdings could be priced. Check the symbols and try again.")
    else:
        table = result["table"]
        partial = bool(saved_rating["failures"])
        a, b, c = st.columns(3)
        a.metric("Priced holdings value" if partial else "Portfolio value", "${:,.2f}".format(result["total"]))
        b.metric("Research rating (priced holdings)" if partial else "Research rating",
                 "{:.0f}/100".format(result["score"]) if result["score"] is not None else "Unavailable")
        c.metric("Largest position", "{} · {:.1%}".format(table.iloc[0]["Ticker"], table.iloc[0]["Weight"]))
        if partial:
            st.info("Unpriced holdings are excluded from value, weights and rating. These results cover only the priced portion of your portfolio.")
        st.caption("Rating: value-weighted stock research scores, combining technical signals (60%) and company fundamentals (40%) where available. Rated coverage: {:.0%} of priced value. Missing components are omitted, not scored as zero. This is not a diversification or risk score.".format(result["coverage"]))
        display = table.copy()
        display["Weight"] = display["Weight"] * 100
        st.dataframe(display, hide_index=True, use_container_width=True, column_config={
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "Value": st.column_config.NumberColumn(format="$%.2f"),
            "Weight": st.column_config.NumberColumn("Weight (%)", format="%.1f%%"),
            "Research score": st.column_config.NumberColumn(format="%.1f"),
            "Technical": st.column_config.NumberColumn(format="%.1f"),
            "Company": st.column_config.NumberColumn(format="%.1f"),
        })
        if table.iloc[0]["Weight"] > .25:
            st.info("Concentration: {} accounts for {:.1%} of priced value.".format(table.iloc[0]["Ticker"], table.iloc[0]["Weight"]))
        sectors = table.groupby("Sector")["Weight"].sum().sort_values(ascending=False)
        with st.expander("Sector breakdown"):
            st.dataframe((sectors * 100).rename("Weight (%)").round(1), use_container_width=True)
        st.caption("Uses cached historical closing prices, not live quotes. Prices may have different dates. Cash, debt, taxes and trading costs are not included. Research scores do not predict guaranteed returns.")
        st.download_button("Download portfolio review", display.to_csv(index=False), "buyntiq_portfolio_review.csv", "text/csv", key="download_rated_portfolio")


st.divider()
st.markdown('<div id="portfolio-builder"></div>', unsafe_allow_html=True)
st.subheader("Portfolio builder")
st.caption(
    "Choose a sector, risk profile, number of holdings, and budget."
)


with st.expander(
    "Portfolio settings",
    expanded=False,
):
    p1, p2, p3, p4 = st.columns(4)

    sector_focus = p1.selectbox(
        "Sector focus",
        SECTOR_OPTIONS,
        index=0,
        key="portfolio_sector_focus",
        help=(
            "Choose one sector, or scan the entire U.S.-listed stock universe across all sectors."
        ),
    )

    risk_profile = p2.selectbox(
        "Risk profile",
        [
            "Conservative",
            "Balanced",
            "Aggressive",
        ],
        index=1,
        key="portfolio_risk_profile",
    )

    selection_mode = st.radio(
        "Selection method",
        ["Best Stocks", "Diversified Portfolio"],
        index=0,
        horizontal=True,
        key="portfolio_selection_mode",
        help=(
            "Best Stocks picks the highest final research scores after full company + ML analysis. "
            "Diversified Portfolio starts from those final scores but can make small substitutions to reduce correlation and sector concentration."
        ),
    )

    # IMPORTANT: do not fetch the market universe during page render.
    # The input can accept up to 500; the real limit is checked only after
    # the user presses the build button.
    holdings_count = p3.number_input(
        "Holdings",
        min_value=1,
        max_value=500,
        value=5,
        step=1,
        key="portfolio_holdings_count",
        help=(
            "Choose how many stocks you want. The app checks the actual "
            "available sector universe only after you press Build Portfolio."
        ),
    )

    holdings_count = int(
        holdings_count
    )

    budget = p4.number_input(
        "Budget",
        min_value=0.0,
        value=10000.0,
        step=1000.0,
        help=(
            "Use 0 if you only want percentages. "
            "This version searches U.S.-listed stocks, so allocations are in USD."
        ),
        key="portfolio_budget",
    )
