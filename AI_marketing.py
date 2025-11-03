import streamlit as st
import requests
import time
import json

# --- Page Configuration ---
st.set_page_config(
    page_title="Digital Marketing Expert",
    page_icon="📣",
    layout="centered"
)

# --- Gemini API Configuration ---
API_KEY = st.secrets["AIzaSyCh97F6OkSXoGIGbZ7Bhd1lfne77HGOaUI"]  # API key from Streamlit secrets
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={API_KEY}"

# System prompt to define the chatbot's persona
SYSTEM_PROMPT = """
You are an expert Digital Marketing Strategist. Your name is 'Marketing Expert'.
Your goal is to provide insightful, actionable, and up-to-date advice on all aspects of digital marketing.
When users ask for information, strategies, or trends, you MUST leverage your built-in search capabilities to find the most current and relevant information.
Always cite your sources when you use search information, providing the title and URI.
Your responses should be professional, clear, and structured.
Use markdown (like lists, bolding, and code blocks for examples) to make your advice easy to understand and follow.
Always be helpful, encouraging, and focused on helping the user achieve their marketing goals.
"""

# --- API Call Function with Retry Logic ---
def get_bot_response(chat_history):
    """
    Calls the Gemini API with the chat history and Google Search tool.
    Implements exponential backoff for retries.
    """
    
    # Construct the payload
    # We send the system prompt + the last 10 messages to keep context
    max_history_length = 10
    recent_history_payload = [msg for msg in chat_history if msg['role'] != 'system']
    recent_history_payload = recent_history_payload[-max_history_length:]
    
    # Add the system prompt at the beginning
    system_message = {"role": "system", "parts": [{"text": SYSTEM_PROMPT}]}
    final_payload_contents = [system_message] + recent_history_payload

    payload = {
        "contents": final_payload_contents,
        "tools": [{"google_search": {}}],
    }

    headers = {'Content-Type': 'application/json'}
    
    # --- Exponential Backoff Retry Logic ---
    retries = 0
    max_retries = 5
    delay = 1  # 1 second

    while retries < max_retries:
        try:
            response = requests.post(API_URL, headers=headers, data=json.dumps(payload))

            if response.ok:
                result = response.json()
                candidate = result.get('candidates', [{}])[0]
                content = candidate.get('content', {}).get('parts', [{}])[0]
                text = content.get('text', '')

                if not text:
                    print("Invalid response structure:", result)
                    raise Exception("Invalid response structure from API.")

                # Extract grounding sources
                sources = []
                grounding_metadata = candidate.get('groundingMetadata', {})
                if grounding_metadata and 'groundingAttributions' in grounding_metadata:
                    sources = [
                        {
                            "uri": attr.get('web', {}).get('uri'),
                            "title": attr.get('web', {}).get('title'),
                        }
                        for attr in grounding_metadata['groundingAttributions']
                        if attr.get('web') and attr.get('web').get('uri') and attr.get('web').get('title')
                    ]
                
                return text, sources

            elif response.status_code == 429 or response.status_code >= 500:
                # Handle rate limiting or server errors
                print(f"API request failed with status {response.status_code}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                retries += 1
            else:
                # Handle other client-side errors
                error_result = response.json()
                print("API Error:", error_result)
                raise Exception(error_result.get('error', {}).get('message', f"HTTP error! status: {response.status_code}"))

        except requests.exceptions.RequestException as e:
            print(f"Fetch error: {e}")
            if retries >= max_retries - 1:
                raise  # Throw error on last retry
            time.sleep(delay)
            delay *= 2
            retries += 1
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"Sorry, I encountered an error: {e}", []

    raise Exception("Max retries reached. Could not get a response from the API.")


# --- Streamlit App UI ---

st.title("📣 Digital Marketing Expert")
st.caption("Your AI-powered marketing strategist")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        # Note: We don't display the system prompt, but it's part of the history
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": "Hello! I'm your AI Digital Marketing strategist. How can I help you today? Feel free to ask about SEO, content strategy, social media, ad campaigns, or the latest market trends."}
    ]

# Display chat messages from history
for message in st.session_state.messages:
    if message["role"] == "system":
        continue  # Skip displaying the system prompt
    
    avatar = "📣" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            st.subheader("Sources", divider="gray")
            for i, source in enumerate(message["sources"]):
                st.markdown(f"{i+1}. [{source['title']}]({source['uri']})")

# Accept user input
if prompt := st.chat_input("Ask about SEO, social media, ads..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant", avatar="📣"):
        with st.spinner("Marketing Expert is typing..."):
            try:
                # Prepare history for API call
                api_history = [
                    {"role": msg["role"], "parts": [{"text": msg["content"]}]}
                    for msg in st.session_state.messages
                ]
                
                bot_response, sources = get_bot_response(api_history)
                
                # Display the main response
                st.markdown(bot_response)
                
                # Display sources if any
                if sources:
                    st.subheader("Sources", divider="gray")
                    for i, source in enumerate(sources):
                        st.markdown(f"{i+1}. [{source['title']}]({source['uri']})")
                
                # Add assistant response to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": bot_response,
                    "sources": sources
                })

            except Exception as e:
                error_message = f"Sorry, I encountered an error: {e}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message, "sources": []})
