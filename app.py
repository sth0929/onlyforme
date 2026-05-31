import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import random
import os

LOG_FILE = "trade_log.csv"

st.set_page_config(layout="wide")

if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=[
        "time", "direction", "entry_price", "exit_price",
        "leverage", "position_ratio", "entry_capital",
        "pnl_dollar", "pnl_pct", "balance_after"
    ]).to_csv(LOG_FILE, index=False)

def generate_chart():
    df_new = pd.read_csv("btc_1h.csv")
    df_new["open_time"] = pd.to_datetime(df_new["open_time"])
    df_new = df_new.sort_values("open_time")
    df_new.set_index("open_time", inplace=True)
    return df_new

if "df_chart" not in st.session_state:
    st.session_state.df_chart = generate_chart()
    st.session_state.start_idx = random.randint(0, len(st.session_state.df_chart) - 300)
    st.session_state.current_step = 300

if "balance" not in st.session_state:
    st.session_state.balance = 1000.0
    st.session_state.position = None
    st.session_state.entry_price = None
    st.session_state.entry_capital = 0
    st.session_state.win = 0
    st.session_state.lose = 0

if "limit_order" not in st.session_state:
    st.session_state.limit_order = None

if "performance_loaded" not in st.session_state:
    if os.path.exists(LOG_FILE):
        log_df = pd.read_csv(LOG_FILE)
        if not log_df.empty:
            st.session_state.trade_count = len(log_df)
            st.session_state.win = (log_df["pnl_dollar"] > 0).sum()
            st.session_state.lose = (log_df["pnl_dollar"] <= 0).sum()
            st.session_state.total_pnl = log_df["pnl_dollar"].sum()
            st.session_state.balance = log_df.iloc[-1]["balance_after"]
    st.session_state.performance_loaded = True

if "trade_markers" not in st.session_state:
    st.session_state.trade_markers = []
if "total_pnl" not in st.session_state:
    st.session_state.total_pnl = 0.0
if "trade_count" not in st.session_state:
    st.session_state.trade_count = 0

# ✅ 수평선 목록 초기화
if "hlines" not in st.session_state:
    st.session_state.hlines = []  # [{"price": float, "color": str, "label": str}]

# ✅ 수평선 그리기 모드
if "hline_mode" not in st.session_state:
    st.session_state.hline_mode = False

# =====================
# 사이드바
# =====================
with st.sidebar:
    st.subheader("⚙️ 매매 설정")
    leverage = st.radio("레버리지", [1, 5, 10, 20, 50], index=3)
    position_ratio = st.radio("진입 비중 (%)", [5, 10, 20], index=0)

    st.markdown("---")
    st.subheader("🧹 성과 관리")
    if st.button("🔄 성과 전체 리셋"):
        st.session_state.reset_confirm = True

if st.session_state.get("reset_confirm", False):
    st.warning("⚠️ 모든 성과 데이터가 초기화됩니다. 정말 진행할까요?")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ 예, 리셋합니다"):
            st.session_state.balance = 1000.0
            st.session_state.position = None
            st.session_state.entry_price = None
            st.session_state.entry_capital = 0
            st.session_state.win = 0
            st.session_state.lose = 0
            st.session_state.total_pnl = 0.0
            st.session_state.trade_count = 0
            st.session_state.trade_markers = []
            st.session_state.limit_order = None
            st.session_state.hlines = []
            pd.DataFrame(columns=[
                "time", "direction", "entry_price", "exit_price",
                "leverage", "position_ratio", "entry_capital",
                "pnl_dollar", "pnl_pct", "balance_after"
            ]).to_csv(LOG_FILE, index=False)
            if "performance_loaded" in st.session_state:
                del st.session_state.performance_loaded
            st.success("✅ 성과가 초기화되었습니다.")
            st.rerun()
    with col_b:
        if st.button("❌ 취소"):
            st.session_state.reset_confirm = False
            st.rerun()

# =====================
# 데이터 슬라이싱
# =====================
start = st.session_state.start_idx
end = start + st.session_state.current_step
df_view = st.session_state.df_chart.iloc[start:end]
current_price = df_view["close"].iloc[-1]

