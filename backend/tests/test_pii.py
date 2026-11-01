import pytest

from app.services.safety.pii import PLACEHOLDER, redact_personal_data


@pytest.mark.parametrize(
    ("text", "kind", "secret"),
    [
        ("My Aadhaar is 2345 6789 0123, can I apply?", "aadhaar", "6789"),
        ("aadhaar 234567890123", "aadhaar", "234567890123"),
        ("aadhaar 2345-6789-0123", "aadhaar", "6789"),
        ("aadhaar 1234 5678 9012", "aadhaar", "5678"),  # never issued, but still a number
        ("আমার আধার ১২৩৪ ৫৬৭৮ ৯০১২", "aadhaar", "৫৬৭৮"),  # Bengali digits
        ("मेरा आधार १२३४ ५६७८ ९०१२", "aadhaar", "५६७८"),  # Devanagari digits
        ("card 4111 1111 1111 1111", "card", "4111"),
        ("my PAN is ABCDE1234F", "pan", "ABCDE1234F"),
        ("IFSC is SBIN0001234", "ifsc", "SBIN0001234"),
        ("mail me at student.name@example.co.in", "email", "student.name"),
        ("call 9876543210", "phone", "9876543210"),
        ("call +91 98765 43210", "phone", "98765"),
        ("account number 123456789012345", "account", "123456789012345"),
    ],
)
def test_personal_numbers_are_removed(text: str, kind: str, secret: str) -> None:
    redacted, kinds = redact_personal_data(text)

    assert kind in kinds
    assert PLACEHOLDER in redacted
    assert secret not in redacted


def test_only_the_number_is_replaced() -> None:
    redacted, kinds = redact_personal_data(
        "My PAN ABCDE1234F and mobile 9876543210 - am I eligible?"
    )

    assert redacted == f"My PAN {PLACEHOLDER} and mobile {PLACEHOLDER} - am I eligible?"
    assert kinds == {"pan", "phone"}


def test_text_around_a_bengali_digit_number_is_kept_exactly() -> None:
    redacted, _ = redact_personal_data("আমার আধার ১২৩৪ ৫৬৭৮ ৯০১২ আর ফোন")

    assert redacted == f"আমার আধার {PLACEHOLDER} আর ফোন"


def test_several_numbers_of_one_kind_are_all_replaced() -> None:
    redacted, _ = redact_personal_data("a@example.com and b@example.org")

    assert redacted == f"{PLACEHOLDER} and {PLACEHOLDER}"


@pytest.mark.parametrize(
    "text",
    [
        "The income limit is Rs. 2,50,000 per annum.",
        "Applications close on 30 November 2026.",
        "Marks must be at least 60% in the 2025-26 session.",
        "Is the 8 lakh income limit per year?",
        "আয়ের সীমা ২,৫০,০০০ টাকা কি?",
        "My family income is 250000 rupees.",
        "I scored 1234 marks and 85.5 percent.",
        "What is the scholarship amount for 2026-27?",
    ],
)
def test_ordinary_figures_are_left_alone(text: str) -> None:
    assert redact_personal_data(text) == (text, set())


def test_empty_text_is_fine() -> None:
    assert redact_personal_data("") == ("", set())
