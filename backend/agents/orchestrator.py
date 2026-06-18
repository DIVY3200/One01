"""
One01 Multi-Agent Orchestrator
Council of Agents (Powered by Google Gemini 1.5 Flash):
  - Professor Agent: curriculum mapping, outline generation
  - Tutor Agent: persona-based teaching, explanations
  - Examiner Agent: quiz generation, gap analysis
  - Scribe Agent: note generation, progress updates
"""
import os
import re
import json
import asyncio
import traceback
from typing import AsyncGenerator, Optional

from utils.config import settings

# ─── Gemini Setup ─────────────────────────────────────────────────
_gemini_model = None

def _get_gemini_model():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    gemini_key = os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY
    if not gemini_key or gemini_key == "your-gemini-api-key-here":
        return None
    import google.generativeai as genai
    genai.configure(api_key=gemini_key)
    _gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    return _gemini_model

def _sanitize_json_response(raw: str) -> str:
    """Strip markdown fences, conversational preamble, and extract raw JSON."""
    if not raw:
        return raw
    # Remove ```json ... ``` or ``` ... ``` wrappers
    cleaned = re.sub(r'^\s*```(?:json)?\s*', '', raw.strip())
    cleaned = re.sub(r'\s*```\s*$', '', cleaned)
    # If the LLM added conversational text before the JSON, extract the JSON object/array
    json_match = re.search(r'(\{[\s\S]*\})', cleaned)
    if json_match:
        return json_match.group(1)
    json_arr_match = re.search(r'(\[[\s\S]*\])', cleaned)
    if json_arr_match:
        return json_arr_match.group(1)
    return cleaned


