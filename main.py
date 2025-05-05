import os
import imapclient
from imapclient.exceptions import LoginError
import pyzmail
import time
from dotenv import load_dotenv
import openai
import smtplib
from email.message import EmailMessage

load_dotenv(dotenv_path="./.env")

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")
SMTP_SERVER = os.getenv("SMTP_SERVER")
USER_FULLNAME= os.getenv("USER_FULLNAME")
USER_CONTACT_INFO= os.getenv("USER_CONTACT_INFO")
USER_JOB_TITLE= os.getenv("USER_JOB_TITLE")
USER_ATTACHMENT_PATH= os.getenv("USER_ATTACHMENT_PATH")
USER_ATTACHMENT_NAME= os.getenv("USER_ATTACHMENT_NAME")
openai.api_key = os.getenv("OPENAI_API_KEY")

def is_job_offer(email_body):
    prompt = f"""
    Analyze the following email content and tell me if it's a job offer or not. Respond only with "YES" or "NO".

    Email content:
    ---
    {email_body}
    ---
    """
    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    reply = response.choices[0].message.content.strip().upper()
    return reply == "YES"

def generate_job_reply(email_body, fullname, contact, job_title):
    prompt = f"""
    Write a professional and enthusiastic email response to a job offer for a {job_title} role.
    Mention that I'm attaching my CV, thank the recruiter, and express excitement to learn more about the role.
    
    My Information:
    Name: {fullname}
    Contact: {contact}

    - Do NOT include placeholders like [Your Name], [Company Name], or [Date].
    - Mention that the CV is attached.
    - Be concise and enthusiastic.
    
    Here's the job offer email:
    ---
    {email_body}
    ---
    """
    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def send_email_reply(to_address, subject, body, attachment_path, attachment_name):
    msg = EmailMessage()
    msg['Subject'] = f"Re: {subject}"
    msg['From'] = EMAIL
    msg['To'] = to_address
    msg.set_content(body)

    with open(attachment_path, 'rb') as f:
        file_data = f.read()
    msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=attachment_name)

    with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
        smtp.login(EMAIL, PASSWORD)
        smtp.send_message(msg)

def process_email(msg_id, imap_conn):
    raw_message = imap_conn.fetch([msg_id], ['BODY[]', 'FLAGS'])
    message = pyzmail.PyzMessage.factory(raw_message[msg_id][b'BODY[]'])
    subject = message.get_subject()
    if isinstance(subject, bytes):
        subject = subject.decode()
    from_ = message.get_addresses('from')
    print(f"New Email from {from_}: {subject}")

    if message.text_part:
        email_body = message.text_part.get_payload().decode(message.text_part.charset)
    elif message.html_part:
        email_body = message.html_part.get_payload().decode(message.html_part.charset)
    else:
        print("No readable content found.")
        return

    if is_job_offer(email_body):
        reply_text = generate_job_reply(email_body, USER_FULLNAME, USER_CONTACT_INFO, USER_JOB_TITLE)
        to_email = from_[0][1]
        send_email_reply(to_email, subject, reply_text, USER_ATTACHMENT_PATH, USER_ATTACHMENT_NAME)
        print("Replied to job offer with CV.")
    else:
        print("Not a job offer.")

def monitor_inbox():
    with imapclient.IMAPClient(IMAP_SERVER, ssl=True) as client:
        try:
            print("Logging in as: ", EMAIL)
            print("Server host: ", IMAP_SERVER)
            client.login(EMAIL, PASSWORD)
            client.select_folder('INBOX', readonly=True)
        except LoginError:
            print("Invalid Credentials. Authentication Failed.")
            exit()
        
        print("Connected.")
        print("Monitoring inbox...")

        # Get the UID of the most recent message
        all_uids = client.search(['ALL'])
        last_seen_uid = max(all_uids) if all_uids else 0

        while True:
            try:
                print("Entering IDLE...")
                client.idle()
                responses = client.idle_check(timeout=300)
                client.idle_done()

                if responses:
                    new_uids = client.search(['UID', f'{last_seen_uid + 1}:*'])
                    for uid in new_uids:
                        process_email(uid, client)
                        last_seen_uid = max(last_seen_uid, uid)
            except KeyboardInterrupt:
                print("Monitoring stopped.")
                break
            except Exception as e:
                print("Error:", e)
                time.sleep(10)

if __name__ == "__main__":
    monitor_inbox()
