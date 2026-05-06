# (everything ABOVE remains EXACTLY the same)

def crypto_app():

    st.title("Crypto Dashboard")

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("⚙️ Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=float(invested), step=10.0)

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(sym, value=float(holdings.get(sym, 0.0)), step=0.0001)

    if st.sidebar.button("💾 Save Holdings"):
        save_crypto_holdings(user_id, holdings)

    # -------------------------------------
    # PRICES
    # -------------------------------------
    try:
        prices = crypto_live_prices() or {}
    except Exception:
        prices = {}

    rows = []
    total_value = 0.0
    data_degraded = False

    for sym, qty in holdings.items():
        raw = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        price, ok = safe_price(sym, raw)

        if price is None:
            data_degraded = True
            continue

        if not ok:
            data_degraded = True

        val = qty * price * rate
        total_value += val
        rows.append([sym, qty, price, val])

    # -------------------------------------
    # PROTECTION
    # -------------------------------------
    last_good = get_last_good_value()

    if total_value > 0 and not data_degraded:
        set_last_good_value(total_value)
    elif last_good is not None:
        total_value = last_good

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])

    # -------------------------------------
    # KPI CARDS
    # -------------------------------------
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    st.subheader("📊 Overview")

    c1, c2, c3 = st.columns(3)
    c1.metric("Portfolio Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # ✅ MTD / YTD (RESTORED CLEANLY)
    # -------------------------------------
    history = load_portfolio_history(user_id)

    mtd_pnl = ytd_pnl = mtd_pct = ytd_pct = 0.0

    if history:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h.sort_values("timestamp")

        now = datetime.utcnow()

        mtd = h[(h["timestamp"].dt.month == now.month) &
                (h["timestamp"].dt.year == now.year)]

        ytd = h[h["timestamp"].dt.year == now.year]

        if not mtd.empty:
            start = mtd.iloc[0]["value_ghs"]
            mtd_pnl = total_value - start
            mtd_pct = (mtd_pnl / start * 100) if start > 0 else 0.0

        if not ytd.empty:
            start = ytd.iloc[0]["value_ghs"]
            ytd_pnl = total_value - start
            ytd_pct = (ytd_pnl / start * 100) if start > 0 else 0.0

    def color_pct(v):
        if v > 0:
            return f"🟢 {pct(v)}"
        elif v < 0:
            return f"🔴 {pct(v)}"
        return pct(v)

    m1, m2 = st.columns(2)
    m1.metric("MTD", fmt(mtd_pnl), color_pct(mtd_pct))
    m2.metric("YTD", fmt(ytd_pnl), color_pct(ytd_pct))

    st.markdown("---")

    # -------------------------------------
    # TABLE
    # -------------------------------------
    st.subheader("Holdings Breakdown")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # AUTOSAVE
    # -------------------------------------
    if total_value > 0 and not data_degraded:
        autosave_portfolio_value(user_id, total_value, "crypto")

    # -------------------------------------
    # CHARTS
    # -------------------------------------
    st.subheader("Portfolio Trend")

    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=h["timestamp"],
            y=h["value_ghs"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.1, width=3),
            fill="tozeroy",
            hovertemplate="GHS %{y:,.2f}<extra></extra>"
        ))

        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.subheader("All-Time PnL Curve")

    pnl_df = build_pnl_history(history, invested)

    if len(pnl_df) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pnl_df["timestamp"],
            y=pnl_df["pnl"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.1, width=3),
            hovertemplate="GHS %{y:,.2f}<extra></extra>"
        ))

        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)

    # -------------------------------------
    # PIE
    # -------------------------------------
    st.subheader("Allocation")

    if not df.empty:
        pie = alt.Chart(df[df["Value (GHS)"] > 0]).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
        )
        st.altair_chart(pie, use_container_width=True)
