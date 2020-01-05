#!/usr/bin/env sh

exit=0

checked() {
  echo "$ $@"
  "$@"
  last="$?"
  if [ "$last" -ne 0 ]; then
    echo "$@: exit $last"
    exit=1
  fi
}

cd $(dirname "$0")/..

checked pytest --cov imux
checked black --check bin imux test
checked flake8 imux test
checked mypy --strict imux

exit "$exit"
