import uuid
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import get_supabase
from portfolio_tracker import autosave_portfolio_value


CURRENCY_OPTIONS = [
    {"code": "GHS", "name": "Ghana Cedi", "symbol": "₵"},
    {"code": "NGN", "name": "Nigerian Naira", "symbol": "₦"},
    {"code": "KES", "name": "Kenyan Shilling", "symbol": "KSh"},
    {"code": "ZAR", "name": "South African Rand", "symbol": "R"},
    {"code": "CFA", "name": "CFA Franc", "symbol": "CFA"},
    {"code": "USD", "name": "US Dollar", "symbol": "$"},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥"},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥"},
    {"code": "GBP", "name": "British Pound", "symbol": "£"},
    {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$"},
    {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF"},
    {"code": "EUR", "name": "Euro", "symbol": "€"},
]

PAYMENT_FREQUENCIES = [
    "Zero Coupon / T-Bill",
    "Annual",
    "Semi-Annual",
    "Quarterly",
    "Monthly",
    "At Maturity",
    "Other",
]

BOND_TYPES = [
    "Treasury Bill",
    "Government Bond",
    "Corporate Bond",
    "Municipal / Local Authority Bond",
    "Fixed Deposit / Note",
    "Other Fixed Income",
]

PLOTLY_CHART_CONFIG = {
    "scrollZoom": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": [
        "pan2d",
        "zoomIn2d",
        "zoomOut2d",
        "resetScale2d",
    ],
    "modeBarButtonsToRemove": [
        "select2d",
        "lasso2d",
    ],
}

DONUT_CHART_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
}


def db():
    supabase = get_supabase()

    if "access_token" in st.session_state:
        try:
            supabase.auth.set_session(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
            )
        except Exception:
            pass

    return supabase


def load_setting(user_id, key, default):
    try:
        res = (
            db()
            .table("user_settings")
            .select("value")
            .eq("user_id", user_id)
            .eq("key", key)
            .single()
            .execute()
        )
        return float(res.data["value"])
    except Exception:
        return default


def save_setting(user_id, key, value):
    db().table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": float(value)},
        on_conflict="user_id,key",
    ).execute()


def currency_label(currency):
    return f'{currency["code"]} - {currency["name"]}'


def load_currency_index(user_id):
    idx = int(load_setting(user_id, "bond_currency_index", 0))
    return idx if 0 <= idx < len(CURRENCY_OPTIONS) else 0


def fmt(value, currency):
    return f'{currency["symbol"]} {float(value):,.2f}'


def metric_delta(value):
    if value > 0:
        return f"+{abs(value):.2f}%"
    if value < 0:
        return f"-{abs(value):.2f}%"
    return "0.00%"


def load_bond_holdings(user_id):
    try:
        res = (
            db()
            .table("bond_holdings")
            .select(
                "id,name,issuer,bond_type,currency_code,usd_to_native_rate,"
                "face_value,purchase_value,current_value,coupon_rate,"
                "income_received,maturity_date,payment_frequency"
            )
            .eq("user_id", user_id)
            .order("created_at")
            .execute()
        )
        return res.data or []
    except Exception as error:
        print("Load bond holdings failed:", error)
        return []


def add_bond_holding(user_id, holding):
    row = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        **holding,
    }
    db().table("bond_holdings").insert(row).execute()


def update_bond_holding(user_id, holding_id, holding):
    (
        db()
        .table("bond_holdings")
        .update(holding)
        .eq("user_id", user_id)
        .eq("id", holding_id)
        .execute()
    )


def delete_bond_holding(user_id, holding_id):
    (
        db()
        .table("bond_holdings")
        .delete()
        .eq("user_id", user_id)
        .eq("id", holding_id)
        .execute()
    )


