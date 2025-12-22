# config.py - Updated for Resend + Cloudinary + Supabase

# JWT Secret Key
SECRET_KEY = "your-secret-key"  # Change to strong key in production

# App settings
DEBUG = True

# Base URL (local ke liye)
BASE_URL = "http://127.0.0.1:5000"

# Cloudinary Settings (already working)
CLOUDINARY_CLOUD_NAME = 'dybxiiypm'
CLOUDINARY_API_KEY = '877246594525295'
CLOUDINARY_API_SECRET = 'IHHSJZDhUZaOG3-NiO-KfVzVKXY'

# Resend Email Settings (new - Gmail ki jagah)
RESEND_API_KEY = "re_SB36d9dp_LcLwKq3kAhnZacXnyyc3MBG3"
RESEND_FROM_EMAIL = "onboarding@resend.dev"  # Default free email, baad mein custom domain verify kar sakte ho