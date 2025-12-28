"""
Story Generator for Passphrase Memorization
Uses lightweight ML (DistilGPT-2) for coherent stories, with template fallback.
"""

import random
import re
from typing import Optional

# Try to import ML libraries
try:
    from transformers import pipeline, set_seed
    import torch
    HAS_ML = True
except ImportError:
    HAS_ML = False

# Global generator (lazy loaded)
_generator = None
_model_loaded = False


def get_generator():
    """Lazy load the text generation model."""
    global _generator, _model_loaded

    if not HAS_ML:
        return None

    if not _model_loaded:
        try:
            # Use distilgpt2 - small (~350MB) and fast
            device = 0 if torch.cuda.is_available() else -1
            _generator = pipeline(
                'text-generation',
                model='distilgpt2',
                device=device,
                torch_dtype=torch.float32
            )
            _model_loaded = True
            print("ML story generator loaded successfully")
        except Exception as e:
            print(f"Could not load ML model: {e}. Using templates.")
            _generator = None
            _model_loaded = True  # Don't retry

    return _generator


def generate_story_ml(day: str, words: list[str], max_attempts: int = 3) -> Optional[str]:
    """
    Generate a story using ML that incorporates all passphrase words.

    Returns None if ML is unavailable or generation fails.
    """
    generator = get_generator()
    if generator is None:
        return None

    # Create a compelling prompt
    words_str = ', '.join(words[:-1]) + f', and {words[-1]}' if len(words) > 1 else words[0]

    prompts = [
        f"{day}, something memorable happened including: {words_str}.",
    ]

    prompt = random.choice(prompts)

    try:
        set_seed(random.randint(0, 10000))

        # Generate text
        result = generator(
            prompt,
            max_new_tokens=80,
            num_return_sequences=1,
            temperature=0.8,
            top_p=0.9,
            do_sample=True,
            pad_token_id=50256,  # eos token for gpt2
        )

        story = result[0]['generated_text']

        # Clean up - get just a few sentences
        story = story.strip()

        # Try to end at a sentence boundary
        for end_char in ['. ', '! ', '? ']:
            last_end = story.rfind(end_char)
            if last_end > len(prompt) + 20:
                story = story[:last_end + 1]
                break

        # Verify most words are present (ML doesn't always include all)
        story_lower = story.lower()
        words_found = sum(1 for w in words if w.lower() in story_lower)

        if words_found < len(words) * 0.5:  # At least 50% of words
            # Append missing words naturally
            missing = [w for w in words if w.lower() not in story_lower]
            if missing:
                story += f" Don't forget: {', '.join(missing)}."

        return story

    except Exception as e:
        print(f"ML generation error: {e}")
        return None


# ============================================================================
# TEMPLATE FALLBACK (always available)
# ============================================================================

