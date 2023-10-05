#!/usr/bin/python3
import sys
import subprocess
import os.path
from os import path

# Args: <Known Failures file> <Known Failures Type File> <DisabledTestsFile> <DisabledTestsTypeFile> <DisabledTestsRunnerFile> <TestName> <Test Harness Executable> <Args>...

if (len(sys.argv) < 7):
    sys.exit()

known_failures = {}
disabled_tests = {}
known_failures_file = sys.argv[1]
known_failures_type_file = sys.argv[2]
disabled_tests_file = sys.argv[3]
disabled_tests_type_file = sys.argv[4]
disabled_tests_runner_file = sys.argv[5]

current_test = sys.argv[6]
runner = sys.argv[7]
args_start_index = 8

# Open the known failures file and add it to a dictionary
with open(known_failures_file) as kff:
    for line in kff:
        known_failures[line.strip()] = 1

if path.exists(known_failures_type_file):
    with open(known_failures_type_file) as dtf:
        for line in dtf:
            known_failures[line.strip()] = 1

with open(disabled_tests_file) as dtf:
    for line in dtf:
        disabled_tests[line.strip()] = 1

if path.exists(disabled_tests_type_file):
    with open(disabled_tests_type_file) as dtf:
        for line in dtf:
            disabled_tests[line.strip()] = 1

if path.exists(disabled_tests_runner_file):
    with open(disabled_tests_runner_file) as dtf:
        for line in dtf:
            disabled_tests[line.strip()] = 1

RunnerArgs = ["catchsegv", runner]
# Add the rest of the arguments
RunnerArgs.extend(
    sys.argv[args_start_index + i]
    for i in range(len(sys.argv) - args_start_index)
)
if (disabled_tests.get(current_test)):
    print("Skipping", current_test)
    sys.exit(0)

# Run the test and wait for it to end to get the result
Process = subprocess.Popen(RunnerArgs)
Process.wait()
ResultCode = Process.returncode

if (known_failures.get(current_test)):
    # If the test is on the known failures list
    if (ResultCode):
        # If we errored but are on the known failures list then "pass" the test
        sys.exit(0)
    else:
        # If we didn't error but are in the known failure list then we need to fail the test
        sys.exit(1)
else:
    # Just return the result code if we don't have this test as a known failure
    sys.exit(ResultCode);

