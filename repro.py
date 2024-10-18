import tracemalloc, secrets, string

def generate_secure_password(length=12):
    # Define the character set for the password
    alphabet = string.ascii_letters + string.digits + string.punctuation

    # Generate a secure password
    password = ''.join(secrets.choice(alphabet) for _ in range(length))

    return password

tracemalloc.start()
a = tracemalloc.get_traced_memory()
generate_secure_password()
b = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(a)
print(b)
