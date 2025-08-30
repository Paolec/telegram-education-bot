import pyotp
secret = pyotp.random_base32()
print(f"ADMIN_2FA_SECRET={secret}")