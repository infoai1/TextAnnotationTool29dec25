import streamlit as st

# Init state
if "panel_open" not in st.session_state:
    st.session_state.panel_open = False
if "selected" not in st.session_state:
    st.session_state.selected = None

# Callback
def open_panel(file_id):
    st.session_state.panel_open = True
    st.session_state.selected = file_id

# Button
st.button("Action", on_click=open_panel, args=("test_file",))

# Panel
if st.session_state.panel_open:
    st.write(f"Panel open for: {st.session_state.selected}")
    if st.button("Close"):
        st.session_state.panel_open = False
else:
    st.write("Panel closed")

# Debug
st.write("State:", dict(st.session_state))
