import random
from django.core.mail import send_mail
from django.conf import settings
from .models import OTPModel

def send_otp_email(user):
   
    otp_code = f"{random.randint(100000, 999999)}"
    
    
    OTPModel.objects.create(user=user, otp=otp_code)
    

    subject = f"Your Mess Mate Email Verification Code: {otp_code}"
    
    email_body = f"""Thank you for using Mess Mate. 

Please use the following One-Time Passcode (OTP) to verify your identity and secure your account:

{otp_code}

For your security, this verification code is strictly confidential and will expire automatically in 15 minutes. Do not share this code with anyone; our team will never ask you to disclose it.

If you did not request this verification, please secure your credentials or contact our system administration team immediately.

Best regards,  
The Mess Mate Team  
Automated Notification System — Please do not reply directly to this message."""

    
    send_mail(
        subject=subject,
        message=email_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,  
    )
    
    return otp_code
