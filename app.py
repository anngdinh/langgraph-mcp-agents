import streamlit as st
import asyncio
import nest_asyncio
import json
import os
import platform
import xml.etree.ElementTree as ET
import requests
from lxml import etree
import xml.dom.minidom

ALLOWED_EMAILS = os.environ.get("ALLOWED_EMAILS").split(",") if os.environ.get("ALLOWED_EMAILS") else []
CURRENT_URL = os.environ.get("CURRENT_URL", "http://localhost:8898/")
# Initialize login session variables
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = ""

# Read query parameters from the URL
params = st.query_params
page = params.get("page")
ticket = params.get("ticket")

if True:
    if ticket and not st.session_state.authenticated:
        # Call your backend API to validate the ticket
        response = requests.get(
            f"https://sso-dev.vngcloud.vn/cas/p3/serviceValidate?service={CURRENT_URL}&ticket=" + ticket
        )

        if response.status_code == 200:
            # add a button logout to redirect to the sso
            if st.button("Logout"):
                # Redirect to the SSO logout URL
                st.markdown(
                    f'<meta http-equiv="refresh" content="0;URL={f"https://sso-dev.vngcloud.vn/cas/logout?service={CURRENT_URL}"}">',
                    unsafe_allow_html=True,
                )
                
            # # Pretty-print the XML
            # try:
            #     dom = xml.dom.minidom.parseString(response.text)
            #     pretty_xml = dom.toprettyxml()
            #     st.code(pretty_xml, language='xml')
            # except Exception as e:
            #     st.error(f"Failed to format XML: {e}")
            #     st.text("Raw response:")
            #     st.text(response.text)

            try:
                # Parse the XML
                root = ET.fromstring(response.text)
                ns = {'cas': 'http://www.yale.edu/tp/cas'}

                user_elem = root.find('.//cas:user', namespaces=ns)
                if user_elem is not None:
                    user_email = user_elem.text
                    # print(user_email)
                    st.success(f"Logged in as: {user_email}")

                    if user_email not in ALLOWED_EMAILS:
                        st.error(
                            "You are not allowed to access this application.")
                        st.stop()

                    st.session_state.authenticated = True
                    st.session_state.user_email = user_email
                    st.success("✅ Login successful! Please wait...")
                    st.rerun()
                else:
                    st.error("User not found in response.")
                    st.stop()
            except ET.ParseError as e:
                st.error(f"Failed to parse CAS response: {e}")
                st.stop()

        else:
            st.error("CAS ticket validation failed.")
            st.stop()

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Apply nest_asyncio: Allow nested calls within an already running event loop
nest_asyncio.apply()

# Create and reuse global event loop (create once and continue using)
if "event_loop" not in st.session_state:
    loop = asyncio.new_event_loop()
    st.session_state.event_loop = loop
    asyncio.set_event_loop(loop)

from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils import astream_graph, random_uuid
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables (get API keys and settings from .env file)
load_dotenv(override=True)

# config.json file path setting
CONFIG_FILE_PATH = "config.json"

# Function to load settings from JSON file
def load_config_from_json():
    """
    Loads settings from config.json file.
    Creates a file with default settings if it doesn't exist.

    Returns:
        dict: Loaded settings
    """
    default_config = {
        "get_current_time": {
            "command": "python",
            "args": ["./mcp_server_time.py"],
            "transport": "stdio"
        }
    }
    
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # Create file with default settings if it doesn't exist
            save_config_to_json(default_config)
            return default_config
    except Exception as e:
        st.error(f"Error loading settings file: {str(e)}")
        return default_config

# Function to save settings to JSON file
def save_config_to_json(config):
    """
    Saves settings to config.json file.

    Args:
        config (dict): Settings to save
    
    Returns:
        bool: Save success status
    """
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving settings file: {str(e)}")
        return False


# Check if login is required
use_login = os.environ.get("USE_LOGIN", "false").lower() == "true"

# Change page settings based on login status
if use_login and not st.session_state.authenticated:
    # Login page uses default (narrow) layout
    st.set_page_config(page_title="Agent with MCP Tools", page_icon="🧠")
