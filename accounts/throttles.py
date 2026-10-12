from rest_framework.throttling import UserRateThrottle

class UserResendOtpPerMinute(UserRateThrottle):
    scope = 'resend_otp_minute'

class UserResendOtpPerDay(UserRateThrottle):
    scope = 'resend_otp_day'
