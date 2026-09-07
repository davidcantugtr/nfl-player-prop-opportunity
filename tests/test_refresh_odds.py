import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "refresh_odds.py"
SPEC = importlib.util.spec_from_file_location("refresh_odds", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class ProbabilityTests(unittest.TestCase):
    def test_american_implied_negative(self):
        self.assertAlmostEqual(MOD.american_implied(-110), 110 / 210)

    def test_american_implied_positive(self):
        self.assertAlmostEqual(MOD.american_implied(150), 100 / 250)

    def test_no_vig_pair_sums_to_one(self):
        rows = [
            {"Pair Key": "book|player|market|50.5", "Raw Implied": MOD.american_implied(-110)},
            {"Pair Key": "book|player|market|50.5", "Raw Implied": MOD.american_implied(-110)},
        ]
        MOD.paired_no_vig(rows)
        self.assertAlmostEqual(sum(row["No-Vig Implied"] for row in rows), 1.0)

    def test_prop_normalization(self):
        events = [{
            "id": "evt1", "commence_time": "2026-09-10T00:00:00Z",
            "home_team": "Home", "away_team": "Away",
            "bookmakers": [{"key": "book", "title": "Book", "last_update": "2026-09-09T00:00:00Z", "markets": [{
                "key": "player_reception_yds", "outcomes": [
                    {"name": "Over", "description": "Example Receiver", "price": -110, "point": 50.5},
                    {"name": "Under", "description": "Example Receiver", "price": -110, "point": 50.5},
                ]
            }]}]
        }]
        rows = MOD.normalize_props(events, 2026, 1, "source")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Player"], "Example Receiver")
        self.assertEqual(rows[0]["Position"], "WR")
        self.assertAlmostEqual(rows[0]["No-Vig Implied"], 0.5)


if __name__ == "__main__":
    unittest.main()

