"""Check the installed cyanrip CLI against OSCAR's fixed command.

The binary shipped in Debian can lag the upstream README. Validate what
the *installed binary* advertises during Docker build, before hardware use.
"""
import re
import subprocess

from oscar.ripping import make_command

_VALUE_OPTIONS = {"-d", "-s", "-o", "-D", "-F"}


def command_flags():
    """Return only CLI switches; skip the values passed to each option."""
    args = make_command("/dev/sr0", 48)[1:]
    flags = []
    pos = 0
    while pos < len(args):
        flag = args[pos]
        if not flag.startswith("-"):
            raise ValueError(f"Unexpected cyanrip CLI argument: {flag}")
        flags.append(flag)
        pos += 2 if flag in _VALUE_OPTIONS else 1
    return flags


def verify_help(help_text):
    if not help_text.strip():
        raise ValueError("cyanrip -h did not produce usage information")
    missing = [flag for flag in command_flags()
               if not re.search(r"(?<![\\w-])" + re.escape(flag) + r"(?![\\w-])",
                                help_text)]
    if missing:
        raise ValueError("Installed cyanrip does not document required flags: " +
                         ", ".join(missing))
    return True


def check_installed():
    result = subprocess.run(["cyanrip", "-h"], capture_output=True, text=True,
                            check=False, timeout=15)
    # Some CLI versions print usage with a non-zero status. Inspect the text.
    verify_help(result.stdout + result.stderr)


if __name__ == "__main__":
    check_installed()
    print("OSCAR cyanrip CLI flags validated against installed binary")