def load_portfolio_history(user_id):
    try:
        res = (
            db()
            .table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "bond")
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def force_snapshot(user_id, value, mode="bond"):
    try:
        db().table("portfolio_history").insert(
            {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "value_ghs": round(float(value), 2),
                "mode": mode,
            }
        ).execute()
        return True
    except Exception as error:
        print("Bond snapshot failed:", error)
        return False


def clean_history(history):
    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(history)

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["value_ghs"] = pd.to_numeric(df["value_ghs"], errors="coerce")
    df = df.dropna().sort_values("timestamp")
    return df


def build_pnl(history_df, invested):
    if history_df.empty:
        return history_df

    df = history_df.copy()
    df["pnl"] = df["value_ghs"] - float(invested)
    return df


def parse_date(value):
    if not value:
        return None

    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def days_to_maturity(maturity_date):
    maturity = parse_date(maturity_date)

    if maturity is None:
        return None

    return (maturity - date.today()).days


def native_to_display(value, usd_to_native_rate, usd_to_display_rate):
    """
    Convert a bond's native-currency value into the dashboard display currency.

    Example:
    - A GHS bond with USD→GHS = 14.5 is first converted to USD by /14.5.
    - The USD value is then multiplied by the dashboard's USD→display rate.
    """
    value = float(value or 0.0)
    native_rate = float(usd_to_native_rate or 0.0)
    display_rate = float(usd_to_display_rate or 0.0)

    if native_rate <= 0 or display_rate <= 0:
        return 0.0

    return (value / native_rate) * display_rate


def holding_display_metrics(holding, usd_to_display_rate):
    face_native = float(holding.get("face_value") or 0.0)
    purchase_native = float(holding.get("purchase_value") or 0.0)
    current_native = float(holding.get("current_value") or 0.0)
    income_native = float(holding.get("income_received") or 0.0)
    coupon_rate = float(holding.get("coupon_rate") or 0.0)
    usd_to_native = float(holding.get("usd_to_native_rate") or 1.0)

    face_display = native_to_display(
        face_native,
        usd_to_native,
        usd_to_display_rate,
    )
    purchase_display = native_to_display(
        purchase_native,
        usd_to_native,
        usd_to_display_rate,
    )
    current_display = native_to_display(
        current_native,
        usd_to_native,
        usd_to_display_rate,
    )
    income_display = native_to_display(
        income_native,
        usd_to_native,
        usd_to_display_rate,
    )

    annual_coupon_native = face_native * coupon_rate / 100.0
    annual_coupon_display = native_to_display(
        annual_coupon_native,
        usd_to_native,
        usd_to_display_rate,
    )

    pnl_display = current_display + income_display - purchase_display
    pnl_pct = (
        pnl_display / purchase_display * 100
        if purchase_display > 0
        else 0.0
    )

    current_yield = (
        annual_coupon_native / current_native * 100
        if current_native > 0 and annual_coupon_native > 0
        else 0.0
    )

    return {
        "face": face_display,
        "purchase": purchase_display,
        "current": current_display,
        "income": income_display,
        "annual_coupon": annual_coupon_display,
        "pnl": pnl_display,
        "pnl_pct": pnl_pct,
        "current_yield": current_yield,
    }


def render_allocation_chart(df, value_col, selected_currency):
    if df.empty:
        return

    chart_df = (
        df[df[value_col] > 0]
        .sort_values(value_col, ascending=False)
        .copy()
    )

    if chart_df.empty:
        return

    if len(chart_df) > 7:
        top = chart_df.head(7).copy()
        other_value = chart_df.iloc[7:][value_col].sum()

        if other_value > 0:
            top = pd.concat(
                [
                    top,
                    pd.DataFrame(
                        [{
                            "Holding": "Others",
                            value_col: other_value,
                        }]
                    ),
                ],
                ignore_index=True,
            )

        chart_df = top

    fig = go.Figure(
        data=[
            go.Pie(
                labels=chart_df["Holding"],
                values=chart_df[value_col],
                hole=0.68,
                sort=False,
                direction="clockwise",
                textinfo="none",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    f"Value: {selected_currency['symbol']} %{{value:,.2f}}<br>"
                    "Allocation: %{percent}<extra></extra>"
                ),
            )
        ]
    )

    fig.update_layout(
        height=360,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=13),
        ),
        annotations=[
            dict(
                text="100%",
                x=0.5,
                y=0.5,
                font=dict(size=26, color="white"),
                showarrow=False,
            )
        ],
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config=DONUT_CHART_CONFIG,
    )


