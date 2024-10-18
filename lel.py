import memray, os, secrets, string

def generate_secure_password(length=12):
    # Define the character set for the password
    alphabet = string.ascii_letters + string.digits + string.punctuation
    
    # Generate a secure password
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    return password

with memray.Tracker("blech.bin", reference_tracking=True, native_traces=True, trace_python_allocators=True) as tracker:
    p = generate_secure_password()
surviving = tracker.get_surviving_objects()

file = memray.FileReader("blech.bin")
all_objects = list(file.get_allocation_records())
addresses = {record.address: record for record in all_objects if record.allocator == 0}
records = [ (obj, addresses.get(id(obj), None)) for obj in surviving]

for (object, record) in records:
    if record is None:
        print(f"Object {object} was not recorded.")
    else:
        stack_trace = record.hybrid_stack_trace()
        print(f"Object {object} was allocated by:")
        for frame in stack_trace:
            print(frame)

os.unlink("blech.bin")