STORY_TEMPLATES = {
    'Monday': [
        "Monday morning began when I discovered a {0} near the {1}. I had to {2} quickly, then grab the {3} before reaching the {4}.",
        "The week started with a {0} appearing at the {1}. My plan was to {2}, secure the {3}, and head toward the {4}.",
        "On Monday, the {0} and the {1} crossed paths. We decided to {2}, bring the {3}, and meet at the {4}.",
    ],
    'Tuesday': [
        "Tuesday brought a {0} to the {1}. Everyone wanted to {2}, especially with the {3} near the {4}.",
        "The {0} arrived Tuesday carrying a {1}. Together we would {2}, protect the {3}, and explore the {4}.",
        "On Tuesday, my {0} transformed into a {1}. I needed to {2}, find the {3}, and unlock the {4}.",
    ],
    'Wednesday': [
        "By Wednesday, the {0} had found a {1}. The mission: {2}, retrieve the {3}, and guard the {4}.",
        "Midweek magic: a {0} emerged from the {1}. We had to {2}, grab the {3}, and escape to the {4}.",
        "Wednesday's {0} was hiding near the {1}. To {2} successfully, we needed the {3} and the {4}.",
    ],
    'Thursday': [
        "Thursday's {0} came with a {1}. Our plan: {2}, then move the {3} inside the {4}.",
        "On Thursday, the {0} met the {1} unexpectedly. They decided to {2}, share the {3}, and visit the {4}.",
        "The {0} adventure on Thursday led us to a {1}. We chose to {2}, carry the {3}, and discover the {4}.",
    ],
    'Friday': [
        "Friday arrived with a {0} and a {1}. Time to {2}, celebrate with the {3}, and toast the {4}!",
        "TGIF! The {0} party featured a {1}. We would {2}, enjoy the {3}, and dance around the {4}.",
        "Friday's surprise was a {0} inside a {1}. Everyone wanted to {2}, taste the {3}, and admire the {4}.",
    ],
    'Saturday': [
        "Saturday morning, the {0} journeyed to the {1}. Goals: {2}, collect the {3}, and protect the {4}.",
        "Weekend mode: a {0} relaxing near a {1}. I chose to {2}, photograph the {3}, and sketch the {4}.",
        "On Saturday, the legendary {0} appeared at the {1}. Heroes must {2}, wield the {3}, and defeat the {4}.",
    ],
    'Sunday': [
        "Sunday peace was broken by a {0} and a {1}. We needed to {2}, fix the {3}, and restore the {4}.",
        "A quiet Sunday with my {0} near the {1}. Plans: {2} later, maybe find the {3}, or visit the {4}.",
        "Sunday sunset revealed a {0} beside a {1}. Time to {2}, remember the {3}, and dream of the {4}.",
    ],
}

# Extensions for 6+ word phrases
EXTENSIONS = [
    [" Suddenly, a {5} appeared!"],
    [" The {6} changed everything."],
    [" Behind it was a {7}."],
    [" Plus a mysterious {8}."],
    [" The {9} completed the quest."],
    [" A {10} watched from afar."],
    [" And finally, the legendary {11}."],
]


def generate_story_template(day: str, words: list[str]) -> str:
    """Generate story using templates (fallback method)."""
    templates = STORY_TEMPLATES.get(day, STORY_TEMPLATES['Monday'])
    template = random.choice(templates)

    # Add extensions for longer phrases
    for i, ext_list in enumerate(EXTENSIONS):
        word_idx = i + 5
        if len(words) > word_idx:
            template += random.choice(ext_list)

    # Pad words list to ensure we have enough for any template
    padded_words = words + [''] * (12 - len(words))

    return template.format(*padded_words)


# ============================================================================
# MAIN API
# ============================================================================

def generate_story(day: str, words: list[str], use_ml: bool = True) -> dict:
    """
    Generate a memorable story incorporating the passphrase words.

    Args:
        day: Day of the week (e.g., 'Monday')
        words: List of passphrase words
        use_ml: Whether to try ML generation first

    Returns:
        dict with 'story' (plain text) and 'story_html' (with highlighted words)
    """
    story = None
    used_ml = False

    # Try ML first if requested
    if use_ml and HAS_ML:
        story = generate_story_ml(day, words)
        if story:
            used_ml = True

    # Fall back to templates
    if story is None:
        story = generate_story_template(day, words)

    # Generate HTML version with highlighted words (RED and CAPS)
    html_story = story
    for word in words:
        # Case-insensitive replacement with highlighted version
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        html_story = pattern.sub(
            f'<span class="story-word">{word.upper()}</span>',
            html_story
        )

    return {
        'story': story,
        'story_html': html_story,
        'used_ml': used_ml
    }


def generate_all_stories(phrases: dict[str, str], use_ml: bool = True) -> dict[str, dict]:
    """
    Generate stories for all days.

    Args:
        phrases: Dict mapping day names to phrase strings
        use_ml: Whether to use ML generation

    Returns:
        Dict mapping day names to story dicts
    """
    stories = {}
    for day, phrase in phrases.items():
        words = phrase.split()
        stories[day] = generate_story(day, words, use_ml=use_ml)
    return stories
