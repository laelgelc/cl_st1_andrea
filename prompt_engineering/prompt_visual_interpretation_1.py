import csv

# ==========================================================
# GLOBAL EXOPHORIC CONTEXT — THEORETICAL FRAMEWORK
# ==========================================================
theoretical_context = """
This annotation protocol follows the social semiotic framework of visual grammar.

KEY CONCEPTS

Represented Participants (RPs):
People, objects, animals, or entities depicted in the image that take part in represented visual processes.

Narrative Representation:
Images that depict unfolding actions and events. Participants are connected by vectors formed by bodies, limbs, tools, or gaze, indicating dynamic processes.

Conceptual Representation:
Images that represent participants in terms of class, structure, identity, or symbolic meaning. They convey generalized, more or less stable, and timeless essences rather than actions.

Hybrid Representation:
Images combining narrative action with embedded conceptual meaning.

Vectors:
Directional lines formed by bodies, limbs, tools, or gaze that indicate action, movement, directionality, or relationships between participants.

Eyeline Vectors:
Vectors formed specifically by participants’ gaze, creating visual interaction.

Viewer:
The implied observer positioned by the image’s composition, perspective, and gaze relations.

Interactive Meaning:
The relationship constructed between represented participants and the viewer.

Representational Processes:
The types of visual structures through which meaning is depicted (narrative or conceptual).

This framework guides all AI interpretation and annotation decisions.
"""

print("\n==========================================================")
print("THEORETICAL FRAMEWORK (EXOPHORIC CONTEXT)")
print("==========================================================")
print(theoretical_context)

# ==========================================================
# QUESTIONS FOR ANALYSIS
# ==========================================================
questions = [
    {
        "question": "What is the picture about?",
        "possible_answers": [
            "only action image",
            "only conceptual image (generalized, more or less stable)",
            "action image with embedded conceptual image",
        ],
        "ai_instruction": {
            "only action image": (
                "Classify as narrative representation: participants connected by "
                "vectors formed by bodies, limbs, or tools performing actions."
            ),
            "only conceptual image (generalized, more or less stable)": (
                "Classify as conceptual representation: participants represented "
                "by class, structure, or symbolic meaning; generalized, more or "
                "less stable, expressing a timeless essence."
            ),
            "action image with embedded conceptual image": (
                "Hybrid representation: narrative action with embedded conceptual "
                "meaning. Analyze both process types."
            ),
        },
        "follow_up": None,
    },
    {
        "question": "Who are the represented participants (RPs) in the image?",
        "possible_answers": [
            "only human(s)",
            "only non-human object(s)",
            "human(s) with non-human object(s)",
        ],
        "ai_instruction": {
            "only human(s)": "Human–human relations detected. Analyze social relations.",
            "only non-human object(s)": "Object–object relations detected. Analyze functional relations.",
            "human(s) with non-human object(s)": "Human–object relations detected. Analyze mediated action.",
        },
        "follow_up": None,
    },
    {
        "question": "Are there any vectors in the image that indicate action?",
        "possible_answers": ["yes", "no"],
        "ai_instruction": {
            "yes": "Action vectors present. Identify action processes.",
            "no": "No action vectors. Interpret conceptual/static representation.",
        },
        "follow_up": {
            "question": "If yes, what kind of story does this action tell?",
            "possible_answers": None,
            "ai_instruction": lambda ans: (
                f"Use action description for narrative analysis: {ans}"
            ),
        },
    },
    {
        "question": "Are the human RPs looking at each other, creating eyeline vectors?",
        "possible_answers": ["yes", "no"],
        "ai_instruction": {
            "yes": "Eyeline vectors present. Analyze participant relationships.",
            "no": "No eyeline vectors. Analyze spatial/disconnected composition.",
        },
        "follow_up": {
            "question": "If yes, is the RP looking directly at the viewer?",
            "possible_answers": ["direct gaze", "indirect gaze"],
            "ai_instruction": {
                "direct gaze": (
                    "Direct gaze creates strong viewer engagement. Analyze interactive meaning."
                ),
                "indirect gaze": (
                    "Indirect gaze creates contemplation. Analyze reflective meaning."
                ),
            },
        },
    },
    {
        "question": "If there are no vectors, what is the image trying to convey in social/cultural terms?",
        "possible_answers": [
            "reflection on social norms",
            "representation of cultural values",
            "other (describe)",
        ],
        "ai_instruction": {
            "reflection on social norms": "Analyze image as social commentary.",
            "representation of cultural values": "Analyze image as cultural representation.",
            "other (describe)": "Use description to interpret socio-cultural meaning.",
        },
        "follow_up": {
            "question": "What types of conventional thinking do different objects evoke?",
            "possible_answers": None,
            "ai_instruction": lambda ans: (
                f"Analyze object symbolism and cultural associations: {ans}"
            ),
        },
    },
    {
        "question": "Is the image complex with more than one process embedded?",
        "possible_answers": ["yes", "no"],
        "ai_instruction": {
            "yes": "Multiple processes detected. Analyze representational complexity.",
            "no": "Single process detected. Analyze representational focus.",
        },
        "follow_up": {
            "question": "If yes, how do these embedded processes add to overall meaning?",
            "possible_answers": None,
            "ai_instruction": lambda ans: (
                f"Use explanation to analyze process interaction: {ans}"
            ),
        },
    },
    {
        "question": "Does the image enhance the intent of the overall document/website and its text?",
        "possible_answers": ["yes", "no", "partially"],
        "ai_instruction": {
            "yes": "Image supports communicative intent.",
            "no": "Image does not support communicative intent.",
            "partially": "Image partially supports communicative intent.",
        },
        "follow_up": None,
    },
]

