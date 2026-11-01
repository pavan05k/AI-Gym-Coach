import streamlit as st

from services.persistence.exercise_repository import get_or_create_user
from services.ui.components import render_html


def render_login_wall():
    if st.session_state.get("user_id") is not None:
        return True

    render_html(
        """
        <div class="login-panel">
            <p class="hero-kicker">Form IQ AI COACH</p>
            <h2>Step in and start training</h2>
            <p>Enter a unique name to load your history and unlock live coaching.</p>
        </div>
        """
    )

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input(
            "Name (unique)",
            placeholder="unique name e.g. Pavan",
            help="Use the same name next time to keep your workout history.",
        )
        submit_button = st.form_submit_button("Start Session", width="stretch", type="primary")

    if submit_button:
        if not username:
            st.error("Name cannot be empty.")
            return False
        user = get_or_create_user(username)

        st.session_state["user_id"] = user["id"]
        st.session_state["username"] = user["username"]

        st.rerun()

    return False