async def _gemini_generate(prompt: str, json_mode: bool = False, timeout: int = 90, temperature: float = 1.0) -> str:
    """Call Gemini and return raw text. Returns None if no key or on timeout."""
    model = _get_gemini_model()
    if model is None:
        return None
    import google.generativeai as genai
    config = genai.types.GenerationConfig(temperature=temperature)
    if json_mode:
        config.response_mime_type = "application/json"
    try:
        response = await asyncio.wait_for(
            model.generate_content_async(prompt, generation_config=config),
            timeout=timeout,
        )
        return response.text
    except asyncio.TimeoutError:
        print(f"[TIMEOUT] Gemini call timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"[ERROR] Gemini generation failed: {e}")
        traceback.print_exc()
        return None


from agents.persona_manager import PersonaManager

def build_persona_context(
    teaching_style: str,
    ai_name: str,
    ai_gender: str,
    nickname: str,
    subject: str,
    purpose: str,
    level: str,
    weak_concepts: list = None,
) -> str:
    return PersonaManager.get_system_prompt(
        persona_type=teaching_style,
        subject=subject,
        topic=purpose, # using purpose as topic context
        user_name=nickname,
        ai_name=ai_name,
        ai_gender=ai_gender,
        purpose=purpose,
        level=level,
        weak_concepts=weak_concepts
    )


# ─── Professor Agent ──────────────────────────────────────────────
async def professor_generate_outline(
    subject: str,
    purpose: str,
    level: str,
    nickname: str,
    ai_name: str,
    base_context: dict = None,
) -> dict:
    """Generate a structured curriculum outline using Gemini."""
    base_ctx_str = f"BASE CONTEXT: Avoid rewriting this similar curriculum completely. Reference it structurally but adapt to '{subject}':\n{base_context}" if base_context else ""
    prompt = f"""You are a Senior Academic Curriculum Designer at a top-tier University (like IIT, MIT, or Stanford).
Your task is to implement a Dynamic Knowledge-Graph approach to outline generation.
Topic: {subject}
Purpose/Goal: {purpose} | Student Level: {level} (Assume M.Tech/Expert Level)
Student Name: {nickname}
{base_ctx_str}

CRITICAL INSTRUCTIONS:
1. RAG-STYLE BRAINSTORMING & VALIDATION: Before deciding on topics, brainstorm the key technical milestones of the specific subject. Then ask yourself: "Could this outline apply to any other subject?" If "Yes", rewrite it to be fundamentally specific to '{subject}'. Write this monologue in the `_internal_brainstorming` JSON field.
2. ZERO-TEMPLATE POLICY: You are strictly forbidden from using generic headers like "Setting Up the Environment", "Optimization & Performance", or "Core Mechanics". Every single header must be highly specific to {subject}.
   - BAD: "Machine Learning: Core Mechanics"
   - GOOD: "Supervised Learning: Loss Functions, Gradient Descent Optimization, and Overfitting"
3. SYLLABUS EMULATION: Simulate a rigorous M.Tech syllabus.
4. DEEP HIERARCHY: You MUST provide EXACTLY 12 main topics. Each main topic must have EXACTLY 5 highly specific, advanced sub-topics. (They act as a hidden list for progress tracking, but you must map them properly).
5. EXPERT TONE: Use advanced terminology (e.g., use "Backpropagation Architectures" instead of "How it works").

CRITICAL: Respond ONLY with a raw JSON object. Do not include ANY conversational text, markdown code blocks, or explanations outside the JSON.
Return ONLY valid JSON with this exact structure:
{{
  "_internal_brainstorming": "Detailed brainstorming, milestones extraction, and validation check here...",
  "subject": "{subject}",
  "total_topics": 12,
  "estimated_hours": 36,
  "topics": [
    {{
      "index": 0,
      "title": "Specific Advanced Topic Title",
      "subtopics": ["1.1 Specific Sub-point A", "1.2 Specific Sub-point B", "1.3 Specific Sub-point C", "1.4 Specific Sub-point D", "1.5 Specific Sub-point E"],
      "estimated_minutes": 180,
      "difficulty": "hard"
    }}
  ]
}}"""

    # Retry logic: attempt up to 3 times if JSON parsing fails
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        current_prompt = prompt
        if attempt > 0:
            # On retries, prepend a stricter instruction
            current_prompt = (
                f"SYSTEM: Your previous response was not valid JSON. "
                f"Error was: {last_error}. "
                f"You MUST respond with ONLY a raw JSON object. No markdown, no commentary, no code fences.\n\n"
                + prompt
            )
            print(f"[RETRY {attempt}/{max_retries}] Retrying outline generation...")

        result = await _gemini_generate(current_prompt, json_mode=True, timeout=120)
        if result:
            try:
                sanitized = _sanitize_json_response(result)
                parsed = json.loads(sanitized)
                # Validate minimum structure
                if "topics" in parsed and isinstance(parsed["topics"], list) and len(parsed["topics"]) > 0:
                    return parsed
                else:
                    last_error = "JSON parsed but missing 'topics' array or it was empty"
                    print(f"[VALIDATION] {last_error}")
            except json.JSONDecodeError as e:
                last_error = str(e)
                print(f"[JSON ERROR attempt {attempt+1}] {e}")
                print(f"[RAW RESPONSE] {result[:500]}...")
        else:
            last_error = "No response from LLM (timeout or no API key)"
            print(f"[LLM] {last_error}")
            break  # Don't retry if the LLM itself is unavailable

    # MOCK FALLBACK (Dynamic to avoid fixed generic templates)
    print("Using MOCK FALLBACK for Professor Agent")
    await asyncio.sleep(0.5)
    
    mock_topics = []
    # Dynamic mock titles simulating M.Tech level syllabus
    base_titles = [
        f"Theoretical Foundations of {subject}",
        f"Advanced Topologies in {subject}",
        f"Algorithmic Complexity & {subject} Mechanics",
        f"State Architecture & Probabilistic Models",
        f"Primary Workflows: A Matrix Approach",
        f"Stochastic Control Structures",
        f"Gradient Optimization & High-Dimensional Scaling",
        f"Ecosystem Tooling & Compiler Optimization",
        f"Distributed Integration Strategies",
        f"Cryptographic Security & Best Practices",
        f"Automated Testing & Heuristics Evaluation",
        f"Real-World Production Deployment & Telemetry"
    ]
    
    for i in range(12):
        diff = "medium" if i < 4 else "hard"
        mock_topics.append({
            "index": i,
            "title": base_titles[i],
            "subtopics": [
                f"{base_titles[i].split(' ')[0]} Methodology", 
                f"Advanced {subject} Implementation", 
                "Mathematical Derivation",
                "Case Study Analysis",
                "Review & Practical Assessment"
            ],
            "estimated_minutes": 90 + (i * 15),
            "difficulty": diff
        })

    return {
        "subject": subject,
        "total_topics": 12,
        "estimated_hours": 40,
        "topics": mock_topics
    }


# ─── Tutor Agent ──────────────────────────────────────────────────

# Different structural templates so the mock never feels repetitive
_MOCK_STRUCTURES = [
    # Structure 0: Story-driven
    lambda title, subject, prev, nxt: f"""# {title}

## 🌍 Why This Matters

Let me paint a picture for you. Imagine you're a researcher working on cutting-edge {subject} problems. The first tool you'd reach for? **{title}**. Here's why it's the backbone of everything that follows.

{f"Building on what we learned about *{prev}*, we're now ready to take the next step." if prev else "This is where our journey begins — and it's going to be an exciting ride!"}

## 📖 What is {title}?

At its heart, **{title}** is about understanding the rules that govern {subject}. Think of it as learning the grammar of a new language — once you get the rules, you can form any sentence.

### The Three Pillars:
1. **Conceptual Foundation** — The "what" and "why" behind {title}
2. **Methodology** — The "how" — techniques and approaches practitioners use
3. **Application** — Where rubber meets the road — real outcomes

## 🔬 Going Deeper

Here's where it gets really interesting:

- **Principle 1**: Every system in {subject} follows predictable patterns once you understand {title}
- **Principle 2**: The relationship between theory and practice is bidirectional — each informs the other
- **Principle 3**: Mastering this concept unlocks the ability to critically evaluate claims and evidence

### A Real-World Scenario
Consider a professional solving a complex problem in {subject}. They wouldn't just guess — they'd apply {title} systematically. First, they'd define the problem. Then, they'd use established frameworks to analyze it. Finally, they'd validate their solution against known benchmarks.

## 🧠 Think About This

Here's something most textbooks won't tell you: the real power of {title} isn't memorizing facts — it's developing intuition. When you truly understand this concept, you start *seeing* patterns everywhere.

## 📌 What You Should Remember

- **Core Insight**: {title} provides the framework for systematic thinking in {subject}
- **Practical Value**: This knowledge is immediately applicable in academic and professional settings
- **Connection**: Everything we cover next builds directly on these ideas

{f"## 🔗 Coming Up: {nxt}" if nxt else "## 🎯 You've Reached the Final Topic!"}

{f"Next, we'll explore **{nxt}**, which takes these foundations and pushes them further." if nxt else "With this, you've covered all the major concepts in this subject. Well done!"}

---

Got any questions, or are you ready to move forward? 💬
""",
    # Structure 1: Question-driven / Socratic
    lambda title, subject, prev, nxt: f"""# {title}

## ❓ Let's Start With a Question

Here's something to think about: *What would happen if we didn't have {title} in {subject}?*

{f"Remember how we explored *{prev}*? That gave us the foundation. Now **{title}** shows us what to *do* with that foundation." if prev else "Every expert in {subject} started exactly where you are now. Let's build something solid."}

The answer reveals just how foundational this concept really is. Without it, most of {subject} would be guesswork. Let's unpack why.

## 🏗️ Building the Framework

### Step 1: The Big Picture
{title} sits at the intersection of theory and practice in {subject}. It's not just an abstract idea — it's a working tool.

### Step 2: The Mechanics
How does it actually work? Let's break it down:

| Component | Role | Why It Matters |
|-----------|------|----------------|
| **Theory** | Provides the rules | Without rules, no structure |
| **Method** | Turns theory into action | Bridges knowing and doing |
| **Evidence** | Validates outcomes | Keeps us honest |

### Step 3: Applying the Knowledge
When practitioners use {title}, they follow a cycle:
1. **Observe** → What's happening?
2. **Hypothesize** → Why might it be happening?
3. **Test** → Does the evidence support our idea?
4. **Refine** → What did we learn?

## 💡 Here's the Insight Most People Miss

The real power of {title} isn't in the individual steps — it's in the *iteration*. Each cycle makes your understanding sharper and your intuition stronger.

## 🎯 Key Takeaways

1. **{title} is a process**, not just a concept — it's something you *do*
2. **Iteration is key** — you get better with each cycle of application
3. **This connects everything** — from fundamental principles to advanced applications in {subject}
4. **Critical thinking** — this is where you learn to question, not just accept

{f"## ➡️ What's Next: {nxt}" if nxt else "## 🏆 Final Topic Complete!"}

{f"In our next topic, **{nxt}**, we'll see how these principles scale up to handle more complex challenges." if nxt else "You've now covered every topic in this subject. Take a moment to appreciate how far you've come!"}

---

Any questions before we continue? I'm here to help. 🤝
""",
    # Structure 2: Analogy-heavy / Visual
    lambda title, subject, prev, nxt: f"""# {title}

## 🎨 The Big Analogy

Think of {subject} as an orchestra. If previous concepts were the individual instruments, then **{title}** is the conductor — it brings everything together into a coherent performance.

{f"We've already tuned our instruments with *{prev}*. Now it's time to learn how they play together." if prev else "Welcome to the stage! Let's start making some music."}

## 🧩 Piece by Piece

### The Foundation Layer
Every tall building needs a strong base. In {title}, that base is:
- **Core Vocabulary** — the precise language professionals use
- **Fundamental Relationships** — how different elements connect
- **Boundary Conditions** — knowing what works and what doesn't

### The Structure Layer
Once the foundation is solid, we build upward:

> *"The best way to understand a complex system is to understand its components and their relationships."*

In {title}, the key relationships are:
1. **Cause and Effect** — When X changes, Y responds in predictable ways
2. **Feedback Loops** — Output becomes input, creating dynamic systems
3. **Emergence** — Simple rules creating complex behaviors

### The Application Layer
This is where knowledge transforms into skill:

**Scenario**: You're faced with a real {subject} problem. Using {title}, you would:
- First, identify which principles apply
- Then, select the appropriate methodology
- Finally, execute and evaluate your approach

## 🔑 Critical Distinctions

Many students confuse similar concepts at this stage. Here's what makes {title} unique:

| What It IS | What It ISN'T |
|------------|---------------|
| A systematic approach | Random guessing |
| Evidence-based | Opinion-based |
| Iterative and adaptive | Fixed and rigid |

## 📝 Summary

- **One sentence**: {title} is the organizing principle that connects theory to practice in {subject}
- **One takeaway**: Understanding this makes everything else in {subject} click into place
- **One action**: Try to identify {title} principles in everyday situations — you'll be surprised how often they appear

{f"## 🚀 Up Next: {nxt}" if nxt else "## 🎓 That's a Wrap!"}

{f"Ready to level up? **{nxt}** will challenge you to apply everything we've covered so far." if nxt else "Congratulations on completing all the topics! You now have a solid understanding of {subject}."}

---

Questions? Confusions? Lightbulb moments? Share them! 💡
""",
]


async def tutor_explain_topic(
    topic_title: str,
    subject: str,
    previous_context: str,
    persona_context: str,
    topic_position: dict = None,
) -> AsyncGenerator[str, None]:
    """Stream a topic explanation with position-aware, non-repetitive content."""
    tp = topic_position or {}
    current_idx = tp.get("current_index", 0)
    total = tp.get("total_topics", 1)
    subtopics = topic_position.get("subtopics", [])
    current_sub_idx = topic_position.get("current_subtopic_index", 0)
    current_subtopic = topic_position.get("current_subtopic", topic_title)
    prev_title = tp.get("prev_title")
    next_title = tp.get("next_title")

    position_context = f"""
TOPIC POSITION:
- You are teaching Main Topic {current_idx + 1} of {total}: "{topic_title}"
- CURRENT SUB-TOPIC: "{current_subtopic}" (Sub-section {current_sub_idx + 1} of {max(1, len(subtopics))})
- All sub-topics in this chapter: {", ".join(subtopics) if subtopics else "N/A"}

CRITICAL RULES:
1. You are a high-skilled, patient tutor. Never summarize a whole chapter in one go.
2. Teach ONE specific sub-concept at a time. Right now, your ONLY focus is: "{current_subtopic}".
3. After explaining this sub-concept, you MUST verify the student's understanding with a logical challenge (a probing, conceptual question).
4. THE GATEKEEPER: You are FORBIDDEN from mentioning "Coming Up", the next chapter, or moving to the next main topic until ALL 5 sub-topics are mastered. Do NOT offer to move on until then.
5. Do NOT say "Ready to move to the next topic?". Instead, ask your probing question and explicitly wait for their response.
6. UNIQUENESS: Do NOT repeat a question with a hash that appears in the conversation history.
"""

    prompt = f"""{persona_context}

{position_context}

Previous context: {previous_context or "This is the first topic — no prior context."}

SYSTEM INSTRUCTION: You are a world-class professor. Stop using 'cookie-cutter' responses. Your goal is mastery, not just completion. If a student asks for depth, prioritize Content Depth over Structural Consistency. 
Give them raw technical insight, research-grade definitions, and complex logical flows.

CRITICAL REQUIREMENTS:
- STATE-DEPENDENT PROMPTING (TURN 1): This is Turn 1. You MUST provide a "Broad Overview" of the concept. Keep it high-level but rigorous.
1. BAN "ANALOGY FIRST": Explicitly forbidden to start your explanation with an analogy. Avoid "painting pictures" or "car analogies" unless specifically asked by the user for a simple explanation, or if clarifying extreme confusion flagged as "too dense".
2. VARIABLE DEPTH LOGIC: Move from General Principles to Specific Mechanisms. If the user requests depth ("go deeper"), you MUST generate a detailed breakdown of the mathematical or architectural foundations of that specific sub-topic.
3. DYNAMIC RESPONSE STRUCTURE: Under NO circumstances should you use fixed headers like "The Three Pillars", "The Short Answer", or "Quick Check". Force adaptive headers specific to the sub-topic being discussed.
4. ADAPTIVE PERSONA: Ensure the persona (especially if "Philosopher" or "Mentor") is strongly maintained through the deep dive. Avoid generic headers.
5. INTERACTIVE ASSESSMENT LOOP (DYNAMIC & CHALLENGING): At the absolute end of your explanation, you MUST generate an interactive multiple-choice question (MCQ) formatted as a JSON block inside a ```quiz codeblock.
CONSTRAINT: Generate a question that tests a specific technical detail or logical edge-case from the exact explanation text you just provided above. Avoid generic definitions. Make it challenging for an M.Tech student.
STATE MANAGEMENT: You must include a unique `content_hash` in the JSON to track the question. Do not ask the same question twice. Example:
```quiz
{{
  "question": "Specific question testing a logical edge-case from the text above?",
  "options": ["A", "B", "C", "D"],
  "correctIndex": 0,
  "content_hash": "unique_hash_string"
}}
```

Teach the current sub-topic ("{current_subtopic}") rigorously (Broad Overview):
- Provide high-level technical breakdown or mathematical foundation.
- Cite 1-2 advanced specific mechanisms or case studies.
- End with the ```quiz codeblock to verify mastery based on the text just generated. Wait for the user to respond before proceeding.

Do NOT use cliché phrases. Emphasize Content Depth over Structural Consistency."""

    result = await _gemini_generate(prompt)
    if result:
        words = result.split(' ')
        chunk = ""
        for i, word in enumerate(words):
            chunk += word + " "
            if len(chunk) > 30 or i == len(words) - 1:
                yield chunk
                chunk = ""
                await asyncio.sleep(0.02)
    else:
        # MOCK FALLBACK — pick a different structure per topic index
        print(f"Using MOCK FALLBACK for Tutor Agent (explain) — topic index {current_idx}")
        struct_idx = current_idx % len(_MOCK_STRUCTURES)
        mock_explanation = _MOCK_STRUCTURES[struct_idx](topic_title, subject, prev_title, next_title)
        mock_explanation += f"\n\n```quiz\n{{\n  \"question\": \"What is the primary role of {current_subtopic} in {subject}?\",\n  \"options\": [\"To act as a core component\", \"It is mostly unused\", \"It provides advanced capabilities\", \"All of the above\"],\n  \"correctIndex\": 0,\n  \"content_hash\": \"mock_hash_{current_idx}_{current_sub_idx}\"\n}}\n```"

        lines = mock_explanation.split('\n')
        for line in lines:
            yield line + "\n"
            await asyncio.sleep(0.03)


async def tutor_handle_doubt(
    doubt: str,
    topic_title: str,
    explanation_so_far: str,
    persona_context: str,
    conversation_history: list,
    topic_position: dict = None,
) -> AsyncGenerator[str, None]:
    """Handle a student's doubt with adaptive, non-repetitive teaching."""
    tp = topic_position or {}
    current_idx = tp.get("current_index", 0)
    next_title = tp.get("next_title")

    current_subtopic = topic_position.get("current_subtopic", topic_title)
    subtopics = topic_position.get("subtopics", [])
    current_sub_idx = topic_position.get("current_subtopic_index", 0)

    history_text = ""
    assistant_count = 0
    for msg in conversation_history:
        role = msg.get("role", "user")
        if role == "assistant":
            assistant_count += 1
        content = msg.get("content", "")[:500]
        history_text += f"\n{role}: {content}\n"
    
    turn_counter = assistant_count + 1

    prompt = f"""{persona_context}

CURRENT MAIN TOPIC: "{topic_title}" 
CURRENT SUB-TOPIC: "{current_subtopic}" (Sub-section {current_sub_idx + 1} of {max(1, len(subtopics))})

Recent conversation (Turn {turn_counter}):
{history_text}

The student responds: "{doubt}"

SYSTEM INSTRUCTION: You are a world-class professor. Stop using 'cookie-cutter' responses. Your goal is mastery, not completion. If a student asks for depth, prioritize Content Depth over Structural Consistency.
Give them raw technical insight, research-grade definitions, and complex logical flows.

CRITICAL REQUIREMENTS:
- STATE-DEPENDENT PROMPTING (TURN COUNTER = {turn_counter}):
   - If this is Turn 2 and the user asks for 'more', you MUST focus entirely on Technical Architecture.
   - If this is Turn 3+ and the user asks for 'deep', you MUST focus entirely on Mathematical Derivations or Code implementation.
1. BAN "ANALOGY FIRST": Explicitly forbidden to start your explanation with an analogy. Avoid "painting pictures" or "car analogies" unless specifically asked by the user for a simple explanation, or if clarifying extreme confusion flagged as "too dense".
2. VARIABLE DEPTH LOGIC: Move from General Principles to Specific Mechanisms. If the user says "explain in deep", "more", or "go deeper", you MUST generate a detailed breakdown of the mathematical or architectural foundations of that specific sub-topic. Include technical specifications, mathematical derivations (LaTeX), or architectural diagrams.
3. DYNAMIC RESPONSE STRUCTURE: Under NO circumstances should you use fixed headers like "The Three Pillars" or "The Short Answer". Force adaptive headers specific to the sub-topic being discussed.
4. CONTEXT-AWARE CONTINUITY: You MUST look at the previous three turns of the conversation. If the structure of the current draft response matches the structure of the last response, you MUST rewrite it with a completely different format.
5. ADAPTIVE PERSONA: Ensure the persona (especially if "Philosopher" or "Mentor") is strongly maintained through the deep dive.
6. INTERACTIVE ASSESSMENT LOOP (DYNAMIC & CHALLENGING): At the absolute end of your explanation, if you have taught a new sub-concept, you MUST generate an interactive multiple-choice question (MCQ) formatted as a JSON block inside a ```quiz codeblock.
CONSTRAINT: The question must test a specific technical detail or logical edge-case from the text above. Avoid generic definitions. Make it challenging for an M.Tech student. Include a unique `content_hash` to ensure the same question is never asked twice in a row.

RULES:
- Query vs. Navigation Logic: If the user asks a question, stay on the current concept and provide a deep-dive solution.
- Evaluate Quiz Response: If the user is responding to the previous quiz question correctly, validate them and state they are ready to move to the next sub-concept.
- REMEDIAL TEACHING LOOP: If the user is responding to the previous quiz question incorrectly, you MUST trigger a "Remedial Explanation" mode. You MUST explicitly say: "I see why you picked that, but here is the core theory you might be missing...". Explain the underlying mechanism of why the chosen answer was wrong BEFORE asking a new, different question.
- Do NOT offer to move to the next 'Main Outline' topic until all sub-concepts are mastered.

End naturally, then output the ```quiz codeblock if testing a concept. Use markdown."""

    result = await _gemini_generate(prompt)
    if result:
        words = result.split(' ')
        chunk = ""
        for i, word in enumerate(words):
            chunk += word + " "
            if len(chunk) > 30 or i == len(words) - 1:
                yield chunk
                chunk = ""
                await asyncio.sleep(0.02)
    else:
        # MOCK FALLBACK — varied responses
        print("Using MOCK FALLBACK for Tutor Agent (doubt)")
        # Pick a varied response style based on conversation length
        turn_count = len(conversation_history)
        
        responses = [
            f"""That's a thoughtful question about **{topic_title}**.

Let me approach it from a different angle. When you say *"{doubt}"*, the core issue usually comes down to understanding the underlying mechanism.

Here's how to think about it:

**The Key Principle:**
In {topic_title}, every action follows a logical chain. Think of it like dominoes — once you understand what triggers the first one, the rest follows naturally.

**Concrete Example:**
Imagine you're working with real data in {topic_title}. The first step is always to identify your variables. Then you establish relationships. Finally, you test whether those relationships hold under different conditions.

**Quick Check:**
- Can you identify the main variables in this concept?
- Do you see how they relate to each other?
- What happens when you change one variable?

If you can answer those three questions, you've got a solid grasp. Want to explore any of these further, or shall we test your understanding with a quiz? 🧪
""",
            f"""Interesting — let me unpack *"{doubt}"* specifically for **{topic_title}**.

### The Short Answer
The confusion often comes from mixing up two related but distinct ideas. Let me separate them clearly.

### The Detailed Breakdown

**Idea A**: The theoretical foundation — this is the "why"
**Idea B**: The practical application — this is the "how"

Most students initially blend these together, but once you see the boundary, everything becomes clearer.

### An Analogy That Works
Think of it like the difference between knowing *why* a car engine works (thermodynamics, combustion) and knowing *how* to drive. Both are valuable, but they're different skills. {topic_title} requires both.

### What To Focus On
For your current level, focus on building strong intuition about *why* things work the way they do. The *how* will come naturally after that.

Need me to go deeper on any part of this, or ready for the next challenge? 💪
""",
            f"""Let me reframe **{topic_title}** based on your question: *"{doubt}"*

Rather than repeating what we've covered, let me show you a completely new perspective.

### The "Reverse Engineering" Approach
Instead of building up from principles, let's start from the end result and work backward:

1. **The Outcome** — What does successful application of {topic_title} look like?
2. **The Process** — What steps lead to that outcome?
3. **The Foundation** — What knowledge makes those steps possible?

When you see it in reverse, the "why" behind each piece becomes immediately obvious.

### Common Confusion Points
Students at this stage typically struggle with:
- **Terminology overlap** — Different terms that mean similar things
- **Scope boundaries** — Knowing where one concept ends and another begins
- **Application context** — When to apply which technique

### My Recommendation
Try to explain {topic_title} to someone else in your own words. If you can do that, you truly understand it. If you get stuck, that's exactly where your gap is.

What aspect would you like to explore further? Or feel confident enough for a quiz? 📝
""",
        ]
        
        mock_response = responses[turn_count % len(responses)]
        mock_response += f"\n\n```quiz\n{{\n  \"question\": \"Which of the following describes {current_subtopic}?\",\n  \"options\": [\"A standard framework\", \"A deprecated tool\", \"A foundational theory\", \"It depends on implementation\"],\n  \"correctIndex\": 2,\n  \"content_hash\": \"mock_hash_doubt_{turn_count}_{current_sub_idx}\"\n}}\n```"
        lines = mock_response.split('\n')
        for line in lines:
            yield line + "\n"
            await asyncio.sleep(0.03)


# ─── Examiner Agent ───────────────────────────────────────────────
async def examiner_generate_quiz(
    topic_title: str,
    subject: str,
    level: str,
    quiz_type: str,
    explanation_content: str,
    weak_concepts: list = None,
    subtopics: list = None,
    past_questions: list = None,
    count: int = 5,
) -> dict:
    """Generate quiz questions for a topic."""
    weak_str = ", ".join(weak_concepts) if weak_concepts else "none"
    subtopics_str = ", ".join(subtopics) if subtopics else "none"
    past_qs_str = "\\n".join(past_questions) if past_questions else "none"

    type_instructions = {
        "mcq": f"""Generate EXACTLY {count} multiple choice questions. Focus on conceptual definitions and logical relationships.
Each question: {{"question": "...", "options": ["A)...", "B)...", "C)...", "D)..."], "correct": "A", "explanation": "...", "concept": "..."}}""",
        "theory": f"""Generate EXACTLY {count} theory/logical questions. Generate complex scenario-based questions that test 'Why' and 'How' rather than 'What'. Use edge cases.
Each question: {{"question": "...", "expected_answer": "...", "key_points": ["..."], "concept": "...", "explanation": "..."}}""",
        "numerical": f"""Generate EXACTLY {count} numerical/calculation problems. Generate word problems requiring mathematical calculation. Include the step-by-step derivation in the hidden 'solution_steps' field.
Each question: {{"question": "...", "solution_steps": ["step1", "step2"], "final_answer": "...", "concept": "...", "explanation": "..."}}""",
    }

    prompt = f"""You are the Examiner Agent for One01.
Generate {quiz_type.upper()} questions for topic: "{topic_title}"
Subject: {subject} | Level: {level}
Student's weak concepts to emphasize: {weak_str}
Specific Sub-topics: {subtopics_str}

CRITICAL CONSTRAINTS:
1. You are strictly forbidden from generating general knowledge questions. You must only use information from the provided chapter text below.
2. DO NOT repeat the following previously asked questions:
{past_qs_str}

CHAPTER_CONTENT:
---
{explanation_content[:2000]}
---

{type_instructions.get(quiz_type, type_instructions["mcq"])}

Return ONLY valid JSON array containing the questions, or a JSON object with 'questions' array:
{{
  "quiz_type": "{quiz_type}",
  "topic": "{topic_title}",
  "questions": [<question objects>]
}}"""

    result = await _gemini_generate(prompt, json_mode=True, temperature=0.8)
    if result:
        try:
            parsed = json.loads(_sanitize_json_response(result))
            # JSON Repair
            if isinstance(parsed, list):
                return {
                    "quiz_type": quiz_type,
                    "topic": topic_title,
                    "questions": parsed
                }
            if "questions" in parsed:
                return parsed
        except Exception as e:
            print(f"Error parsing Gemini quiz: {e}")
            print(f"[RAW] {result[:300]}")

    # MOCK FALLBACK
    print("Using MOCK FALLBACK for Examiner Agent")
    await asyncio.sleep(0.5)
    return {
        "quiz_type": quiz_type,
        "topic": topic_title,
        "questions": [
            {
                "question": f"What is the primary purpose of {topic_title} in {subject}?",
                "options": [
                    f"A) To provide a theoretical framework for {subject}",
                    f"B) To enable practical applications in industry",
                    f"C) To serve as a foundation for advanced research",
                    f"D) All of the above"
                ],
                "correct": "D",
                "explanation": f"{topic_title} serves multiple purposes in {subject}, combining theory and practice.",
                "concept": topic_title
            },
            {
                "question": f"Which of the following best describes a key principle of {topic_title}?",
                "options": [
                    "A) Linear progression of concepts",
                    "B) Iterative learning and refinement",
                    "C) Memorization of formulas",
                    "D) Independent study only"
                ],
                "correct": "B",
                "explanation": "Iterative learning allows for deeper understanding through repeated application.",
                "concept": "Learning Methodology"
            },
            {
                "question": f"In the context of {subject}, what role does {topic_title} play?",
                "options": [
                    "A) A minor supplementary topic",
                    "B) A core foundational concept",
                    "C) An advanced specialization only",
                    "D) A historical reference point"
                ],
                "correct": "B",
                "explanation": f"{topic_title} is fundamental to understanding {subject}.",
                "concept": topic_title
            },
            {
                "question": f"How does understanding {topic_title} benefit practical applications?",
                "options": [
                    "A) It has no practical applications",
                    "B) It only benefits research",
                    "C) It enables better problem-solving and decision-making",
                    "D) It is only useful for exams"
                ],
                "correct": "C",
                "explanation": "Understanding core concepts directly improves practical problem-solving skills.",
                "concept": "Practical Application"
            },
            {
                "question": f"What is the recommended approach to mastering {topic_title}?",
                "options": [
                    "A) Reading only",
                    "B) Practice with real examples and iterative review",
                    "C) Watching videos exclusively",
                    "D) Skipping to advanced topics"
                ],
                "correct": "B",
                "explanation": "Active practice with examples and iterative review leads to the best learning outcomes.",
                "concept": "Study Strategy"
            }
        ]
    }


async def examiner_analyze_answers(
    quiz_type: str,
    questions: list,
    user_answers: list,
    topic_title: str,
) -> dict:
    """Analyze quiz answers and identify knowledge gaps."""
    qa_pairs = []
    for i, (q, a) in enumerate(zip(questions, user_answers)):
        qa_pairs.append(f"Q{i+1}: {q.get('question', '')}\nUser Answer: {a}\nCorrect: {q.get('correct', q.get('final_answer', q.get('expected_answer', 'N/A')))}")

    prompt = f"""You are the Examiner Agent analyzing student performance.
Topic: {topic_title} | Quiz Type: {quiz_type}

Questions and Answers:
{chr(10).join(qa_pairs)}

Analyze and return ONLY valid JSON:
{{
  "score": <0-100 float>,
  "correct_count": <int>,
  "total_count": <int>,
  "wrong_concepts": ["concept1", "concept2"],
  "strong_concepts": ["concept3"],
  "detailed_feedback": "...",
  "teaching_suggestion": "...",
  "per_question": [
    {{"question_index": 0, "is_correct": true, "feedback": "..."}}
  ]
}}"""

    result = await _gemini_generate(prompt, json_mode=True)
    if result:
        try:
            return json.loads(_sanitize_json_response(result))
        except Exception as e:
            print(f"Error parsing Gemini analysis: {e}")
            print(f"[RAW] {result[:300]}")

    # MOCK FALLBACK
    print("Using MOCK FALLBACK for Examiner Analyze")
    correct_count = 0
    per_question = []
    for i, (q, a) in enumerate(zip(questions, user_answers)):
        correct = q.get("correct", "")
        is_correct = str(a).strip().upper() == str(correct).strip().upper()
        if is_correct:
            correct_count += 1
        per_question.append({
            "question_index": i,
            "is_correct": is_correct,
            "feedback": "Correct! Well done." if is_correct else f"The correct answer was {correct}."
        })

    total = len(questions)
    score = (correct_count / total * 100) if total > 0 else 0

    return {
        "score": score,
        "correct_count": correct_count,
        "total_count": total,
        "wrong_concepts": [topic_title] if correct_count < total else [],
        "strong_concepts": [topic_title] if correct_count == total else [],
        "detailed_feedback": f"You scored {correct_count}/{total}. {'Great job!' if score >= 70 else 'Keep practicing!'}",
        "teaching_suggestion": "Review the topic explanation and focus on the areas you missed." if score < 70 else "You have a strong understanding. Consider moving to the next topic.",
        "per_question": per_question
    }


# ─── Scribe Agent ─────────────────────────────────────────────────
async def scribe_generate_notes(
    topic_title: str,
    subject: str,
    explanation_content: str,
    wrong_concepts: list = None,
    existing_notes: str = "",
) -> str:
    """Generate/update markdown notes for a topic."""
    wrong_str = ", ".join(wrong_concepts) if wrong_concepts else "none"

    prompt = f"""You are the Scribe Agent for One01.
Generate comprehensive markdown notes for: "{topic_title}" ({subject})

Based on explanation:
---
{explanation_content[:2000]}
---

Student struggled with: {wrong_str}

Generate notes with:
# {topic_title}

## 📌 Key Definitions
[important terms with concise definitions]

## 🔑 Core Concepts  
[main ideas as clear bullet points]

## 📐 Formulas & Equations
[any mathematical formulas in LaTeX: $formula$]

## 💡 Key Principles
[fundamental rules or laws]

## ⚠️ Common Mistakes to Avoid
[include mistakes related to: {wrong_str}]

## 🔗 Quick Summary
[3-5 sentence summary]

---
*Notes generated by One01 Scribe Agent*

Return ONLY the markdown content."""

    result = await _gemini_generate(prompt)
    if result:
        return result

    # MOCK FALLBACK
    print("Using MOCK FALLBACK for Scribe Agent")
    return f"""# {topic_title}

## 📌 Key Definitions

- **{topic_title}**: A fundamental concept in {subject} that encompasses the core principles and methodologies used in this field.
- **Core Methodology**: The systematic approach used to study and apply {topic_title} concepts.
- **Application Framework**: The structured way in which {topic_title} principles are put into practice.

## 🔑 Core Concepts  

- {topic_title} provides the foundational knowledge needed for {subject}
- Understanding the theoretical basis helps in practical applications
- Key relationships between concepts form the backbone of this topic
- Real-world examples demonstrate the importance and relevance

## 📐 Formulas & Equations

- Core relationship: The fundamental equation linking key variables
- Application formula: Used for practical problem-solving
- Analysis framework: For evaluating results and outcomes

## 💡 Key Principles

1. **Foundation First**: Build a strong theoretical understanding before moving to applications
2. **Iterative Learning**: Revisit and refine understanding through practice
3. **Connect the Dots**: Link new concepts to previously learned material
4. **Apply Knowledge**: Use real-world examples to solidify understanding

## ⚠️ Common Mistakes to Avoid

- Skipping foundational concepts and jumping to advanced topics
- Memorizing without understanding the underlying principles
- Not practicing with enough examples
- Ignoring the connections between related concepts

## 🔗 Quick Summary

{topic_title} is a core topic in {subject} that establishes fundamental principles and methodologies. Understanding this topic is crucial for progressing to more advanced concepts. The key to mastering this material is combining theoretical knowledge with practical application through examples and exercises.

---
*Notes generated by One01 Scribe Agent*
"""


async def scribe_process_feedback(
    feedback_text: str,
    subject: str,
    ai_name: str,
    teaching_style: str,
    current_style_notes: str = "",
) -> dict:
    """Process user feedback and generate style adjustments."""
    prompt = f"""You are the Scribe Agent processing feedback for teacher {ai_name}.
Subject: {subject} | Current style: {teaching_style}

Student Feedback:
"{feedback_text}"

Analyze this feedback and return ONLY valid JSON:
{{
  "tone_adjustment": "...",
  "pace_adjustment": "...",
  "style_notes": "...",
  "response_to_student": "...",
  "priority_changes": ["change1", "change2"]
}}"""

    result = await _gemini_generate(prompt, json_mode=True)
    if result:
        try:
            return json.loads(_sanitize_json_response(result))
        except Exception as e:
            print(f"Error parsing Gemini feedback: {e}")
            print(f"[RAW] {result[:300]}")

    # MOCK FALLBACK
    print("Using MOCK FALLBACK for Scribe Feedback")
    return {
        "tone_adjustment": "Maintaining current tone with slight adjustments based on feedback.",
        "pace_adjustment": "Adjusting pace to match student comfort level.",
        "style_notes": f"Student provided feedback: {feedback_text[:100]}. Incorporating suggestions.",
        "response_to_student": f"Thank you for your feedback! I'll adjust my teaching approach to better suit your learning style. Your input helps me become a better teacher for you!",
        "priority_changes": [
            "Adjust explanation depth based on feedback",
            "Incorporate more examples as requested"
        ]
    }


# ─── Question Bank Agent ──────────────────────────────────────────
async def generate_question_bank(
    subject: str,
    topic_title: str,
    question_type: str,
    count: int,
    level: str,
) -> dict:
    """Generate question bank on demand."""
    prompt = f"""Generate a question bank for: {topic_title} ({subject})
Type: {question_type} | Level: {level} | Count: {count}

Return ONLY valid JSON:
{{
  "subject": "{subject}",
  "topic": "{topic_title}",
  "type": "{question_type}",
  "questions": [<{count} question objects appropriate for {question_type}>]
}}

For MCQ: {{"question": "...", "options": ["A)...", "B)...", "C)...", "D)..."], "correct": "A", "explanation": "..."}}
For theory: {{"question": "...", "expected_answer": "...", "key_points": ["..."]}}
For numerical: {{"question": "...", "solution_steps": ["..."], "final_answer": "..."}}"""

    result = await _gemini_generate(prompt, json_mode=True)
    if result:
        try:
            return json.loads(_sanitize_json_response(result))
        except Exception as e:
            print(f"Error parsing Gemini question bank: {e}")
            print(f"[RAW] {result[:300]}")

    # MOCK FALLBACK
    print("Using MOCK FALLBACK for Question Bank")
    questions = []
    for i in range(min(count, 5)):
        questions.append({
            "question": f"Question {i+1} about {topic_title} in {subject} ({level} level)",
            "options": [
                f"A) Option A for question {i+1}",
                f"B) Option B for question {i+1}",
                f"C) Option C for question {i+1}",
                f"D) Option D for question {i+1}"
            ],
            "correct": ["A", "B", "C", "D"][i % 4],
            "explanation": f"This tests understanding of key concepts in {topic_title}."
        })

    return {
        "subject": subject,
        "topic": topic_title,
        "type": question_type,
        "questions": questions
    }