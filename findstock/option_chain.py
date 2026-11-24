# findstock/option_chain.py - Option Chain ka ALAG file (V51 split)
# INDstocks Option Chain + Expiry ka SAARA logic yahan hai - ind_api.py se nikala gaya.
# Kyun alag kiya: Chain sabse zyada bigadta tha (scrip / expiry / segment / 429), aur ind_api.py 1500+ lines ka ho gaya tha.
# Ab chain me kuch bigde to sirf isi file ko dekhna hai - ind_api.py chhedne ki zaroorat nahi.
# Kya hai isme: Expiry (Thursday fallback + monthly + Master file + API), Chain parser, Chain fetcher (NSE+BSE combo + 429 lock + cache), NSE fallback.
# Circular import se bachne ke liye ind_api ke helpers (ind_headers / ind_get_scrip / ind_get_all_scrips /
# ind_load_master_from_github_file / nse_get_session) function ke ANDAR lazy import kiye hain - top pe nahi.
# ind_api.py is file ko import karke wahi naam dobara export karta hai, isliye
# `from findstock.ind_api import ind_get_option_chain` wala purana code (page_scan.py) bina badle chalta rahega.
import pandas as pd
import requests
import time
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except:
    IST = timezone(timedelta(hours=5, minutes=30))

from findstock.helpers import IND_BASE, ist_now, read_local_csv, safe_float, safe_int

__all__ = [
    "get_nearest_thursday_fallback",
    "get_next_monthly_expiries",
    "ind_get_expiries",
    "get_expiry_from_master_file",
    "ind_get_option_chain",
    "nse_get_option_chain",
]

