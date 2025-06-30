import os
import json
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import base64

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
    def __init__(self, request):
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
        flow.redirect_uri = self.request.build_absolute_uri(reverse('communications:google_oauth_callback'))
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to get refresh token
        )
        
        # Store state in session for security
        self.request.session['google_auth_state'] = state
        self.request.session['service_type'] = service_type
        
        return authorization_url
    
    def handle_oauth_callback(self, authorization_code, state):
        """
        Handle OAuth callback and store credentials
        
        Args:
            authorization_code (str): Authorization code from Google
            state (str): State parameter for security
        
        Returns:
            bool: Success status
        """
        # Verify state parameter
        if state != self.request.session.get('google_auth_state'):
            return False
        
        try:
            service_type = self.request.session.get('service_type', 'combined')
            scopes = {
                'gmail': GMAIL_SCOPES,
                'drive': DRIVE_SCOPES,
                'combined': COMBINED_SCOPES
            }
            
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=scopes.get(service_type, COMBINED_SCOPES)
            )
            flow.redirect_uri = self.request.build_absolute_uri(reverse('communications:google_oauth_callback'))
            
            # Exchange authorization code for credentials
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # Store credentials in session (or database for production)
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
    
    def get_credentials(self):
        """Get credentials from session"""
        creds_data = self.request.session.get('google_credentials')
        if not creds_data:
            return None
        
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
