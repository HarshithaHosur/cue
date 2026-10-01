# ============================================================
#  VOICE INTENT CLASSIFIER — NLP & Hybrid Fuzzy Matching
#  Supports high-accuracy regex extraction, TF-IDF + Naive Bayes,
#  and fuzzy token similarity for Windows apps, files, and tabs.
# ============================================================

import re
import difflib
from typing import Optional, Tuple, Dict, List, Any

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from fuzzywuzzy import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


TRAINING_CORPUS = {
    'open_chrome': [
        'open chrome', 'launch chrome', 'start chrome', 'open google chrome',
        'launch browser', 'start browser', 'open the browser', 'chrome please',
        'run chrome', 'open my browser', 'browser'
    ],
    'open_spotify': [
        'open spotify', 'launch spotify', 'start spotify', 'play some music',
        'open music player', 'spotify please', 'spotify'
    ],
    'open_vscode': [
        'open vs code', 'launch vs code', 'open visual studio code', 'open code',
        'start coding', 'open editor', 'code editor', 'vs code', 'vscode'
    ],
    'open_calculator': [
        'open calculator', 'launch calculator', 'start calculator', 'calculator',
        'open calc', 'calc please', 'run calculator'
    ],
    'open_notepad': [
        'open notepad', 'launch notepad', 'start notepad', 'open text editor',
        'notepad please', 'run notepad'
    ],
    'open_file_explorer': [
        'open file explorer', 'open explorer', 'open files', 'file manager',
        'open my computer', 'this pc'
    ],
    'open_new_tab': [
        'open new tab', 'new tab', 'create tab', 'add tab', 'create a new tab'
    ],
    'close_tab': [
        'close tab', 'close this tab', 'shut tab', 'dismiss tab'
    ],
    'close_first_tab': [
        'close first tab', 'close tab 1', 'shut first tab', 'close the first tab'
    ],
    'close_current_tab': [
        'close current tab', 'close active tab', 'close this current tab'
    ],
    'close_all_tabs': [
        'close all tabs', 'close every tab', 'shut all tabs', 'close all browser tabs'
    ],
    'switch_to_first_tab': [
        'switch to first tab', 'go to first tab', 'switch tab 1', 'first tab'
    ],
    'switch_to_last_tab': [
        'switch to last tab', 'go to last tab', 'switch to 9th tab', 'last tab'
    ],
    'next_tab': [
        'next tab', 'switch to next tab', 'go to next tab', 'forward tab', 'advance tab'
    ],
    'previous_tab': [
        'previous tab', 'prev tab', 'switch to previous tab', 'go to previous tab', 'back tab'
    ],
    'take_screenshot': [
        'take screenshot', 'screenshot', 'capture screen', 'screen grab',
        'snapshot', 'save screenshot', 'take a screenshot', 'capture the screen'
    ],
    'volume_up': [
        'volume up', 'increase volume', 'louder', 'turn it up', 'raise volume'
    ],
    'volume_down': [
        'volume down', 'decrease volume', 'softer', 'lower volume', 'turn it down'
    ],
    'mute': [
        'mute', 'silence', 'mute audio', 'unmute', 'shut up'
    ],
    'play_pause': [
        'play', 'pause', 'play pause', 'resume music', 'stop music', 'toggle playback'
    ],
    'next_song': [
        'next song', 'skip song', 'next track', 'skip track', 'play next'
    ],
    'previous_song': [
        'previous song', 'last song', 'previous track', 'go back track'
    ],
    'close_window': [
        'close window', 'close this window', 'exit window', 'shut window', 'close app'
    ],
    'start_presentation': [
        'start presentation', 'start slideshow', 'begin slides', 'present now'
    ],
    'stop_presentation': [
        'stop presentation', 'end presentation', 'exit slideshow', 'quit presentation'
    ],
    'next_slide': [
        'next slide', 'forward slide', 'advance slide'
    ],
    'previous_slide': [
        'previous slide', 'back slide', 'last slide'
    ],
    'support_agent': [
        'help me', 'help me replace', 'help me return', 'help me refund',
        'replace this order', 'return this order', 'refund this order',
        'explain this page', 'summarize this policy', 'explain this',
        'highlight refund policy', 'contact support', 'open customer support',
        'fill this form', 'scroll down', 'scroll up', 'continue',
        'my order arrived cold', 'my order is delayed', 'wrong product',
        'download my statement', 'download statement', 'help me with this order',
        'replace this', 'return this', 'what is this page',
        'order is wrong', 'damaged product', 'complaint about my order'
    ]
}


