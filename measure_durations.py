import subprocess
import sys
import re

DURATION_RE = re.compile(r"Total duration: (\d+) ms", re.IGNORECASE)

with open("tests.txt") as testsfile:
    tests = [test.strip() for test in testsfile.readlines()]

results = []

for test in tests:
    print(test)
    try:
        output = subprocess.check_output([sys.executable, "-m", "test", test], text=True, stderr=subprocess.STDOUT)
        memray_output = subprocess.check_output([sys.executable, "-m", "memray", "run", "-fo", "/dev/null", "-m", "test", test], text=True, stderr=subprocess.STDOUT)
    except Exception as e:
        print(f"Oh no: {e.}")
        continue
    match = DURATION_RE.findall(output)
    memray_match = DURATION_RE.findall(memray_output)
    if match and memray_match:
        results.append((test, int(match[0]), int(memray_match[0])))

with open("results_benchmark.txt", "w") as result_file:
    for test, before, after in results:
        result_file.write(f"{test},{before},{after},{(after/before)*100}\n")
