import os
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.db import models
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import base64
from communications.models import AdminNotification
from users.models import Evaluator
# Assuming you have an AdminNotification model - adjust import as needed
# from your_app.models import AdminNotification

# Google OAuth Token Storage Model
class GoogleOAuthToken(models.Model):
    """
    Model to store Google OAuth tokens persistently
    """
    service_type = models.CharField(
        max_length=50, 
        choices=[
            ('gmail', 'Gmail'),
            ('drive', 'Drive'),
            ('combined', 'Combined')
        ],
        default='combined'
    )
    token = models.TextField()
    refresh_token = models.TextField()
    token_uri = models.URLField()
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Google OAuth Token"
        verbose_name_plural = "Google OAuth Tokens"
    
    def __str__(self):
        return f"Google {self.service_type} Token - {self.created_at}"

# Scopes
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
]

DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
]

# Combined scopes for single authentication
COMBINED_SCOPES = GMAIL_SCOPES + DRIVE_SCOPES

class GoogleServiceManager:
    def __init__(self, request=None):
        self.request = request
        self.client_secrets_file = os.path.join(settings.BASE_DIR, 'web-client-secret.json')
        
    def get_authorization_url(self, service_type='combined'):
        """
        Generate authorization URL for OAuth flow
        
        Args:
            service_type (str): 'gmail', 'drive', or 'combined'
        
        Returns:
            str: Authorization URL
        """
        scopes = {
            'gmail': GMAIL_SCOPES,
            'drive': DRIVE_SCOPES,
            'combined': COMBINED_SCOPES
        }
        
        flow = Flow.from_client_secrets_file(
            self.client_secrets_file,
            scopes=scopes.get(service_type, COMBINED_SCOPES)
        )
        
        # Set redirect URI - adjust this to match your Django URL
        if self.request:
            flow.redirect_uri = self.request.build_absolute_uri(reverse('communications:google_oauth_callback'))
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to get refresh token
        )
        
        # Store state in session for security
        if self.request:
            self.request.session['google_auth_state'] = state
            self.request.session['service_type'] = service_type
        
        return authorization_url
    
    def handle_oauth_callback(self, authorization_code, state):
        """
        Handle OAuth callback and store credentials persistently in database
        
        Args:
            authorization_code (str): Authorization code from Google
            state (str): State parameter for security
        
        Returns:
            bool: Success status
        """
        # Verify state parameter
        if self.request and state != self.request.session.get('google_auth_state'):
            return False
        
        try:
            service_type = self.request.session.get('service_type', 'combined') if self.request else 'combined'
            scopes = {
                'gmail': GMAIL_SCOPES,
                'drive': DRIVE_SCOPES,
                'combined': COMBINED_SCOPES
            }
            
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=scopes.get(service_type, COMBINED_SCOPES)
            )
            
            if self.request:
                flow.redirect_uri = self.request.build_absolute_uri(reverse('communications:google_oauth_callback'))
            
            # Exchange authorization code for credentials
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # Store credentials in database instead of session
            self.store_credentials_in_db(credentials, service_type)
            
            # Also store in session for immediate use (optional)
            if self.request:
                self.request.session['google_credentials'] = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                }
            
            return True
            
        except Exception as e:
            print(f"OAuth callback error: {e}")
            return False
    
    def store_credentials_in_db(self, credentials, service_type='combined'):
        """
        Store credentials in database
        
        Args:
            credentials: Google OAuth credentials object
            service_type (str): Type of service ('gmail', 'drive', 'combined')
        """
        try:
            # Deactivate existing tokens for this service type
            GoogleOAuthToken.objects.filter(
                service_type=service_type,
                is_active=True
            ).update(is_active=False)
            
            # Create new token entry
            GoogleOAuthToken.objects.create(
                service_type=service_type,
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                is_active=True
            )
            
            print(f"Successfully stored {service_type} credentials in database")
            
        except Exception as e:
            print(f"Error storing credentials in database: {e}")
    
    def get_credentials_from_db(self, service_type='combined'):
        """
        Get credentials from database
        
        Args:
            service_type (str): Type of service to retrieve
            
        Returns:
            Credentials object or None
        """
        try:
            # Get the most recent active token for the service type
            token_obj = GoogleOAuthToken.objects.filter(
                service_type=service_type,
                is_active=True
            ).order_by('-created_at').first()
            
            if not token_obj:
                print(f"No active {service_type} credentials found in database")
                return None
            
            from google.oauth2.credentials import Credentials
            credentials = Credentials(
                token=token_obj.token,
                refresh_token=token_obj.refresh_token,
                token_uri=token_obj.token_uri,
                client_id=token_obj.client_id,
                client_secret=token_obj.client_secret,
                scopes=token_obj.scopes
            )
            
            # Refresh if needed
            if credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    # Update database with new token
                    token_obj.token = credentials.token
                    token_obj.updated_at = datetime.now()
                    token_obj.save()
                    print(f"Refreshed {service_type} token")
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    # Mark token as inactive if refresh fails
                    token_obj.is_active = False
                    token_obj.save()
                    return None
                    
            return credentials
            
        except Exception as e:
            print(f"Error loading credentials from database: {e}")
            return None
    
    def get_credentials_from_stored(self):
        """
        Get credentials from stored location (database)
        This method is for management commands (not session-based)
        """
        return self.get_credentials_from_db('combined')
    
    def get_credentials(self):
        """Get credentials from session or database"""
        if self.request:
            # For web requests, try session first, then database
            creds_data = self.request.session.get('google_credentials')
            if creds_data:
                from google.oauth2.credentials import Credentials
                credentials = Credentials(
                    token=creds_data['token'],
                    refresh_token=creds_data['refresh_token'],
                    token_uri=creds_data['token_uri'],
                    client_id=creds_data['client_id'],
                    client_secret=creds_data['client_secret'],
                    scopes=creds_data['scopes']
                )
                
                # Refresh if needed
                if credentials.expired and credentials.refresh_token:
                    try:
                        credentials.refresh(Request())
                        # Update session with new token
                        self.request.session['google_credentials']['token'] = credentials.token
                    except Exception as e:
                        print(f"Token refresh failed: {e}")
                        return None
                        
                return credentials
            else:
                # Fallback to database
                return self.get_credentials_from_db('combined')
        else:
            # For management commands, always use database
            return self.get_credentials_from_db('combined')
    
    def get_gmail_service(self):
        """Get Gmail service"""
        credentials = self.get_credentials()
        if not credentials:
            return None
        return build('gmail', 'v1', credentials=credentials)
    
    def get_drive_service(self):
        """Get Drive service"""
        credentials = self.get_credentials()
        if not credentials:
            return None
        return build('drive', 'v3', credentials=credentials)
    
    def is_authenticated(self, service_type='combined'):
        """
        Check if we have valid credentials for the specified service
        
        Args:
            service_type (str): Service type to check
            
        Returns:
            bool: True if authenticated, False otherwise
        """
        credentials = self.get_credentials_from_db(service_type)
        return credentials is not None
    
    def revoke_credentials(self, service_type='combined'):
        """
        Revoke and remove credentials for a service type
        
        Args:
            service_type (str): Service type to revoke
            
        Returns:
            bool: Success status
        """
        try:
            # Mark all tokens as inactive
            GoogleOAuthToken.objects.filter(
                service_type=service_type,
                is_active=True
            ).update(is_active=False)
            
            print(f"Revoked {service_type} credentials")
            return True
            
        except Exception as e:
            print(f"Error revoking credentials: {e}")
            return False
    
    @staticmethod
    def get_all_active_tokens():
        """
        Get all active tokens (for admin purposes)
        
        Returns:
            QuerySet: All active GoogleOAuthToken objects
        """
        return GoogleOAuthToken.objects.filter(is_active=True)