else:
    # Main app uses wide layout
    st.set_page_config(page_title="Agent with MCP Tools",
                       page_icon="🧠", layout="wide")

# Display login screen if login feature is enabled and not yet authenticated
if use_login and not st.session_state.authenticated:
    st.title("🔐 Login")
    st.markdown("Login is required to use the system.")

    # add a button to redirect to the sso
    sso_url = os.environ.get("SSO_URL")
    if sso_url:
        if st.button("Login with VNGCLOUD SSO"):
            st.markdown(
                f'<meta http-equiv="refresh" content="0;URL={f"https://sso-dev.vngcloud.vn/cas/login?service={CURRENT_URL}"}">', unsafe_allow_html=True)
    else:
        st.markdown(
            "SSO URL is not configured. Please contact the administrator to set it up."
        )

    # # Place login form in the center of the screen with narrow width
    # with st.form("login_form"):
    #     username = st.text_input("Username")
    #     password = st.text_input("Password", type="password")
    #     submit_button = st.form_submit_button("Login")

    #     if submit_button:
    #         expected_username = os.environ.get("USER_ID")
    #         expected_password = os.environ.get("USER_PASSWORD")

    #         if username == expected_username and password == expected_password:
    #             st.session_state.authenticated = True
    #             st.success("✅ Login successful! Please wait...")
    #             st.rerun()
    #         else:
    #             st.error("❌ Username or password is incorrect.")

    # Don't display the main app on the login screen
    st.stop()

# add a button logout to redirect to the sso
if st.sidebar.button("Logout"):
    # Redirect to the SSO logout URL
    st.sidebar.markdown(
        # f'<meta http-equiv="refresh" content="0;URL={"https://sso-dev.vngcloud.vn/cas/logout"}">',
        f'<meta http-equiv="refresh" content="0;URL={"https://sso-dev.vngcloud.vn/cas/logout?service=http://localhost:8898/"}">',
        unsafe_allow_html=True,
    )

# Add author information at the top of the sidebar (placed before other sidebar elements)
st.sidebar.markdown(
    "### ✍️ Made by [TeddyNote](https://youtube.com/c/teddynote) 🚀")
st.sidebar.markdown(
    "### 💻 [Project Page](https://github.com/teddynote-lab/langgraph-mcp-agents)"
)

st.sidebar.divider()  # Add divider

# Existing page title and description
st.title("💬 MCP Tool Utilization Agent")
st.markdown("✨ Ask questions to the ReAct agent that utilizes MCP tools.")

SYSTEM_PROMPT = """<ROLE>
You are a helpful assistant that can utilize various tools to answer questions.
You can use the tools to get information, perform calculations, and more.
You can also ask clarifying questions if needed.
You are not allowed to use the tools for any other purpose.
You never always try to answer the question using your own knowledge first.
If you need to use a tool, you should explain why you are using it.
"""

OUTPUT_TOKEN_INFO = {
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 64000},
    "gpt-4o": {"max_tokens": 16000},
    "gpt-4o-mini": {"max_tokens": 16000},
}

# Initialize session state
if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = False  # Session initialization flag
    st.session_state.agent = None  # Storage for ReAct agent object
    st.session_state.history = []  # List for storing conversation history
    st.session_state.mcp_client = None  # Storage for MCP client object
    st.session_state.timeout_seconds = (
        120  # Response generation time limit (seconds), default 120 seconds
    )
    st.session_state.selected_model = (
        "claude-3-7-sonnet-latest"  # Default model selection
    )
    st.session_state.recursion_limit = 100  # Recursion call limit, default 100

if "thread_id" not in st.session_state:
    st.session_state.thread_id = random_uuid()


# --- Function Definitions ---


async def cleanup_mcp_client():
    """
    Safely terminates the existing MCP client.

    Properly releases resources if an existing client exists.
    """
    if "mcp_client" in st.session_state and st.session_state.mcp_client is not None:
        try:

            await st.session_state.mcp_client.__aexit__(None, None, None)
            st.session_state.mcp_client = None
        except Exception as e:
            import traceback

            # st.warning(f"Error while terminating MCP client: {str(e)}")
            # st.warning(traceback.format_exc())


