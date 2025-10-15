# -*- coding: utf-8 -*-
# @Time : 16:29
# @Author : hkk
# @File : app.py
# @Project : AutoExcelToPpt
# Streamlit 部署版：KPI 自然语言生成引擎

import os
import json
import re
import streamlit as st
# from dotenv import load_dotenv
# import requests
#
# load_dotenv()
#
# # ============= 配置区 =============
# SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
# if not SILICONFLOW_API_KEY:
#     st.error("❌ 请在 .env 文件中设置 SILICONFLOW_API_KEY=你的硅基流动APIKey")
#     st.stop()


# 从 Streamlit Secrets 读取api
try:
    SILICONFLOW_API_KEY = st.secrets["SILICONFLOW_API_KEY"]
except KeyError:
    st.error("❌ API Key 未配置，请联系管理员设置 Streamlit Secrets")
    st.stop()


MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Instruct"  

# 78 个变量白名单
VARIABLES = {
    "机构标准扣罚单价", "机构分组2增量贡献度", "机构考核基数", "对比基数", "行员目标值", "年末",
    "利润参数", "行员标准计酬单价", "机构考核得分", "行员指标值", "当年已计价工资", "行员力争值",
    "机构标准计酬单价", "考核月份", "维度权重", "机构指标值(2位小数)", "机构超力争得分系数",
    "机构力争值", "地区差异系数", "行员超任务单价", "行员计划值", "机构计划值", "最高分",
    "代码描述", "行员考核基数", "职能部室挂靠支行数", "行员考核得分", "行员标准得分系数",
    "职能部室挂靠支行得分", "行员新增单价", "最低分", "权重", "机构进度值", "考核总分",
    "职能部室挂靠支行业绩", "机构标准得分系数", "不良清收奖励", "存款保底基数", "机构指标值",
    "指标值", "机构超计划得分系数", "机构指标区间值", "是否中山分行", "行员绩效工资",
    "机构分组1增量贡献度", "机构公共户业绩", "行员指标区间值", "机构目标值2", "行员超计划得分系数",
    "机构指标分组平均", "无维度参数"
}

# 构建AI请求的提示词
def build_prompt(user_input):
    var_list = ', '.join(VARIABLES)
    return f"""你是一个银行业绩考核系统AI专家，必须严格遵守以下规则：

【变量规范】
- 你只能使用以下变量（完全匹配，禁止任何修改）：{var_list}
- 所有变量必须写成：$ 变量名 []$，例如：$ 机构目标值 []$，$ 权重 []$，$ 机构指标值 []$（注意有空格和 []）

【公式规范】
- 公式只允许使用：+ - * / > < >= <= != = ( )
- 所有“完成率”必须写作：$ 机构指标值 []$ / $ 机构计划值 []$
- 百分比计算：必须写为 * 100 / 某值，禁止写 0.1 或 10%
- 不允许使用函数：IF、SUM、MAX、AVERAGE 等

【输出格式】
必须输出严格的 JSON 格式，不要任何额外文字：
{{
  "condition": "条件表达式",
  "formula": "计算公式",
  "explanation": "原输入语句（原样输出）"
}}

【示例】
输入：完成率在60%至100%（不含）之间，每少完成10%，扣0.5分
输出：
{{
  "condition": "$ 机构目标值 []$ != 0 and $ 机构指标值 []$ / $ 机构计划值 []$ > 0.6 and $ 机构指标值 []$ / $ 机构计划值 []$ < 1",
  "formula": "$ 权重 []$ - (($ 机构计划值 []$ - $ 机构指标值 []$) * 100 / $ 机构计划值 []$) / 10 * 0.5",
  "explanation": "完成率在60%至100%（不含）之间，每少完成10%，扣0.5分"
}}

你现在接收一条新输入，请输出JSON：
输入："{user_input}"
"""

