import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class SMSService:
    """
    SMS service for sending OTP codes
    Uses super OTP for development, can be extended for production services
    """
    
    SUPER_OTP = "123456"  # Development super OTP
    
    def __init__(self):
        self.development_mode = getattr(settings, 'DEBUG', True)
        # Also consider test mode as development
        import sys
        if 'test' in sys.argv:
            self.development_mode = True
    
    def send_otp(self, phone_number, otp_code):
        """
        Send OTP to phone number
        
        Args:
            phone_number (str): Phone number to send OTP to
            otp_code (str): OTP code to send
            
        Returns:
            bool: True if SMS sent successfully, False otherwise
        """
        try:
            if self.development_mode:
                # In development, always use super OTP and log the message
                logger.info(f"Development SMS: Sending OTP {otp_code} to {phone_number}")
                logger.info(f"Super OTP available: {self.SUPER_OTP}")
                print(f"📱 SMS to {phone_number}: Your verification code is {otp_code}")
                print(f"🔑 Development Super OTP: {self.SUPER_OTP}")
                return True
            else:
                # Production mode - integrate with real SMS service
                return self._send_production_sms(phone_number, otp_code)
                
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
            return False
    
    def _send_production_sms(self, phone_number, otp_code):
        """
        Send SMS using production service (Twilio, AWS SNS, etc.)
        This method should be implemented when moving to production
        """
        # TODO: Implement production SMS service
        # Example implementations:
        
        # Option 1: Twilio
        # from twilio.rest import Client
        # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # message = client.messages.create(
        #     body=f"Your verification code is {otp_code}",
        #     from_=settings.TWILIO_PHONE_NUMBER,
        #     to=phone_number
        # )
        # return message.sid is not None
        
        # Option 2: AWS SNS
        # import boto3
        # sns = boto3.client('sns')
        # response = sns.publish(
        #     PhoneNumber=phone_number,
        #     Message=f"Your verification code is {otp_code}"
        # )
        # return response['ResponseMetadata']['HTTPStatusCode'] == 200
        
        # Option 3: Free services like TextBelt (limited)
        # import requests
        # response = requests.post('https://textbelt.com/text', {
        #     'phone': phone_number,
        #     'message': f"Your verification code is {otp_code}",
        #     'key': 'textbelt'  # Free tier has limitations
        # })
        # return response.json().get('success', False)
        
        logger.warning("Production SMS service not implemented")
        return False
    
    def is_super_otp(self, otp_code):
        """
        Check if the provided OTP is the super OTP
        
        Args:
            otp_code (str): OTP code to check
            
        Returns:
            bool: True if it's the super OTP
        """
        return otp_code == self.SUPER_OTP and self.development_mode