# =====================
# 지정가 체결 체크
# =====================
def check_limit_order():
    lo = st.session_state.limit_order
    if lo is None or st.session_state.position is not None:
        return
    candle = df_view.iloc[-1]
    low, high = candle["low"], candle["high"]
    triggered = (lo["direction"] == "LONG" and low <= lo["price"] <= high) or \
                (lo["direction"] == "SHORT" and low <= lo["price"] <= high)
    if triggered:
        capital = st.session_state.balance * (lo["ratio"] / 100)
        st.session_state.entry_capital = capital
        st.session_state.entry_price = lo["price"]
        st.session_state.position = lo["direction"]
        st.session_state.trade_markers.append({
            "time": df_view.index[-1],
            "price": lo["price"],
            "label": f"L-{lo['direction']}",
            "color": "lime" if lo["direction"] == "LONG" else "red",
            "symbol": "triangle-up" if lo["direction"] == "LONG" else "triangle-down"
        })
        st.session_state.limit_order = None

check_limit_order()

# =====================
# 강제청산 체크
# =====================
if st.session_state.position:
    if st.session_state.position == "LONG":
        liq_pnl = (current_price - st.session_state.entry_price) / st.session_state.entry_price * leverage
    else:
        liq_pnl = (st.session_state.entry_price - current_price) / st.session_state.entry_price * leverage
    if st.session_state.entry_capital * liq_pnl <= -st.session_state.entry_capital:
        loss = -st.session_state.entry_capital
        st.session_state.balance += loss
        st.session_state.total_pnl += loss
        st.session_state.trade_count += 1
        st.session_state.lose += 1
        st.session_state.trade_markers.append({
            "time": df_view.index[-1],
            "price": current_price,
            "label": "LIQ",
            "color": "black",
            "symbol": "x"
        })
        st.session_state.position = None
        st.session_state.entry_price = None
        st.session_state.entry_capital = 0
        st.warning("💥 강제청산 발생!")
        st.rerun()

# =====================
# 차트 구성
# =====================
price_fig = go.Figure()
price_fig.add_trace(go.Candlestick(
    x=df_view.index,
    open=df_view["open"],
    high=df_view["high"],
    low=df_view["low"],
    close=df_view["close"],
    name="BTC"
))

# ✅ 사용자가 그린 수평선
HLINE_COLORS = {"지지선": "dodgerblue", "저항선": "tomato", "기타": "gold"}
for hl in st.session_state.hlines:
    price_fig.add_hline(
        y=hl["price"],
        line_dash="dash",
        line_color=HLINE_COLORS.get(hl["label"], "white"),
        line_width=1.5,
        annotation_text=f"{hl['label']} {hl['price']:,.0f}",
        annotation_font_color=HLINE_COLORS.get(hl["label"], "white"),
        annotation_font_size=11
    )

# 지정가 주문선
if st.session_state.limit_order:
    lo = st.session_state.limit_order
    color = "lime" if lo["direction"] == "LONG" else "red"
    price_fig.add_hline(
        y=lo["price"],
        line_dash="dot",
        line_color=color,
        annotation_text=f"지정가 {lo['direction']} @ {lo['price']:,.0f}",
        annotation_font_color=color
    )

# 매매 마커
for m in st.session_state.trade_markers:
    price_fig.add_trace(go.Scatter(
        x=[m["time"]], y=[m["price"]],
        mode="markers+text",
        marker=dict(size=12, color=m["color"], symbol=m["symbol"]),
        text=[m["label"]], textposition="top center",
        name=m["label"]
    ))

price_fig.update_layout(
    xaxis_rangeslider_visible=False,
    height=500,
    dragmode="pan",  # 기본은 pan
    newshape=dict(line=dict(color="dodgerblue", width=2)),
    modebar_add=["drawline", "eraseshape"]
)

# =====================
# ✅ 수평선 그리기 모드 UI
# =====================
st.markdown("### 📏 수평선 그리기")
hl_col1, hl_col2, hl_col3, hl_col4 = st.columns([2, 1, 1, 1])

with hl_col1:
    hl_price = st.number_input(
        "수평선 가격 입력",
        value=float(round(current_price, 2)),
        step=100.0,
        format="%.2f",
        key="hl_price_input"
    )
