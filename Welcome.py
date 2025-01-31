import streamlit as st

# Set page configuration to wide layout
st.set_page_config(
    page_title="VUmc Optimised Staff Scheduling",
    layout="wide",

)

# Initialize session state at top level
if 'button_clicked' not in st.session_state:
    st.session_state.button_clicked = False
if 'model' not in st.session_state:
    st.session_state.model = None
if 'schedule_generated' not in st.session_state:
    st.session_state.schedule_generated = False
if 'calendar_data' not in st.session_state:
    st.session_state.calendar_data = None
if 'calendar_view' not in st.session_state:
    st.session_state.calendar_view = 'dayGridMonth'
if 'input_file' not in st.session_state:
    st.session_state.input_file = None

# Apply global CSS for sans-serif font, center the title, and set background color to white
st.markdown(
    """
    <style>
    body {
        font-family: Arial, Helvetica, sans-serif;
        text-align: center;
    }
    h1 {
        text-align: center;
    }
    h2, h3, h4, h5, h6 {
        font-family: Arial, Helvetica, sans-serif;
    }
    .right-align {
        display: flex;
        justify-content: flex-end;
    }
    .left-align {
        display: flex;
        justify-content: flex-start;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    st.image("images/amsterdam-umc-universitair-medische-centra-logo-vector-2_black.png", width=400)
with col4:
    st.image("images/VU_logo_black.png", width=400)

if 'init' not in st.session_state:
    st.session_state.init = True
    st.session_state.form_submitted = False

if __name__ == "__main__":
    # Center the page title
    st.markdown("<h1>VUmc Optimised Staff Scheduling</h1>", unsafe_allow_html=True)
    st.markdown("<b1>This Nurse Scheduling Optimization Tool uses an input file to determine the optimal schedule for the next 7 days</b1>", unsafe_allow_html=True)


