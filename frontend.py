
import os
import json
import streamlit as st
from groq import Groq

st.set_page_config(page_title="Fitness AI Agent", page_icon="\U0001F4AA", layout="centered")

#MODEL_CHAT = "llama-3.3-70b-versatile"
MODEL_CHAT = "openai/gpt-oss-120b" # coaching dialogue, plan generation, negotiation
#MODEL_FAST = "llama-3.1-8b-instant"
MODEL_FAST = "openai/gpt-oss-120b"    # structured extraction / classification

REQUIRED_FIELDS = ["goal", "weight", "food_pref", "injuries", "equipment"]

# ---------------- Session state ----------------
defaults = {
    "stage": "onboarding",
    "messages": [],
    "profile": {**{f: None for f in REQUIRED_FIELDS}, "missing": REQUIRED_FIELDS.copy()},
    "plan": None,
    "negotiation_turns": 0,
    "negotiation_messages": [],
    "streak": 0,
    "badges": [],
    "skip_counts": {"low_motivation": 0, "sick": 0, "logistics": 0},
    "groq_api_key": os.environ.get("grop_api", ""),
    "fail_response": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------- Groq helpers ----------------
def get_client():
  key = st.session_state.get("groq_api_key")
  if not key:
    return None
  return Groq(api_key=key)


def chat_completion(system_prompt, messages, model=MODEL_CHAT, json_mode=False):
  client = get_client()
  if client is None:
    return None
  kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
  resp = client.chat.completions.create(
      model=model,
      messages=[{"role": "system", "content": system_prompt}] + messages,
      temperature=0.6,
      **kwargs,
  )
  return resp.choices[0].message.content


def extract_profile(messages):
  system = (
      "You extract a fitness client's profile from a coaching conversation. "
      "Return ONLY a JSON object with these keys: goal, weight, food_pref,"
      " injuries, equipment, and missing (a list of the field names above that"
      " are still unknown). Use null for values you don't know yet. No text"
      " outside the JSON."
  )
  convo = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
  raw = chat_completion(
      system,
      [{"role": "user", "content": convo}],
      model=MODEL_FAST,
      json_mode=True,
  )
  try:
    data = json.loads(raw)
    data.setdefault("missing", [f for f in REQUIRED_FIELDS if not data.get(f)])
    return data
  except Exception:
    return st.session_state.profile


def generate_daily_plan(profile, streak):
  system = (
      "You are a fitness coach generating TODAY's single small habit"
      f" assignment.\nClient profile: {json.dumps(profile)}\nCurrent streak:"
      f" {streak} days.\nRules: start very small (e.g. a short walk) if streak"
      " is 0-2 days, then add roughly one new element every few days. Never"
      ' assign more than one new habit change at once.\nReturn ONLY JSON: {"habit":'
      ' "...", "duration_minutes": number, "reason": "one sentence explaining'
      ' why this is today\'s plan"}'
  )
  raw = chat_completion(
      system,
      [{"role": "user", "content": "Generate today's plan."}],
      json_mode=True,
  )
  try:
    return json.loads(raw)
  except Exception:
    return {
        "habit": "15-minute walk after dinner",
        "duration_minutes": 15,
        "reason": (
            "Starting small builds the habit before we add intensity."
        ),
    }


def negotiation_reply(plan, user_text, turn):
  if turn == 1:
    system = (
        "You are a fitness coach. The client is pushing back on today's plan:"
        f" {json.dumps(plan)}. Acknowledge what they want, then briefly explain"
        " the reasoning behind today's plan. Warm, 3-4 sentences. Do not change"
        " the plan yet."
    )
  elif turn == 2:
    system = (
        "You are a fitness coach. The client is still pushing back on:"
        f" {json.dumps(plan)}. Offer exactly two constrained alternatives for"
        " today, numbered 1 and 2. Keep it short."
    )
  else:
    system = (
        "You are a fitness coach. The client has pushed back multiple times"
        f" on: {json.dumps(plan)}. Set a firm, kind boundary: today's plan"
        " stands as originally set or as the alternative already offered."
        " Briefly explain why trusting the process matters today. No further"
        " negotiation offered."
    )
  return chat_completion(system, [{"role": "user", "content": user_text}])


def classify_skip_reason(user_text):
  system = (
      "Classify why a fitness client missed today's habit. Return ONLY JSON: "
      '{"category": "low_motivation" | "sick" | "logistics", "summary": "one'
      ' short sentence"}'
  )
  raw = chat_completion(
      system,
      [{"role": "user", "content": user_text}],
      model=MODEL_FAST,
      json_mode=True,
  )
  try:
    return json.loads(raw)
  except Exception:
    return {"category": "logistics", "summary": user_text[:80]}


# ---------------- Sidebar ----------------
with st.sidebar:
  st.subheader("⚙️ System Config")
  key_input = st.text_input(
      "🔑 Groq API Key:",
      type="password",
      value=st.session_state.groq_api_key,
      help="Free key at console.groq.com/keys",
  )
  if key_input:
    st.session_state.groq_api_key = key_input
  st.divider()
  st.subheader("Progress")
  st.metric("Streak", f"{st.session_state.streak} days")
  if st.session_state.badges:
    st.write("Badges: " + ", ".join(st.session_state.badges))
  st.caption(f"Stage: {st.session_state.stage}")
  if st.button("Reset demo"):
    for k, v in defaults.items():
      st.session_state[k] = v
    st.rerun()

st.title("💪 Fitness AI Agent")

if not st.session_state.groq_api_key:
  st.info(
      "Enter your free Groq API key in the sidebar to start. Get one at"
      " console.groq.com/keys"
  )
  st.stop()

# ---------------- Stage: onboarding ----------------
if st.session_state.stage == "onboarding":
  st.subheader("Let's get to know you")
  for m in st.session_state.messages:
    with st.chat_message(m["role"]):
      st.write(m["content"])

  if not st.session_state.messages:
    opener = "Hey! I'm your fitness coach. What's your main goal right now?"
    st.session_state.messages.append({"role": "assistant", "content": opener})
    with st.chat_message("assistant"):
      st.write(opener)

  user_input = st.chat_input("🤚 Type your reply...")
  if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
      st.write(user_input)

    with st.spinner("..."):
      profile = extract_profile(st.session_state.messages)
    st.session_state.profile = profile
    missing = profile.get("missing") or []

    if missing:
      system = (
          "You are a warm, encouraging fitness coach onboarding a new client."
          f" Ask ONE short follow-up question about: {missing[0]}. Do not ask"
          f" about anything already known: {json.dumps(profile)}."
      )
      with st.spinner("..."):
        reply = chat_completion(system, st.session_state.messages)
    else:
      reply = (
          "Great, I've got what I need! Tap 'Start my plan' below whenever"
          " you're ready."
      )

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
      st.write(reply)

  missing = st.session_state.profile.get("missing") or []
  filled = len(REQUIRED_FIELDS) - len(missing)
  st.progress(
      filled / len(REQUIRED_FIELDS),
      text=f"Profile completeness: {filled}/{len(REQUIRED_FIELDS)}",
  )

  col1, col2 = st.columns(2)
  with col1:
    if not missing and st.button("Start my plan →"):
      st.session_state.stage = "daily_plan"
      st.rerun()
  with col2:
    if missing and st.button("Skip remaining questions"):
      st.session_state.stage = "daily_plan"
      st.rerun()

# ---------------- Stage: daily plan + negotiation ----------------
elif st.session_state.stage == "daily_plan":
  if st.session_state.plan is None:
    with st.spinner("👍 Building today's plan..."):
      st.session_state.plan = generate_daily_plan(
          st.session_state.profile, st.session_state.streak
      )

  plan = st.session_state.plan
  st.subheader("🎯 Today's mission")
  st.write(
      f"**{plan.get('habit', '')}** — {plan.get('duration_minutes', '')} min"
  )
  st.caption(plan.get("reason", ""))
  st.divider()

  st.write(
      "Want to push back, ask for something different, or just chat about"
      " today's plan?"
  )
  for m in st.session_state.negotiation_messages:
    with st.chat_message(m["role"]):
      st.write(m["content"])

  user_input = st.chat_input("🔊 Say something to your coach...")
  if user_input:
    st.session_state.negotiation_messages.append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user"):
      st.write(user_input)
    st.session_state.negotiation_turns += 1
    with st.spinner("🤔 Coach is thinking..."):
      reply = negotiation_reply(
          plan, user_input, st.session_state.negotiation_turns
      )
    st.session_state.negotiation_messages.append(
        {"role": "assistant", "content": reply}
    )
    with st.chat_message("assistant"):
      st.write(reply)

  col1, col2 = st.columns(2)
  with col1:
    if st.button("✅ I completed it"):
      st.session_state.stage = "checkin"
      st.rerun()
  with col2:
    if st.button("❌ I couldn't do it today"):
      st.session_state.stage = "fail_flow"
      st.rerun()

# ---------------- Stage: positive flow ----------------
elif st.session_state.stage == "checkin":
  st.subheader("🎉 Nice work!")
  if not st.session_state.get("streak_counted_today"):
    st.session_state.streak += 1
    st.session_state.streak_counted_today = True
    milestones = {
        3: "3-day starter",
        7: "One week strong",
        30: "Habit builder",
    }
    if st.session_state.streak in milestones:
      badge = milestones[st.session_state.streak]
      if badge not in st.session_state.badges:
        st.session_state.badges.append(badge)
        st.balloons()
        st.success(f"💫 New badge unlocked: {badge}!")

  st.text_input("How did it feel? (optional)", key="feeling_input")
  if st.button("Continue to tomorrow"):
    st.session_state.plan = None
    st.session_state.negotiation_turns = 0
    st.session_state.negotiation_messages = []
    st.session_state.streak_counted_today = False
    st.session_state.stage = "daily_plan"
    st.rerun()

# ---------------- Stage: negative flow ----------------
elif st.session_state.stage == "fail_flow":
  st.subheader("That's okay — be honest 😊")
  reason_text = st.text_area("Mind sharing what got in the way today?")
  if st.button("Share") and reason_text:
    with st.spinner("..."):
      classification = classify_skip_reason(reason_text)
    category = classification.get("category", "logistics")
    st.session_state.skip_counts[category] = (
        st.session_state.skip_counts.get(category, 0) + 1
    )
    count = st.session_state.skip_counts[category]

    if category == "low_motivation":
      msg = (
          "Everyone has days like this. No judgment — let's just pick it back"
          " up tomorrow."
          if count <= 3
          else (
              "This is several days in a row — let's talk about whether the plan"
              " itself needs to change, not just today."
          )
      )
    elif category == "sick":
      msg = (
          "Sorry to hear that. Rest is part of the plan too. Light stretching"
          " only if you're up for it, and ginger tea can help settle things —"
          " otherwise just rest and hydrate."
      )
    else:
      msg = (
          "Life happens. We'll pick this back up tomorrow — no need to make up"
          " for it today."
      )

    st.session_state.fail_response = msg
    st.session_state.streak = 0

  if st.session_state.fail_response:
    st.info(st.session_state.fail_response)
    if st.button("Continue to tomorrow"):
      st.session_state.plan = None
      st.session_state.negotiation_turns = 0
      st.session_state.negotiation_messages = []
      st.session_state.fail_response = None
      st.session_state.stage = "daily_plan"
      st.rerun()