with hl_col2:
    hl_label = st.selectbox("종류", ["지지선", "저항선", "기타"], key="hl_label_select")
with hl_col3:
    if st.button("➕ 수평선 추가"):
        st.session_state.hlines.append({"price": hl_price, "label": hl_label})
        st.rerun()
with hl_col4:
    if st.button("🗑️ 전체 삭제"):
        st.session_state.hlines = []
        st.rerun()

# 수평선 개별 삭제
if st.session_state.hlines:
    with st.expander("📋 수평선 목록 / 개별 삭제"):
        for i, hl in enumerate(st.session_state.hlines):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{hl['label']}** — {hl['price']:,.2f}")
            with c2:
                if st.button("❌", key=f"del_hl_{i}"):
                    st.session_state.hlines.pop(i)
                    st.rerun()

# =====================
# 차트 렌더링 (클릭 이벤트 수신)
# =====================
clicked = st.plotly_chart(
    price_fig,
    use_container_width=True,
    on_select="rerun",   # ✅ 클릭 시 rerun + 이벤트 반환
    key="price_chart"
)

# ✅ 차트 클릭으로 수평선 추가
if clicked and clicked.get("selection") and clicked["selection"].get("points"):
    pt = clicked["selection"]["points"][0]
    clicked_y = pt.get("y")
    if clicked_y:
        st.session_state.hlines.append({"price": round(clicked_y, 2), "label": hl_label})
        st.rerun()

# =====================
# 거래량 차트
# =====================
volume_fig = go.Figure()
volume_fig.add_trace(go.Bar(x=df_view.index, y=df_view["volume"], name="Volume"))
volume_fig.update_layout(height=200, xaxis_title="Time", yaxis_title="Volume")
st.plotly_chart(volume_fig, use_container_width=True)

# =====================
# 계좌 정보
# =====================
st.markdown(f"### 💰 Balance: **${st.session_state.balance:.2f}**  |  현재가: **{current_price:,.2f}**  |  포지션: **{st.session_state.position or '없음'}**")

if st.button("➡️ Next Candle"):
    st.session_state.current_step += 1
    st.rerun()

if st.session_state.position:
    if st.session_state.position == "LONG":
        pnl_pct = (current_price - st.session_state.entry_price) / st.session_state.entry_price * leverage * 100
    else:
        pnl_pct = (st.session_state.entry_price - current_price) / st.session_state.entry_price * leverage * 100
    pnl_dollar = st.session_state.entry_capital * (pnl_pct / 100)
    st.markdown(f"""
    ### 📌 현재 포지션
    - 방향: **{st.session_state.position}** | 진입가: **{st.session_state.entry_price:,.2f}** | 현재가: **{current_price:,.2f}**
    - 진입규모: **${st.session_state.entry_capital:,.2f}** | 레버리지: **{leverage}x**
    - 수익률: **{pnl_pct:.2f}%** | 평가손익: **${pnl_dollar:,.2f}**
    """)

# =====================
# 지정가 주문 UI
# =====================
st.markdown("---")
st.markdown("### 🎯 지정가 주문")
if st.session_state.limit_order:
    lo = st.session_state.limit_order
    st.info(f"⏳ 대기 중: **{lo['direction']}** @ **{lo['price']:,.0f}** | 비중 {lo['ratio']}% | 레버리지 {lo['leverage']}x")
    if st.button("🗑️ 지정가 주문 취소"):
        st.session_state.limit_order = None
        st.rerun()
else:
    lim_col1, lim_col2, lim_col3 = st.columns(3)
    with lim_col1:
        limit_price = st.number_input("진입 희망 가격", value=float(round(current_price, 2)), step=100.0, format="%.2f")
    with lim_col2:
        if st.button("🟢 지정가 LONG"):
            if st.session_state.position is None:
                st.session_state.limit_order = {"direction": "LONG", "price": limit_price, "ratio": position_ratio, "leverage": leverage}
                st.rerun()
            else:
                st.warning("포지션 보유 중에는 지정가 주문 불가")
    with lim_col3:
        if st.button("🔴 지정가 SHORT"):
            if st.session_state.position is None:
                st.session_state.limit_order = {"direction": "SHORT", "price": limit_price, "ratio": position_ratio, "leverage": leverage}
                st.rerun()
            else:
                st.warning("포지션 보유 중에는 지정가 주문 불가")