class VoiceIntentClassifier:
    """Classifies user spoken input into structured system actions or dynamic targets."""

    def __init__(self):
        self.all_phrases = []
        self.phrase_to_intent = {}

        for intent, phrases in TRAINING_CORPUS.items():
            for p in phrases:
                self.all_phrases.append(p)
                self.phrase_to_intent[p] = intent

        self.model = None
        if SKLEARN_AVAILABLE:
            X, y = [], []
            for intent, phrases in TRAINING_CORPUS.items():
                for p in phrases:
                    X.append(p)
                    y.append(intent)
            try:
                self.model = Pipeline([
                    ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
                    ('clf', MultinomialNB())
                ])
                self.model.fit(X, y)
            except Exception:
                self.model = None

    @staticmethod
    def normalize_text(text: str) -> str:
        """Cleans and standardizes transcript for classification."""
        substitutions = {
            r'\bchromee?\b': 'chrome',
            r'\bvs\s*code\b': 'vs code',
            r'\bv\s*s\s*code\b': 'vs code',
            r'\bpower\s*point\b': 'powerpoint',
            r'\bcalc\b': 'calculator',
            r'\bspotifyy?\b': 'spotify',
            r'\bscreen\s*shot\b': 'screenshot'
        }
        clean = text.lower().strip()
        for pat, repl in substitutions.items():
            clean = re.sub(pat, repl, clean)
        return clean

    def predict(self, raw_text: str, confidence_thresh: float = 0.55) -> Optional[Tuple[str, float, Optional[str]]]:
        """
        Predicts intent and optional target payload.
        Returns: Tuple of (intent_name, confidence, target_arg)
        """
        text = self.normalize_text(raw_text)
        if not text:
            return None

        # ── 1. Priority Pattern Matching for Specific Prompt Requirements ──

        # Tab Commands
        if 'close first tab' in text or 'close 1st tab' in text:
            return 'close_first_tab', 1.0, None
        if 'close all tabs' in text:
            return 'close_all_tabs', 1.0, None
        if 'close current tab' in text:
            return 'close_current_tab', 1.0, None
        if 'close tab' in text or 'close this tab' in text:
            return 'close_tab', 1.0, None
        if 'open new tab' in text or 'new tab' in text:
            return 'open_new_tab', 1.0, None
        if 'switch to first tab' in text or 'switch to 1st tab' in text:
            return 'switch_to_first_tab', 1.0, None
        if 'switch to last tab' in text:
            return 'switch_to_last_tab', 1.0, None
        if 'next tab' in text or 'switch to next tab' in text or 'go to next tab' in text:
            return 'next_tab', 1.0, None
        if 'previous tab' in text or 'prev tab' in text or 'switch to previous tab' in text or 'go to previous tab' in text:
            return 'previous_tab', 1.0, None

        # Screenshot Commands
        if any(kw in text for kw in ['take screenshot', 'capture screen', 'screenshot', 'take a screenshot', 'screen capture']):
            return 'take_screenshot', 1.0, None

        # Dynamic Application or File Openings ("open <target>")
        open_match = re.match(r'^(?:open|launch|start)\s+(.+)$', text)
        if open_match:
            target = open_match.group(1).strip()
            # If target matches known apps
            if target in ['chrome', 'google chrome', 'browser']:
                return 'open_chrome', 1.0, 'chrome'
            elif target in ['spotify', 'music']:
                return 'open_spotify', 1.0, 'spotify'
            elif target in ['vs code', 'vscode', 'code', 'visual studio code', 'visual studio']:
                return 'open_vscode', 1.0, 'code'
            elif target in ['calculator', 'calc']:
                return 'open_calculator', 1.0, 'calculator'
            elif target in ['notepad', 'notes']:
                return 'open_notepad', 1.0, 'notepad'
            elif target in ['file explorer', 'explorer', 'files']:
                return 'open_file_explorer', 1.0, 'explorer'
            else:
                # Dynamic App or File Opening (e.g. "open project report", "open EC Hackathon PDF")
                return 'open_item', 0.95, target

        # ── 2. Exact Dictionary Match ──
        if text in self.phrase_to_intent:
            return self.phrase_to_intent[text], 1.0, None

        # ── 3. Sklearn ML Model ──
        if self.model is not None:
            try:
                probs = self.model.predict_proba([text])[0]
                best_idx = probs.argmax()
                confidence = probs[best_idx]
                if confidence >= confidence_thresh:
                    return self.model.classes_[best_idx], float(confidence), None
            except Exception:
                pass

        # ── 4. Fuzzy Matching ──
        if FUZZY_AVAILABLE:
            match, score = process.extractOne(text, self.all_phrases, scorer=fuzz.token_sort_ratio)
            if score >= 72:
                return self.phrase_to_intent[match], score / 100.0, None
        else:
            matches = difflib.get_close_matches(text, self.all_phrases, n=1, cutoff=0.72)
            if matches:
                return self.phrase_to_intent[matches[0]], 0.80, None

        return None
