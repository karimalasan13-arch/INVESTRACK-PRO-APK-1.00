"""Read scheduled hourly observations using the signed-in user's client."""
import pandas as pd
import streamlit as st
from db import get_supabase


def hourly_history(user_id, mode, display_usd_rate):
    """Return an hourly USD history converted at the CURRENT chosen FX rate.

    Conversion at today's rate keeps the axis consistent with the live dashboard,
    but does not reconstruct historical FX fluctuations.
    """
    client = get_supabase()
    if 'access_token' in st.session_state:
        client.auth.set_session(access_token=st.session_state.access_token,
                                refresh_token=st.session_state.refresh_token)
    result = []
    offset = 0
    while True:
        batch = (client.table('portfolio_hourly_snapshots')
                 .select('snapshot_hour,value_usd,pnl_usd')
                 .eq('user_id', user_id).eq('mode', mode)
                 .order('snapshot_hour').range(offset, offset + 999).execute().data or [])
        result.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    if not result:
        return pd.DataFrame()
    df = pd.DataFrame(result)
    rate = float(display_usd_rate)
    df['timestamp'] = pd.to_datetime(df['snapshot_hour'], utc=True)
    df['value_ghs'] = pd.to_numeric(df['value_usd']) * rate
    df['pnl'] = pd.to_numeric(df['pnl_usd']) * rate
    return df[['timestamp','value_ghs','pnl']]