def print_message():
    """
    Displays chat history on the screen.

    Distinguishes between user and assistant messages on the screen,
    and displays tool call information within the assistant message container.
    """
    i = 0
    while i < len(st.session_state.history):
        message = st.session_state.history[i]

        if message["role"] == "user":
            st.chat_message("user", avatar="🧑‍💻").markdown(message["content"])
            i += 1
        elif message["role"] == "assistant":
            # Create assistant message container
            with st.chat_message("assistant", avatar="🤖"):
                # Display assistant message content
                st.markdown(message["content"])

                # Check if the next message is tool call information
                if (
                    i + 1 < len(st.session_state.history)
                    and st.session_state.history[i + 1]["role"] == "assistant_tool"
                ):
                    # Display tool call information in the same container as an expander
                    with st.expander("🔧 Tool Call Information", expanded=False):
                        st.markdown(st.session_state.history[i + 1]["content"])
                    i += 2  # Increment by 2 as we processed two messages together
                else:
                    i += 1  # Increment by 1 as we only processed a regular message
        else:
            # Skip assistant_tool messages as they are handled above
            i += 1


def get_streaming_callback(text_placeholder, tool_placeholder):
    """
    Creates a streaming callback function.

    This function creates a callback function to display responses generated from the LLM in real-time.
    It displays text responses and tool call information in separate areas.

    Args:
        text_placeholder: Streamlit component to display text responses
        tool_placeholder: Streamlit component to display tool call information

    Returns:
        callback_func: Streaming callback function
        accumulated_text: List to store accumulated text responses
        accumulated_tool: List to store accumulated tool call information
    """
    accumulated_text = []
    accumulated_tool = []

    def callback_func(message: dict):
        nonlocal accumulated_text, accumulated_tool
        message_content = message.get("content", None)

        if isinstance(message_content, AIMessageChunk):
            content = message_content.content
            # If content is in list form (mainly occurs in Claude models)
            if isinstance(content, list) and len(content) > 0:
                message_chunk = content[0]
                # Process text type
                if message_chunk["type"] == "text":
                    accumulated_text.append(message_chunk["text"])
                    text_placeholder.markdown("".join(accumulated_text))
                # Process tool use type
                elif message_chunk["type"] == "tool_use":
                    if "partial_json" in message_chunk:
                        accumulated_tool.append(message_chunk["partial_json"])
                    else:
                        tool_call_chunks = message_content.tool_call_chunks
                        tool_call_chunk = tool_call_chunks[0]
                        accumulated_tool.append(
                            "\n```json\n" + str(tool_call_chunk) + "\n```\n"
                        )
                    with tool_placeholder.expander(
                        "🔧 Tool Call Information", expanded=True
                    ):
                        st.markdown("".join(accumulated_tool))
            # Process if tool_calls attribute exists (mainly occurs in OpenAI models)
            elif (
                hasattr(message_content, "tool_calls")
                and message_content.tool_calls
                and len(message_content.tool_calls[0]["name"]) > 0
            ):
                tool_call_info = message_content.tool_calls[0]
                accumulated_tool.append(
                    "\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander(
                    "🔧 Tool Call Information", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
            # Process if content is a simple string
            elif isinstance(content, str):
                accumulated_text.append(content)
                text_placeholder.markdown("".join(accumulated_text))
            # Process if invalid tool call information exists
            elif (
                hasattr(message_content, "invalid_tool_calls")
                and message_content.invalid_tool_calls
            ):
                tool_call_info = message_content.invalid_tool_calls[0]
                accumulated_tool.append(
                    "\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander(
                    "🔧 Tool Call Information (Invalid)", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
            # Process if tool_call_chunks attribute exists
            elif (
                hasattr(message_content, "tool_call_chunks")
                and message_content.tool_call_chunks
            ):
                tool_call_chunk = message_content.tool_call_chunks[0]
                accumulated_tool.append(
                    "\n```json\n" + str(tool_call_chunk) + "\n```\n"
                )
                with tool_placeholder.expander(
                    "🔧 Tool Call Information", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
            # Process if tool_calls exists in additional_kwargs (supports various model compatibility)
            elif (
                hasattr(message_content, "additional_kwargs")
                and "tool_calls" in message_content.additional_kwargs
            ):
                tool_call_info = message_content.additional_kwargs["tool_calls"][0]
                accumulated_tool.append(
                    "\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander(
                    "🔧 Tool Call Information", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
        # Process if it's a tool message (tool response)
        elif isinstance(message_content, ToolMessage):
            accumulated_tool.append(
                "\n```json\n" + str(message_content.content) + "\n```\n"
            )
            with tool_placeholder.expander("🔧 Tool Call Information", expanded=True):
                st.markdown("".join(accumulated_tool))
        return None

    return callback_func, accumulated_text, accumulated_tool


async def process_query(query, text_placeholder, tool_placeholder, timeout_seconds=60):
    """
    Processes user questions and generates responses.

    This function passes the user's question to the agent and streams the response in real-time.
    Returns a timeout error if the response is not completed within the specified time.

    Args:
        query: Text of the question entered by the user
        text_placeholder: Streamlit component to display text responses
        tool_placeholder: Streamlit component to display tool call information
        timeout_seconds: Response generation time limit (seconds)

    Returns:
        response: Agent's response object
        final_text: Final text response
        final_tool: Final tool call information
    """
    try:
        if st.session_state.agent:
            streaming_callback, accumulated_text_obj, accumulated_tool_obj = (
                get_streaming_callback(text_placeholder, tool_placeholder)
            )
            try:
                response = await asyncio.wait_for(
                    astream_graph(
                        st.session_state.agent,
                        {"messages": [HumanMessage(content=query)]},
                        callback=streaming_callback,
                        config=RunnableConfig(
                            recursion_limit=st.session_state.recursion_limit,
                            thread_id=st.session_state.thread_id,
                        ),
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                error_msg = f"⏱️ Request time exceeded {timeout_seconds} seconds. Please try again later."
                return {"error": error_msg}, error_msg, ""

            final_text = "".join(accumulated_text_obj)
            final_tool = "".join(accumulated_tool_obj)
            return response, final_text, final_tool
        else:
            return (
                {"error": "🚫 Agent has not been initialized."},
                "🚫 Agent has not been initialized.",
                "",
            )
    except Exception as e:
        import traceback

        error_msg = f"❌ Error occurred during query processing: {str(e)}\n{traceback.format_exc()}"
        return {"error": error_msg}, error_msg, ""


async def initialize_session(mcp_config=None):
    """
    Initializes MCP session and agent.

    Args:
        mcp_config: MCP tool configuration information (JSON). Uses default settings if None

    Returns:
        bool: Initialization success status
    """
    with st.spinner("🔄 Connecting to MCP server..."):
        # First safely clean up existing client
        await cleanup_mcp_client()

        if mcp_config is None:
            # Load settings from config.json file
            mcp_config = load_config_from_json()
        client = MultiServerMCPClient(mcp_config)
        await client.__aenter__()
        tools = client.get_tools()
        st.session_state.tool_count = len(tools)
        st.session_state.mcp_client = client

        # Initialize appropriate model based on selection
        selected_model = st.session_state.selected_model

        # if selected_model in [
        #     "claude-3-7-sonnet-latest",
        #     "claude-3-5-sonnet-latest",
        #     "claude-3-5-haiku-latest",
        # ]:
        #     model = ChatAnthropic(
        #         model=selected_model,
        #         temperature=0.1,
        #         max_tokens=OUTPUT_TOKEN_INFO[selected_model]["max_tokens"],
        #     )
        # else:  # Use OpenAI model
        # model = ChatOpenAI(
        #     model=selected_model,
        #     temperature=0.1,
        #     max_tokens=OUTPUT_TOKEN_INFO[selected_model]["max_tokens"],
        # )
        model = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            api_key=os.environ.get("GEMINI_API_KEY"),
            temperature=0
        )
        agent = create_react_agent(
            model,
            tools,
            checkpointer=MemorySaver(),
            prompt=SYSTEM_PROMPT,
        )
        st.session_state.agent = agent
        st.session_state.session_initialized = True
        return True


# --- Sidebar: System Settings Section ---
with st.sidebar:
    st.subheader("⚙️ System Settings")

    # Model selection feature
    # Create list of available models
    available_models = []

    # Check Gemini API key
    has_gemini_key = os.environ.get("GEMINI_API_KEY") is not None
    if has_gemini_key:
        available_models.extend(["gemini-1.5-flash"])

    # Display message if no models are available
    if not available_models:
        st.warning(
            "⚠️ API keys are not configured. Please add GEMINI_API_KEY to your .env file."
        )
        # Add Claude model as default (to show UI even without keys)
        available_models = ["gemini-1.5-flash"]

    # Model selection dropdown
    previous_model = st.session_state.selected_model
    st.session_state.selected_model = st.selectbox(
        "🤖 Select model to use",
        options=available_models,
        index=(
            available_models.index(st.session_state.selected_model)
            if st.session_state.selected_model in available_models
            else 0
        ),
        help="Anthropic models require ANTHROPIC_API_KEY and OpenAI models require OPENAI_API_KEY to be set as environment variables.",
    )

    # Notify when model is changed and session needs to be reinitialized
    if (
        previous_model != st.session_state.selected_model
        and st.session_state.session_initialized
    ):
        st.warning(
            "⚠️ Model has been changed. Click 'Apply Settings' button to apply changes."
        )

    # Add timeout setting slider
    st.session_state.timeout_seconds = st.slider(
        "⏱️ Response generation time limit (seconds)",
        min_value=60,
        max_value=300,
        value=st.session_state.timeout_seconds,
        step=10,
        help="Set the maximum time for the agent to generate a response. Complex tasks may require more time.",
    )

    st.session_state.recursion_limit = st.slider(
        "⏱️ Recursion call limit (count)",
        min_value=10,
        max_value=200,
        value=st.session_state.recursion_limit,
        step=10,
        help="Set the recursion call limit. Setting too high a value may cause memory issues.",
    )

    st.divider()  # Add divider

    # Tool settings section
    st.subheader("🔧 Tool Settings")

    # Manage expander state in session state
    if "mcp_tools_expander" not in st.session_state:
        st.session_state.mcp_tools_expander = False

    # MCP tool addition interface
    with st.expander("🧰 Add MCP Tools", expanded=st.session_state.mcp_tools_expander):
        # Load settings from config.json file
        loaded_config = load_config_from_json()
        default_config_text = json.dumps(
            loaded_config, indent=2, ensure_ascii=False)

        # Create pending config based on existing mcp_config_text if not present
        if "pending_mcp_config" not in st.session_state:
            try:
                st.session_state.pending_mcp_config = loaded_config
            except Exception as e:
                st.error(f"Failed to set initial pending config: {e}")

        # UI for adding individual tools
        st.subheader("Add Tool(JSON format)")
        st.markdown(
            """
        Please insert **ONE tool** in JSON format.

        [How to Set Up?](https://teddylee777.notion.site/MCP-Tool-Setup-Guide-English-1d324f35d1298030a831dfb56045906a)

        ⚠️ **Important**: JSON must be wrapped in curly braces (`{}`).
        """
        )

        # Provide clearer example
        example_json = {
            "github": {
                "command": "npx",
                "args": [
                    "-y",
                    "@smithery/cli@latest",
                    "run",
                    "@smithery-ai/github",
                    "--config",
                    '{"githubPersonalAccessToken":"your_token_here"}',
                ],
                "transport": "stdio",
            }
        }

        default_text = json.dumps(example_json, indent=2, ensure_ascii=False)

        new_tool_json = st.text_area(
            "Tool JSON",
            default_text,
            height=250,
        )

        # Add button
        if st.button(
            "Add Tool",
            type="primary",
            key="add_tool_button",
            use_container_width=True,
        ):
            try:
                # Validate input
                if not new_tool_json.strip().startswith(
                    "{"
                ) or not new_tool_json.strip().endswith("}"):
                    st.error("JSON must start and end with curly braces ({}).")
                    st.markdown('Correct format: `{ "tool_name": { ... } }`')
                else:
                    # Parse JSON
                    parsed_tool = json.loads(new_tool_json)

                    # Check if it's in mcpServers format and process accordingly
                    if "mcpServers" in parsed_tool:
                        # Move contents of mcpServers to top level
                        parsed_tool = parsed_tool["mcpServers"]
                        st.info(
                            "'mcpServers' format detected. Converting automatically."
                        )

                    # Check number of tools entered
                    if len(parsed_tool) == 0:
                        st.error("Please enter at least one tool.")
                    else:
                        # Process all tools
                        success_tools = []
                        for tool_name, tool_config in parsed_tool.items():
                            # Check URL field and set transport
                            if "url" in tool_config:
                                # Set transport to "sse" if URL exists
                                tool_config["transport"] = "sse"
                                st.info(
                                    f"URL detected in '{tool_name}' tool, setting transport to 'sse'."
                                )
                            elif "transport" not in tool_config:
                                # Set default "stdio" if URL doesn't exist and transport isn't specified
                                tool_config["transport"] = "stdio"

                            # Check required fields
                            if (
                                "command" not in tool_config
                                and "url" not in tool_config
                            ):
                                st.error(
                                    f"'{tool_name}' tool configuration requires either 'command' or 'url' field."
                                )
                            elif "command" in tool_config and "args" not in tool_config:
                                st.error(
                                    f"'{tool_name}' tool configuration requires 'args' field."
                                )
                            elif "command" in tool_config and not isinstance(
                                tool_config["args"], list
                            ):
                                st.error(
                                    f"'args' field in '{tool_name}' tool must be an array ([]) format."
                                )
                            else:
                                # Add tool to pending_mcp_config
                                st.session_state.pending_mcp_config[tool_name] = (
                                    tool_config
                                )
                                success_tools.append(tool_name)

                        # Success message
                        if success_tools:
                            if len(success_tools) == 1:
                                st.success(
                                    f"{success_tools[0]} tool has been added. Click 'Apply Settings' button to apply."
                                )
                            else:
                                tool_names = ", ".join(success_tools)
                                st.success(
                                    f"Total {len(success_tools)} tools ({tool_names}) have been added. Click 'Apply Settings' button to apply."
                                )
                            # Collapse expander after adding
                            st.session_state.mcp_tools_expander = False
                            st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"JSON parsing error: {e}")
                st.markdown(
                    f"""
                **How to fix**:
                1. Check that your JSON format is correct.
                2. All keys must be wrapped in double quotes (").
                3. String values must also be wrapped in double quotes (").
                4. When using double quotes within a string, they must be escaped (\\").
                """
                )
            except Exception as e:
                st.error(f"Error occurred: {e}")

    # Display registered tools list and add delete buttons
    with st.expander("📋 Registered Tools List", expanded=True):
        try:
            pending_config = st.session_state.pending_mcp_config
        except Exception as e:
            st.error("Not a valid MCP tool configuration.")
        else:
            # Iterate through keys (tool names) in pending config
            for tool_name in list(pending_config.keys()):
                col1, col2 = st.columns([8, 2])
                col1.markdown(f"- **{tool_name}**")
                if col2.button("Delete", key=f"delete_{tool_name}"):
                    # Delete tool from pending config (not applied immediately)
                    del st.session_state.pending_mcp_config[tool_name]
                    st.success(
                        f"{tool_name} tool has been deleted. Click 'Apply Settings' button to apply."
                    )

    st.divider()  # Add divider

# --- Sidebar: System Information and Action Buttons Section ---
with st.sidebar:
    st.subheader("📊 System Information")
    st.write(
        f"🛠️ MCP Tools Count: {st.session_state.get('tool_count', 'Initializing...')}"
    )
    selected_model_name = st.session_state.selected_model
    st.write(f"🧠 Current Model: {selected_model_name}")

    # Move Apply Settings button here
    if st.button(
        "Apply Settings",
        key="apply_button",
        type="primary",
        use_container_width=True,
    ):
        # Display applying message
        apply_status = st.empty()
        with apply_status.container():
            st.warning("🔄 Applying changes. Please wait...")
            progress_bar = st.progress(0)

            # Save settings
            st.session_state.mcp_config_text = json.dumps(
                st.session_state.pending_mcp_config, indent=2, ensure_ascii=False
            )

            # Save settings to config.json file
            save_result = save_config_to_json(
                st.session_state.pending_mcp_config)
            if not save_result:
                st.error("❌ Failed to save settings file.")

            progress_bar.progress(15)

            # Prepare session initialization
            st.session_state.session_initialized = False
            st.session_state.agent = None

            # Update progress
            progress_bar.progress(30)

            # Run initialization
            success = st.session_state.event_loop.run_until_complete(
                initialize_session(st.session_state.pending_mcp_config)
            )

            # Update progress
            progress_bar.progress(100)

            if success:
                st.success("✅ New settings have been applied.")
                # Collapse tool addition expander
                if "mcp_tools_expander" in st.session_state:
                    st.session_state.mcp_tools_expander = False
            else:
                st.error("❌ Failed to apply settings.")

        # Refresh page
        st.rerun()

    st.divider()  # Add divider

    # Action buttons section
    st.subheader("🔄 Actions")

    # Reset conversation button
    if st.button("Reset Conversation", use_container_width=True, type="primary"):
        # Reset thread_id
        st.session_state.thread_id = random_uuid()

        # Reset conversation history
        st.session_state.history = []

        # Notification message
        st.success("✅ Conversation has been reset.")

        # Refresh page
        st.rerun()

    # Show logout button only if login feature is enabled
    if use_login and st.session_state.authenticated:
        st.divider()  # Add divider
        if st.button("Logout", use_container_width=True, type="secondary"):
            st.session_state.authenticated = False
            st.success("✅ You have been logged out.")
            st.rerun()

# --- Initialize default session (if not initialized) ---
if not st.session_state.session_initialized:
    st.info(
        "MCP server and agent are not initialized. Please click the 'Apply Settings' button in the left sidebar to initialize."
    )


# --- Print conversation history ---
print_message()

# Sample questions
sample_questions = [
    "What is Cloudflare object storage?",
    "What tools are available? Give me a list with descriptions.",
]

# Create columns for horizontal layout
cols = st.columns(len(sample_questions))  # Creates a column for each question
# Add buttons to columns
for i, question in enumerate(sample_questions):
    with cols[i]:
        if st.button(question, key=f"sample_{i}"):
            st.session_state.user_query = question

# # Display sample questions with a header
# # st.write("**Try asking one of these:**")
# for question in sample_questions:
#     # Make each question clickable to populate the input
#     if st.button(question, key=f"sample_{question}"):
#         # This will store the question for use in your chat
#         st.session_state.user_query = question

# --- User input and processing ---
user_query = st.chat_input("💬 Enter your question")
if 'user_query' in st.session_state:
    user_query = st.session_state.user_query
    # Clear it after use if you want
    del st.session_state.user_query
if user_query:
    if st.session_state.session_initialized:
        st.chat_message("user", avatar="🧑‍💻").markdown(user_query)
        with st.chat_message("assistant", avatar="🤖"):
            tool_placeholder = st.empty()
            text_placeholder = st.empty()
            resp, final_text, final_tool = (
                st.session_state.event_loop.run_until_complete(
                    process_query(
                        user_query,
                        text_placeholder,
                        tool_placeholder,
                        st.session_state.timeout_seconds,
                    )
                )
            )
        if "error" in resp:
            st.error(resp["error"])
        else:
            st.session_state.history.append(
                {"role": "user", "content": user_query})
            st.session_state.history.append(
                {"role": "assistant", "content": final_text}
            )
            if final_tool.strip():
                st.session_state.history.append(
                    {"role": "assistant_tool", "content": final_tool}
                )
            st.rerun()
    else:
        st.warning(
            "⚠️ MCP server and agent are not initialized. Please click the 'Apply Settings' button in the left sidebar to initialize."
        )