responses = []
ai_instructions = []

# ==========================================================
# INPUT VALIDATION
# ==========================================================
def get_valid_input(prompt, options=None):
    while True:
        answer = input(prompt).strip()
        if options:
            normalized = [opt.lower() for opt in options]
            if answer.lower() in normalized:
                return options[normalized.index(answer.lower())]
            print(f"Invalid answer. Choose from: {', '.join(options)}")
        else:
            if answer:
                return answer
            print("Please enter a response.")

# ==========================================================
# AI SELF-INSTRUCTION PROCESSING
# ==========================================================
def process_ai_self_instruction(question_text, ai_answer, instruction_rules):
    if callable(instruction_rules):
        instruction_text = instruction_rules(ai_answer)
    elif isinstance(instruction_rules, dict):
        instruction_text = instruction_rules.get(ai_answer.strip(), "")
    else:
        instruction_text = str(instruction_rules)

    if instruction_text:
        ai_instructions.append(
            {
                "question": question_text,
                "ai_answer": ai_answer,
                "instruction": instruction_text,
            }
        )

    return instruction_text

# ==========================================================
# QUESTION HANDLER
# ==========================================================
def ask_question(q):
    print(f"\n- {q['question']}")
    if q.get("possible_answers"):
        print(f"Possible answers: {', '.join(q['possible_answers'])}")

    ai_answer = get_valid_input("Your answer: ", q.get("possible_answers"))

    response_entry = {
        "question": q["question"],
        "answer": ai_answer,
        "follow_up": "",
        "ai_instruction": "",
    }

    if "ai_instruction" in q:
        ai_text = process_ai_self_instruction(
            q["question"], ai_answer, q["ai_instruction"]
        )
        response_entry["ai_instruction"] = ai_text or ""

    follow_up = q.get("follow_up")
    if follow_up:
        follow_up_answer = get_valid_input(
            f"{follow_up['question']} ", follow_up.get("possible_answers")
        )
        response_entry["follow_up"] = follow_up_answer

        if "ai_instruction" in follow_up:
            ai_text_fu = process_ai_self_instruction(
                follow_up["question"], follow_up_answer, follow_up["ai_instruction"]
            )
            if ai_text_fu:
                if response_entry["ai_instruction"]:
                    response_entry["ai_instruction"] += " | " + ai_text_fu
                else:
                    response_entry["ai_instruction"] = ai_text_fu

    responses.append(response_entry)

# ==========================================================
# RUN QUESTIONNAIRE
# ==========================================================
for q in questions:
    ask_question(q)

# ==========================================================
# OUTPUT
# ==========================================================
print("\nCompleted analysis:")
for r in responses:
    print(f"\n- {r['question']}")
    print(f"Answer: {r['answer']}")
    if r["follow_up"]:
        print(f"Follow-up: {r['follow_up']}")
    if r["ai_instruction"]:
        print(f"AI Instruction: {r['ai_instruction']}")

print("\nHolistic AI instruction set:")
for instr in ai_instructions:
    print(f"- {instr['instruction']}")

# ==========================================================
# SAVE CSV
# ==========================================================
csv_filename = "image_analysis_responses.csv"
with open(csv_filename, mode="w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["Question", "Answer", "Follow-up", "AI Instruction"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for r in responses:
        writer.writerow(
            {
                "Question": r["question"],
                "Answer": r["answer"],
                "Follow-up": r["follow_up"],
                "AI Instruction": r["ai_instruction"],
            }
        )

print(f"\nSaved to {csv_filename}")