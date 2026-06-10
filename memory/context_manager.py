# memory/context_manager.py
# ─────────────────────────────────────────────────────────────────────────────
# Manages live conversation context — entities, pronouns, topic, state.
# Lives in RAM only. Resets each session. Fast — no disk I/O.
#
# Tracks:
#   - Active entities (people, places, apps, objects) with recency scores
#   - Current topic
#   - Pronoun → entity resolution
#   - Recent message window
#   - Emotional tone of conversation
# ─────────────────────────────────────────────────────────────────────────────

import re
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Entity:
    name: str
    entity_type: str        # person, place, app, project, object, concept
    mentions: int = 1
    last_mentioned: float = field(default_factory=time.monotonic)
    gender: Optional[str] = None   # male, female, neutral — for pronoun resolution

    def score(self) -> float:
        """Recency + frequency score. Higher = more relevant."""
        age = time.monotonic() - self.last_mentioned
        recency = 1.0 / (1.0 + age / 30.0)   # decays over 30s
        return self.mentions * recency


@dataclass
class Turn:
    user: str
    leon: str
    timestamp: float = field(default_factory=time.monotonic)
    entities: list[str] = field(default_factory=list)
    topic: str = ""


class ContextManager:
    """
    Live in-session context. Tracks entities, resolves pronouns, maintains topic.
    Zero disk I/O — pure RAM.
    """

    # Entity type patterns
    _PERSON_CUES  = re.compile(
        r'\b(who is|tell me about|what about|regarding|'
        r'actor|actress|player|singer|politician|ceo|founder|director)\b',
        re.IGNORECASE
    )
    _APP_CUES     = re.compile(
        r'\b(open|launch|close|start|install|app|application|browser|software)\b',
        re.IGNORECASE
    )
    _PROJECT_CUES = re.compile(
        r'\b(project|build|building|working on|develop|app i|website i)\b',
        re.IGNORECASE
    )
    _PLACE_CUES   = re.compile(
        r'\b(in|at|near|city|country|place|location|state|district)\b',
        re.IGNORECASE
    )

    # Pronoun sets
    _MALE_PRONOUNS    = {"he", "his", "him", "himself"}
    _FEMALE_PRONOUNS  = {"she", "her", "hers", "herself"}
    _NEUTRAL_PRONOUNS = {"it", "its", "itself", "they", "them", "their",
                         "that", "those", "this", "these"}

    def __init__(self, window: int = 10):
        self._window    = window          # max turns in short-term memory
        self._turns: list[Turn] = []
        self._entities: dict[str, Entity] = {}  # name → Entity
        self._topic     = ""
        self._tone      = "neutral"       # neutral, curious, frustrated, positive

    # ── Entity registration ───────────────────────────────────────────────────

    def _classify_entity(self, name: str, context: str) -> str:
        if self._PERSON_CUES.search(context):
            return "person"
        if self._APP_CUES.search(context):
            return "app"
        if self._PROJECT_CUES.search(context):
            return "project"
        if self._PLACE_CUES.search(context):
            return "place"
        return "concept"

    def _detect_gender(self, name: str, reply: str) -> Optional[str]:
        """Infer gender from Leon's reply about a person."""
        text = reply.lower()
        male_words   = {"he", "his", "him", "actor", "king", "sir", "mr"}
        female_words = {"she", "her", "actress", "queen", "ms", "mrs"}
        male_count   = sum(1 for w in male_words   if f" {w} " in f" {text} ")
        female_count = sum(1 for w in female_words if f" {w} " in f" {text} ")
        if male_count > female_count:
            return "male"
        if female_count > male_count:
            return "female"
        return None

    def register_entity(self, name: str, context: str = "",
                        entity_type: str = "", gender: str = None):
        key = name.lower().strip()
        if not key or len(key) < 2:
            return
        if key in self._entities:
            self._entities[key].mentions      += 1
            self._entities[key].last_mentioned = time.monotonic()
            if gender:
                self._entities[key].gender = gender
        else:
            etype = entity_type or self._classify_entity(name, context)
            self._entities[key] = Entity(
                name=name, entity_type=etype, gender=gender
            )

    def _extract_entities_from_text(self, text: str) -> list[str]:
        """
        Extract named entities from text using simple heuristics.
        Looks for capitalized words and known patterns.
        Returns list of entity name strings.
        """
        found = []

        # Capitalized proper nouns (2+ words or standalone)
        proper = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        for p in proper:
            if len(p) > 2 and p not in {
                "I", "Leon", "Ok", "Okay", "Yes", "No", "Hey", "Hi"
            }:
                found.append(p)

        # "X is a ..." pattern — strong entity signal
        for m in re.finditer(
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+is\s+(?:a|an|the)\b', text
        ):
            found.append(m.group(1))

        return list(set(found))

    # ── Pronoun resolution ────────────────────────────────────────────────────

    def resolve_pronoun(self, word: str) -> Optional[str]:
        """
        Resolve a pronoun to the most recently mentioned relevant entity.
        Returns entity name or None.
        """
        word = word.lower().strip()

        if word in self._MALE_PRONOUNS:
            candidates = [
                e for e in self._entities.values()
                if e.gender == "male" or e.entity_type == "person"
            ]
        elif word in self._FEMALE_PRONOUNS:
            candidates = [
                e for e in self._entities.values()
                if e.gender == "female" or e.entity_type == "person"
            ]
        elif word in self._NEUTRAL_PRONOUNS:
            candidates = list(self._entities.values())
        else:
            return None

        if not candidates:
            return None

        # Return highest scoring entity
        best = max(candidates, key=lambda e: e.score())
        return best.name

    def resolve_pronouns_in_text(self, text: str) -> str:
        """
        Replace pronouns in user input with their resolved entities.
        E.g. "who is his wife" → "who is Akshay Kumar's wife"
        """
        all_pronouns = (
            self._MALE_PRONOUNS | self._FEMALE_PRONOUNS | self._NEUTRAL_PRONOUNS
        )

        def _replace(match):
            word     = match.group(0)
            resolved = self.resolve_pronoun(word.lower())
            if resolved:
                # Preserve grammatical case
                if word.lower() in {"his", "her", "its", "their"}:
                    return f"{resolved}'s"
                return resolved
            return word

        pattern = r'\b(' + '|'.join(re.escape(p) for p in all_pronouns) + r')\b'
        return re.sub(pattern, _replace, text, flags=re.IGNORECASE)

    # ── Topic management ──────────────────────────────────────────────────────

    def update_topic(self, user_text: str, leon_reply: str = ""):
        """Detect and update the current conversation topic."""
        combined = f"{user_text} {leon_reply}".lower()

        topic_patterns = [
            (r'\b(akshay kumar|shahrukh|salman|celebrity|actor|bollywood)\b', "Bollywood"),
            (r'\b(python|javascript|react|coding|programming|code|bug|error)\b', "coding"),
            (r'\b(ai|machine learning|llm|neural|model|training)\b', "AI/ML"),
            (r'\b(leon|voice assistant|jarvis|tts|whisper|ollama)\b', "Leon project"),
            (r'\b(weather|rain|temperature|forecast|climate)\b', "weather"),
            (r'\b(youtube|spotify|music|song|video|stream)\b', "media"),
            (r'\b(file|folder|document|resume|download)\b', "files"),
            (r'\b(health|exercise|diet|sleep|fitness)\b', "health"),
            (r'\b(money|finance|stock|invest|price|cost)\b', "finance"),
        ]

        for pattern, topic in topic_patterns:
            if re.search(pattern, combined):
                self._topic = topic
                return

    # ── Tone detection ────────────────────────────────────────────────────────

    def _detect_tone(self, text: str):
        t = text.lower()
        if any(w in t for w in ("frustrated", "annoyed", "angry", "stupid", "useless", "broken")):
            self._tone = "frustrated"
        elif any(w in t for w in ("thanks", "great", "awesome", "love", "perfect", "nice")):
            self._tone = "positive"
        elif any(w in t for w in ("why", "how", "what", "explain", "tell me")):
            self._tone = "curious"
        else:
            self._tone = "neutral"

    # ── Turn management ───────────────────────────────────────────────────────

    def add_turn(self, user: str, leon: str):
        """Register a completed conversation turn."""
        # Extract entities from both sides
        entities_found = self._extract_entities_from_text(user)
        entities_found += self._extract_entities_from_text(leon)

        for ent in entities_found:
            gender = self._detect_gender(ent, leon)
            self.register_entity(ent, context=user, gender=gender)

        self.update_topic(user, leon)
        self._detect_tone(user)

        turn = Turn(
            user=user,
            leon=leon,
            entities=entities_found,
            topic=self._topic,
        )
        self._turns.append(turn)

        # Keep window size
        if len(self._turns) > self._window:
            self._turns = self._turns[-self._window:]

    # ── Context retrieval ─────────────────────────────────────────────────────

    def get_active_entities(self, top_n: int = 5) -> list[Entity]:
        """Return top N most relevant entities right now."""
        sorted_entities = sorted(
            self._entities.values(), key=lambda e: e.score(), reverse=True
        )
        return sorted_entities[:top_n]

    def get_context_block(self) -> str:
        """
        Build a compact context string to inject into the LLM prompt.
        Keeps the prompt lightweight.
        """
        parts = []

        if self._topic:
            parts.append(f"Current topic: {self._topic}")

        active = self.get_active_entities(top_n=4)
        if active:
            ent_str = ", ".join(
                f"{e.name} ({e.entity_type})" for e in active
            )
            parts.append(f"Active entities: {ent_str}")

        if self._tone != "neutral":
            parts.append(f"User tone: {self._tone}")

        # Last 3 turns summary
        recent = self._turns[-3:]
        if recent:
            history = []
            for t in recent:
                history.append(f"User: {t.user[:80]}")
                history.append(f"Leon: {t.leon[:80]}")
            parts.append("Recent:\n" + "\n".join(history))

        return "\n".join(parts)

    def get_recent_turns(self, n: int = 6) -> list[dict]:
        """Return last N turns as LLM message format."""
        messages = []
        for turn in self._turns[-n:]:
            messages.append({"role": "user",      "content": turn.user})
            messages.append({"role": "assistant",  "content": turn.leon})
        return messages

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def tone(self) -> str:
        return self._tone


# ── Global singleton ──────────────────────────────────────────────────────────
# Shared across all modules in the session

_context = ContextManager(window=12)


def get_context() -> ContextManager:
    return _context
