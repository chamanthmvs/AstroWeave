import httpx
import streamlit as st


st.set_page_config(
    page_title="AstroWeave",
    page_icon="✦",
    layout="wide",
)


st.title("AstroWeave")
st.caption("Hierarchical multi-agent astrology system")

with st.sidebar:
    st.header("Connection")
    api_url = st.text_input("API URL", value="http://127.0.0.1:8000")
    st.divider()
    st.header("Conversation")
    username = st.text_input("Username", value="demo-user")
    conversation_id = st.text_input("Conversation ID", value="conversation-1")
    session_id = st.text_input("Session ID", value="session-1")

st.subheader("Ask AstroWeave")
with st.form("query_form"):
    query = st.text_area(
        "Astrology question",
        placeholder="Ask a question for the AstroWeave backend...",
    )
    methodology = st.selectbox(
        "Methodology",
        ["Let the system decide", "Vedic", "KP", "Both"],
    )
    submitted = st.form_submit_button("Send to API", type="primary")

if submitted:
    if not query.strip():
        st.warning("Enter an astrology question first.")
    else:
        payload = {
            "query": query,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "username": username,
            "methodology": methodology,
        }
        try:
            response = httpx.post(f"{api_url.rstrip('/')}/run", json=payload, timeout=10)
        except httpx.RequestError as error:
            st.error(f"Could not connect to the API: {error}")
        else:
            if response.status_code == 501:
                st.info(response.json().get("detail", "Execution is not available yet."))
            elif response.is_success:
                st.success("Request completed.")
                st.json(response.json())
            else:
                st.error(f"API returned HTTP {response.status_code}: {response.text}")

st.divider()
st.caption("The Streamlit interface communicates with AstroWeave through HTTP; it does not execute the graph directly.")