def bond_form(
    prefix,
    default=None,
    default_display_currency="GHS",
):
    default = default or {}

    name = st.text_input(
        "Holding name",
        value=str(default.get("name") or ""),
        placeholder="e.g. Ghana 91-Day Treasury Bill",
        key=f"{prefix}_name",
    )

    issuer = st.text_input(
        "Issuer",
        value=str(default.get("issuer") or ""),
        placeholder="e.g. Government of Ghana",
        key=f"{prefix}_issuer",
    )

    type_default = default.get("bond_type") or BOND_TYPES[0]
    type_index = (
        BOND_TYPES.index(type_default)
        if type_default in BOND_TYPES
        else 0
    )

    bond_type = st.selectbox(
        "Fixed-income type",
        BOND_TYPES,
        index=type_index,
        key=f"{prefix}_bond_type",
    )

    currency_codes = [item["code"] for item in CURRENCY_OPTIONS]
    native_default = default.get("currency_code") or default_display_currency
    native_index = (
        currency_codes.index(native_default)
        if native_default in currency_codes
        else 0
    )

    currency_code = st.selectbox(
        "Holding currency",
        currency_codes,
        index=native_index,
        key=f"{prefix}_currency",
    )

    default_fx = float(default.get("usd_to_native_rate") or 1.0)

    usd_to_native_rate = st.number_input(
        f"USD → {currency_code} rate",
        min_value=0.000001,
        value=default_fx,
        step=0.1 if default_fx >= 1 else 0.01,
        format="%.6f",
        key=f"{prefix}_fx",
        help=(
            "Enter how many units of the holding currency equal USD 1. "
            "Use 1.0 for USD holdings."
        ),
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        face_value = st.number_input(
            f"Face / maturity value ({currency_code})",
            min_value=0.0,
            value=float(default.get("face_value") or 0.0),
            step=100.0,
            key=f"{prefix}_face",
        )

    with c2:
        purchase_value = st.number_input(
            f"Purchase / principal value ({currency_code})",
            min_value=0.0,
            value=float(default.get("purchase_value") or 0.0),
            step=100.0,
            key=f"{prefix}_purchase",
        )

    with c3:
        current_value = st.number_input(
            f"Current / estimated value ({currency_code})",
            min_value=0.0,
            value=float(default.get("current_value") or 0.0),
            step=100.0,
            key=f"{prefix}_current",
            help=(
                "For instruments without a live market price, enter your "
                "best current statement or estimated redemption value."
            ),
        )

    c4, c5 = st.columns(2)

    with c4:
        coupon_rate = st.number_input(
            "Coupon / stated annual rate (%)",
            min_value=0.0,
            value=float(default.get("coupon_rate") or 0.0),
            step=0.1,
            key=f"{prefix}_coupon",
            help="Use 0 for a discount Treasury bill or zero-coupon instrument.",
        )

    with c5:
        income_received = st.number_input(
            f"Interest / coupon income received ({currency_code})",
            min_value=0.0,
            value=float(default.get("income_received") or 0.0),
            step=10.0,
            key=f"{prefix}_income",
            help="Enter cumulative cash income already received from this holding.",
        )

    maturity_default = parse_date(default.get("maturity_date")) or date.today()

    maturity_date = st.date_input(
        "Maturity date",
        value=maturity_default,
        key=f"{prefix}_maturity",
    )

    frequency_default = (
        default.get("payment_frequency")
        or PAYMENT_FREQUENCIES[0]
    )
    frequency_index = (
        PAYMENT_FREQUENCIES.index(frequency_default)
        if frequency_default in PAYMENT_FREQUENCIES
        else 0
    )

    payment_frequency = st.selectbox(
        "Payment frequency",
        PAYMENT_FREQUENCIES,
        index=frequency_index,
        key=f"{prefix}_frequency",
    )

    return {
        "name": name.strip(),
        "issuer": issuer.strip(),
        "bond_type": bond_type,
        "currency_code": currency_code,
        "usd_to_native_rate": float(usd_to_native_rate),
        "face_value": float(face_value),
        "purchase_value": float(purchase_value),
        "current_value": float(current_value),
        "coupon_rate": float(coupon_rate),
        "income_received": float(income_received),
        "maturity_date": maturity_date.isoformat(),
        "payment_frequency": payment_frequency,
    }


def bond_app():
    st.title("Bond & Fixed-Income Dashboard")
    st.caption(
        "Track Treasury bills, government bonds, corporate bonds and "
        "other fixed-income holdings — including instruments without live tickers."
    )

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    currency_index = load_currency_index(user_id)
    selected_currency = CURRENCY_OPTIONS[currency_index]

    usd_to_display_rate = load_setting(
        user_id,
        "bond_rate",
        14.5 if selected_currency["code"] == "GHS" else 1.0,
    )
    cash = load_setting(user_id, "bond_cash", 0.0)

    st.sidebar.header("⚙️ Bond Settings")

    currency_labels = [currency_label(c) for c in CURRENCY_OPTIONS]

    selected_label = st.sidebar.selectbox(
        "Display Currency",
        currency_labels,
        index=currency_index,
        key="bond_display_currency",
    )

    selected_index = currency_labels.index(selected_label)
    selected_currency = CURRENCY_OPTIONS[selected_index]
    currency_code = selected_currency["code"]

    usd_to_display_rate = st.sidebar.number_input(
        f"USD → {currency_code}",
        min_value=0.000001,
        value=float(usd_to_display_rate),
        step=0.1 if float(usd_to_display_rate) >= 1 else 0.01,
        format="%.6f",
        key="bond_display_rate",
    )

    cash = st.sidebar.number_input(
        f"Fixed-income cash ({currency_code})",
        min_value=0.0,
        value=float(cash),
        step=10.0,
        key="bond_cash",
    )

    if st.sidebar.button(
        "💾 Save Bond Settings",
        key="save_bond_settings",
    ):
        save_setting(
            user_id,
            "bond_currency_index",
            selected_index,
        )
        save_setting(
            user_id,
            "bond_rate",
            usd_to_display_rate,
        )
        save_setting(
            user_id,
            "bond_cash",
            cash,
        )
        st.sidebar.success("Bond settings saved")

    st.sidebar.caption(
        "Each holding keeps its own native currency and USD conversion "
        "rate, so local bonds and Treasury bills can sit in one portfolio."
    )

    holdings = load_bond_holdings(user_id)

    with st.expander("➕ Add Bond / Fixed-Income Holding", expanded=False):
        new_holding = bond_form(
            "bond_add",
            default_display_currency=currency_code,
        )

        if st.button(
            "Add Holding",
            type="primary",
            key="bond_add_button",
            use_container_width=True,
        ):
            if not new_holding["name"]:
                st.error("Enter a holding name.")
            elif new_holding["purchase_value"] <= 0:
                st.error("Enter a purchase/principal value greater than zero.")
            else:
                try:
                    add_bond_holding(user_id, new_holding)
                    st.success("Fixed-income holding added.")
                    st.rerun()
                except Exception as error:
                    print("Add bond failed:", error)
                    st.error("The holding could not be saved.")

    if holdings:
        with st.expander("✏️ Edit / Remove Holdings", expanded=False):
            labels = {
                f"{h.get('name', 'Holding')} · {h.get('issuer', '')} · {h.get('currency_code', '')}": h
                for h in holdings
            }

            selected_label_edit = st.selectbox(
                "Choose holding",
                list(labels.keys()),
                key="bond_edit_select",
            )
            selected = labels[selected_label_edit]

            edited = bond_form(
                f"bond_edit_{selected['id']}",
                default=selected,
                default_display_currency=currency_code,
            )

            edit_col, delete_col = st.columns([3, 1])

            with edit_col:
                if st.button(
                    "💾 Save Changes",
                    key=f"bond_save_{selected['id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        update_bond_holding(
                            user_id,
                            selected["id"],
                            edited,
                        )
                        st.success("Holding updated.")
                        st.rerun()
                    except Exception as error:
                        print("Update bond failed:", error)
                        st.error("The holding could not be updated.")

            with delete_col:
                if st.button(
                    "🗑️ Remove",
                    key=f"bond_delete_{selected['id']}",
                    use_container_width=True,
                ):
                    try:
                        delete_bond_holding(
                            user_id,
                            selected["id"],
                        )
                        st.success("Holding removed.")
                        st.rerun()
                    except Exception as error:
                        print("Delete bond failed:", error)
                        st.error("The holding could not be removed.")

    rows = []
    total_current_value = float(cash)
    total_invested = 0.0
    total_income = 0.0
    total_annual_coupon = 0.0

    value_col = f"Value ({currency_code})"
    purchase_col = f"Invested ({currency_code})"
    income_col = f"Income Received ({currency_code})"

    for holding in holdings:
        metrics = holding_display_metrics(
            holding,
            usd_to_display_rate,
        )

        total_current_value += metrics["current"]
        total_invested += metrics["purchase"]
        total_income += metrics["income"]
        total_annual_coupon += metrics["annual_coupon"]

        maturity_days = days_to_maturity(
            holding.get("maturity_date")
        )

        if maturity_days is None:
            maturity_display = "—"
        elif maturity_days < 0:
            maturity_display = "Matured"
        elif maturity_days == 0:
            maturity_display = "Today"
        else:
            maturity_display = f"{maturity_days:,} days"

        rows.append(
            {
                "Holding": holding.get("name") or "Unnamed holding",
                "Issuer": holding.get("issuer") or "—",
                "Type": holding.get("bond_type") or "—",
                "Currency": holding.get("currency_code") or "—",
                purchase_col: round(metrics["purchase"], 2),
                value_col: round(metrics["current"], 2),
                income_col: round(metrics["income"], 2),
                "Coupon %": round(float(holding.get("coupon_rate") or 0.0), 3),
                "Current Yield %": round(metrics["current_yield"], 3),
                "Maturity": holding.get("maturity_date") or "—",
                "Time to Maturity": maturity_display,
                "Payment": holding.get("payment_frequency") or "—",
            }
        )

    if cash > 0:
        rows.append(
            {
                "Holding": "CASH",
                "Issuer": "—",
                "Type": "Cash",
                "Currency": currency_code,
                purchase_col: 0.0,
                value_col: round(cash, 2),
                income_col: 0.0,
                "Coupon %": 0.0,
                "Current Yield %": 0.0,
                "Maturity": "—",
                "Time to Maturity": "—",
                "Payment": "—",
            }
        )

    df = pd.DataFrame(rows)

    total_return_value = (
        total_current_value
        + total_income
        - total_invested
    )

    total_return_pct = (
        total_return_value / total_invested * 100
        if total_invested > 0
        else 0.0
    )

    st.subheader("📊 Overview")

    top1, top2, top3, top4 = st.columns(4)

    top1.metric(
        "Fixed-Income Value",
        fmt(total_current_value, selected_currency),
    )
    top2.metric(
        "Principal Invested",
        fmt(total_invested, selected_currency),
    )
    top3.metric(
        "Income Received",
        fmt(total_income, selected_currency),
    )
    top4.metric(
        "Total Return",
        fmt(total_return_value, selected_currency),
        metric_delta(total_return_pct),
    )

    second1, second2 = st.columns(2)

    second1.metric(
        "Est. Annual Coupon",
        fmt(total_annual_coupon, selected_currency),
    )

    weighted_yield = (
        total_annual_coupon / total_current_value * 100
        if total_current_value > 0
        else 0.0
    )

    second2.metric(
        "Portfolio Coupon Yield",
        f"{weighted_yield:.2f}%",
    )

    st.caption(
        "Total return = current/estimated value + cash income received − "
        "principal invested. Values are estimates where a live market price "
        "is unavailable."
    )

    st.markdown("---")
    st.subheader("🏦 Fixed-Income Holdings")

    if df.empty:
        st.info(
            "No fixed-income holdings entered yet. Add a Treasury bill, "
            "government bond, corporate bond or other instrument above."
        )
    else:
        st.dataframe(
            df.sort_values(value_col, ascending=False),
            use_container_width=True,
            hide_index=True,
        )

    history = clean_history(load_portfolio_history(user_id))

    st.subheader("Portfolio Trend")

    if len(history) >= 2:
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=history["timestamp"],
                y=history["value_ghs"],
                mode="lines",
                fill="tozeroy",
                line=dict(
                    shape="spline",
                    smoothing=1.2,
                    width=3,
                ),
                hovertemplate=(
                    f'{selected_currency["symbol"]} '
                    "%{y:,.2f}<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified",
            yaxis_title=f"Value ({currency_code})",
            dragmode="pan",
            uirevision="bond_portfolio_trend",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config=PLOTLY_CHART_CONFIG,
        )
    else:
        st.caption(
            "Portfolio trend will appear after at least two bond snapshots."
        )

    st.subheader("All-Time Return Curve")

    pnl_df = build_pnl(history, total_invested)

    if len(pnl_df) >= 2:
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=pnl_df["timestamp"],
                y=pnl_df["pnl"],
                mode="lines",
                line=dict(
                    shape="spline",
                    smoothing=1.2,
                    width=3,
                ),
                hovertemplate=(
                    f'{selected_currency["symbol"]} '
                    "%{y:,.2f}<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            margin=dict(l=10, r=10, b=10, t=10),
            hovermode="x unified",
            yaxis_title=f"Return ({currency_code})",
            dragmode="pan",
            uirevision="bond_return_curve",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config=PLOTLY_CHART_CONFIG,
        )

    st.markdown("---")
    st.subheader("Allocation")

    if not df.empty:
        render_allocation_chart(
            df,
            value_col,
            selected_currency,
        )

    # Autosave only when the portfolio has an actual positive value.
    if total_current_value > 0:
        autosave_portfolio_value(
            user_id,
            total_current_value,
            "bond",
        )

    if st.button(
        "Save Bond Snapshot",
        key="bond_snapshot",
    ):
        if total_current_value > 0:
            if force_snapshot(
                user_id,
                total_current_value,
                "bond",
            ):
                st.success("Bond portfolio snapshot saved.")
            else:
                st.error("Snapshot could not be saved.")
        else:
            st.warning(
                "Add a positive fixed-income value before saving a snapshot."
            )

    st.markdown(
        """
        <div style="
            border-left:4px solid #84cc16;
            background:rgba(132,204,22,.08);
            border-radius:10px;
            padding:.9rem 1rem;
            margin:1rem 0;
        ">
            <strong>Fixed-income valuation note:</strong>
            InvesTrack Pro does not independently price manually entered
            bonds or Treasury bills. Current values, exchange rates and
            income figures should be taken from your broker, bank, issuer,
            custodian or other reliable records.
        </div>
        """,
        unsafe_allow_html=True,
    )
