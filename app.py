# app.py
import streamlit as st
from PIL import Image
from openai import OpenAI
import time
import io

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

# --- Sidebar Logo ---
logo = Image.open("assets/ceiyone_logo.png")
st.sidebar.image(logo, width=120)
st.sidebar.markdown("### Ceiyone Risk Analyzer")

# --- Sidebar Menu ---
with st.sidebar:
    st.markdown("---")

    def render_card_option(label, menu_key):
        is_selected = st.session_state.selected_menu == menu_key
        button_class = "selected-option card-option" if is_selected else "card-option"
        if st.button(label, key=f"btn_{menu_key}"):
            st.session_state.selected_menu = menu_key

    render_card_option("Upload Vendor Form", "upload")
    render_card_option("Upload SOC 2 Document", "soc2")
    render_card_option("Chat History", "chat")

    st.markdown("---")
    st.caption("Built for vendor security & compliance reviews.")

# --- Chat-based Vendor Form Analysis ---
if st.session_state.selected_menu == "upload":
    st.markdown("## 🧾 Vendor Risk Assessment Chat")
    st.chat_message("assistant").write("Hi there! Please upload the vendor security form (PDF) to get started.")

    form_file = st.file_uploader("Upload Vendor Security Review Form (PDF)", type=["pdf"])
    if form_file:
        st.success("Thanks! Analyzing the document...")

        try:
            file_bytes = form_file.read()
            file_response = client.files.create(
                file=(form_file.name, io.BytesIO(file_bytes)),
                purpose="assistants"
            )
            file_id = file_response.id

            assistant = client.beta.assistants.create(
                name="Form Risk Evaluator",
                instructions="""
You are a cybersecurity expert reviewing vendor onboarding forms.
First check if the form is filled or mostly blank.
If blank, return: \"Form incomplete. Please submit a filled version.\"
If filled, analyze for any indicators of risk related to:
- Personal data
- Cloud access
- OKTA or SSO integration
- Sensitive system access
Then summarize risk severity: Low / Medium / High / Critical
Provide this output:

Form Status:
Risk Severity:
Risk Summary:
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
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
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
                            st.session_state.chat_history.append({"role": "assistant", "content": response})
                            st.chat_message("assistant").markdown(response)

                            if "Risk Severity: High" in response:
                                st.warning("⚠️ High risk detected. Please upload the SOC 2 document for further analysis.")
                                st.session_state.selected_menu = "soc2"
            else:
                st.warning("⚠️ Assistant completed but returned no response.")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# --- SOC2 Upload Section ---
elif st.session_state.selected_menu == "soc2":
    st.markdown("## 🛡️ SOC 2 Risk Assessment")
    st.chat_message("assistant").write("Please upload the SOC 2 Type 2 report (PDF) for additional analysis.")

    soc2_file = st.file_uploader("Upload SOC 2 Type 2 Document (PDF)", type=["pdf"], key="soc2")
    if soc2_file:
        st.success("Thanks! Analyzing the SOC 2 document...")

        try:
            soc2_bytes = soc2_file.read()
            file_response = client.files.create(
                file=(soc2_file.name, io.BytesIO(soc2_bytes)),
                purpose="assistants"
            )
            file_id = file_response.id

            assistant = client.beta.assistants.create(
                name="SOC2 Risk Evaluator",
                instructions="""
You are a cybersecurity professional and expert in vendor risk analysis. Review SOC2 reports for data security, access control, compliance, application security, and integration risks. Analyze audit tables for exceptions.
Output:
Vendor Legal Name:
Vendor Legal Address:
Risk Category, Risk Level & Reason:
Assessment Summary:
Audit Report Findings:
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
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
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
                            st.session_state.chat_history.append({"role": "assistant", "content": response})
                            st.chat_message("assistant").markdown(response)
            else:
                st.warning("⚠️ Assistant returned no response.")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# --- Chat History Section ---
elif st.session_state.selected_menu == "chat":
    st.markdown("## 💬 Chat History")

    if st.session_state.chat_history:
        for chat in reversed(st.session_state.chat_history):
            with st.chat_message(chat['role']):
                st.markdown(chat['content'])

        chat_export = io.StringIO()
        for chat in st.session_state.chat_history:
            chat_role = chat["role"].capitalize()
            chat_export.write(f"{chat_role}: {chat['content']}\n\n")

        st.download_button(
            label="📥 Download Chat History",
            data=chat_export.getvalue(),
            file_name="chat_history.txt",
            mime="text/plain"
        )
    else:
        st.info("No chat history available yet.")
