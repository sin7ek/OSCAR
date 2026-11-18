"""Regression: the packaged Debian cyanrip must accept OSCAR's flags."""
import pytest

from oscar.cyanrip_compat import command_flags, verify_help


def test_flags_skip_cli_values():
    assert command_flags() == ["-d", "-s", "-o", "-D", "-F",
                               "-N", "-U", "-G", "-K", "-W"]


def test_missing_flag_fails_before_drive_use():
    simulated = "cyanrip usage: -d -s -o -D -F -N -U -G -K -W"
    assert verify_help(simulated)
    with pytest.raises(ValueError, match="required flags: -W"):
        verify_help(simulated.replace(" -W", ""))


def test_b_is_not_required_for_debian_093():
    simulated = "cyanrip usage: -d -s -o -D -F -N -U -G -K -W"
    assert verify_help(simulated)
    assert "-B" not in command_flags()


def test_cannot_silently_accept_empty_help():
    with pytest.raises(ValueError, match="usage information"):
        verify_help("")