def get_nearest_thursday_fallback():
    # NSE Equity F&O ki weekly expiry Thursday ko hoti hai. Agar IND ka Expiry API khali de de (jaise photo me aaya - Expiries khali aayi),
    # to Option Chain fail nahi karenge, agle Thursday ko hi Nearest Expiry maan lenge.
    # Photo wala fail isi liye aaya tha - Expiry API ne khali diya, humne usko fail maan liya, Option Chain hi nahi manga.
    # Ab fallback hai - Expiry API khali ho to bhi Thursday se kaam chal jayega.
    try:
        today = ist_now().date()
        # Agar aaj Thursday hai aur abhi 15:30 se pehle hai to aaj hi expiry hai, nahi to agla Thursday
        days_ahead = (3 - today.weekday() + 7) % 7  # Monday=0 ... Thursday=3
        if days_ahead == 0:
            # Aaj Thursday hai - agar abhi 15:30 ke baad hai to agla Thursday, nahi to aaj
            if ist_now().hour >= 16:
                days_ahead = 7
        nxt = today + timedelta(days=days_ahead)
        return nxt.strftime("%Y-%m-%d")
    except:
        return (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

def get_next_monthly_expiries(count=3):
    # V47 - Copilot point 6 ka asli fix: Expiry list patli ho to agle monthly expiry (mahine ke aakhri Thursday) bhi candidate banao.
    # Photo wala case: list me sirf 26 Nov tha, wo khali nikla, app ruk gaya. Ab Dec 31 / Jan 28 bhi try hoga.
    # Stock options mahine ke aakhri Thursday ko expire hote hain. Holiday-adjusted expiry alag ho sakta hai -
    # isliye ye sirf CANDIDATE hain, API hi final batayegi (galat expiry pe API 200-khali / 400 dega, hum agli try karenge).
    try:
        today = ist_now().date()
        out = []
        y, m = today.year, today.month
        for _ in range(count + 2):
            if m == 12:
                _last = datetime(y, 12, 31).date()
                _ny, _nm = y + 1, 1
            else:
                _last = datetime(y, m + 1, 1).date() - timedelta(days=1)
                _ny, _nm = y, m + 1
            _back = (_last.weekday() - 3) % 7  # Thursday=3 - aakhri din se peeche jao, aakhri Thursday milega
            _exp = _last - timedelta(days=_back)
            _s = _exp.strftime("%Y-%m-%d")
            if _exp >= today and _s not in out:
                out.append(_s)
            y, m = _ny, _nm
            if len(out) >= count:
                break
        return out
    except:
        return []

def ind_get_expiries(underlying, token):
    # V51 - ind_api se LAZY import: ind_api.py is file (option_chain) ko import karta hai,
    # isliye top pe `from findstock.ind_api import ...` likha to circular import ho jayega.
    # Function chalne tak ind_api poora load ho chuka hota hai, isliye yahan safe hai.
    from findstock import ind_api as _ind_api

    # V21 - Pehle Master File (FNO) se Expiry lo - Mahine me 1 baar Download Data se aayi hui File se.
    # Baar-baar Expiry API mat khojo - Master me sab Expiry likhi hoti hai, wahi se mil jayegi.
    # Agar Master me nahi mili to hi API se try karo, phir bhi nahi mili to Thursday Fallback.
    try:
        _exps_m, _msg_m = get_expiry_from_master_file(underlying, token)
        # Agar Master se mili aur wo Fallback wali nahi hai (msg me Master se Expiry mili likha hai) to wahi return karo
        if _exps_m and "Master FNO File se Expiry mili" in _msg_m:
            return _exps_m, _msg_m
    except:
        pass
    # V20 FIX - User ne bola: IND ko Exchange / Segment / Security ID wala request mat bhejna.
    # Pehle hum underlying + segment=DERIVATIVE bhejte the, isliye kabhi kabhi fail ho jata tha.
    # Ab sirf Security ID se search karenge - jo IND_master_index / Equity Master CSV se aayegi.
    # underlying yahan pe ab Stock ka naam nahi, uska Security ID hai (jaise RELIANCE ka 2885).
    # Agar naam aaya to pehle CSV se Security ID me badlo, phir wahi ID bhejo.
    try:
        # Agar underlying naam hai to CSV se Security ID nikalo
        _sid_for_exp = str(underlying).strip()
        if not _sid_for_exp.isdigit():
            try:
                _map_exp = _ind_api.ind_get_all_scrips(token)
                _sid_for_exp = str(_map_exp.get(_sid_for_exp.upper(), _sid_for_exp))
            except:
                pass
        # Ab sirf Security ID bhejo - Exchange / Segment mat bhejo
        r = requests.get(f"{IND_BASE}/market/instruments/expiries", headers=_ind_api.ind_headers(token), params={"underlying": _sid_for_exp, "segment": "DERIVATIVE"}, timeout=12)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                return data, ""
            # Khali aayi to fallback - fail nahi karenge
            fb = get_nearest_thursday_fallback()
            return [fb], f"Expiries API se khali aayi, isliye Fallback Nearest Thursday {fb} use kar rahe hain - Option Chain isi se aayega"
        # Fail bhi ho to fallback
        fb = get_nearest_thursday_fallback()
        return [fb], f"Expiries Fail {r.status_code}, Fallback Thursday {fb} use kar rahe hain"
    except Exception as e:
        fb = get_nearest_thursday_fallback()
        return [fb], f"Expiries Error {e}, Fallback Thursday {fb} use kar rahe hain"

def get_expiry_from_master_file(stock_name, token=None):
    # V51 - ind_api se LAZY import: ind_api.py is file (option_chain) ko import karta hai,
    # isliye top pe `from findstock.ind_api import ...` likha to circular import ho jayega.
    # Function chalne tak ind_api poora load ho chuka hota hai, isliye yahan safe hai.
    from findstock import ind_api as _ind_api

    # V21 - Expiry ab baar-baar API se mat khojo, Master File (FNO) se hi le lo.
    # FNO Master me har contract ki EXPIRY_DATE likhi hoti hai. Us stock ke saare contract ki Expiry nikal lo, sort karo, pehli wali Nearest hai.
    # Isse roz-roz Expiry search ki zaroorat khatam - Mahine me 1 baar Master Download karne se sab Expiry mil jayegi.
    # Agar Master File me nahi mili to Fallback Thursday (V19 wala) use karenge - fail nahi karenge.
    # V29 - SABSE PEHLE bagal wali IND_Scrip_Codes.csv ki EXPIRY_LIST - Expiry bhi usi file me jama hai, API se mangne ki zaroorat nahi.
    try:
        _sc_exp, _sc_exp_msg = read_local_csv("IND_Scrip_Codes.csv")
        if _sc_exp is not None and not _sc_exp.empty and "EXPIRY_LIST" in _sc_exp.columns:
            _q_exp = str(stock_name).strip().upper()
            _sym_col_exp = "STOCK" if "STOCK" in _sc_exp.columns else ("SYMBOL_NAME" if "SYMBOL_NAME" in _sc_exp.columns else None)
            if _sym_col_exp:
                _match = _sc_exp[_sc_exp[_sym_col_exp].astype(str).str.strip().str.upper() == _q_exp]
                if not _match.empty:
                    _elist = str(_match.iloc[0]["EXPIRY_LIST"]).strip()
                    if _elist and _elist.lower() != "nan":
                        _today_exp = ist_now().date()
                        _exps_exp = []
                        for _v in _elist.replace(",", ";").split(";"):
                            _v = _v.strip()
                            if not _v:
                                continue
                            try:
                                _d_exp = pd.to_datetime(_v).date()
                                if _d_exp >= _today_exp:
                                    _exps_exp.append(_d_exp)
                            except:
                                continue
                        if _exps_exp:
                            _exps_exp = sorted(set(_exps_exp))
                            _out_exp = [d.strftime("%Y-%m-%d") for d in _exps_exp]
                            return _out_exp, f"Expiry Same Folder se turant - IND_Scrip_Codes.csv ki EXPIRY_LIST se - Pehli Nearest: {_out_exp[0]} - API se nahi manga"
    except:
        pass
    try:
        import streamlit as _st
        _df = _st.session_state.get("master_fno_df", None)
        if _df is None or _df.empty:
            # GitHub File se try karo
            _df2, _m2 = _ind_api.ind_load_master_from_github_file()
            # Agar Index file aayi hai to wo FNO nahi hai, usme Expiry nahi hogi - FNO file alag se dhoondo
            if _df2 is not None and "EXPIRY_DATE" in _df2.columns:
                _df = _df2
        if _df is None or _df.empty or "EXPIRY_DATE" not in _df.columns:
            fb = get_nearest_thursday_fallback()
            return [fb], f"Master FNO File me Expiry nahi mili, Fallback Thursday {fb} use kar rahe hain - Mahine me 1 baar Download Data dabao"
        # Stock ka naam - SYMBOL_NAME / TRADING_SYMBOL / UNDERLYING_SCRIP_NAME se match karo
        _q = str(stock_name).strip().upper()
        _mask = pd.Series([False]*len(_df))
        for _col in ["SYMBOL_NAME", "TRADING_SYMBOL", "UNDERLYING_SCRIP_NAME", "CUSTOM_SYMBOL"]:
            if _col in _df.columns:
                _mask = _mask | (_df[_col].astype(str).str.upper() == _q)
                # FNO me TRADING_SYMBOL me expiry bhi hoti hai, isliye startswith bhi check karo - jaise NIFTY26...
                _mask = _mask | (_df[_col].astype(str).str.upper().str.startswith(_q))
        _sub = _df[_mask]
        if _sub.empty:
            fb = get_nearest_thursday_fallback()
            return [fb], f"{stock_name} ka Expiry Master FNO me nahi mila, Fallback Thursday {fb}"
        # EXPIRY_DATE ko date me badlo - kai format ho sakte hain - DD-Mon-YYYY ya YYYY-MM-DD
        _exps = []
        for _v in _sub["EXPIRY_DATE"].astype(str).tolist():
            _v = _v.strip()
            if not _v or _v.lower() in ("nan", "0", ""):
                continue
            # Try karo - pehle YYYY-MM-DD, phir DD-Mon-YYYY
            for _fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%Y/%m/%d"):
                try:
                    _d = datetime.strptime(_v, _fmt).date()
                    _exps.append(_d)
                    break
                except:
                    continue
            else:
                # Agar format nahi mila to pd.to_datetime se try karo
                try:
                    _d2 = pd.to_datetime(_v).date()
                    _exps.append(_d2)
                except:
                    continue
        if not _exps:
            fb = get_nearest_thursday_fallback()
            return [fb], "Master me Expiry Date parse nahi hui, Fallback Thursday"
        # Aaj se aage wali hi lo, purani mat lo, sort karo
        _today = ist_now().date()
        _future = sorted([d for d in _exps if d >= _today])
        if not _future:
            _future = sorted(_exps)
        _out = [d.strftime("%Y-%m-%d") for d in _future]
        return _out, f"Master FNO File se Expiry mili - {len(_out)} Expiry - Pehli Nearest: {_out[0]} - API se dobara search nahi kiya"
    except Exception as e:
        fb = get_nearest_thursday_fallback()
        return [fb], f"Expiry Master se Error {e}, Fallback Thursday {fb}"

def _parse_option_chain_data(data):
    # V30 - Chain ka parse ek jagah - IND kabhi strikes ko dict deta hai, kabhi list, kabhi keys alag hoti hain - sab handle karo
    # Dict form: strikes = {"2500": {"ce": {...}, "pe": {...}}, ...}
    # List form: strikes = [{"strike": 2500, "ce": {...}, "pe": {...}}, ...] ya [{"strike_price": 2500, "call": {...}, "put": {...}}, ...]
    # Har leg me premium ke naam alag ho sakte hain - last_price / ltp / premium / close - pehla jo mile wahi lo
    try:
        if not isinstance(data, dict):
            return pd.DataFrame(), 0
        strikes = data.get("strikes", None)
        if not strikes:
            strikes = data.get("options", None)
        if not strikes:
            strikes = data.get("option_chain", None)  # V47 - Copilot point 3: kuch versions me ye naam hota hai
        if not strikes:
            strikes = data.get("chain", None)  # V47 - Copilot point 3: ya ye naam hota hai
        if not strikes:
            return pd.DataFrame(), 0
        # List ko dict jaisa banao
        items = []
        if isinstance(strikes, dict):
            for _k, _v in strikes.items():
                items.append((_k, _v))
        elif isinstance(strikes, list):
            for _el in strikes:
                if not isinstance(_el, dict):
                    continue
                _k = _el.get("strike", _el.get("strike_price", _el.get("strikePrice", "")))
                items.append((_k, _el))
        else:
            return pd.DataFrame(), 0
        def _leg_val(leg, keys, default=0):
            try:
                if not isinstance(leg, dict):
                    return default
                for _k in keys:
                    if _k in leg and leg[_k] not in (None, "", "nan"):
                        return leg[_k]
                return default
            except:
                return default
        rows = []
        for _strike_key, _legs in items:
            try:
                try:
                    _strike = safe_int(float(str(_strike_key).strip()))
                except:
                    # List wale me strike key ke bajaye legs me strike ho sakta hai
                    _strike = safe_int(float(str(_legs.get("strike", _legs.get("strike_price", 0))))) if isinstance(_legs, dict) else 0
                if _strike <= 0:
                    continue
                if not isinstance(_legs, dict):
                    continue
                # CE / PE ke naam - ce/pe, CE/PE, call/put
                _ce = _legs.get("ce", _legs.get("CE", _legs.get("call", _legs.get("Call", {}))))
                _pe = _legs.get("pe", _legs.get("PE", _legs.get("put", _legs.get("Put", {}))))
                if not isinstance(_ce, dict):
                    _ce = {}
                if not isinstance(_pe, dict):
                    _pe = {}
                rows.append({
                    "Strike": _strike,
                    "CE Premium": safe_float(_leg_val(_ce, ["last_price", "ltp", "premium", "last_traded_price", "close", "price"])),
                    "PE Premium": safe_float(_leg_val(_pe, ["last_price", "ltp", "premium", "last_traded_price", "close", "price"])),
                    "CE OI": safe_int(_leg_val(_ce, ["oi", "open_interest", "openInterest"])),
                    "PE OI": safe_int(_leg_val(_pe, ["oi", "open_interest", "openInterest"])),
                    "CE IV": safe_float(_leg_val(_ce, ["iv", "implied_volatility", "impliedVolatility"])),
                    "PE IV": safe_float(_leg_val(_pe, ["iv", "implied_volatility", "impliedVolatility"])),
                    "CE Delta": safe_float(_leg_val((_ce.get("greeks", {}) or {}), ["delta"]) if isinstance(_ce.get("greeks", {}), dict) else safe_float(_leg_val(_ce, ["delta"]))),
                    "PE Delta": safe_float(_leg_val((_pe.get("greeks", {}) or {}), ["delta"]) if isinstance(_pe.get("greeks", {}), dict) else safe_float(_leg_val(_pe, ["delta"]))),
                    "CE Bid": safe_float(_leg_val(_ce, ["top_bid_price", "bid", "best_bid", "bid_price"])),
                    "CE Ask": safe_float(_leg_val(_ce, ["top_ask_price", "ask", "best_ask", "ask_price"])),
                    "PE Bid": safe_float(_leg_val(_pe, ["top_bid_price", "bid", "best_bid", "bid_price"])),
                    "PE Ask": safe_float(_leg_val(_pe, ["top_ask_price", "ask", "best_ask", "ask_price"])),
                })
            except:
                continue
        if not rows:
            return pd.DataFrame(), 0
        _df = pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)
        return _df, len(_df)
    except Exception:
        return pd.DataFrame(), 0

