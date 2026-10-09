"""Prompt locally and run the primary CLI with isolated token authentication."""
import getpass
import os
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ('-h', '--help'):
        print('Usage: python scripts/run_with_earthdata_token.py [--visible-token] '
              '--config CONFIG run-catalog [primary CLI options]')
        return 0
    visible = args[0] == '--visible-token'
    if visible:
        args.pop(0)
    prompt = input if visible else getpass.getpass
    try:
        token = prompt('Paste Earthdata token (visible): ' if visible else
                       'Paste Earthdata token (input hidden): ').strip()
    except (EOFError, KeyboardInterrupt):
        print('\nToken entry cancelled.', file=sys.stderr)
        return 2
    if not token:
        print('No token entered.', file=sys.stderr)
        return 2
    env = os.environ.copy()
    env['EARTHDATA_TOKEN'] = token
    # Isolate both token validation and subsequent download redirects from netrc.
    # Preserve HTTPS_PROXY, REQUESTS_CA_BUNDLE and other environment settings.
    env['NETRC'] = os.devnull
    script = Path(__file__).resolve().with_name('run_primary.py')
    return subprocess.run([sys.executable, str(script), *args], env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
