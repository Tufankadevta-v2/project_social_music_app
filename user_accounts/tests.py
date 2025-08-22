from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from unittest.mock import patch, MagicMock

from .models import User, PhoneVerification, UserProfile
from .services import SMSService


class PhoneVerificationModelTest(TestCase):
    """Test PhoneVerification model functionality"""
    
    def setUp(self):
        self.phone_number = "+1234567890"
    
    def test_create_otp(self):
        """Test OTP creation"""
        verification = PhoneVerification.create_otp(self.phone_number)
        
        self.assertEqual(verification.phone_number, self.phone_number)
        self.assertEqual(len(verification.otp_code), 6)
        self.assertFalse(verification.is_used)
        self.assertEqual(verification.attempts, 0)
        self.assertFalse(verification.is_expired())
    
    def test_otp_expiration(self):
        """Test OTP expiration logic"""
        verification = PhoneVerification.objects.create(
            phone_number=self.phone_number,
            expires_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        
        self.assertTrue(verification.is_expired())
        self.assertFalse(verification.is_valid())
    
    def test_otp_max_attempts(self):
        """Test OTP max attempts logic"""
        verification = PhoneVerification.create_otp(self.phone_number)
        
        # Exceed max attempts
        for _ in range(PhoneVerification.MAX_ATTEMPTS):
            verification.increment_attempts()
        
        self.assertFalse(verification.is_valid())
    
    def test_verify_otp_success(self):
        """Test successful OTP verification"""
        verification = PhoneVerification.create_otp(self.phone_number)
        otp_code = verification.otp_code
        
        is_valid, result = PhoneVerification.verify_otp(self.phone_number, otp_code)
        
        self.assertTrue(is_valid)
        self.assertEqual(result, verification)
        verification.refresh_from_db()
        self.assertTrue(verification.is_used)
    
    def test_verify_otp_invalid(self):
        """Test invalid OTP verification"""
        PhoneVerification.create_otp(self.phone_number)
        
        is_valid, result = PhoneVerification.verify_otp(self.phone_number, "000000")
        
        self.assertFalse(is_valid)
        self.assertIsNone(result)
    
    def test_verify_super_otp(self):
        """Test super OTP verification in development"""
        with patch('django.conf.settings.DEBUG', True):
            is_valid, result = PhoneVerification.verify_otp(self.phone_number, "123456")
            
            self.assertTrue(is_valid)
            self.assertIsNotNone(result)
            self.assertEqual(result.phone_number, self.phone_number)


class SMSServiceTest(TestCase):
    """Test SMS service functionality"""
    
    def setUp(self):
        self.sms_service = SMSService()
        self.phone_number = "+1234567890"
        self.otp_code = "123456"
    
    def test_development_mode_sms(self):
        """Test SMS sending in development mode"""
        with patch('django.conf.settings.DEBUG', True):
            result = self.sms_service.send_otp(self.phone_number, self.otp_code)
            self.assertTrue(result)
    
    def test_is_super_otp(self):
        """Test super OTP detection"""
        with patch('django.conf.settings.DEBUG', True):
            self.assertTrue(self.sms_service.is_super_otp("123456"))
            self.assertFalse(self.sms_service.is_super_otp("000000"))


class AuthenticationAPITest(APITestCase):
    """Test authentication API endpoints"""
    
    def setUp(self):
        self.phone_number = "+1234567890"
        self.valid_otp = "123456"
        self.invalid_otp = "000000"
    
    def test_send_otp_success(self):
        """Test successful OTP sending"""
        url = reverse('user_accounts:send_otp')
        data = {'phone_number': self.phone_number}
        
        with patch('user_accounts.views.SMSService') as mock_sms:
            mock_sms_instance = MagicMock()
            mock_sms_instance.send_otp.return_value = True
            mock_sms.return_value = mock_sms_instance
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('message', response.data)
            self.assertEqual(response.data['phone_number'], self.phone_number)
    
    def test_send_otp_invalid_phone(self):
        """Test OTP sending with invalid phone number"""
        url = reverse('user_accounts:send_otp')
        data = {'phone_number': 'invalid'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)
    
    def test_send_otp_existing_verified_user(self):
        """Test OTP sending for existing verified user"""
        User.objects.create_user(
            phone_number=self.phone_number,
            password='testpass123',
            is_phone_verified=True
        )
        
        url = reverse('user_accounts:send_otp')
        data = {'phone_number': self.phone_number}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_verify_otp_success_new_user(self):
        """Test successful OTP verification for new user"""
        # First send OTP
        PhoneVerification.create_otp(self.phone_number)
        
        url = reverse('user_accounts:verify_otp')
        data = {
            'phone_number': self.phone_number,
            'otp_code': self.valid_otp
        }
        
        with patch('django.conf.settings.DEBUG', True):
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(response.data['user_exists'])
            self.assertEqual(response.data['next_step'], 'complete_registration')
    
    def test_verify_otp_success_existing_user(self):
        """Test successful OTP verification for existing user"""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            password='testpass123',
            is_phone_verified=False
        )
        
        url = reverse('user_accounts:verify_otp')
        data = {
            'phone_number': self.phone_number,
            'otp_code': self.valid_otp
        }
        
        with patch('django.conf.settings.DEBUG', True):
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['user_exists'])
            self.assertIn('token', response.data)
            
            # Check user is now verified
            user.refresh_from_db()
            self.assertTrue(user.is_phone_verified)
    
    def test_verify_otp_invalid(self):
        """Test OTP verification with invalid code"""
        PhoneVerification.create_otp(self.phone_number)
        
        url = reverse('user_accounts:verify_otp')
        data = {
            'phone_number': self.phone_number,
            'otp_code': self.invalid_otp
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_user_success(self):
        """Test successful user registration"""
        # First verify phone
        PhoneVerification.objects.create(
            phone_number=self.phone_number,
            otp_code=self.valid_otp,
            is_used=True
        )
        
        url = reverse('user_accounts:register_user')
        data = {
            'phone_number': self.phone_number,
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'display_name': 'Test User'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertIn('user', response.data)
        
        # Check user was created
        user = User.objects.get(phone_number=self.phone_number)
        self.assertTrue(user.is_phone_verified)
        self.assertTrue(hasattr(user, 'profile'))
    
    def test_register_user_password_mismatch(self):
        """Test user registration with password mismatch"""
        PhoneVerification.objects.create(
            phone_number=self.phone_number,
            otp_code=self.valid_otp,
            is_used=True
        )
        
        url = reverse('user_accounts:register_user')
        data = {
            'phone_number': self.phone_number,
            'password': 'testpass123',
            'password_confirm': 'different123'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_user_unverified_phone(self):
        """Test user registration without phone verification"""
        url = reverse('user_accounts:register_user')
        data = {
            'phone_number': self.phone_number,
            'password': 'testpass123',
            'password_confirm': 'testpass123'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_success(self):
        """Test successful user login"""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            password='testpass123',
            is_phone_verified=True
        )
        
        url = reverse('user_accounts:login_user')
        data = {
            'phone_number': self.phone_number,
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertIn('user', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        User.objects.create_user(
            phone_number=self.phone_number,
            password='testpass123',
            is_phone_verified=True
        )
        
        url = reverse('user_accounts:login_user')
        data = {
            'phone_number': self.phone_number,
            'password': 'wrongpass'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_unverified_phone(self):
        """Test login with unverified phone"""
        User.objects.create_user(
            phone_number=self.phone_number,
            password='testpass123',
            is_phone_verified=False
        )
        
        url = reverse('user_accounts:login_user')
        data = {
            'phone_number': self.phone_number,
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_logout_success(self):
        """Test successful logout"""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            password='testpass123',
            is_phone_verified=True
        )
        token = Token.objects.create(user=user)
        
        url = reverse('user_accounts:logout_user')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=user).exists())
    
    def test_user_profile_authenticated(self):
        """Test user profile access with authentication"""
        user = User.objects.create_user(
            phone_number=self.phone_number,
            password='testpass123',
            is_phone_verified=True
        )
        # Profile is created automatically by signal, just update it
        user.profile.display_name = 'Test User'
        user.profile.save()
        
        token = Token.objects.create(user=user)
        
        url = reverse('user_accounts:user_profile')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], self.phone_number)
    
    def test_user_profile_unauthenticated(self):
        """Test user profile access without authentication"""
        url = reverse('user_accounts:user_profile')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