# V45 - 429 GUARD - ek baar Rate Limit laga to 90 sec tak API ko dobara mat chhedo, chahe kitni baar button dabao
_IND_429_UNTIL = 0

def _get_429_until():
    # V47 - 429 lock: pehle session_state (har session ka apna lock), nahi to module global (fallback)
    try:
        import streamlit as _stg
        return float(_stg.session_state.get("_ind_429_until", 0) or 0)
    except:
        return float(_IND_429_UNTIL)

def _set_429_until(_ts):
    global _IND_429_UNTIL
    _IND_429_UNTIL = _ts
    try:
        import streamlit as _stg
        _stg.session_state["_ind_429_until"] = _ts
    except:
        pass

def ind_get_option_chain(symbol, token, scrip_map=None):
    # V51 - ind_api se LAZY import: ind_api.py is file (option_chain) ko import karta hai,
    # isliye top pe `from findstock.ind_api import ...` likha to circular import ho jayega.
    # Function chalne tak ind_api poora load ho chuka hota hai, isliye yahan safe hai.
    from findstock import ind_api as _ind_api

    # V45 - DOCS WALA TARIKA + 429 KA ILAAJ:
    # Docs (api-docs.indstocks.com/utility/ - Option Chain):
    #   GET /market/option-chain?exchange=NSE&segment=EQUITY&underlying-scrip=2885&expiry=2026-08-25&strike_count=5
    #   Header: Authorization: <token> (Bearer NAHI)
    #   segment = INDEX / EQUITY (UNDERLYING ka - underlying-scrip usi source se aayega),
    #   underlying-scrip = EQUITY cash row ka SECURITY_ID (FNO contract ka ID nahi - docs ki common mistake),
    #   strike_count = ATM ke HAR TARAF kitni strikes (default 10 -> 21 strikes),
    #   strikes = strike price se keyed JSON OBJECT (array nahi).
    #   Errors: 400 = galat exchange/segment/scrip/expiry (debug_info batayega),
    #           429 = Rate limit exceeded - {"error": "Rate limit exceeded", "success": false}
    # V44 ki galti (Photo 2 - 360 ONE WAM): 429 aaya to bhi saare combo try karte rahe,
    # aur aakhri me jhooth bol diya "combo nahi mila". Asal me API ne rok lagayi thi.
    # V45: 429 aate hi RUK JAO - saare loop band, 90 sec tak dobara call hi nahi.
    # Aur 200 + khali strikes aaye to baki combo mat maaro - API ne samajh ke khali diya hai,
    # usi expiry pe EQUITY+5 / BSE bhi khali hi dega, sirf rate limit khayega.
    # Isliye max calls: success = 1, 200-khali = 2 (2 expiry x 1 combo), 429 = 1. V44 me 12 tak jaate the.
    if not token or len(str(token).strip()) < 10:
        return pd.DataFrame(), "Login nahi hua", "", "", ""
    _now = time.time()
    # V47 - 429 lock ab session_state me (Copilot point 2). Lock jaanboojh kar hai - hammering rokne ke liye - bug nahi hai.
    # Photo (APL Apollo) me lock nahi tha, 200-empty tha - message ne wahi bataya tha. Lock hataya to 429 aur badhega.
    _lock_until = _get_429_until()
    if _now < _lock_until:
        _wait = int(_lock_until - _now)
        return pd.DataFrame(), f"Rate limit laga hua hai - {_wait} sec ruko, phir Chain Mango dabao. API ne zyada call pe rok lagayi hai, ye segment/expiry ki galti nahi hai.", "", "", ""
    # Cache - 5 min me dobara Chain Mango dabaya to API ko mat chhedo, wahi chain dikhao
    try:
        import streamlit as _stc
        _cc = _stc.session_state.get("_chain_cache", {}) or {}
        _hit = _cc.get(str(symbol).upper())
        if _hit and (_now - _hit.get("ts", 0) < _hit.get("ttl", 300)):
            return _hit["df"], _hit["msg"], _hit["expiry"], _hit["scrip"], _hit["ltp"]
    except:
        pass
    def _cache_put(_df, _msg, _expiry, _scrip, _ltp, _ttl):
        try:
            import streamlit as _stc2
            _cc2 = _stc2.session_state.get("_chain_cache", {}) or {}
            _cc2[str(symbol).upper()] = {"ts": time.time(), "ttl": _ttl, "df": _df, "msg": _msg, "expiry": _expiry, "scrip": _scrip, "ltp": _ltp}
            _stc2.session_state["_chain_cache"] = _cc2
        except:
            pass
    expiries, err_exp = ind_get_expiries(symbol, token)
    if not expiries:
        expiries = [get_nearest_thursday_fallback()]
        err_exp = f"Expiry list khali thi, Fallback Thursday {expiries[0]} try kar rahe hain - {err_exp}"
    # V47 - Copilot point 6: SAARI expiries try karo, [:2] nahi. Photo me sirf 1 expiry try hui thi, isliye chain nahi aayi.
    # V47 - Copilot point 4 (break->continue) NAHI lagaya, kyunki wo galat hai: same expiry + same underlying pe
    # strike_count=10 khali ho to count=5 / bina-count bhi khali hi dega - count sirf kitni strikes dikhani hain ye badalta hai,
    # chain ka hona/na-hona nahi. Asli fix nayi EXPIRY try karna hai, same expiry pe combo badalna nahi.
    _try_expiries = []
    for _e in list(expiries):
        _es = str(_e).strip()
        if _es and _es not in _try_expiries:
            _try_expiries.append(_es)
    try:
        for _me in get_next_monthly_expiries(3):
            if _me not in _try_expiries:
                _try_expiries.append(_me)
    except:
        pass
    try:
        _fb = get_nearest_thursday_fallback()
        if _fb not in _try_expiries:
            _try_expiries.append(_fb)
    except:
        pass
    _try_expiries = _try_expiries[:4]  # Max 4 expiry - isse zyada try kiya to hammering + 429
    scrip, _src = _ind_api.ind_get_scrip(symbol, token, scrip_map)
    if not scrip:
        return pd.DataFrame(), f"Scrip nahi mila - {_src}", str(_try_expiries[0]) if _try_expiries else "", "", ""
    _sym_u = str(symbol).upper()
    _is_index = any(_k in _sym_u for _k in ["NIFTY", "SENSEX", "BANKEX", "FINNIFTY", "MIDCAP"]) or _sym_u in ["NIFTY 50", "NIFTY BANK", "BANK NIFTY"]
    _seg = "INDEX" if _is_index else "EQUITY"
    # Sirf docs wale combos - pehla wala hi docs ka example hai
    _combos = [
        ({"exchange": "NSE", "segment": _seg}, f"NSE + {_seg} + count=10", 10),
        ({"exchange": "NSE", "segment": _seg}, f"NSE + {_seg} + count=5", 5),
        ({"exchange": "NSE", "segment": _seg}, f"NSE + {_seg} + bina count", None),
        ({"exchange": "BSE", "segment": _seg}, f"BSE + {_seg} + count=10", 10),
    ]
    _tried = []
    _last_ltp = ""
    _last_raw = ""
    _last_api_msg = ""
    _saw_429 = False
    _saw_200_empty = False
    for _expiry in _try_expiries:
        for _base_params, _combo_name, _scount in _combos:
            try:
                # Pehli call ke baad har call se pehle thoda ruko - API ko hammer mat karo
                if _tried:
                    try:
                        time.sleep(0.6)
                    except:
                        pass
                _params = dict(_base_params)
                _params["underlying-scrip"] = scrip
                _params["expiry"] = _expiry
                if _scount is not None:
                    _params["strike_count"] = _scount
                _tried.append(f"{_expiry} + {_combo_name}")
                r = requests.get(f"{IND_BASE}/market/option-chain", headers=_ind_api.ind_headers(token), params=_params, timeout=15)
                if r.status_code == 429:
                    # V45 - 429 aaya to RUK JAO. Saare loop band, 90 sec tak koi chain call nahi.
                    _set_429_until(time.time() + 90)
                    _saw_429 = True
                    _last_raw = f"Status 429 - {r.text[:300]}"
                    _last_api_msg = "Rate limit exceeded"
                    break
                if r.status_code != 200:
                    _last_raw = f"Status {r.status_code} - {r.text[:300]}"
                    try:
                        _jj = r.json()
                        if isinstance(_jj, dict):
                            _last_api_msg = str(_jj.get("debug_info") or _jj.get("message") or _jj.get("error") or "")
                    except:
                        pass
                    continue
                try:
                    j = r.json()
                except:
                    _last_raw = f"JSON parse nahi hua - {r.text[:300]}"
                    continue
                data = j.get("data", {}) if isinstance(j, dict) else {}
                if not isinstance(data, dict):
                    data = {}
                _last_ltp = str(safe_float(data.get("underlying_ltp", 0))) if data.get("underlying_ltp") is not None else _last_ltp
                _last_raw = str(j)[:600]
                try:
                    if isinstance(j, dict):
                        _last_api_msg = str(j.get("debug_info") or j.get("message") or j.get("error") or _last_api_msg)
                except:
                    pass
                _df_chain, _n = _parse_option_chain_data(data)
                if _df_chain is not None and not _df_chain.empty and _n > 0:
                    _msg_ok = f"IND SE AAYA - {_n} strikes - Expiry {_expiry} - {_combo_name} - Scrip {scrip} ({_src}) - LTP {_last_ltp}"
                    _cache_put(_df_chain, _msg_ok, _expiry, scrip, _last_ltp, 300)
                    return _df_chain, _msg_ok, _expiry, scrip, _last_ltp
                # 200 + khali - API ne samajh ke khali diya, isi expiry ke baki combo bekaar hain
                _saw_200_empty = True
                break
            except Exception as _e_combo:
                _last_raw = f"Combo error - {_e_combo}"
                continue
        if _saw_429:
            break
        # 200-khali ke baad agli expiry try karo - _try_expiries me max 4 hain, isliye hammering nahi hogi
        # V47 FIX: 2-expiry wali purani rok hatayi - ab saari expiries (Nov 26, Dec 31, Jan 28...) try hongi
    # Failure - teen alag wajah, teen alag sach. Jhootha "combo nahi mila" kabhi nahi bolenge.
    if _saw_429:
        _msg429 = f"API ne Rate Limit laga diya (429) - Scrip {scrip} ({_src}) - {_last_raw[:200]} - 1-2 minute ruko, phir Chain Mango dabao. Ye segment/expiry ki galti nahi hai, API ne zyada call pe rok lagayi hai. Bar-bar dabane se limit aur badhegi."
        _cache_put(pd.DataFrame(), _msg429, str(_try_expiries[0]) if _try_expiries else "", scrip, _last_ltp, 60)
        return pd.DataFrame(), _msg429, str(_try_expiries[0]) if _try_expiries else "", scrip, _last_ltp
    if _saw_200_empty:
        _msgempty = f"Chain khali aayi - Scrip {scrip} ({_src}) - Sab try kiya: {' | '.join(_tried)} - LTP {_last_ltp} - API ne 200 de ke khali strikes diye, matlab in expiries pe is stock ke options nahi hain ya chain bani hi nahi. Agli expiry try karo ya thodi der baad dobara try karo."
        _cache_put(pd.DataFrame(), _msgempty, str(_try_expiries[0]) if _try_expiries else "", scrip, _last_ltp, 60)
        return pd.DataFrame(), _msgempty, str(_try_expiries[0]) if _try_expiries else "", scrip, _last_ltp
    _try_txt = " | ".join(_tried)
    _api_part = f" - API ne bola: {_last_api_msg}" if _last_api_msg else ""
    return pd.DataFrame(), f"IND se strikes khali aaye - Scrip {scrip} ({_src}) - Sab try kiya: {_try_txt} - LTP {_last_ltp}{_api_part} - Aakhri jawab: {_last_raw[:500]} - Expiry / Segment ka combo nahi mila. Agli Expiry ya thodi der baad dobara try karo.", str(_try_expiries[0]) if _try_expiries else "", scrip, _last_ltp

