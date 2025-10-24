#!/bin/sh
# Get a list of staged Python files
staged_files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')

# If there are no staged Python files, exit
if [ -z "$staged_files" ]; then
  exit 0
fi

# Run black on the staged files
py -m black $staged_files --target-version py312 --line-length 80 --skip-string-normalization

# Add changes to staging if black made any changes
git add $staged_files