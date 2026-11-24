# Find Stock - V50 FIXED (docs-exact option chain + BSE fallback + history tz fix + GitHub Models chatbot)
FIXES:
1. Option Chain - Docs (api-docs.indstocks.com -> Options Toolkit) ke hisab se bilkul sahi call:
   - segment = INDEX / EQUITY ONLY (DERIVATIVE yahan valid hi nahi tha)
   - underlying-scrip = Equity cash-market row ka SECURITY_ID (ind_get_equity_scrip - IND_Master_Equity.csv se, MAP sirf fallback)
   - expiry = YYYY-MM-DD, strike_count = 10, base = https://api.indstocks.com
2. ASLI BUG - 200-empty pe break BSE ko kabhi try hi nahi karne deta tha. Ab continue hota hai - NSE khali to BSE try hoga (alag exchange ki apni chain hoti hai).
3. History Download - "can't compare offset-naive and offset-aware datetimes" fix. Isi se Candle/Gap/VWAP/Volume 0 aa raha tha.
4. Chatbot advance - GitHub Models (LLM) se jawab, sirf apne scan/live data ke context ke saath. Token na ho to purana rule-based chatbot chalta hai.
   GitHub Models token: Streamlit Secrets me daalo -> GITHUB_MODELS_TOKEN = "ghp_...."
   GitHub me PAT banao (Settings -> Developer settings -> Personal access tokens), usme models:read permission do.
5. Circular import fix (data.py) + fresh-session KeyError fix + manual_list NameError fix - pehle wale fixes bane hue hain.
GitHub me: pages/ DELETE karo, app.py + findstock/ + views/ upload karo, data/ wali Master files rehne do, Streamlit Cloud -> Reboot.
Title me "Find Stock Version 50" dikhega to samjho nayi wali deploy hui.