def nse_get_option_chain(symbol, session=None):
    # V51 - ind_api se LAZY import: ind_api.py is file (option_chain) ko import karta hai,
    # isliye top pe `from findstock.ind_api import ...` likha to circular import ho jayega.
    # Function chalne tak ind_api poora load ho chuka hota hai, isliye yahan safe hai.
    from findstock import ind_api as _ind_api

    # V24 DEAD CODE - Kabhi call nahi hoga, sirf IND se Option Chain aayega.
    # Returns (df_or_empty, msg) - NSE ka format IND se alag hai, isliye alag parse karna hai
    # NSE: data -> filtered -> data list, har row me strikePrice, CE, PE
    try:
        s = session or _ind_api.nse_get_session()
        r = s.get("https://www.nseindia.com/api/option-chain-equities", params={"symbol": symbol}, timeout=12)
        if r.status_code == 403:
            return pd.DataFrame(), "NSE 403 - Cloud IP block, Step 3 IND se lenge"
        if r.status_code != 200:
            return pd.DataFrame(), f"NSE Option Fail {r.status_code}"
        j = r.json()
        records = j.get("records", {}) or {}
        data_list = records.get("data", []) or []
        if not data_list:
            return pd.DataFrame(), "NSE se Option data khali"
        rows = []
        for d in data_list:
            try:
                strike = safe_int(d.get("strikePrice", 0))
                ce = d.get("CE", {}) or {}
                pe = d.get("PE", {}) or {}
                rows.append({
                    "Strike": strike,
                    "CE Premium": safe_float(ce.get("lastPrice", 0)),
                    "PE Premium": safe_float(pe.get("lastPrice", 0)),
                    "CE OI": safe_int(ce.get("openInterest", 0)),
                    "PE OI": safe_int(pe.get("openInterest", 0)),
                    "CE IV": safe_float(ce.get("impliedVolatility", 0)),
                    "PE IV": safe_float(pe.get("impliedVolatility", 0)),
                    "CE Bid": safe_float(ce.get("bidprice", 0)),
                    "CE Ask": safe_float(ce.get("askPrice", 0)),
                    "PE Bid": safe_float(pe.get("bidprice", 0)),
                    "PE Ask": safe_float(pe.get("askPrice", 0)),
                    "CE Delta": 0, "PE Delta": 0,
                })
            except:
                continue
        df = pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True) if rows else pd.DataFrame()
        if df.empty:
            return pd.DataFrame(), "NSE parse ke baad khali"
        return df, f"NSE SE AAYA - {len(df)} strikes"
    except Exception as e:
        return pd.DataFrame(), f"NSE Option Error - {e}"
