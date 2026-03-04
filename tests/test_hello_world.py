import hello_world
from io import StringIO
import sys

def test_greet_default():
    """Test greet function with default name."""
    # Capture stdout
    old_stdout = sys.stdout
    redirected_output = StringIO()
    sys.stdout = redirected_output
    try:
        hello_world.greet()
        assert redirected_output.getvalue().strip() == "Hello, IgnyteDev!"
    finally:
        sys.stdout = old_stdout

def test_greet_custom_name():
    """Test greet function with a custom name."""
    old_stdout = sys.stdout
    redirected_output = StringIO()
    sys.stdout = redirected_output
    try:
        hello_world.greet("World")
        assert redirected_output.getvalue().strip() == "Hello, World!"
    finally:
        sys.stdout = old_stdout
