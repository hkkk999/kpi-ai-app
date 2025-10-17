# _*_ coding: utf-8 _*_
# @Time : 16:29
# @Author : hkk
# @File : kpi_ai_streamlit.py
# @Project : AutoExcelToPpt

import os
import json
import re
import streamlit as st
from dotenv import load_dotenv
import requests
import TEMPLATE_DESCRIPTIONS as TEMPLATE
import VARIABLES as VARIABLES
import  build_prompt as build_prompt
import  pandas as pd

# # ==================== 加载配置 ====================
# load_dotenv()

# 从 Streamlit Secrets 读取api
try:
    SILICONFLOW_API_KEY = st.secrets["SILICONFLOW_API_KEY"]
except KeyError:
    st.error("❌ API Key 未配置，请联系管理员设置 Streamlit Secrets")
    st.stop()
MODEL_NAME = "Qwen/Qwen3-Omni-30B-A3B-Instruct"

# ==================== 调用 API ====================
def call_siliconflow(user_input):
    url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = build_prompt.build_prompt(user_input)

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "top_p": 0,
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']

        # 提取 JSON
        json_start = content.find('[')
        json_end = content.rfind(']') + 1
        if json_start == -1 or json_end == 0:
            return {"error": "AI 返回内容不是有效 JSON 数组格式"}

        json_str = content[json_start:json_end]
        parsed = json.loads(json_str)

        # 修复变量格式：确保所有 $var$ → $ var []$
        def fix_var(text):
            for var in VARIABLES.VARIABLES:
                text = text.replace(f"${var}$", f"$ {var} []$")
                text = text.replace(f"$ {var} $", f"$ {var} []$")
                if f"$ {var}" in text and "]$" not in text:
                    text = text.replace(f"$ {var}", f"$ {var} []$")
            return text

        for item in parsed:
            item["condition"] = fix_var(item.get("condition", ""))
            item["formula"] = fix_var(item.get("formula", ""))
            item["explanation"] = user_input  # 保持原始输入
        return parsed

    except Exception as e:
        return {"error": f"调用API失败：{str(e)}"}




# ==================== Streamlit UI ====================
st.set_page_config(
    page_title="🏦 KPI规则AI生成器",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 标题
st.title("🏦 KPI 自然语言转规则 AI 助手")
st.markdown("""
**输入你的人类语言 KPI 规则，AI 自动生成标准 JSON 公式逻辑。**  
""")

# ==================== 侧边栏：历史记录 + 变量提示 ====================
with st.sidebar:
    st.header("📂 历史记录")

    # 初始化历史记录
    if "history" not in st.session_state:
        st.session_state.history = []

    # 显示历史记录
    if len(st.session_state.history) == 0:
        st.info("✨ 暂无历史记录，生成第一条规则吧！")
    else:
        # 倒序展示（最新在上）
        for i, record in enumerate(reversed(st.session_state.history)):
            with st.expander(f"📅 {record['timestamp']} ⚙️ {record['input'][:30]}...", expanded=False):
                st.caption("🔧 原始输入")
                st.markdown(f"`{record['input']}`")
                st.caption("📊 AI 生成")
                st.json(record['result'], expanded=False)

                # 重新加载此记录按钮
                if st.button(f"↩️ 重新加载 #{i + 1}", key=f"load_{i}"):
                    st.session_state.input_text = record['input']
                    st.session_state.result = record['result']
                    st.rerun()

                # 下载此记录按钮
                json_str = json.dumps(record['result'], ensure_ascii=False, indent=2)
                st.download_button(
                    label="📥 下载此记录",
                    data=json_str,
                    file_name=f"kpi_{i + 1}_{record['timestamp'].replace(':', '-')}.json",
                    mime="application/json",
                    key=f"download_{i}"
                )

    # 清空历史按钮
    if st.button("🗑️ 清空历史记录", type="secondary", use_container_width=True):
        st.session_state.history = []
        st.rerun()

    st.divider()

    st.header("⚠️ 变量规范")
    st.info("""
    - 必须使用以下 **79个变量名**（请复制粘贴，避免拼写错误）
    - 所有变量格式：`$ 变量名 []$`（注意空格和中括号）
    - 示例：$ 机构计划值 []$，$ 权重 []$
    - 百分比转小数：5% → 0.05，1.5% → 0.015
    - 1BP = 0.01% = 0.0001
    """)
    st.subheader("可用变量 (共79个)")
    for var in sorted(VARIABLES.VARIABLES):
        st.text(f"• $ {var} []$")

# ==================== 主界面：输入 + 生成 ====================
st.subheader("✍️ 输入KPI规则描述")

# 初始化输入文本
if "input_text" not in st.session_state:
    st.session_state.input_text = ""

# 文本输入框（绑定 session_state）
user_input = st.text_area(
    "请输入你的KPI规则（例如：完成率在60%~100%之间，每少10%扣0.5分）",
    height=150,
    placeholder="示例：机构存款净增完成率超过100%，每超1%，加0.2分，最高加5分。",
    value=st.session_state.input_text,
    key="input_area"
)

# 示例按钮（已修复）
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("💡 使用示例"):
        st.session_state.input_text = "完成率在60%至100%（不含）之间，每少完成10%，扣0.5分"
        st.rerun()

# 生成按钮
if st.button("🧠 AI 生成规则", type="primary", use_container_width=True):
    if not user_input.strip():
        st.warning("⚠️ 请输入一条KPI规则描述。")
    else:
        with st.spinner("🪄 正在调用AI模型进行分析，请稍候...（约5-10秒）"):
            result = call_siliconflow(user_input)

        if "error" in result:
            st.error(f"❌ 错误：{result['error']}")
            st.info("💡 请检查输入是否清晰，或尝试使用示例规则。")
        else:
            st.success("✅ AI 分析完成！")

            # 保存到历史
            st.session_state.history.append({
                "input": user_input,
                "result": result,
                "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
            })

            # 显示结果
            st.session_state.result = result

# 结果展示区
if 'result' in st.session_state:
    result = st.session_state.result
    st.subheader("📊 生成结果")
    st.write(f"🔍 共识别出 **{len(result)}** 个逻辑分支")

    df = st.dataframe(
        result,
        use_container_width=True,
        column_config={
            "condition": st.column_config.TextColumn("🛡️ 条件", width="large"),
            "formula": st.column_config.TextColumn("🧮 公式", width="large"),
            "explanation": st.column_config.TextColumn("💬 说明", width="large")
        }
    )

    # 下载按钮（当前结果）
    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    st.download_button(
        label="📥 下载本次 JSON 规则文件",
        data=json_str,
        file_name="kpi_rules.json",
        mime="application/json",
        use_container_width=True
    )

    with st.expander("📋 查看完整JSON代码"):
        st.code(json_str, language="json")

