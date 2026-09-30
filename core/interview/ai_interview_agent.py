import time

class ObservationEngine:
    def __init__(self):
        self.observations = []

    def record_observation(self, text: str):
        self.observations.append({"time": time.time(), "text": text})
        # print(f"Observation recorded: {text}")

    def analyze_gaze(self, is_looking_at_screen: bool):
        if not is_looking_at_screen:
            self.record_observation("Extended gaze away from screen.")

    def detect_multiple_faces(self, face_count: int):
        if face_count > 1:
            self.record_observation("Multiple faces detected.")

    def monitor_tab_switching(self, switch_count: int):
        if switch_count > 3:
            self.record_observation("Frequent tab switching observed.")

class IntegrityMonitor:
    def __init__(self, observation_engine: ObservationEngine):
        self.observation_engine = observation_engine

    def check_requirements(self):
        return {
            "screen_sharing": True,
            "camera_active": True,
            "microphone_active": True
        }

class VoiceAnalysis:
    def __init__(self):
        self.metrics = {
            "speaking_clarity": 0,
            "speaking_pace": 0,
            "filler_words": 0
        }

    def analyze_communication(self, text: str, duration: float):
        self.metrics["speaking_pace"] = len(text.split()) / duration if duration > 0 else 0
        return self.metrics

class AIAssistant:
    def __init__(self):
        pass

    def generate_next_question(self, context: str):
        return "Can you explain the complexity of this approach?"
        
    def summarize_answer(self, answer: str):
        return f"Summary: {answer[:30]}..."

class InterviewNotes:
    def __init__(self):
        self.notes = []

    def add_note(self, question: str, response: str, key_points: list):
        self.notes.append({
            "question": question,
            "response": response,
            "key_points": key_points
        })

class ReportGenerator:
    def __init__(self):
        pass

    def generate_report(self, notes: list, observations: list, voice_metrics: dict):
        return {
            "Candidate Information": "John Doe",
            "Technical Performance": "Strong problem solving.",
            "Observations": observations,
            "Overall Recommendation": "Proceed to next round."
        }

class AIInterviewAgent:
    def __init__(self):
        self.observation_engine = ObservationEngine()
        self.integrity_monitor = IntegrityMonitor(self.observation_engine)
        self.voice_analysis = VoiceAnalysis()
        self.ai_assistant = AIAssistant()
        self.notes = InterviewNotes()
        self.report_generator = ReportGenerator()

    def start_interview(self):
        reqs = self.integrity_monitor.check_requirements()
        if all(reqs.values()):
            return "Interview Started"
        return "Pre-interview requirements not met."

    def end_interview(self):
        report = self.report_generator.generate_report(
            self.notes.notes,
            self.observation_engine.observations,
            self.voice_analysis.metrics
        )
        return report
