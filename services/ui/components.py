from __future__ import annotations

import html
import time
from typing import Optional

import streamlit as st

from services.config.workout_config import EXERCISE_OPTIONS

EXERCISE_META = {
    "Squats": {"icon": "🏋️", "focus": "Legs & glutes", "cue": "Chest up, sit back, drive through your heels."},
    "Push-ups": {"icon": "🫸", "focus": "Chest & core", "cue": "Keep a straight line from head to heels."},
    "Biceps Curls (Dumbbell)": {"icon": "💪", "focus": "Biceps", "cue": "Pin elbows, control the lower, no swing."},
    "Shoulder Press": {"icon": "🙌", "focus": "Shoulders", "cue": "Brace your core and press overhead."},
    "Lunges": {"icon": "🦵", "focus": "Legs & balance", "cue": "Front knee tracks over the toes, torso tall."},
}


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def render_html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def ratio(current: int, target: int) -> float:
    if target <= 0:
        return 0.0
    return max(0.0, min(1.0, current / target))


def elapsed_label(started_at) -> str:
    try:
        started = float(started_at or 0)
    except (TypeError, ValueError):
        started = 0.0
    if started <= 0:
        return "0:00"
    seconds = max(0, int(time.time() - started))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def render_hero(workout_started: bool, username: Optional[str] = None) -> None:
    status = "LIVE SESSION" if workout_started else "READY TO TRAIN"
    status_class = "is-live" if workout_started else "is-idle"
    greeting = f"Hey {_esc(username)}" if username else "Form IQ AI COACH"
    render_html(
        f"""
        <div class="hero-banner">
            <div>
                <p class="hero-kicker">Form IQ AI COACH</p>
                <h1 class="hero-title">{greeting}</h1>
                <p class="hero-sub">Live pose tracking with voice cues as you train.</p>
            </div>
            <span class="status-chip {status_class}">
                <span class="status-dot"></span>
                {status}
            </span>
        </div>
        """
    )


def render_idle_panel() -> None:
    cards = "".join(
        f"""
        <div class="idle-card">
            <span class="idle-icon">{meta['icon']}</span>
            <strong>{_esc(name)}</strong>
            <span>{_esc(meta['focus'])}</span>
        </div>
        """
        for name, meta in EXERCISE_META.items()
        if name in EXERCISE_OPTIONS
    )
    render_html(
        f"""
        <div class="idle-panel">
            <div class="idle-copy">
                <h2>Set your workout plan</h2>
                <p>Pick an exercise, sets, and reps in the sidebar, then hit <strong>Start Workout</strong> to open the camera and coach.</p>
            </div>
            <div class="idle-grid">{cards}</div>
        </div>
        """
    )


def render_coach_bubble(message: str) -> None:
    if not message:
        return
    render_html(
        f"""
        <div class="coach-bubble">
            <div class="coach-avatar">🤖</div>
            <div>
                <p class="coach-label">Coach</p>
                <p class="coach-text">{_esc(message)}</p>
            </div>
        </div>
        """
    )


def render_live_banner(exercise: str, camera_live: bool, elapsed: str) -> None:
    meta = EXERCISE_META.get(exercise, {"icon": "🏋️", "cue": "Stay in frame and keep moving."})
    cam = "CAMERA LIVE" if camera_live else "START CAMERA"
    cam_class = "is-live" if camera_live else "is-idle"
    render_html(
        f"""
        <div class="live-banner">
            <div class="live-banner-main">
                <span class="live-icon">{meta['icon']}</span>
                <div>
                    <p class="live-exercise">{_esc(exercise)}</p>
                    <p class="live-cue">{_esc(meta.get('cue', ''))}</p>
                </div>
            </div>
            <div class="live-meta">
                <span class="status-chip {cam_class}">
                    <span class="status-dot"></span>
                    {cam}
                </span>
                <span class="elapsed-chip">⏱ {elapsed}</span>
            </div>
        </div>
        """
    )


def render_set_track(sets_completed: int, target_sets: int) -> None:
    target = max(int(target_sets or 0), 0)
    done = max(int(sets_completed or 0), 0)
    if target <= 0:
        return
    dots = []
    for index in range(target):
        if index < done:
            state = "done"
        elif index == done:
            state = "current"
        else:
            state = "todo"
        dots.append(f'<span class="set-dot {state}" title="Set {index + 1}"></span>')
    render_html(
        f"""
        <div class="set-track">
            <span class="set-track-label">Sets</span>
            <div class="set-dots">{''.join(dots)}</div>
        </div>
        """
    )


def render_session_plan(exercise: str, sets, reps) -> None:
    meta = EXERCISE_META.get(exercise, {"icon": "🏋️", "focus": "Full body"})
    render_html(
        f"""
        <div class="plan-card">
            <span class="plan-icon">{meta['icon']}</span>
            <div>
                <strong>{_esc(exercise)}</strong>
                <p>{_esc(sets)} sets · {_esc(reps)} reps · {_esc(meta['focus'])}</p>
            </div>
        </div>
        """
    )


def render_history_empty() -> None:
    render_html(
        """
        <div class="history-empty">
            <strong>No workouts logged yet</strong>
            <p>Finish a session and your sets, reps, and time will show up here.</p>
        </div>
        """
    )
