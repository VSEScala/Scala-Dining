import datetime
from unittest.mock import Mock, patch

from django.utils import timezone

__all__ = ["patch", "patch_time", "mock_now"]


def patch_time(dt=None):
    """Adjusts current time to a set point in time for the patched testcase method.

    Args:
        dt: The 'current' datetime according to the program. Defaults to Monday 25th of April 2022 10 o'clock.

    Returns:
        Method with adjusted datetime.
    """
    if dt is not None and not isinstance(dt, datetime.datetime) and callable(dt):
        raise ValueError(
            "Patch time incorrectly called. Make sure you patched through @patch_time() and not @patch_time"
        )

    def wrapper_func(func):
        def inner(*args, **kwargs):
            with patch("django.utils.timezone.now") as mock:
                mock.side_effect = mock_now(dt=dt)
                func(*args, **kwargs)

        return inner

    return wrapper_func


def mock_now(dt=None):
    """Script that changes the default now time to a preset value."""
    if dt is None:
        dt = datetime.datetime(2022, 4, 25, 10, 0)

    def adjust_now_time():
        return timezone.make_aware(dt)

    return adjust_now_time


class TestPatchMixin:
    @staticmethod
    def assert_has_no_call(mock: Mock, **kwargs):
        """Asserts that a given mock does not have a call with the (partially) given attributes.

        Args:
            mock: The Mock instance
            kwargs: List of keyword arguments used in the method call.
                Use arg_## as a keyword argument to check for a non-keyword argument in original method call.
        """
        try:
            TestPatchMixin.assert_has_call(mock, **kwargs)
        except AssertionError:
            return
        else:
            raise AssertionError(
                f"At least one undesired call was made with the given attributes: {kwargs}"
            )

    @staticmethod
    def assert_has_call(mock: Mock, **kwargs):
        """Asserts that a given mock has a call with the (partially) given attributes.

        Args:
            mock: The Mock instance.
            kwargs: List of keyword arguments used in the method call.
                Use arg_## as a keyword argument to check for a non-keyword argument in original method call

        Returns:
            A list of all valid calls represented as dictionaries. Use 'args' key to retrieve initial method
            arguments from the dict.
        """
        # Copy the dict so in the case of an error we can reconstruct the given kwargs
        call_kwargs = kwargs.copy()
        arg_dict = {}
        for arg_key in filter(lambda kwarg: kwarg.startswith("arg_"), kwargs.keys()):
            arg_dict[int(arg_key[4:]) - 1] = call_kwargs.pop(arg_key)

        # Construct a list of all valid calls
        # Calls are tuples of (positional args, keyword args)
        valid_calls = []
        for kall in mock.call_args_list:
            valid = True
            for key, value in arg_dict.items():
                if kall[0][key] != value:
                    valid = False
                    break
            for key, value in call_kwargs.items():
                if kall[1][key] != value:
                    valid = False
                    break
            if valid:
                valid_calls.append({"args": kall[0], **kall[1]})

        if not valid_calls:
            raise AssertionError(
                f"No calls were made with the desired attributes: {kwargs}"
            )
        return valid_calls
