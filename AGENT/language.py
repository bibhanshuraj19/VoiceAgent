"""Lightweight English / Hindi detection for voice replies."""

from __future__ import annotations

import re

EN, HI = "en-IN", "hi-IN"
NAMES = {EN: "english", HI: "hindi"}

DID_NOT_CATCH = {
    EN: "Sorry, I didn't catch that. Could you say it again?",
    HI: "माफ़ कीजिए, मैं समझ नहीं पाया। क्या आप दोबारा बोल सकते हैं?",
}
LLM_FAILURE = {
    EN: "I'm having trouble answering right now. Please try again in a moment.",
    HI: "मुझे अभी जवाब देने में दिक्कत हो रही है। कृपया थोड़ी देर बाद फिर कोशिश कीजिए।",
}

_HI = frozenset(
    "aap apka apki apko acha achha aaj batao bataye batana baje bolo chahiye de dena "
    "dijiye hai hain hoon hum hume ham hoga kal ka ki ke kaise karo karna karni karne "
    "kijiye kya kab kyu kyon liye main mera meri mere mujhe namaste nahi par pe sirf "
    "samajh theek thik tum ye yeh".split()
)
_EN = frozenset(
    "about appointment book course degree engineering hello help meeting move please "
    "schedule tell thanks today tomorrow what when where".split()
)
_CAL = frozenset(
    "appointment book booking calendar cancel delete meeting move reschedule schedule slot "
    "अपॉइंटमेंट कैलेंडर बुक बदल बदलो मुलाकात रद्द शेड्यूल".split()
)
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def pick(table: dict[str, str], code: str) -> str:
    return table.get(code) or table[EN]


def name(code: str) -> str:
    return NAMES.get(code, NAMES[EN])


def detect(text: str, *, last: str = EN) -> str:
    clean = (text or "").strip()
    if not clean:
        return last or EN
    if has_devanagari(clean) or _hinglish(clean):
        return HI
    if looks_english(clean):
        return EN
    return HI if last == HI else EN


def calendar_request(text: str) -> bool:
    clean = (text or "").strip().lower()
    if not clean:
        return False
    words = set(_words(clean))
    return bool(words & _CAL) or any(t in clean for t in _CAL if any(ord(c) > 127 for c in t))


def _words(text: str) -> list[str]:
    return ["".join(c for c in w.lower() if c.isalpha()) for w in text.split() if any(c.isalpha() for c in w)]


def _hinglish(text: str) -> bool:
    words = _words(text)
    if not words:
        return False
    hits = sum(w in _HI for w in words)
    return hits >= 2 or (hits >= 1 and len(words) <= 4)


def looks_english(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 2 or sum(c.isascii() for c in letters) / len(letters) < 0.98:
        return False
    return any(w in _EN for w in _words(text))


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text or ""))
