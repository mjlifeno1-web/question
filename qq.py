import streamlit as st
import google.generativeai as genai

# 頁面標題與設定
st.set_page_config(page_title="100 核心架構萬能解題系統", page_icon="🧠")
st.title("100 核心架構萬能解題系統")

# 側邊欄：設定 Gemini API Key
with st.sidebar:
    st.header("⚙️ 系統設定")
    api_key = st.text_input("請輸入 Gemini API Key：", type="password")
    st.markdown("[👉 點此免費取得 Gemini API Key](https://aistudio.google.com/app/apikey)")

# 主畫面輸入區
user_input = st.text_area("請在此輸入題目或參數：", placeholder="例如：輪班睡不著該如何調整...", height=150)

# 系統提示詞（System Prompt），固定 100 核心架構的角色與輸出格式
SYSTEM_PROMPT = """
你是一個精通「100 核心架構」的萬能解題專家。
請針對使用者提出的問題進行深度分析，並提供結構化、實用且具體的解答。

回答結構必須包含：
1. 【核心問題診斷】：精準切中問題根源。
2. 【100 核心架構拆解】：從不同維度或模組進行系統化分析。
3. 【最佳處置方案與行動清單】：給出清晰、可立即執行的步驟建議。

請保持回答條理分明、專業且易於閱讀。
"""

if st.button("開始解題", type="primary"):
    if not api_key:
        st.error("請先在左側邊欄輸入你的 Gemini API Key！")
    elif not user_input.strip():
        st.warning("請輸入題目或參數！")
    else:
        try:
            with st.spinner("AI 正在運用 100 核心架構深度分析中..."):
                # 設定 Gemini API Key
                genai.configure(api_key=api_key)
                
                # 初始化模型
                model = genai.GenerativeModel("gemini-2.5-flash")
                
                # 組合 Prompt 並發送請求
                full_prompt = f"{SYSTEM_PROMPT}\n\n使用者問題：\n{user_input}"
                response = model.generate_content(full_prompt)
                
            st.success("解題完成！")
            st.subheader("分析解答")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"解題失敗，請檢查 API Key 是否正確或稍後重試。\n錯誤訊息：{e}")
