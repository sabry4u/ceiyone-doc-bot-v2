import streamlit as st
from PIL import Image
from openai import OpenAI
import time
import io
from datetime import datetime
import re

# --- Config ---
st.set_page_config(page_title="Ceiyone Vendor Risk Analyzer", layout="wide")
client = OpenAI(api_key=st.secrets["openai_api_key"])

# --- Session State ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "form_uploaded" not in st.session_state:
    st.session_state.form_uploaded = False
if "selected_menu" not in st.session_state:
    st.session_state.selected_menu = "upload"

# --- Custom CSS Styling ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #f7f9fc;
    }
    .css-1d391kg {
        width: 280px !important;
    }
    .sidebar-logo {
        display: flex;
        justify-content: center;
        margin-bottom: 1rem;
    }
    div[data-testid="stButton"] > button {
        background-color: white;
        color: #333;
        width: 100%;
        text-align: left;
        padding: 0.75rem 1rem;
        margin: 5px 0;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        font-weight: 500;
        transition: 0.2s all ease-in-out;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #e5f1fb;
        border-color: #3399ff;
        color: #3399ff;
    }
    div[data-testid="stButton"] > button[selected="true"] {
        background-color: #d0e8ff !important;
        color: #0066cc !important;
        border-color: #3399ff !important;
    }
    .summary-box {
        font-size: 1rem;
        line-height: 1.6;
        padding: 0.5rem;
    }
    .highlight-high-risk {
        color: red;
        font-weight: bold;
    }
    [data-testid="stSidebar"] {
        width: 280px !important;
    }
    .st-emotion-cache-t1wise {
        padding: 2rem 1rem 10rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar Layout ---
with st.sidebar:
    logo = Image.open("assets/ceiyone_logo.png")
    st.image(logo, width=100)
    st.markdown("### Ceiyone Risk Analyzer")

    def render_card_option(label, menu_key):
        selected = st.session_state.selected_menu == menu_key
        btn = st.button(label, key=menu_key)
        if btn:
            st.session_state.selected_menu = menu_key

    render_card_option("📄 Upload Vendor Form", "upload")
    render_card_option("📄 Upload SOC 2 Document", "soc2")
    render_card_option("💬 Chat History", "chat")

    st.markdown("---")
    st.caption("Built for vendor security & compliance.")

# --- Vendor Form Upload ---
if st.session_state.selected_menu == "upload":
    st.markdown("## Vendor Risk Assessment Assistant")
    st.chat_message("assistant").write("Hi there! Please upload the vendor security form (PDF) to get started.")

    form_file = st.file_uploader("Upload Vendor Security Review Form (PDF)", type=["pdf"])
    if form_file:
        st.markdown("""
        <div style="background-color:#f0f4ff;padding:1rem;border-left:5px solid #3399ff;border-radius:8px;">
            <strong>🔄 Reviewing your vendor submission...</strong><br>
            Our system is currently analyzing the document for potential risks. This may take a moment.
        </div>
        """, unsafe_allow_html=True)

        try:
            file_bytes = form_file.read()
            file_response = client.files.create(
                file=(form_file.name, io.BytesIO(file_bytes)),
                purpose="assistants"
            )
            file_id = file_response.id

            assistant = client.beta.assistants.create(
                name="Form Risk Evaluator",
                instructions="""You are a cybersecurity expert reviewing vendor onboarding forms.
First check if the form is filled or mostly blank.
If blank, return: "Form incomplete. Please submit a filled version."
If filled, analyze for any indicators of risk related to:
- Personal data
- Cloud access
- OKTA or SSO integration
- Sensitive system access
Then summarize risk severity: Low / Medium / High / Critical
Provide this output:
<b>Form Status:</b>
<b>Risk Severity:</b>
<b>Risk Summary:</b>
""",
                tools=[{"type": "file_search"}],
                model="gpt-4-turbo"
            )

            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="Please review this vendor form for completeness and risk level.",
                attachments=[{
                    "file_id": file_id,
                    "tools": [{"type": "file_search"}]
                }]
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id
            )

            while True:
                run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
                if run_status.status == "completed":
                    break
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    st.error(f"❌ Assistant run {run_status.status}. Please try again.")
                    break
                time.sleep(2)

            messages = client.beta.threads.messages.list(thread_id=thread.id)
            assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]

            if assistant_messages:
                for msg in reversed(assistant_messages):
                    for content in msg.content:
                        if hasattr(content, "text"):
                            response = content.text.value

                            severity_match = re.search(r"(Risk Severity:\s*)(High)", response, re.IGNORECASE)
                            if severity_match:
                                st.warning("⚠️ High risk detected. Please upload the SOC 2 document for further analysis.")
                                st.session_state.selected_menu = "soc2"
                                response = re.sub(r"(Risk Severity:\s*)(High)", r"\1<span class='highlight-high-risk'>\2</span>", response, flags=re.IGNORECASE)

                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": response,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            st.chat_message("assistant").markdown(f"<div class='summary-box'>{response}</div>", unsafe_allow_html=True)
            else:
                st.warning("⚠️ Assistant completed but returned no response.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# --- SOC 2 Upload ---
elif st.session_state.selected_menu == "soc2":
    st.markdown("## 🛡️ SOC 2 Risk Assessment")
    st.chat_message("assistant").write("Please upload the SOC 2 Type 2 report (PDF) for additional analysis.")

    soc2_file = st.file_uploader("Upload SOC 2 Type 2 Document (PDF)", type=["pdf"], key="soc2_upload")
    if soc2_file:
        st.markdown("""
        <div style="background-color:#f0f4ff;padding:1rem;border-left:5px solid #3399ff;border-radius:8px;">
            <strong>🔄 Processing SOC 2 Report...</strong><br>
            Extracting trust criteria, control exceptions, and potential risks. Please wait while we generate insights.
        </div>
        """, unsafe_allow_html=True)

        try:
            soc2_bytes = soc2_file.read()
            file_response = client.files.create(
                file=(soc2_file.name, io.BytesIO(soc2_bytes)),
                purpose="assistants"
            )
            file_id = file_response.id

            assistant = client.beta.assistants.create(
                name="SOC2 Risk Evaluator",
                instructions="""You are a cyber security professional and expert in vendor risk analysis process flow. Your goal is to review the security certification documents such as Soc2 audit report and ISO report, analyze the document for risk elements from data security, access security, storage security, integration security, privacy & compliance, application security...etc and provide a summarized report as below. Also if there is structured information, for example, in the Soc2 report there will be a table in the end that walks through different audit controls and its result for the vendor, then pay additional attention to that data and make sure every line item has a positive result that the audit was successful with no exceptions.

Summarization Output Example:
Vendor Legal Name: 
Vendor Legal Address:
Risk Category, Risk Level & Risk Reason: 
Assessment Summary:
Audit Report Findings: No exceptions

For the risk category please be exhaustive based on cyber security expert knowledge.
For risk level, please use your own rubric to classify the risks as Critical, High, Medium & Low
For Assessment summary, please provide your verdict on the vendor risk assessment based on the document data
For Audit report findings, please use the structured data in the end to find and report any exceptions highlighted.
</b>
""",
                tools=[{"type": "file_search"}],
                model="gpt-4-turbo"
            )

            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="Please review this SOC2 document.",
                attachments=[{
                    "file_id": file_id,
                    "tools": [{"type": "file_search"}]
                }]
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id
            )

            while True:
                run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
                if run_status.status == "completed":
                    break
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    st.error(f"❌ Assistant run {run_status.status}.")
                    break
                time.sleep(2)

            messages = client.beta.threads.messages.list(thread_id=thread.id)
            assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]

            if assistant_messages:
                for msg in reversed(assistant_messages):
                    for content in msg.content:
                        if hasattr(content, "text"):
                            response = content.text.value
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": response,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            # Highlight high/critical risks in SOC 2 summary
                            response = re.sub(r"(Overall SOC2 Risk:\s*)(High|Critical)", r"\1<span class='highlight-high-risk'>\2</span>", response, flags=re.IGNORECASE)

                            # Display formatted box
                            st.chat_message("assistant").markdown(f"<div class='summary-box'>{response}</div>", unsafe_allow_html=True)

            else:
                st.warning("⚠️ Assistant returned no response.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# --- Chat History Section ---
elif st.session_state.selected_menu == "chat":
    st.markdown("## 💬 Chat History")

    if st.session_state.chat_history:
        for chat in reversed(st.session_state.chat_history):
            timestamp = chat.get("timestamp", "Unknown")
            content = chat["content"].strip()
            role = chat["role"].capitalize()

            if "Audit Report Findings" in content:
                doc_type = "SOC 2 Type 2"
            elif "Form Status" in content or "Risk Severity" in content:
                doc_type = "Vendor Security Review Form"
            else:
                doc_type = "Analysis"

            risk_line = ""
            for line in content.splitlines():
                if "Risk Severity" in line:
                    risk_line = line.strip()
                    break

            if not risk_line:
                summary_preview = content.replace("\n", " ").strip()
                risk_line = summary_preview[:100] + ("..." if len(summary_preview) > 100 else "")
            clean_risk_line = re.sub(r'<.*?>', '', risk_line)  # removes all HTML tags
            summary_line = f"{doc_type} — {clean_risk_line} — {timestamp}"

            with st.expander(summary_line, expanded=False):
                st.markdown(f"<div class='summary-box'>{content}</div>", unsafe_allow_html=True)

        chat_export = io.StringIO()
        for chat in st.session_state.chat_history:
            chat_export.write(f"{chat.get('timestamp', 'Unknown')} | {chat['role'].capitalize()}: {chat['content']}\n\n")

        st.download_button(
            label="📅 Download Chat History",
            data=chat_export.getvalue(),
            file_name="chat_history.txt",
            mime="text/plain"
        )
    else:
        st.info("No chat history available yet.")
