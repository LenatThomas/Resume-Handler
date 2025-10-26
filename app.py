import time
import os
import requests
from requests.auth import HTTPBasicAuth
from utils.logger import setupLogger
from flask import Flask
from flask import render_template, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from flask_cors import CORS
from datetime import datetime, timedelta
from process import ResumeHandler, ChatHandler

START_TIME = time.time()

app = Flask(__name__)
CORS(app)

TWILIO_SID  = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")

logger = setupLogger(app = app, logFile = './logs/logs.log')
uploaddir = './uploads/'
resume_handler = ResumeHandler.ResumeHandler(logger = logger)
chat_handler = ChatHandler.ChatHandler(logger = logger)

@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    sender = request.form.get("From", "")
    nmedia = int(request.form.get("NumMedia", 0))
    message = request.form.get("Body", "").strip()
    resp = MessagingResponse()

    logger.info(f'Recieved message from sender {sender}: {message}')
    logger.info(f'Number of media : {nmedia}')

    resume_status = None

    if not message and not nmedia:
        resp.message("Hello! How can I assist you today?")
        return str(resp)

    if nmedia > 0:
        url = request.form.get("MediaUrl0")
        ftype = request.form.get("MediaContentType0")

        try:
            fresponse = requests.get(url, auth = HTTPBasicAuth(TWILIO_SID, TWILIO_AUTH))
            if fresponse.status_code != 200:
                logger.error(f"Failed to fetch media: {fresponse.status_code} {fresponse.text}")
                resume_status = f"Failed to fetch media: {fresponse.status_code} {fresponse.text}"
                reply = chat_handler.process(message, resume_status)
                resp.message(reply)
                return str(resp)
            fbytes = fresponse.content
            if "pdf" in ftype:
                resume_handler.from_pdf(fbytes)
            elif "word" in ftype or "docx" in ftype:
                resume_handler.from_doc(fbytes)
            else:
                resume_status = "Unsupported file type. Please send a PDF or DOCX resume."
                reply = chat_handler.process(message, resume_status)
                resp.message(reply)
                return str(resp)
            
            resume_status = resume_handler.process()

        except Exception as e:
            logger.error(f"Error processing resume: {e}")
            resume_status = f"Error processing resume: {e}" 
    
    reply = chat_handler.process(
        message = message or "User uploaded a resume.", 
        status = resume_status
        )
    resp.message(reply)
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)