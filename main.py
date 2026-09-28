import os
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from services.auth.login_wall import render_login_wall
from services.coaching.llm import LLMCoach
from services.coaching.tss import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio
from services.config.workout_config import EXERCISE_OPTIONS, METRICS_FIELDS
from services.persistence.exercise_repository import (
    add_exercise,
    delete_users_exercises,
    get_users_exercises,
    init_db,
)
from services.state.session_defaults import initial_session_defaults
from services.tracking.metrics import sync_metrics_update
from services.ui.components import (
    EXERCISE_META,
    elapsed_label,
    ratio,
    render_coach_bubble,
    render_hero,
    render_history_empty,
    render_idle_panel,
    render_live_banner,
    render_session_plan,
    render_set_track,
)
from services.ui.style_loader import inject_local_font, inject_webrtc_styles, load_css
from services.vision.exercise_video_prosessor import VideoProcessorClass

load_dotenv()

PLAN_PRESETS = [
    ("3×8", 3, 8),
    ("3×10", 3, 10),
    ("4×12", 4, 12),
    ("5×5", 5, 5),
]


def _apply_plan_preset(sets, reps):
    st.session_state.plan_sets = int(sets)
    st.session_state.plan_reps = int(reps)


def _start_workout(plan_exercise, plan_sets, plan_reps):
    st.session_state.exercise_type = plan_exercise
    st.session_state.target_sets = int(plan_sets)
    st.session_state.reps_per_set = int(plan_reps)
    st.session_state.reps = 0
    st.session_state.current_set_reps = 0
    st.session_state.sets_completed = 0
    st.session_state.workout_started = True
    now = time.time()
    st.session_state.set_cycle_started_at = now
    st.session_state.workout_started_at = now
    st.session_state.last_saved_sets_completed = 0
    # The WebRTC processor may be reused between sessions. Reset it
    # once when this session starts, not on every live UI refresh.
    st.session_state.detector_reset_pending = True

    if st.session_state.voice_pipeline:
        result = st.session_state.voice_pipeline.process_event(
            event="workout_started",
            exercise=plan_exercise,
            metrics={}
        )

        if result:
            st.session_state.audio_to_play, st.session_state.coach_feedback = result

    st.session_state.last_notified_sets_completed = 0
    st.session_state.last_notified_workout_complete = False
    st.rerun()


def _save_unsaved_workout_progress(exercise):
    user_id = st.session_state.get("user_id")
    total_reps = int(st.session_state.get("reps", 0) or 0)
    reps_per_set = int(st.session_state.get("reps_per_set", 0) or 0)
    saved_sets = int(st.session_state.get("last_saved_sets_completed", 0) or 0)
    completed_sets = int(st.session_state.get("sets_completed", 0) or 0)

    if not isinstance(user_id, int) or user_id <= 0 or total_reps <= 0:
        return

    saved_reps = saved_sets * reps_per_set
    unsaved_reps = max(total_reps - saved_reps, 0)
    unsaved_sets = max(completed_sets - saved_sets, 0)
    if unsaved_reps <= 0 and unsaved_sets <= 0:
        return

    started_at = st.session_state.get("workout_started_at", time.time())
    add_exercise(
        user_id,
        exercise,
        unsaved_reps,
        unsaved_sets,
        max(time.time() - started_at, 0),
    )


def _end_workout(exercise):
    _save_unsaved_workout_progress(exercise)
    st.session_state.workout_started = False
    st.session_state.camera_live = False

    if st.session_state.voice_pipeline:
        result = st.session_state.voice_pipeline.process_event(
            event="workout_completed",
            exercise=exercise,
            metrics={}
        )
        if result:
            st.session_state.audio_to_play, st.session_state.coach_feedback = result

    st.rerun()


def _reset_workout_history(user_id):
    delete_users_exercises(user_id)
    st.rerun()