def send_mail_with_attachments(request, to_email, subject, body, drive_file_ids=None):
    """
    Send email with attachments from Google Drive
    
    Args:
        request: Django request object
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content
        drive_file_ids (list): List of Google Drive file IDs to attach
    
    Returns:
        dict: Result with success status and message
    """
    try:
        service_manager = GoogleServiceManager(request)
        gmail_service = service_manager.get_gmail_service()
        
        if not gmail_service:
            return {
                'success': False,
                'message': 'Gmail service not available. Please authenticate first.',
                'auth_url': service_manager.get_authorization_url('combined')
            }
        
        # Create message
        message = MIMEMultipart()
        message['to'] = to_email
        message['from'] = 'noreply-dareapp@gmail.com'  # Update with your email
        message['subject'] = subject
        message.attach(MIMEText(body, 'plain'))
        
        # Add attachments from Google Drive if provided
        if drive_file_ids:
            drive_service = service_manager.get_drive_service()
            
            if not drive_service:
                return {
                    'success': False,
                    'message': 'Drive service not available. Please authenticate first.',
                    'auth_url': service_manager.get_authorization_url('combined')
                }
            
            for file_id in drive_file_ids:
                try:
                    # Get file metadata
                    file_metadata = drive_service.files().get(
                        fileId=file_id, 
                        fields='name,mimeType,size'
                    ).execute()
                    
                    file_name = file_metadata['name']
                    file_mime_type = file_metadata['mimeType']
                    file_size = int(file_metadata.get('size', 0))
                    
                    # Check file size (Gmail has 25MB limit)
                    if file_size > 25 * 1024 * 1024:  # 25MB in bytes
                        print(f"Warning: File {file_name} is too large ({file_size} bytes). Skipping.")
                        continue
                    
                    # Determine if it's a Google Docs file
                    is_google_doc = file_mime_type in [
                        'application/vnd.google-apps.document',
                        'application/vnd.google-apps.spreadsheet',
                        'application/vnd.google-apps.presentation',
                        'application/vnd.google-apps.drawing'
                    ]
                    
                    if is_google_doc:
                        # Handle Google Docs files by exporting to PDF
                        export_mime_type = 'application/pdf'
                        if file_mime_type == 'application/vnd.google-apps.spreadsheet':
                            export_mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        elif file_mime_type == 'application/vnd.google-apps.document':
                            export_mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        
                        # Update file extension based on export type
                        if export_mime_type == 'application/pdf':
                            file_name = f"{os.path.splitext(file_name)[0]}.pdf"
                        elif export_mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                            file_name = f"{os.path.splitext(file_name)[0]}.xlsx"
                        elif export_mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                            file_name = f"{os.path.splitext(file_name)[0]}.docx"
                        
                        file_content = drive_service.files().export(
                            fileId=file_id,
                            mimeType=export_mime_type
                        ).execute()
                    else:
                        # Handle regular binary files
                        file_content = drive_service.files().get_media(
                            fileId=file_id
                        ).execute()
                    
                    # Determine the main type and subtype for MIME
                    if is_google_doc:
                        main_type, sub_type = export_mime_type.split('/', 1)
                    elif '/' in file_mime_type:
                        main_type, sub_type = file_mime_type.split('/', 1)
                    else:
                        main_type, sub_type = 'application', 'octet-stream'
                    
                    # Create attachment
                    attachment = MIMEApplication(
                        file_content,
                        _subtype=sub_type,
                        name=file_name
                    )
                    attachment.add_header('Content-Disposition', 'attachment', filename=file_name)
                    message.attach(attachment)
                    
                    print(f"Attached file: {file_name}")
                    
                except Exception as e:
                    print(f"Error attaching file {file_id}: {e}")
                    continue
        
        # Encode and send message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = gmail_service.users().messages().send(
            userId='me', 
            body={'raw': raw_message}
        ).execute()
        
        return {
            'success': True,
            'message': f"Email sent successfully. Message ID: {send_message['id']}",
            'message_id': send_message['id']
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Error sending email: {str(e)}"
        }

