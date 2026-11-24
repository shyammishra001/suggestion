# app.py - V48 - Thin entry: Login + Menu + sirf chuna hua page load hoga
# V48 split: Logic findstock/ me, har option alag page file me. Jis option pe click hoga, sirf wahi page import hoga.
from findstock.helpers import *
from findstock import diary as _diary_mod
from findstock import ind_api as _ind_api_mod
# V50 FIX - fresh session me keys pehle se set, warna line 8 pe KeyError
for _k, _v in [("authenticated", False), ("indmoney_secret", ""), ("indmoney_connected", False)]:
    st.session_state.setdefault(_k, _v)
_diary_mod._ensure_diary_csv()
# ---------------- LOGIN ----------------
if not st.session_state.authenticated:
    st.title("Scan Stock")
    st.caption(f"Find Stock Version {APP_VERSION}")
    st.write("Token daalo.")
    with st.form("login_form"):
        indmoney_secret = st.text_input("Token", type="password", placeholder="Token")
        submit = st.form_submit_button("Kholo", use_container_width=True)
        if submit:
            if not indmoney_secret or len(indmoney_secret) < 10:
                st.error("Token daalo")
            else:
                ok, msg = _ind_api_mod.ind_test_profile(indmoney_secret)
                if not ok:
                    st.error(msg)
                    st.write("Token galat hai.")
                else:
                    st.session_state.authenticated = True
                    st.session_state.indmoney_secret = indmoney_secret
                    st.session_state.indmoney_connected = True
                    st.session_state.indmoney_debug = msg
                    st.rerun()
    if st.button("Bina Token ke Dekho"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.indmoney_connected = False
        st.rerun()
    st.stop()
# ---------------- MASTER CSV - chupchaap load, screen pe kuch nahi ----------------
try:
    _gh_df, _gh_msg = _ind_api_mod.ind_load_master_from_github_file()
    if _gh_df is not None and not _gh_df.empty:
        st.session_state["master_equity_df"] = _gh_df
except Exception:
    pass
# ---------------- MENU - sirf chuna hua option load hoga ----------------
st.sidebar.title("Menu")
_choice = st.sidebar.radio("Option", ["Scan", "Diary", "Download Data", "AI Chat"], key="main_menu_choice")
if _choice == "Scan":
    from views import page_scan as _pg
elif _choice == "Diary":
    from views import page_diary as _pg
elif _choice == "Download Data":
    from views import page_download as _pg
else:
    from views import page_ai as _pg
_pg.render()
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear(); st.rerun()
if st.sidebar.button("Logout"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()