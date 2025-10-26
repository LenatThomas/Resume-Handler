from PyPDF2 import PdfReader
from io import BytesIO
from docx import Document
from dotenv import load_dotenv
import google.generativeai as genai
import os
from utils.logger import setupLogger
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

class ResumeHandler():
    def __init__(self, logger):
        self._model = None
        self._text = None
        self._logger = logger
        self._sheet = None
        self._createModel()
        self._setupSheet()

    def from_pdf(self, filebytes):
        reader = PdfReader(BytesIO(filebytes))
        self._text = ""
        for page in reader.pages:
            self._text += page.extract_text() or ""

    def from_doc(self, filebytes):
        doc = Document(BytesIO(filebytes))
        self._text = "\n".join([p.text for p in doc.paragraphs])

    def _setupSheet(self):
        try:
            SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
            CREDS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'service-account-key.json')
            SHEET_ID = os.getenv('GOOGLE_SHEET_ID')  
            if not SHEET_ID:
                self._logger.warning("GOOGLE_SHEET_ID not set. Google Sheets integration disabled.")
                return
            if os.path.exists(CREDS_FILE):
                creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
            else:
                creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON')
                if creds_json:
                    creds_dict = json.loads(creds_json)
                    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
                else:
                    self._logger.warning("Google Sheets credentials not found. Sheets integration disabled.")
                    return
            client = gspread.authorize(creds)
            self._sheet = client.open_by_key(SHEET_ID).sheet1
            self._logger.info("Successfully connected to Google Sheets")
            self._ensureHeaders()
            
        except Exception as e:
            self._logger.error(f"Google Sheets setup failed: {e}")
            self._sheet = None

    def _ensureHeaders(self):
        if not self._sheet:
            return
            
        try:
            current_headers = self._sheet.row_values(1)
            expected_headers = [
                "Timestamp", "Full Name", "Email", 
                "Phone Number", "Education", "Experience", "Skills"
            ]
            
            if not current_headers or current_headers != expected_headers:
                self._sheet.clear()
                self._sheet.append_row(expected_headers)
                self._logger.info("Google Sheets headers initialized")
        except Exception as e:
            self._logger.error(f"Error setting up headers: {e}")

    def _extract_ocr(self):
        pass

    def save(self):
        if not self._sheet:
            self._logger.warning("Google Sheets not available. Data not saved.")
            return False
            
        if not self._data:
            self._logger.warning("No data to save. Process the resume first.")
            return False

        try:
            sheet_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  
                self._data.get('name', ''),                    
                self._data.get('email', ''),                   
                self._data.get('phone', ''),                   
                str(self._data.get('education', '')),          
                str(self._data.get('experience', '')),         
                str(self._data.get('skills', '')),             
            ]
            
            self._sheet.append_row(sheet_data)
            self._logger.info("Resume data saved to Google Sheets")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save data to Google Sheets: {e}")
            return False

    def _createModel(self):
        load_dotenv()
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        genai.configure(api_key = GOOGLE_API_KEY)
        context =   """
                        Extract the following details from incoming resume texts:
                        - Valid Resume
                        - Full Name
                        - Email
                        - Phone Number
                        - Education (degrees, university names)
                        - Work Experience (company, role, duration)
                        - Skills (technical and soft skills)

                        Return the answer in JSON format with keys:
                        valid_resume, name, email, phone, education, experience, skills.
                        The 'valid_resume' key is boolean — false if not a resume.
                        Do not consider cover letters as resume.
                    """
        self._model = genai.GenerativeModel(
            model_name= "gemini-2.5-flash", 
            system_instruction = context
            ) 

    def process(self):
        if self._text is None:
            return {"error" : "No resume loaded"}
        try:
            response = self._model.generate_content(self._text)
            
            try:
                self._data = json.loads(response.text.strip())
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    self._data = json.loads(json_match.group())
                else:
                    self._data = {"error": "Invalid JSON response", "raw_response": response.text}

            if self._data.get('valid_resume', False):
                self.save()
            
            return self._data
            
        except Exception as e:
            self._logger.error(f"Error in ResumeHandler. Resume processing failed: {e}")
            return {"error": str(e)}