def _render_live_metrics(exercise):
    total_reps = int(st.session_state.get("reps", 0) or 0)
    current_set_reps = int(st.session_state.get("current_set_reps", 0) or 0)
    reps_per_set = int(st.session_state.get("reps_per_set", 0) or 0)
    sets_completed = int(st.session_state.get("sets_completed", 0) or 0)
    target_sets = int(st.session_state.get("target_sets", 0) or 0)

    st.subheader("Progress")
    render_set_track(sets_completed, target_sets)
    st.progress(
        ratio(current_set_reps, reps_per_set),
        text=f"This set  {current_set_reps} / {reps_per_set}",
    )
    st.progress(
        ratio(sets_completed, target_sets),
        text=f"Workout  {sets_completed} / {target_sets} sets",
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Reps", f"{total_reps}")
    c2.metric("Current Set", f"{current_set_reps} / {reps_per_set}")
    c3.metric("Sets", f"{sets_completed} / {target_sets}")

    field_map = {
        "Squats": ("Squat Metrics", [
            ("Knee Angle", f"{st.session_state.get('knee_angle', 0)}°"),
            ("Back Angle", f"{st.session_state.get('back_angle', 0)}°"),
            ("Depth Status", st.session_state.get("depth_status", "N/A")),
        ]),
        "Push-ups": ("Push-up Metrics", [
            ("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°"),
            ("Body Alignment", st.session_state.get("body_alignment", "N/A")),
            ("Hip Position", st.session_state.get("hip_status", "N/A")),
        ]),
        "Biceps Curls (Dumbbell)": ("Curl Metrics", [
            ("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°"),
            ("Shoulder Stability", st.session_state.get("shoulder_status", "N/A")),
            ("Swing Detection", st.session_state.get("swing_status", "N/A")),
        ]),
        "Shoulder Press": ("Shoulder Press Metrics", [
            ("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°"),
            ("Arm Extension", st.session_state.get("extension_status", "N/A")),
            ("Back Arch", st.session_state.get("back_arch_status", "N/A")),
        ]),
        "Lunges": ("Lunge Metrics", [
            ("Front Knee Angle", f"{st.session_state.get('front_knee_angle', 0)}°"),
            ("Torso Angle", f"{st.session_state.get('torso_angle', 0)}°"),
            ("Balance Status", st.session_state.get("balance_status", "N/A")),
        ]),
    }

    if exercise in field_map:
        title, metrics = field_map[exercise]
        st.divider()
        st.subheader(title)
        cols = st.columns(3)
        for col, (label, value) in zip(cols, metrics):
            col.metric(label, value)
    elif exercise in METRICS_FIELDS:
        st.divider()
        st.subheader("Form Metrics")


def main():
    st.set_page_config(
        page_icon="🏋️‍♀️",
        page_title="Form IQ AI COACH",
        initial_sidebar_state="expanded",
        layout="centered"
    )

    load_css(os.path.join(os.getcwd(), "static", "style.css"))
    inject_local_font(os.path.join(os.getcwd(), "static", "AdobeClean.otf"), "AdobeClean")

    init_db()

    if not render_login_wall():
        return

    initial_session_defaults()

    if "voice_pipeline" not in st.session_state:
        try:
            api_key = os.environ.get("GROQ_API_KEY", "")

            if not api_key and hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                api_key = st.secrets["GROQ_API_KEY"]

            if not api_key:
                st.warning("Voice coaching is unavailable. Configure GROQ_API_KEY to enable it.")
                st.session_state.voice_pipeline = None
            else:
                groq_client = Groq(api_key=api_key)
                llm_coach = LLMCoach(groq_client)
                tts = TextToSpeech()
                st.session_state.voice_pipeline = VoicePipeline(llm_coach, tts)
        except (OSError, RuntimeError, ValueError):
            st.session_state.voice_pipeline = None

    workout_started = st.session_state.get("workout_started", False)

    with st.sidebar:
        st.title("🏋️‍♂️ Form IQ AI COACH")

        if st.session_state.username:
            st.caption(f"👤 Logged in as {st.session_state.username}")

        st.divider()
        st.subheader("Workout Plan")

        if not workout_started:
            plan_exercise = st.pills(
                "Exercise",
                options=EXERCISE_OPTIONS,
                key="plan_exercise",
            )
            if not plan_exercise:
                plan_exercise = st.session_state.get("last_exercise_type", EXERCISE_OPTIONS[0])

            meta = EXERCISE_META.get(plan_exercise, {})
            if meta:
                st.caption(f"{meta['icon']} {meta['focus']} — {meta['cue']}")

            st.markdown("Quick plan")
            preset_cols = st.columns(len(PLAN_PRESETS))
            for col, (label, sets, reps) in zip(preset_cols, PLAN_PRESETS):
                col.button(
                    label,
                    key=f"preset_{label}",
                    width="stretch",
                    on_click=_apply_plan_preset,
                    args=(sets, reps),
                )

            plan_sets = st.number_input("Sets", min_value=0, max_value=50, key="plan_sets", step=1)
            plan_reps = st.number_input("Reps per Set", min_value=0, max_value=50, key="plan_reps", step=1)

            st.markdown("")
            start_session_button = st.button(
                "Start Workout",
                width="stretch",
                key="start_session_button",
                type="primary",
            )

            if start_session_button:
                _start_workout(plan_exercise, plan_sets, plan_reps)
        else:
            exercise = st.session_state.get("exercise_type", "Workout")
            sets = st.session_state.get("target_sets")
            reps = st.session_state.get("reps_per_set")
            render_session_plan(exercise, sets, reps)

            end_session_button = st.button("End Workout", key="end_session_button", width="stretch")
            if end_session_button:
                _end_workout(exercise)

        if workout_started:
            st.divider()
            _render_live_metrics(st.session_state.get("exercise_type", "N/A"))

    render_hero(workout_started, st.session_state.get("username"))

    if st.session_state.get("audio_to_play"):
        autoplay_audio(
            st.session_state.audio_to_play,
            st.session_state.get("coach_feedback"),
        )

    render_coach_bubble(st.session_state.get("coach_feedback", ""))

    if not workout_started:
        render_idle_panel()
    else:
        exercise = st.session_state.get("exercise_type", "Workout")
        render_live_banner(
            exercise,
            st.session_state.get("camera_live", False),
            elapsed_label(st.session_state.get("workout_started_at")),
        )
        context = webrtc_streamer(
            key="exercise-analysis",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=VideoProcessorClass,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
            media_stream_constraints={
                "video": True,
                "audio": False
            },
            async_processing=True
        )

        camera_live = bool(context.state.playing)
        st.session_state.camera_live = camera_live

        sync_metrics_update(context)

        if camera_live:
            time.sleep(0.1)
            st.rerun()

        inject_webrtc_styles()

    user_id = st.session_state.get("user_id", 0)

    if isinstance(user_id, int):
        st.divider()
        history_title, history_action = st.columns([4, 1])
        history_title.markdown("#### Workout History")
        if history_action.button(
            "Reset",
            key="reset_workout_history",
            help="Delete all workout history for this account.",
            type="secondary",
            width="stretch",
        ):
            _reset_workout_history(user_id)

        history_rows = get_users_exercises(user_id)

        arr = [
            {
                "Exercise": row['exercise_name'],
                "Reps": row['reps'],
                "Sets": row['sets'],
                "Time (sec)": row['time'],
                "Date": row['created_at']
            }
            for row in history_rows
        ]

        df = pd.DataFrame(arr)

        if not df.empty:
            df["Date"] = pd.to_datetime(df["Date"]).dt.date
            agg_df = df.groupby(["Exercise", "Date"]).agg({
                "Reps": 'sum',
                "Sets": "sum",
                "Time (sec)": "sum"
            }).reset_index()
            agg_df.index += 1
            agg_df["Time (sec)"] = agg_df["Time (sec)"].round(1)

            table_tab, trend_tab = st.tabs(["Log", "Trends"])
            with table_tab:
                st.dataframe(agg_df, width="stretch", hide_index=False)
            with trend_tab:
                chart_df = agg_df.copy()
                chart_df["Date"] = pd.to_datetime(chart_df["Date"])
                st.bar_chart(chart_df, x="Date", y="Reps", color="Exercise", width="stretch")
        else:
            render_history_empty()


if __name__ == "__main__":
    main()
