import os
from dotenv import load_dotenv
import google.generativeai as genai
import json

class ChatHandler:
    def __init__(self, logger):
        self._model = None
        self._chat = None
        self._logger = logger
        self._createModel()

    def _createModel(self):
        load_dotenv()
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        genai.configure(api_key=GOOGLE_API_KEY)

        context = """
            You are a polite and professional assistant designed to handle user
            conversations over WhatsApp. You are part of a resume handling system.
            You will sometimes be provided with the *status or extracted details*
            from a resume. Respond appropriately from this context.

            Always maintain a courteous and clear tone.

            - If the user greets you, respond warmly.
            - If they send a resume, thank them and summarize what was extracted.
            - If the resume seems invalid, politely ask for a clearer version.
            - If they ask about status, respond based on the latest resume info.
            - Avoid long paragraphs; keep responses conversational and concise.
            - Never disclose API or system details.

            Example tone:
            "Thanks for sending your resume, John! I see you have experience in data analysis — we'll review your application shortly."
            "Hello! How can I assist you today?"
            "It seems your document wasn't a valid resume. Could you please resend it as a PDF?"
        """

        self._model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=context
        )
        self._chat = self._model.start_chat(history=[])

    def process(self, message: str, status : dict = None) -> str:
        
        try:
            if status:
                if isinstance(status, dict):
                    status_text = json.dumps(status, indent=2)
                else:
                    status_text = str(status)
                prompt = f"""
                    User message: "{message}"
                    Resume status: {status_text}
                    """
            else:
                prompt = f"User message: {message}"

            response = self._chat.send_message(prompt)
            return response.text.strip()

        except Exception as e:
            self._logger.error(f"ChatHandler error: {e}")
            return "Apologies, I'm having some trouble responding right now."