# =====================
# 시장가 버튼
# =====================
st.markdown("---")
st.markdown("### ⚡ 시장가 주문")

def enter_position(pos_type):
    capital = st.session_state.balance * (position_ratio / 100)
    st.session_state.entry_capital = capital
    st.session_state.entry_price = current_price
    st.session_state.position = pos_type

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("📈 LONG"):
        if st.session_state.position is None:
            enter_position("LONG")
            st.session_state.trade_markers.append({"time": df_view.index[-1], "price": current_price, "label": "LONG", "color": "lime", "symbol": "triangle-up"})
            st.rerun()

with col2:
    if st.button("📉 SHORT"):
        if st.session_state.position is None:
            enter_position("SHORT")
            st.session_state.trade_markers.append({"time": df_view.index[-1], "price": current_price, "label": "SHORT", "color": "red", "symbol": "triangle-down"})
            st.rerun()

with col3:
    if st.button("✂️ 부분청산 50%"):
        if st.session_state.position:
            pnl = (
                (current_price - st.session_state.entry_price)
                if st.session_state.position == "LONG"
                else (st.session_state.entry_price - current_price)
            ) / st.session_state.entry_price * leverage
            profit = st.session_state.entry_capital * pnl * 0.5
            st.session_state.balance += profit
            st.session_state.entry_capital *= 0.5
            st.session_state.trade_markers.append({"time": df_view.index[-1], "price": current_price, "label": "TP 50%", "color": "orange", "symbol": "circle"})
            st.rerun()

with col4:
    if st.button("❌ 전체청산"):
        if st.session_state.position:
            pnl = (
                (current_price - st.session_state.entry_price)
                if st.session_state.position == "LONG"
                else (st.session_state.entry_price - current_price)
            ) / st.session_state.entry_price * leverage
            pnl_pct_val = pnl * 100
            profit = st.session_state.entry_capital * pnl
            st.session_state.balance += profit
            st.session_state.total_pnl += profit
            st.session_state.trade_count += 1
            if profit > 0:
                st.session_state.win += 1
            else:
                st.session_state.lose += 1
            pd.DataFrame([{
                "time": df_view.index[-1],
                "direction": st.session_state.position,
                "entry_price": st.session_state.entry_price,
                "exit_price": current_price,
                "leverage": leverage,
                "position_ratio": position_ratio,
                "entry_capital": st.session_state.entry_capital,
                "pnl_dollar": profit,
                "pnl_pct": pnl_pct_val,
                "balance_after": st.session_state.balance
            }]).to_csv(LOG_FILE, mode="a", header=False, index=False)
            st.session_state.position = None
            st.session_state.entry_capital = 0
            st.session_state.entry_price = None
            st.rerun()

with col5:
    if st.button("🔄 다른 시간대 차트"):
        st.session_state.df_chart = generate_chart()
        st.session_state.start_idx = random.randint(0, len(st.session_state.df_chart) - 300)
        st.session_state.current_step = 300
        st.session_state.position = None
        st.session_state.entry_price = None
        st.session_state.entry_capital = 0
        st.session_state.trade_markers = []
        st.session_state.limit_order = None
        st.rerun()

# =====================
# 누적 성과
# =====================
total = st.session_state.win + st.session_state.lose
winrate = (st.session_state.win / total * 100) if total > 0 else 0
total_return_pct = (st.session_state.total_pnl / 1000.0) * 100

st.markdown(f"""
## 📊 누적 성과
- 총 트레이드 수: **{st.session_state.trade_count}회**
- 승: **{st.session_state.win}** | 패: **{st.session_state.lose}** | 승률: **{winrate:.2f}%**
- 누적 손익: **${st.session_state.total_pnl:,.2f}** | 누적 수익률: **{total_return_pct:.2f}%**
- 현재 잔고: **${st.session_state.balance:,.2f}**
""")