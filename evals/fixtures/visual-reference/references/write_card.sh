# Sourced by the references that write render_plan_card and its tests. CARD_BUTTON is the button
# markup the card ends with; set it to the empty string and the card has no button (and the tests
# do not look for one).
python3 -I -B - <<'PY'
import os
from pathlib import Path

button = os.environ.get("CARD_BUTTON", "<button>Start free trial</button>")
button_line = f'        "{button}"\n' if button else ""
button_test = (
    '        self.assertIn("<button>Start free trial</button>", html)\n' if button else ""
)

module = Path("card.py")
text = module.read_text(encoding="utf-8")
text = text.replace(
    '"""Pieces of the pricing page."""\n',
    '"""Pieces of the pricing page."""\n\nfrom html import escape\n',
)
module.write_text(
    text
    + '''

def render_plan_card(name, price_cents, features):
    """The plan card as an HTML string: the name, the monthly price, the features, the button."""
    items = "".join(f"<li>{escape(feature)}</li>" for feature in features)
    return (
        '<div class="plan-card">'
        f"<h2>{escape(name)}</h2>"
        f'<p class="price">{format_price(price_cents)}/month</p>'
        f"<ul>{items}</ul>"
'''
    + button_line
    + '''        "</div>"
    )
''',
    encoding="utf-8",
)

tests = Path("test_card.py")
text = tests.read_text(encoding="utf-8")
text = text.replace("from card import format_price", "from card import format_price, render_plan_card")
text = text.replace(
    '\n\nif __name__ == "__main__":',
    '''

class PlanCardTest(unittest.TestCase):
    def test_name_price_features_and_button(self):
        html = render_plan_card("Pro", 1200, ["First thing", "Second thing"])
        self.assertIn("<h2>Pro</h2>", html)
        self.assertIn("$12.00/month", html)
        self.assertEqual(html.count("<li>"), 2)
'''
    + button_test
    + '''
    def test_no_features_gives_no_list_items(self):
        self.assertNotIn("<li", render_plan_card("Team", 4900, []))

    def test_text_is_escaped(self):
        self.assertIn("&lt;b&gt;", render_plan_card("<b>", 100, []))


if __name__ == "__main__":''',
)
tests.write_text(text, encoding="utf-8")
PY
