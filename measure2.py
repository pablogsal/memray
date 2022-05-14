import subprocess
import sys
import re

FIL = "/home/pablogsal/.pyenv/versions/3.10.1/envs/memray/bin/fil-profile"

DURATION_RE = re.compile(r"Total duration: (\d+\.\d+)", re.IGNORECASE)

with open("tests.txt") as testsfile:
    tests = [test.strip() for test in testsfile.readlines()]

results = []

env = {"PYTHONMALLOC": "malloc"}

def run(test):
    try:
        output = subprocess.check_output(
            [sys.executable, "-m", "test", test],
            text=True,
            stderr=subprocess.STDOUT,
            env=env,
        )
        memray_output = subprocess.check_output(
            [
                sys.executable,
                "-m",
                "memray",
                "run",
                "-fo",
                "/dev/null",
                "-m",
                "test",
                test,
            ],
            text=True,
            stderr=subprocess.STDOUT,
            env=env,
        )
        fil_output = subprocess.check_output(
            [FIL, "--no-browser", "run", "-m", "test", test],
            text=True,
            stderr=subprocess.STDOUT,
            env=env,
        )
    except Exception as e:
        print(f"{test}: Oh no!")
        return None
    match = DURATION_RE.findall(output)
    memray_match = DURATION_RE.findall(memray_output)
    fil_match = DURATION_RE.findall(fil_output)
    if match and memray_match and fil_match:
        res = (test, float(match[0]), float(memray_match[0]), float(fil_match[0]))
        results.append(res)
        print(f"{test}: Finished!")
        return res
    else:
        print(f"{test}: No match!")
        return None


with open("results_benchmark_no_pymalloc.txt", "w") as result_file:
    for test in tests:
        res = run(test)
        if res is None:
            continue
        test, base, mem, fil= res
        print((1-mem/fil)*100)
        result_file.write(f"{test},{base},{mem},{fil}\n")
        result_file.flush()