def send_simple_email(request, to_email, subject, body):
    """
    Send a simple email without attachments
    
    Args:
        request: Django request object
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content
    
    Returns:
        dict: Result with success status and message
    """
    try:
        service_manager = GoogleServiceManager(request)
        gmail_service = service_manager.get_gmail_service()
        
        if not gmail_service:
            return {
                'success': False,
                'message': 'Gmail service not available. Please authenticate first.',
                'auth_url': service_manager.get_authorization_url('gmail')
            }
        
        # Create message
        message = MIMEMultipart()
        message['to'] = to_email
        message['from'] = 'noreply-dareapp@gmail.com'  # Update with your email
        message['subject'] = subject
        message.attach(MIMEText(body, 'plain'))
        
        # Encode and send message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = gmail_service.users().messages().send(
            userId='me', 
            body={'raw': raw_message}
        ).execute()
        
        return {
            'success': True,
            'message': f"Email sent successfully. Message ID: {send_message['id']}",
            'message_id': send_message['id']
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Error sending email: {str(e)}"
        }

def get_recieved_emails_for_today():
    """
    Retrieve emails from the previous day, filter by evaluator emails,
    and store them in admin notifications.
    
    This function is designed to run daily via Django management command.
    If run at 1 AM on 2/7/25, it will extract emails from 1/7/25 (12:00 AM to 11:59 PM).
    
    Returns:
        dict: Result with success status, message, and processed emails count
    """
    try:
        # Initialize service manager without request (for management command)
        service_manager = GoogleServiceManager()
        gmail_service = service_manager.get_gmail_service()
        
        if not gmail_service:
            return {
                'success': False,
                'message': 'Gmail service not available. Please authenticate first.',
                'processed_emails': 0
            }
        
        # Calculate yesterday's date range
        now = datetime.now() + timedelta(days=1)
        yesterday = now - timedelta(days=1)
        
        # Set time boundaries for yesterday (12:00 AM to 11:59 PM)
        start_of_yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_yesterday = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Convert to Unix timestamps for Gmail API
        start_timestamp = int(start_of_yesterday.timestamp())
        end_timestamp = int(end_of_yesterday.timestamp())
        
        print(f"Searching for emails from {start_of_yesterday} to {end_of_yesterday}")
        
        # Get evaluator emails
        evaluator_emails = ['tunde@connektcapitl.com','senthilkumaran1803@gmail.com'] #set(Evaluator.objects.values_list('email', flat=True))
        
        if not evaluator_emails:
            return {
                'success': True,
                'message': 'No evaluator emails found in database.',
                'processed_emails': 0
            }
        
        print(f"Found {len(evaluator_emails)} evaluator emails to check")
        
        # Build Gmail search query for yesterday's emails
        # Gmail uses internal date format, we'll search by date and then filter by timestamp
        query = f"after:{start_of_yesterday.strftime('%Y/%m/%d')} before:{end_of_yesterday.strftime('%Y/%m/%d')}"
        print(query)
        # Get message IDs
        try:
            messages_result = gmail_service.users().messages().list(
                userId='me',
                q="newer_than:1d",#query,
                maxResults=500  # Adjust as needed
            ).execute()
            
            messages = messages_result.get('messages', [])
            
            if not messages:
                return {
                    'success': True,
                    'message': f'No emails found for {yesterday.strftime("%Y-%m-%d")}',
                    'processed_emails': 0
                }
            
            print(f"Found {len(messages)} messages to process")
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error retrieving message list: {str(e)}',
                'processed_emails': 0
            }
        
        processed_emails = 0
        matched_emails = []
        
        # Process each message
        for message in messages:
            try:
                message_id = message['id']
                
                # Get full message details
                full_message = gmail_service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()
                
                # Extract headers
                headers = full_message.get('payload', {}).get('headers', [])
                
                # Find sender email and other details
                sender_email = None
                subject = None
                date_header = None
                
                for header in headers:
                    if header['name'].lower() == 'from':
                        sender_email = header['value']
                        # Extract email from "Name <email@domain.com>" format
                        if '<' in sender_email and '>' in sender_email:
                            sender_email = sender_email.split('<')[1].split('>')[0].strip()
                    elif header['name'].lower() == 'subject':
                        subject = header['value']
                    elif header['name'].lower() == 'date':
                        date_header = header['value']
                
                # Check if sender email matches any evaluator email
                if sender_email and sender_email.lower() in {email.lower() for email in evaluator_emails}:
                    
                    # Get message timestamp
                    internal_date = int(full_message.get('internalDate', 0)) / 1000  # Convert to seconds
                    message_datetime = datetime.fromtimestamp(internal_date)
                    
                    # Double-check if message is within our time range
                    if start_of_yesterday <= message_datetime <= end_of_yesterday:
                        
                        # Extract email body
                        body = extract_email_body(full_message)
                        
                        email_data = {
                            'message_id': message_id,
                            'sender_email': sender_email,
                            'subject': subject or 'No Subject',
                            'body': body,
                            'received_date': message_datetime,
                            'date_header': date_header
                        }
                        
                        matched_emails.append(email_data)
                        processed_emails += 1
                        
                        print(f"Processed email from {sender_email}: {subject}")
                        
                        # Store in admin notification
                        # Note: You'll need to adjust this based on your AdminNotification model
                        try:
                            AdminNotification.objects.create(
                                from_email=sender_email,
                                title = subject or 'No Subject',
                                message = body,
                                priority = 'LOW',
                                google_message_id=message_id,
                                notification_type='RECEIVED_EMAIL',  # To be filled by admin
                                project=None,  # To be filled by admin
                                is_read=False,
                            )
                            
                            print(f"Stored notification for email from {sender_email}")
                            
                        except Exception as e:
                            print(f"Error storing notification for email {message_id}: {e}")
                            
            except Exception as e:
                print(f"Error processing message {message.get('id', 'unknown')}: {e}")
                continue
        
        return {
            'success': True,
            'message': f'Successfully processed {processed_emails} emails from evaluators on {yesterday.strftime("%Y-%m-%d")}',
            'processed_emails': processed_emails,
            'matched_emails': matched_emails
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'Error in get_recieved_emails_for_today: {str(e)}',
            'processed_emails': 0
        }

def extract_email_body(message):
    """
    Extract email body from Gmail message payload
    
    Args:
        message (dict): Gmail message object
        
    Returns:
        str: Email body content
    """
    try:
        payload = message.get('payload', {})
        
        # Check if message has parts (multipart)
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                elif part.get('mimeType') == 'text/html':
                    # If no plain text, get HTML as fallback
                    data = part.get('body', {}).get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        else:
            # Single part message
            if payload.get('mimeType') == 'text/plain':
                data = payload.get('body', {}).get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif payload.get('mimeType') == 'text/html':
                data = payload.get('body', {}).get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
        
        return "Could not extract email body"
        
    except Exception as e:
        print(f"Error extracting email body: {e}")
        return f"Error extracting email body: {str(e)}"