# 调用硅基流动 API
def call_siliconflow(user_input):
    url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = build_prompt(user_input)

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "top_p": 0,
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']

        # 提取 JSON
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            return {"error": "AI返回内容不是有效JSON格式"}

        json_str = content[json_start:json_end]
        parsed = json.loads(json_str)

        # 修复变量格式 —— 自动补全 $ 变量名 []$
        def fix_var(text):
            for var in VARIABLES:
                # 修复 $变量名$ → $ 变量名 []$
                if f"${var}$" in text:
                    text = text.replace(f"${var}$", f"$ {var} []$")
                # 修复 $ 变量名 $ → $ 变量名 []$
                if f"$ {var} $" in text:
                    text = text.replace(f"$ {var} $", f"$ {var} []$")
                # 修复 $ 变量名 → $ 变量名 []$
                if f"$ {var}" in text and "]$" not in text:
                    text = text.replace(f"$ {var}", f"$ {var} []$")
            return text

        parsed["condition"] = fix_var(parsed.get("condition", ""))
        parsed["formula"] = fix_var(parsed.get("formula", ""))
        parsed["explanation"] = user_input  # 强制使用原输入

        return parsed

    except Exception as e:
        return {"error": f"调用API失败：{str(e)}"}

# ========== Streamlit 界面 ==========
st.set_page_config(
    page_title="🔥 KPI智能生成助手",
    page_icon="📊",
    layout="centered"
)

# 页面标题
st.title("📊 KPI智能自然语言生成系统")
st.markdown("""
**让业务人员一句话，自动生成KPI公式！**  
✅ 支持79种考核逻辑  
✅ 自动识别变量、补全格式  
✅ 输出合法JSON
""")

# 输入框
user_input = st.text_area(
    "📝 请输入你的KPI考核规则（自然语言）：",
    placeholder="例如：完成率低于80%，扣（100-完成率）*0.3分\n\n控制在7088万以内得5分，超过得0分",
    height=120
)

# 生成按钮
if st.button("🚀 生成KPI公式", type="primary", use_container_width=True):
    if not user_input.strip():
        st.warning("⚠️ 请输入描述内容")
    else:
        with st.spinner("🧠 AI正在理解你的需求，请稍候...（约5-8秒）"):
            result = call_siliconflow(user_input)

        st.divider()

        if "error" in result:
            st.error(f"❌ AI出错了：{result['error']}")
            st.info("💡 建议：请用清晰的句子，例如：‘每超10万加2分’、‘完成率在60%~80%之间得3分’")
        else:
            # 显示结果
            st.success("✅ AI生成成功！")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("#### 🛡️ 条件")
                st.code(result["condition"], language="text")
            with col2:
                st.markdown("#### 🧮 公式")
                st.code(result["formula"], language="text")
            with col3:
                st.markdown("#### 💬 说明")
                st.text(result["explanation"])

            # 复制按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 复制公式", key="copy_formula"):
                    st.write(result["formula"])  # 触发复制（Streamlit的代码块可复制）
                    st.toast("✅ 公式已复制到剪贴板", icon="📋")
            with col2:
                if st.button("📋 复制条件", key="copy_condition"):
                    st.write(result["condition"])
                    st.toast("✅ 条件已复制到剪贴板", icon="📋")

            # 下载JSON
            json_str = json.dumps(result, ensure_ascii=False, indent=2)
            st.download_button(
                label="💾 下载 JSON 文件",
                data=json_str,
                file_name="kpi_formula.json",
                mime="application/json",
                use_container_width=True
            )

# 添加使用说明
st.divider()
st.markdown("""
### ℹ️ 如何使用？
1. 将KPI规则用自然语言输入（如：“超计划200万，每10万加2分”）
2. 点击 **“生成KPI公式”**
3. 复制粘贴 `condition` 和 `formula` 到你的考核系统


### 💡 支持的关键词：
- 完成率、超计划、控制在、扣分、加分、每、以上、以下、达标、标杆、基数、上限、封顶  
- 机构、行员、计划值、指标值、权重、目标值、考核基数
""")

